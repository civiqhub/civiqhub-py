# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Where data comes from: the port through which rows enter the SDK.

A :class:`Source` has one duty: give rows in the format :data:`~civiqhub.dataset.FORMAT`,
at the level of exposure asked for. A :class:`~civiqhub.dataset.Dataset` is then built
from them. :class:`MemorySource` serves rows held in memory, and :class:`FileSource` a
file written by :meth:`~civiqhub.dataset.Dataset.save`. :class:`ApiSource` reads the public
API of CiviqHub with a personal access token; it is provisional, since the API is not
published yet.

To write your own source:

1. Derive a class from :class:`Source` and give it a short ``name``.
2. Write its ``fetch(container=None, *, exposure)``. It returns rows in the format
   :data:`~civiqhub.dataset.FORMAT`, whose key ``exposure`` is the level asked for.
   :func:`at_exposure` serves rows held at one level at the level asked for.
3. Write its ``describe()``: one line that says where the rows come from, never a secret.

Then ``Dataset(source.fetch(exposure=Exposure.AGGREGATED), source=source.describe())``
builds a dataset from it, and nothing in the package changes.
"""

import copy
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, ClassVar, TypeAlias
from urllib.parse import quote, urlencode

from .dataset import FORMAT, _read_file
from .errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from .values import SCORES, Exposure

__all__ = [
    "DEFAULT_URL",
    "TOKEN_PREFIX",
    "TOKEN_VARIABLE",
    "ApiSource",
    "FileSource",
    "MemorySource",
    "Source",
    "Transport",
    "at_exposure",
]

#: The environment variable that holds the token, when none is passed.
TOKEN_VARIABLE = "CIVIQHUB_TOKEN"

#: How every personal access token of CiviqHub starts.
TOKEN_PREFIX = "civ_pat_"

#: The base address of the public API. Provisional: the API is not published yet.
DEFAULT_URL = "https://api.civiqhub.com/v1"

#: What sends a request for :class:`ApiSource`: it receives an address and headers, sends
#: a GET, and returns the status code, the headers and the body of the answer.
Transport: TypeAlias = Callable[[str, Mapping[str, str]], tuple[int, Mapping[str, str], bytes]]

# The sections that describe individuals, left out at the aggregated level.
_INDIVIDUAL = ("actants", "votes", "impressions")

# The sections whose rows name an author, a pseudonym that the aggregated level hides.
_AUTHORED = ("proposals", "arguments")

_Row = dict[str, Any]


class Source(ABC):
    """Anything that gives rows in the format of a dataset: the API, a file, memory.

    A source is the first point of extension of the SDK: a class derived from it works
    with :class:`~civiqhub.dataset.Dataset` as the sources of the package do. The
    docstring of :mod:`civiqhub.sources` says how to write one.
    """

    #: A short word for the kind of source, such as ``"memory"``.
    name: ClassVar[str] = "source"

    @abstractmethod
    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Return the rows of what the source covers, at the level of exposure asked for.

        Args:
            container: The id or the slug of one Project, when the source covers several.
                Without it, the rows cover everything the source covers.
            exposure: The level of detail of the rows. Their key ``exposure`` equals it.

        Returns:
            Rows in the format :data:`~civiqhub.dataset.FORMAT`.
        """

    def describe(self) -> str:
        """Return one line that says where the rows come from, never with a secret.

        A :class:`~civiqhub.dataset.Dataset` shows it as its source. By default, it is
        :attr:`name`.
        """
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.describe()!r})"


def at_exposure(rows: Mapping[str, Any], exposure: Exposure) -> dict[str, Any]:
    """Serve rows held at one level of exposure at the level asked for.

    Rows never gain detail. Rows held at the level asked for come back as a copy.
    Pseudonymised rows asked for at the aggregated level come back reduced: without the
    sections ``actants``, ``votes`` and ``impressions``, without the key ``author_id`` in
    ``proposals`` and ``arguments``, and with a row of ``vote_counts``, counted from the
    votes, for each revision that has votes and no such row.

    Args:
        rows: The rows, in the format :data:`~civiqhub.dataset.FORMAT`. They are not
            changed.
        exposure: The level asked for.

    Returns:
        New rows, at the level asked for.

    Raises:
        ExposureError: The rows are aggregated and the pseudonymised level is asked for.
        ValidationError: The rows or the level are not valid, or a vote cannot be
            counted.
    """
    asked = _level(exposure, "The level asked for")
    if not isinstance(rows, Mapping):
        raise ValidationError(
            f"The rows of a dataset are a dictionary of sections; got {type(rows).__name__}."
        )
    held = _level(rows.get("exposure"), "The level of the rows ('exposure')")
    if held is asked:
        return copy.deepcopy(dict(rows))
    if held is Exposure.AGGREGATED:
        raise ExposureError(
            "These rows are aggregated: they hold the vote counts of each revision and no "
            "individual vote, so they cannot be served at the pseudonymised level.",
            hint="Ask for the aggregated level, or get pseudonymised rows from the source "
            "that made these.",
        )
    return _aggregate(rows)


