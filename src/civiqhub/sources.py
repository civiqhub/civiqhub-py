# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Where a snapshot comes from: the product API, a saved file, or data built in memory.

The same objects describe a live Project, a laboratory replay and a fleet of agents;
only the source changes.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote, urlencode

from .errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from .model import FORMAT, Exposure

Payload = dict[str, Any]
Transport = Callable[[str, Mapping[str, str]], tuple[int, Mapping[str, str], bytes]]

TOKEN_VARIABLE = "CIVIQHUB_TOKEN"
TOKEN_PREFIX = "civ_pat_"
DEFAULT_URL = "https://api.civiqhub.com/v1"  # namespace still open on the product side


class Source(ABC):
    """Anything that can hand over the data of a Project or a Group as one payload."""

    name: ClassVar[str] = "source"

    @abstractmethod
    def fetch(self, container: str | None = None, *, exposure: Exposure) -> Payload:
        """Return a payload in the ``civiqhub.snapshot/0`` format."""

    def describe(self) -> str:
        """One line naming the source; it never contains a secret."""
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.describe()})"


class MemorySource(Source):
    """A payload already in memory: synthetic data, a laboratory replay, agents."""

    name = "memory"

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> Payload:
        return _at_exposure(self._payload, exposure)


class FileSource(Source):
    """A snapshot saved earlier with ``project.save(path)``."""

    name = "file"
    path: Path

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def describe(self) -> str:
        return f"file {self.path.name}"

    def read(self) -> Payload:
        """The payload exactly as it was saved."""
        if not self.path.exists():
            raise NotFoundError(f"no snapshot file at {self.path}; save one with project.save()")
        payload: Payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> Payload:
        return _at_exposure(self.read(), exposure)


