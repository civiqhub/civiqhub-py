# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The front door: a token in, a Project out. The API is played by a stand-in."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import TOKEN, VOTES, FakeApi, small_payload

import civiqhub

CORE = (
    "Actant",
    "ActantKind",
    "Agent",
    "Amendment",
    "AmendmentStatus",
    "ApiSource",
    "Argument",
    "AuthenticationError",
    "CellState",
    "CiviqHubError",
    "Client",
    "Entity",
    "Exposure",
    "ExposureError",
    "FileSource",
    "Group",
    "Listing",
    "Member",
    "MemorySource",
    "MissingExtraError",
    "NotFoundError",
    "Participation",
    "Position",
    "Project",
    "Proposal",
    "RateLimitedError",
    "Revision",
    "Role",
    "Snapshot",
    "Source",
    "UnavailableError",
    "ValidationError",
    "Vote",
    "VoteTally",
    "__version__",
    "connect",
    "load",
)


def test_the_core_names_are_importable_from_the_package() -> None:
    assert set(CORE) <= set(civiqhub.__all__)
    assert all(getattr(civiqhub, name) is not None for name in CORE)
    assert civiqhub.__all__ == sorted(civiqhub.__all__, key=lambda name: (name.islower(), name))


def test_three_lines_from_a_token_to_a_project() -> None:
    source = civiqhub.ApiSource(TOKEN, transport=FakeApi(small_payload()))
    project = civiqhub.connect(source=source, exposure="pseudonymised").project()
    assert len(project.proposals) == 5
    assert len(project.votes) == len(VOTES)
    assert project.as_of == "T0"
    assert TOKEN not in repr(source)
    assert TOKEN not in project.snapshot.source


def test_connect_reads_the_token_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIVIQHUB_TOKEN", TOKEN)
    client = civiqhub.connect()  # builds the client; nothing is fetched yet
    assert isinstance(client.source, civiqhub.ApiSource)
    assert client.exposure is civiqhub.Exposure.AGGREGATED  # the default
    assert repr(client) == "Client(api https://api.civiqhub.com/v1, aggregated)"
    assert TOKEN not in repr(client)
    assert TOKEN[-4:] not in repr(client)
    elsewhere = civiqhub.connect(base_url="https://api.invalid/public/v1/")
    assert repr(elsewhere) == "Client(api https://api.invalid/public/v1, aggregated)"


def test_token_errors_say_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIVIQHUB_TOKEN", raising=False)
    with pytest.raises(civiqhub.AuthenticationError, match="CIVIQHUB_TOKEN"):
        civiqhub.connect()
    with pytest.raises(civiqhub.AuthenticationError, match="civ_pat_"):
        civiqhub.connect("not-a-token")
    wrong = civiqhub.ApiSource("civ_pat_revoked", transport=FakeApi(small_payload()))
    with pytest.raises(civiqhub.AuthenticationError, match="expired or revoked"):
        civiqhub.connect(source=wrong).project()


def test_a_client_takes_one_snapshot_and_keeps_it_until_refreshed() -> None:
    api = FakeApi(small_payload())
    client = civiqhub.connect(source=civiqhub.ApiSource(TOKEN, transport=api))
    first = client.project()
    asked = len(api.calls)
    assert client.project().snapshot is first.snapshot
    assert client.snapshot() is first.snapshot
    assert len(api.calls) == asked  # navigating and asking again read nothing
    client.refresh()
    assert client.project().snapshot is not first.snapshot
    assert client.project() == first  # same data, a new snapshot
    assert len(api.calls) == 2 * asked


def test_the_exposure_asked_at_the_door_applies_to_what_is_read() -> None:
    source = civiqhub.MemorySource(small_payload())
    public = civiqhub.connect(source=source).project()
    assert public.exposure is civiqhub.Exposure.AGGREGATED
    assert public.proposals["p-1"].tally.total == 3
    with pytest.raises(civiqhub.ExposureError, match="pseudonymised"):
        _ = public.votes
    detailed = civiqhub.connect(source=source, exposure="pseudonymised").project()
    assert len(detailed.votes) == len(VOTES)
    with pytest.raises(ValueError, match="everything"):
        civiqhub.connect(source=source, exposure="everything")


def test_a_saved_snapshot_replays_identically(tmp_path: Path) -> None:
    source = civiqhub.MemorySource(small_payload())
    project = civiqhub.connect(source=source, exposure="pseudonymised").project()
    path = project.save(tmp_path / "demo.json")
    again = civiqhub.load(path).project()  # no network, no token
    assert again.snapshot.fingerprint() == project.snapshot.fingerprint()
    assert again.proposals.ids == project.proposals.ids
    assert again.snapshot.source == "file demo.json"
    replay = civiqhub.connect(source=civiqhub.FileSource(path), exposure="pseudonymised")
    assert replay.project("demo-project") == project
    with pytest.raises(civiqhub.NotFoundError, match="demo-project"):
        replay.project("budget")
    with pytest.raises(civiqhub.NotFoundError, match="no snapshot file"):
        civiqhub.load(tmp_path / "missing.json")


def test_a_client_reads_the_groups_the_source_holds() -> None:
    client = civiqhub.connect(source=civiqhub.MemorySource(small_payload()))
    group = client.group("demo-collective")
    assert [project.slug for project in group.projects] == ["demo-project"]
    with pytest.raises(civiqhub.NotFoundError, match="name one of"):
        client.group()