class MemorySource(Source):
    """Rows held in memory: for tests, simulations and the data of another system.

    The source keeps a deep copy of the rows: changing them afterwards does not change
    what it gives. It covers what the rows cover, so ``container`` is ignored.

    Args:
        rows: The rows, in the format :data:`~civiqhub.dataset.FORMAT`.

    Raises:
        ValidationError: The rows are not a dictionary.
    """

    name = "memory"

    def __init__(self, rows: Mapping[str, Any]) -> None:
        if not isinstance(rows, Mapping):
            raise ValidationError(
                f"The rows of a dataset are a dictionary of sections; got {type(rows).__name__}."
            )
        self._rows = copy.deepcopy(dict(rows))

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Return a copy of the rows, at the level asked for (see :func:`at_exposure`).

        Args:
            container: Ignored: the source covers what its rows cover.
            exposure: The level asked for.

        Raises:
            ExposureError: The rows are aggregated and the pseudonymised level is asked
                for.
        """
        return at_exposure(self._rows, exposure)


class FileSource(Source):
    """A file written by :meth:`~civiqhub.dataset.Dataset.save`, read without network.

    The file is read at each :meth:`fetch`. It covers what its rows cover, so
    ``container`` is ignored.

    Args:
        path: The path of the file.
    """

    name = "file"

    #: The path of the file.
    path: Path

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def describe(self) -> str:
        """Return ``"file <name of the file>"``."""
        return f"file {self.path.name}"

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Read the file and return its rows, at the level asked for.

        Args:
            container: Ignored: the source covers what its file covers.
            exposure: The level asked for.

        Raises:
            NotFoundError: No file is at the path.
            ValidationError: The file is not JSON, or not a dictionary of sections.
            ExposureError: The file is aggregated and the pseudonymised level is asked
                for.
        """
        return at_exposure(_read_file(self.path), exposure)


