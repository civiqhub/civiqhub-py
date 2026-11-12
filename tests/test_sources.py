# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Where a snapshot comes from: memory, a file, or the API played by a stand-in.

No test opens a connection. ``ApiSource`` is provisional: its paths are the ones the
prototype assumed, and these tests only hold it to that assumption.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from support import TOKEN, VOTES, FakeApi, aggregated_payload, small_payload

from civiqhub.errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from civiqhub.model import Exposure, Snapshot
from civiqhub.sources import DEFAULT_URL, ApiSource, FileSource, MemorySource, Source


def test_a_memory_source_serves_what_it_holds_at_the_level_asked() -> None:
    held = small_payload(impressions=True)
    source = MemorySource(held)
    assert isinstance(source, Source)
    assert source.fetch(exposure=Exposure.PSEUDONYMISED) == held
    reduced = source.fetch(exposure=Exposure.AGGREGATED)
    assert reduced["exposure"] == "aggregated"
    assert not {"members", "votes", "impressions"} & set(reduced)
    assert all("author_id" not in row for row in reduced["proposals"] + reduced["arguments"])
    assert reduced["tallies"] == held["tallies"]
    assert "votes" in held  # what the source holds is left as it was
    assert Snapshot(reduced).project().proposals["p-1"].tally.total == 3
    assert source.describe() == "memory"
    assert repr(source) == "MemorySource(memory)"


def test_a_stored_payload_never_gains_detail() -> None:
    public = MemorySource(aggregated_payload())
    with pytest.raises(ExposureError, match="saved at the aggregated level"):
        public.fetch(exposure=Exposure.PSEUDONYMISED)
    assert public.fetch(exposure=Exposure.AGGREGATED)["exposure"] == "aggregated"
    uncounted = small_payload()
    del uncounted["tallies"]
    with pytest.raises(ValidationError, match="votes but no tallies"):
        MemorySource(uncounted).fetch(exposure=Exposure.AGGREGATED)


def test_a_file_source_reads_a_saved_snapshot(tmp_path: Path) -> None:
    path = Snapshot(small_payload()).save(tmp_path / "demo.json")
    source = FileSource(path)
    assert source.read() == small_payload()
    assert source.fetch(exposure=Exposure.AGGREGATED)["exposure"] == "aggregated"
    assert source.describe() == "file demo.json"  # the name, not the directories above it
    with pytest.raises(NotFoundError, match="no snapshot file"):
        FileSource(tmp_path / "missing.json").read()


def test_the_api_source_assembles_a_snapshot_page_by_page() -> None:
    held = small_payload()
    api = FakeApi(held, page=2)
    source = ApiSource(TOKEN, transport=api)
    payload = source.fetch(exposure=Exposure.PSEUDONYMISED)
    assert payload["as_of"] == "T0"
    assert payload["exposure"] == "pseudonymised"
    for section in ("proposals", "revisions", "amendments", "arguments", "tallies", "votes"):
        assert payload[section] == held[section]
    assert payload["members"] == held["members"]
    assert payload["participation"] == held["participation"]
    project = Snapshot(payload, source=source.describe()).project()
    assert len(project.votes) == len(VOTES)
    assert all(url.startswith(DEFAULT_URL + "/") for url in api.calls)
    assert api.calls[0] == f"{DEFAULT_URL}/token"
    # every read after the first is pinned to the instant the token endpoint gave
    assert all(query["as_of"] == "T0" for query in api.queries[1:])
    proposals = [url for url in api.calls if "/proposals" in url]
    assert len(proposals) == 3  # five rows, two per page
    detailed = [q for url, q in zip(api.calls, api.queries, strict=True) if "/members" in url]
    assert detailed
    assert all(q["exposure"] == "pseudonymised" for q in detailed)


def test_the_api_source_only_reads_what_the_exposure_allows() -> None:
    api = FakeApi(small_payload(), detailed=False)
    payload = ApiSource(TOKEN, transport=api).fetch(exposure=Exposure.AGGREGATED)
    assert Snapshot(payload).project().proposals["p-1"].tally.total == 3
    assert "members" not in payload
    assert "votes" not in payload
    assert not any("/members" in url or url.split("?")[0].endswith("/votes") for url in api.calls)
    with pytest.raises(ExposureError, match="administrator") as refused:
        ApiSource(TOKEN, transport=api).fetch(exposure=Exposure.PSEUDONYMISED)
    assert "/projects/demo/votes" in str(refused.value)