class ApiSource(Source):
    """The CiviqHub API, read with a personal access token. It only ever sends GET.

    The token is scoped to one container, a Project or a Group, and never gives more
    than its owner can see.

    Provisional. The public API does not exist yet: the base URL, the paths, the
    pagination, the token endpoint and the shape of the answers are assumptions taken
    from the library mission. They will change when the product publishes its contract.
    """

    name = "api"

    # Paths follow the public reads listed in the library mission. They are provisional
    # until the product publishes the API.
    PATHS: ClassVar[dict[str, str]] = {
        "scope": "/token",
        "group": "/groups/{id}",
        "group_projects": "/groups/{id}/projects",
        "project": "/projects/{id}",
        "proposals": "/projects/{id}/proposals",
        "revisions": "/projects/{id}/revisions",
        "amendments": "/projects/{id}/amendments",
        "arguments": "/projects/{id}/arguments",
        "tallies": "/projects/{id}/votes/aggregates",
        "participation": "/projects/{id}/participation",
        "members": "/projects/{id}/members",
        "votes": "/projects/{id}/votes",
    }
    _DETAILED: ClassVar[tuple[str, ...]] = ("members", "votes")
    _LISTS: ClassVar[tuple[str, ...]] = (
        "proposals",
        "revisions",
        "amendments",
        "arguments",
        "tallies",
    )

    base_url: str
    timeout: float  # seconds

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_URL,
        transport: Transport | None = None,
        timeout: float = 30.0,
    ) -> None:
        token = token or os.environ.get(TOKEN_VARIABLE)
        if not token:
            raise AuthenticationError(
                f"no token: pass one to civiqhub.connect(token) or set {TOKEN_VARIABLE}. "
                "Create a token from the settings of your Project."
            )
        if not token.startswith(TOKEN_PREFIX):
            raise AuthenticationError(
                f"this does not look like a CiviqHub token (they start with {TOKEN_PREFIX!r}); "
                "copy it again from the settings of your Project"
            )
        self._token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport or self._urllib

    def describe(self) -> str:
        return f"api {self.base_url}, token {TOKEN_PREFIX}...{self._token[-4:]}"

    # reading -----------------------------------------------------------------------
    def fetch(self, container: str | None = None, *, exposure: Exposure) -> Payload:
        scope = self._get(self.PATHS["scope"])
        as_of = str(scope["as_of"])
        payload: Payload = {"format": FORMAT, "as_of": as_of, "exposure": exposure.value}
        payload.update({key: [] for key in ("groups", "projects", "participation", *self._LISTS)})
        if scope["kind"] == "group":
            group = self._get(self.PATHS["group"], id=scope["id"], as_of=as_of)
            payload["groups"].append(group)
            listed = self._pages(self.PATHS["group_projects"], id=scope["id"], as_of=as_of)
            wanted = [p["id"] for p in listed if container in (None, p["id"], p.get("slug"))]
        else:
            wanted = [container or scope["id"]]
        if exposure is Exposure.PSEUDONYMISED:
            payload.update({key: [] for key in self._DETAILED})
        members: dict[str, Any] = {}
        for ref in wanted:
            project = self._get(self.PATHS["project"], id=ref, as_of=as_of)
            payload["projects"].append(project)
            for key in self._LISTS:
                payload[key] += self._pages(self.PATHS[key], id=project["id"], as_of=as_of)
            payload["participation"].append(
                self._get(self.PATHS["participation"], id=project["id"], as_of=as_of)
            )
            if exposure is Exposure.PSEUDONYMISED:
                detail = {"as_of": as_of, "exposure": exposure.value}
                payload["votes"] += self._pages(self.PATHS["votes"], id=project["id"], **detail)
                for row in self._pages(self.PATHS["members"], id=project["id"], **detail):
                    members[row["pseudonym"]] = row
        if exposure is Exposure.PSEUDONYMISED:
            payload["members"] = list(members.values())
        return payload

    def _pages(self, path: str, *, id: str, **query: str) -> list[Any]:
        rows: list[Any] = []
        cursor: str | None = None
        while True:
            page = self._get(path, id=id, **query, **({"cursor": cursor} if cursor else {}))
            rows += page["data"]
            cursor = page.get("next_cursor")
            if not cursor:
                return rows

    def _get(self, path: str, *, id: str = "", **query: str) -> Any:
        url = self.base_url + path.format(id=quote(id, safe=""))
        if query:
            url += "?" + urlencode(query)
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        status, answered, body = self._transport(url, headers)
        if status == 200:
            return json.loads(body)
        where = url.removeprefix(self.base_url)
        if status == 401:
            raise AuthenticationError(
                "the token was refused: it is expired or revoked. "
                "Create a new one from the settings of your Project."
            )
        if status == 403:
            raise ExposureError(
                f"the token does not allow {where}. Pseudonymised votes must be enabled by an "
                "administrator and need enough participants; aggregated data stays available "
                "with civiqhub.connect(exposure='aggregated')."
            )
        if status == 404:
            raise NotFoundError(f"nothing at {where} for this token; check the Project it covers")
        if status == 429:
            wait = answered.get("Retry-After")
            raise RateLimitedError(
                f"too many requests; wait {wait or 'a moment'} seconds and call again",
                retry_after=float(wait) if wait else None,
            )
        raise CiviqHubError(f"the API answered {status} at {where}; try again later")

    def _urllib(self, url: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                return answer.status, dict(answer.headers), answer.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), error.read()
        except urllib.error.URLError as error:
            raise CiviqHubError(
                f"could not reach {self.base_url} ({error.reason}); check the connection"
            ) from error


def _at_exposure(payload: Mapping[str, Any], exposure: Exposure) -> Payload:
    """Serve a stored payload at the asked level; a stored payload never gains detail."""
    held = Exposure(payload.get("exposure", "aggregated"))
    if exposure is Exposure.PSEUDONYMISED and held is Exposure.AGGREGATED:
        raise ExposureError(
            "this snapshot was saved at the aggregated level and holds no vote rows; "
            "open it with exposure='aggregated', or fetch a pseudonymised one from the API"
        )
    if exposure is held:
        return dict(payload)
    if "tallies" not in payload and payload.get("votes"):
        raise ValidationError("cannot aggregate this payload: it has votes but no tallies")
    hidden = ("members", "votes", "impressions")
    reduced = {key: value for key, value in payload.items() if key not in hidden}
    reduced["exposure"] = Exposure.AGGREGATED.value
    for section in ("proposals", "arguments"):
        reduced[section] = [
            {k: v for k, v in row.items() if k != "author_id"} for row in payload.get(section, ())
        ]
    return reduced