class ApiSource(Source):
    """The public API of CiviqHub, read with a personal access token. It only sends GET.

    A token covers one container, a Project or a Group, and never gives more than what
    its owner sees. :meth:`fetch` reads everything the token covers at one instant: it
    asks the API what the token covers and when (``as_of``), then passes that instant to
    every other read, so that all of them describe the same moment.

    **Provisional.** The public API is not published. The base address, the paths
    (:attr:`PATHS`), the read that says what a token covers, the pagination and the
    reading at an instant are assumptions taken from the prototype. They live in this
    class only, so that they change without touching anything else.

    The token is kept private. :meth:`describe` and ``repr`` show its last four
    characters at most, and no message of an error holds it.

    Args:
        token: The personal access token. Without it, the variable
            :data:`TOKEN_VARIABLE` is read.
        base_url: The base address of the API.
        transport: What sends the requests. Without it, ``urllib.request`` sends them,
            with the delay ``timeout``. Tests pass a fake one, so that no request leaves.
        timeout: How many seconds to wait for an answer.

    Raises:
        AuthenticationError: No token is given and the variable is not set, or the token
            does not start with :data:`TOKEN_PREFIX`. The message never repeats it.
        ValidationError: The base address is not an ``http`` or ``https`` address, or
            the delay is not a positive number.
    """

    name = "api"

    #: The path of each read, under the base address. ``{id}`` is the id of a Group or
    #: of a Project. A read of pages answers ``{"data": [...], "next_cursor": ...}`` and
    #: is read again with the parameter ``cursor`` until no cursor comes back.
    #:
    #: - ``scope``: what the token covers, ``{"kind": "project" or "group", "id": ...,
    #:   "as_of": ...}``;
    #: - ``group``, ``project``, ``participation``: one row;
    #: - ``group_projects``, ``proposals``, ``revisions``, ``amendments``, ``arguments``,
    #:   ``vote_counts``: pages;
    #: - ``actants``, ``votes``: pages, at the pseudonymised level only.
    PATHS: ClassVar[dict[str, str]] = {
        "scope": "/token",
        "group": "/groups/{id}",
        "group_projects": "/groups/{id}/projects",
        "project": "/projects/{id}",
        "proposals": "/projects/{id}/proposals",
        "revisions": "/projects/{id}/revisions",
        "amendments": "/projects/{id}/amendments",
        "arguments": "/projects/{id}/arguments",
        "vote_counts": "/projects/{id}/votes/aggregates",
        "participation": "/projects/{id}/participation",
        "actants": "/projects/{id}/actants",
        "votes": "/projects/{id}/votes",
    }

    # The sections read as pages for each Project, in the order of the reads.
    _LISTS: ClassVar[tuple[str, ...]] = (
        "proposals",
        "revisions",
        "amendments",
        "arguments",
        "vote_counts",
    )

    #: The base address of the API, without a final slash.
    base_url: str
    #: How many seconds to wait for an answer.
    timeout: float

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_URL,
        transport: Transport | None = None,
        timeout: float = 30.0,
    ) -> None:
        if token is None:
            token = os.environ.get(TOKEN_VARIABLE)
        if not token:
            raise AuthenticationError(
                f"No token was given, and the variable {TOKEN_VARIABLE} is not set."
            )
        if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
            raise AuthenticationError(
                f"This does not look like a CiviqHub token: every token starts with "
                f"{TOKEN_PREFIX!r}.",
                hint="Copy the token again from the settings of your Project, then pass it "
                f"to civiqhub.connect(token) or set {TOKEN_VARIABLE}.",
            )
        if not isinstance(base_url, str) or not base_url.startswith(("https://", "http://")):
            raise ValidationError(
                f"The base address of the API starts with 'https://'; got {base_url!r}."
            )
        if not isinstance(timeout, int | float) or isinstance(timeout, bool) or timeout <= 0:
            raise ValidationError(f"The timeout is a positive number of seconds; got {timeout!r}.")
        self._token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self._transport: Transport = transport or self._send

    def describe(self) -> str:
        """Return ``"api <base address>, token civ_pat_...<last four characters>"``.

        A token so short that four characters would show half of its secret part shows
        fewer.
        """
        secret = self._token[len(TOKEN_PREFIX) :]
        shown = secret[len(secret) - min(4, len(secret) // 2) :] if secret else ""
        return f"api {self.base_url}, token {TOKEN_PREFIX}...{shown}"

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Read everything the token covers, at one instant, at the level asked for.

        Args:
            container: The id or the slug of one Project of the Group that the token
                covers. Without it, every Project the token covers is read.
            exposure: The level asked for. At the pseudonymised level, the votes and the
                actants are read too, and the actants of several Projects are merged by
                pseudonym.

        Returns:
            Rows in the format :data:`~civiqhub.dataset.FORMAT`. A link to a Group that
            the token does not cover, such as the Group of a Project read with a token of
            that Project, is left out, so that the rows hold no link to a missing row.

        Raises:
            AuthenticationError: The API refused the token: it is expired or revoked.
            ExposureError: The token does not allow a read, such as the votes.
            NotFoundError: The API has nothing at a path, or ``container`` names no
                Project that the token covers.
            RateLimitedError: The API asks to slow down; ``retry_after`` says how long.
            CiviqHubError: The API cannot be reached, or answered something else.
        """
        level = _level(exposure, "The level asked for")
        if container is not None and (not isinstance(container, str) or not container):
            raise ValidationError(
                f"The container is the id or the slug of a Project; got {container!r}."
            )
        scope = self._read_scope()
        as_of = scope["as_of"]
        rows: _Row = {"format": FORMAT, "as_of": as_of, "exposure": level.value}
        sections = ["groups", "projects", "participation", *self._LISTS]
        if level is Exposure.PSEUDONYMISED:
            sections += ["actants", "votes"]
        rows.update({section: [] for section in sections})
        if scope["kind"] == "group":
            rows["groups"] += self._one("groups", "group", scope["id"], as_of=as_of)
            listed = self._pages("projects", "group_projects", scope["id"], as_of=as_of)
            wanted = [
                str(project.get("id"))
                for project in listed
                if container is None or container in (project.get("id"), project.get("slug"))
            ]
            if container is not None and not wanted:
                raise NotFoundError(
                    f"The Group that the token covers has no Project with the id or slug "
                    f"{container!r}; it has {_count(len(listed), 'project')}."
                )
        else:
            wanted = [scope["id"]]
        actants: dict[str, _Row] = {}
        for project_id in wanted:
            project = self._one("projects", "project", project_id, as_of=as_of)
            if container is not None and scope["kind"] == "project":
                row = project[0] if project else {}
                if container not in (row.get("id"), row.get("slug")):
                    raise NotFoundError(
                        f"The token covers the Project {row.get('slug')!r}, not {container!r}."
                    )
            rows["projects"] += project
            for section in self._LISTS:
                rows[section] += self._pages(section, section, project_id, as_of=as_of)
            rows["participation"] += self._one(
                "participation", "participation", project_id, as_of=as_of
            )
            if level is Exposure.PSEUDONYMISED:
                detail = {"as_of": as_of, "exposure": level.value}
                rows["votes"] += self._pages("votes", "votes", project_id, **detail)
                for actant in self._pages("actants", "actants", project_id, **detail):
                    actants.setdefault(str(actant.get("pseudonym")), actant)
        if level is Exposure.PSEUDONYMISED:
            rows["actants"] = list(actants.values())
        _detach(rows)
        return rows

    def _to_rows(self, section: str, answer: Any) -> list[_Row]:
        """Turn an answer of the API into rows of a section of the format.

        It is the only place where the shape of the answers meets the format of the
        rows. Today, the API is assumed to answer rows already.
        """
        answered = [answer] if isinstance(answer, dict) else answer
        if not isinstance(answered, list) or not all(isinstance(row, dict) for row in answered):
            raise CiviqHubError(
                f"The API answered rows of {section!r} that are not JSON objects.",
                hint=_CHANGED,
            )
        return answered

    def _read_scope(self) -> _Row:
        scope = self._get("scope")
        if (
            not isinstance(scope, dict)
            or scope.get("kind") not in ("project", "group")
            or not isinstance(scope.get("id"), str)
            or not isinstance(scope.get("as_of"), str)
        ):
            raise CiviqHubError(
                f"The API answered {self.PATHS['scope']} without saying what the token "
                f"covers: a kind 'project' or 'group', an id and an instant 'as_of'.",
                hint=_CHANGED,
            )
        result: _Row = scope
        return result

    def _one(self, section: str, key: str, id: str, **query: str) -> list[_Row]:
        return self._to_rows(section, self._get(key, id, **query))

    def _pages(self, section: str, key: str, id: str, **query: str) -> list[_Row]:
        rows: list[_Row] = []
        cursors: set[str] = set()
        cursor: str | None = None
        while True:
            page = self._get(key, id, **query, **({"cursor": cursor} if cursor else {}))
            if not isinstance(page, dict) or not isinstance(page.get("data"), list):
                raise CiviqHubError(
                    f"The API answered {self._path(key, id)} with a page that has no list 'data'.",
                    hint=_CHANGED,
                )
            rows += self._to_rows(section, page["data"])
            cursor = page.get("next_cursor")
            if not cursor:
                return rows
            if not isinstance(cursor, str) or cursor in cursors:
                raise CiviqHubError(
                    f"The API answered {self._path(key, id)} with a cursor that does not "
                    f"move forward.",
                    hint=_LATER,
                )
            cursors.add(cursor)

    def _path(self, key: str, id: str = "") -> str:
        return self.PATHS[key].format(id=quote(id, safe=""))

    def _get(self, key: str, id: str = "", **query: str) -> Any:
        path = self._path(key, id)
        url = self.base_url + path + ("?" + urlencode(query) if query else "")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        status, answered, body = self._transport(url, headers)
        if status == 200:
            try:
                return json.loads(body)
            except (UnicodeDecodeError, ValueError):
                raise CiviqHubError(
                    f"The API answered {path} with a body that is not JSON.", hint=_LATER
                ) from None
        if status == 401:
            raise AuthenticationError(
                f"The API refused the token at {path}: it is expired or revoked."
            )
        if status == 403:
            raise ExposureError(
                f"The token does not allow {path}.",
                hint="Aggregated data stays available with "
                'civiqhub.connect(exposure="aggregated"). Pseudonymised data must be enabled '
                "by an administrator of the Project.",
            )
        if status == 404:
            raise NotFoundError(f"The API has nothing at {path} for this token.")
        if status == 429:
            wait = _retry_after(answered)
            told = f": wait {wait:g} seconds" if wait is not None else ""
            raise RateLimitedError(f"The API asks to slow down at {path}{told}.", retry_after=wait)
        raise CiviqHubError(f"The API answered {status} at {path}.", hint=_LATER)

    def _send(self, url: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                return int(answer.status), dict(answer.headers), bytes(answer.read())
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers or {}), error.read()
        except (urllib.error.URLError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise CiviqHubError(
                f"Could not reach {self.base_url} ({reason}).",
                hint="Check the connection and the base address, then call again.",
            ) from None


# The hints of the errors that the API itself causes.
_CHANGED = "The public API may have changed; update civiqhub, then call again."
_LATER = "Call again later; if it lasts, report it to CiviqHub."


def _retry_after(headers: Mapping[str, str]) -> float | None:
    for name, value in headers.items():
        if name.lower() == "retry-after":
            try:
                wait = float(value)
            except (TypeError, ValueError):
                return None
            # A delay that is negative, infinite or not a number is no delay.
            return wait if 0 <= wait < float("inf") else None
    return None


def _detach(rows: _Row) -> None:
    """Leave out the links to Groups that the rows do not hold."""
    known = {group.get("id") for group in rows["groups"]}
    for group in rows["groups"]:
        if group.get("parent_id") is not None and group["parent_id"] not in known:
            del group["parent_id"]
    for project in rows["projects"]:
        if project.get("group_id") is not None and project["group_id"] not in known:
            del project["group_id"]


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _level(value: object, what: str) -> Exposure:
    if isinstance(value, str) and value in {level.value for level in Exposure}:
        return Exposure(value)
    raise ValidationError(f"{what} is 'aggregated' or 'pseudonymised'; got {value!r}.")


def _aggregate(rows: Mapping[str, Any]) -> _Row:
    reduced = {key: copy.deepcopy(value) for key, value in rows.items() if key not in _INDIVIDUAL}
    reduced["exposure"] = Exposure.AGGREGATED.value
    for section in _AUTHORED:
        if isinstance(reduced.get(section), list):
            for row in reduced[section]:
                if isinstance(row, dict):
                    row.pop("author_id", None)
    counted = _count_votes(rows.get("votes", []))
    if counted:
        given = reduced.get("vote_counts", [])
        if not isinstance(given, list):
            raise ValidationError(
                f"The section 'vote_counts' is a list of rows; got {type(given).__name__}."
            )
        known = {row.get("revision_id") for row in given if isinstance(row, dict)}
        missing = [
            revision_id for revision_id in _ordered(rows, counted) if revision_id not in known
        ]
        reduced["vote_counts"] = given + [
            {"revision_id": revision_id, "counts": counted[revision_id]} for revision_id in missing
        ]
    return reduced


def _count_votes(votes: object) -> dict[str, list[int]]:
    if not isinstance(votes, list):
        raise ValidationError(f"The section 'votes' is a list of rows; got {type(votes).__name__}.")
    counted: dict[str, list[int]] = {}
    for index, row in enumerate(votes):
        revision_id = row.get("revision_id") if isinstance(row, dict) else None
        score = row.get("score") if isinstance(row, dict) else None
        if not isinstance(revision_id, str) or not revision_id:
            raise ValidationError(
                f"The row votes[{index}] has no valid 'revision_id', so it cannot be counted; "
                f"got {row!r}."
            )
        if not isinstance(score, int) or isinstance(score, bool) or score not in SCORES:
            raise ValidationError(
                f"The row votes[{index}] has the score {score!r}: a score is an integer from "
                f"-2 to +2, so it cannot be counted."
            )
        counts = counted.setdefault(revision_id, [0] * len(SCORES))
        counts[SCORES.index(score)] += 1
    return counted


def _ordered(rows: Mapping[str, Any], counted: Mapping[str, list[int]]) -> list[str]:
    """Return the counted revisions in the order of the section ``revisions``."""
    revisions = rows.get("revisions")
    if not isinstance(revisions, list):
        revisions = []
    listed = [row.get("id") for row in revisions if isinstance(row, dict)]
    first = [
        revision_id
        for revision_id in listed
        if isinstance(revision_id, str) and revision_id in counted
    ]
    seen = set(first)
    return first + [revision_id for revision_id in counted if revision_id not in seen]