def test_a_token_scoped_to_a_group_reads_the_group_and_its_projects() -> None:
    api = FakeApi(small_payload(), scope="group")
    source = ApiSource(TOKEN, transport=api)
    payload = source.fetch(exposure=Exposure.AGGREGATED)
    snapshot = Snapshot(payload)
    assert snapshot.group().slug == "demo-collective"
    assert snapshot.group().projects == snapshot.projects
    assert snapshot.project().group == snapshot.group()
    by_slug = source.fetch("demo-project", exposure=Exposure.AGGREGATED)
    assert [row["id"] for row in by_slug["projects"]] == ["demo"]
    other = source.fetch("budget", exposure=Exposure.AGGREGATED)
    assert other["projects"] == []  # the Group holds no such Project


def test_a_missing_or_malformed_token_is_refused_before_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CIVIQHUB_TOKEN", raising=False)
    with pytest.raises(AuthenticationError, match="CIVIQHUB_TOKEN") as missing:
        ApiSource()
    assert "CIVIQHUB_TOKEN" in missing.value.__notes__[0]
    with pytest.raises(AuthenticationError, match="civ_pat_"):
        ApiSource("not-a-token")
    api = FakeApi(small_payload())
    with pytest.raises(AuthenticationError, match="expired or revoked"):
        ApiSource("civ_pat_revoked", transport=api).fetch(exposure=Exposure.AGGREGATED)
    assert len(api.calls) == 1  # the first refusal stops the reading


def test_the_token_is_read_from_the_environment_and_never_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CIVIQHUB_TOKEN", TOKEN)
    source = ApiSource(transport=FakeApi(small_payload()))
    payload = source.fetch(exposure=Exposure.AGGREGATED)
    snapshot = Snapshot(payload, source=source.describe())
    assert TOKEN not in repr(source)
    assert TOKEN not in source.describe()
    assert TOKEN not in snapshot.source
    assert TOKEN not in repr(snapshot)
    assert TOKEN not in json.dumps(payload)
    assert source.describe().startswith(f"api {DEFAULT_URL}")


@pytest.mark.parametrize(
    ("status", "answered", "error", "message"),
    [
        (404, {}, NotFoundError, "nothing at /projects/demo"),
        (429, {"Retry-After": "7"}, RateLimitedError, "wait 7 seconds"),
        (429, {}, RateLimitedError, "wait a moment"),
        (500, {}, CiviqHubError, "answered 500"),
    ],
)
def test_a_refusal_of_the_api_becomes_an_error_of_the_library(
    status: int, answered: dict[str, str], error: type[CiviqHubError], message: str
) -> None:
    api = FakeApi(small_payload(), answers={"/projects/demo": (status, answered)})
    with pytest.raises(error, match=message) as raised:
        ApiSource(TOKEN, transport=api).fetch(exposure=Exposure.AGGREGATED)
    assert TOKEN not in str(raised.value)
    if isinstance(raised.value, RateLimitedError):
        assert raised.value.retry_after == (7.0 if answered else None)


class _Answer:
    """What ``urlopen`` hands back, reduced to what the source reads."""

    status = 200
    headers: Message = Message()

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Answer:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_the_default_transport_sends_one_get_with_the_token_as_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[urllib.request.Request, float]] = []

    def opened(request: urllib.request.Request, timeout: float) -> _Answer:
        seen.append((request, timeout))
        return _Answer(json.dumps({"kind": "project", "id": "demo", "as_of": "T0"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", opened)
    source = ApiSource(TOKEN, base_url="https://api.invalid/v1/", timeout=5.0)
    assert source._get("/token") == {"kind": "project", "id": "demo", "as_of": "T0"}
    request, timeout = seen[0]
    assert request.get_method() == "GET"
    assert request.full_url == "https://api.invalid/v1/token"
    assert request.get_header("Authorization") == f"Bearer {TOKEN}"
    assert timeout == 5.0


def test_an_http_error_and_an_unreachable_host_are_told_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(request: urllib.request.Request, timeout: float) -> Any:
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", Message(), io.BytesIO())

    def unreachable(request: urllib.request.Request, timeout: float) -> Any:
        raise urllib.error.URLError("no route to host")

    source = ApiSource(TOKEN, base_url="https://api.invalid/v1")
    monkeypatch.setattr(urllib.request, "urlopen", refused)
    with pytest.raises(AuthenticationError, match="expired or revoked"):
        source.fetch(exposure=Exposure.AGGREGATED)
    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(CiviqHubError, match="could not reach") as lost:
        source.fetch(exposure=Exposure.AGGREGATED)
    assert "https://api.invalid/v1" in str(lost.value)
    assert TOKEN not in str(lost.value)
