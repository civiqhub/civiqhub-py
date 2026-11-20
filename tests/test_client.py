# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The client, connect and load: from a token or a source to a Project, without network."""

import socket
import urllib.request
from pathlib import Path
from typing import Any

import pytest

import civiqhub
from civiqhub.client import Client
from civiqhub.dataset import Dataset
from civiqhub.errors import (
    AuthenticationError,
    ExposureError,
    NotFoundError,
    ValidationError,
)
from civiqhub.sources import TOKEN_VARIABLE, ApiSource, FileSource, MemorySource, Source
from civiqhub.values import Exposure
from support import TOKEN, FakeApi, api_rows, pseudonymised_rows, reference_rows


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to open a connection fail, and forget the token of the machine."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test of the SDK tried to open a connection")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)


class CountingSource(Source):
    """A source in memory that counts how many times it is read."""

    name = "counting"

    def __init__(self, rows: dict[str, Any]) -> None:
        self.inner = MemorySource(rows)
        self.reads = 0

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        self.reads += 1
        return self.inner.fetch(container, exposure=exposure)


# Criterion 1: three lines.


def test_three_lines_give_a_project() -> None:
    fake = FakeApi(api_rows())
    project = civiqhub.connect(source=ApiSource("civ_pat_test1234", transport=fake)).project()
    assert isinstance(project, civiqhub.Project)
    assert project.proposals
    assert project.dataset.source == "api https://api.civiqhub.com/v1, token civ_pat_...1234"


# Criterion 2: the token is read from the environment.


def test_connect_reads_the_token_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    client = civiqhub.connect()
    assert isinstance(client.source, ApiSource)
    assert client.source.describe() == "api https://api.civiqhub.com/v1, token civ_pat_...1234"
    assert client.exposure is Exposure.AGGREGATED


def test_connect_passes_the_token_and_the_base_address() -> None:
    client = civiqhub.connect(TOKEN, base_url="https://api.example.test/v9/")
    assert isinstance(client.source, ApiSource)
    assert client.source.base_url == "https://api.example.test/v9"


def test_connect_without_a_token_raises_an_authentication_error() -> None:
    with pytest.raises(AuthenticationError, match=TOKEN_VARIABLE):
        civiqhub.connect()


# Criterion 3: one read, kept; refresh reads again.


def test_a_project_is_read_once_and_kept() -> None:
    source = CountingSource(pseudonymised_rows())
    client = civiqhub.connect(source=source)
    first = client.project()
    assert client.project() is first
    assert client.load() is first.dataset
    assert source.reads == 1


def test_refresh_reads_the_source_again_and_keeps_the_old_objects_valid() -> None:
    source = CountingSource(pseudonymised_rows())
    client = civiqhub.connect(source=source)
    old = client.project()
    client.refresh()
    new = client.project()
    assert source.reads == 2
    assert new is not old
    assert new.dataset is not old.dataset
    assert new.dataset.fingerprint() == old.dataset.fingerprint()
    assert [proposal.id for proposal in old.proposals] == ["p-01", "p-02", "p-03"]
    assert old.proposals[0].current_revision.vote_counts.total == 3


def test_each_container_is_loaded_and_kept_apart() -> None:
    source = CountingSource(reference_rows())
    client = civiqhub.connect(source=source)
    by_slug = client.project("budget-2027")
    assert client.project("budget-2027") is by_slug
    assert client.project() is not by_slug
    assert source.reads == 2


# Criterion 4: the level of exposure.


def test_the_pseudonymised_level_gives_the_actants() -> None:
    rows = pseudonymised_rows()
    project = civiqhub.connect(source=MemorySource(rows), exposure="pseudonymised").project()
    assert [actant.pseudonym for actant in project.actants] == ["m-001", "m-002", "m-003", "g-001"]


def test_the_default_level_is_aggregated_and_hides_the_actants() -> None:
    client = civiqhub.connect(source=MemorySource(pseudonymised_rows()))
    assert client.exposure is Exposure.AGGREGATED
    project = client.project()
    assert project.dataset.exposure is Exposure.AGGREGATED
    with pytest.raises(ExposureError):
        _ = project.actants


def test_the_level_may_be_given_as_a_value_of_exposure() -> None:
    client = Client(MemorySource(pseudonymised_rows()), exposure=Exposure.PSEUDONYMISED)
    assert client.exposure is Exposure.PSEUDONYMISED


# Criterion 5: what connect refuses.


@pytest.mark.parametrize("level", ["secret", "Aggregated", None, 1])
def test_an_unknown_level_is_refused(level: Any) -> None:
    with pytest.raises(ValidationError, match="'aggregated' or 'pseudonymised'"):
        civiqhub.connect(exposure=level)
    with pytest.raises(ValidationError, match="'aggregated' or 'pseudonymised'"):
        Client(MemorySource(reference_rows()), exposure=level)


def test_a_token_and_a_source_together_are_refused() -> None:
    with pytest.raises(ValidationError, match="Pass a token or a source, not both"):
        civiqhub.connect("civ_pat_x", source=MemorySource(reference_rows()))


def test_a_base_address_with_a_source_is_refused() -> None:
    with pytest.raises(ValidationError, match="base address with a token only"):
        civiqhub.connect(source=MemorySource(reference_rows()), base_url="https://elsewhere")


@pytest.mark.parametrize("source", [reference_rows(), "memory", None])
def test_a_client_needs_a_source(source: Any) -> None:
    with pytest.raises(ValidationError, match=r"derives from civiqhub.Source"):
        Client(source)


# Criterion 6: a token of a Project covers no Group.


def test_a_project_token_covers_no_group() -> None:
    fake = FakeApi(api_rows(), kind="project", container_id="budget-2027")
    client = civiqhub.connect(source=ApiSource(TOKEN, transport=fake))
    with pytest.raises(NotFoundError, match="The token covers no Group") as raised:
        client.group()
    assert "client.project()" in raised.value.hint
    assert TOKEN not in str(raised.value)
    assert client.project().slug == "budget-2027"


def test_a_group_token_gives_its_group() -> None:
    client = civiqhub.connect(source=ApiSource(TOKEN, transport=FakeApi(api_rows())))
    group = client.group()
    assert group.slug == "demo-collective"
    assert [project.slug for project in group.projects] == ["budget-2027"]
    assert client.group("g-1") is group


# Criterion 7: load reopens a saved dataset.


def test_load_reopens_a_saved_dataset(tmp_path: Path) -> None:
    dataset = Dataset(pseudonymised_rows())
    reopened = civiqhub.load(dataset.save(tmp_path / "consultation.json"))
    assert isinstance(reopened, Dataset)
    assert reopened.fingerprint() == dataset.fingerprint()
    assert reopened.source == "file consultation.json"
    assert civiqhub.load(str(tmp_path / "consultation.json")).project().slug == "budget-2027"


def test_load_of_a_missing_file_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        civiqhub.load(tmp_path / "missing.json")


def test_a_client_of_a_file_source_reads_it_at_its_level(tmp_path: Path) -> None:
    path = Dataset(pseudonymised_rows()).save(tmp_path / "d.json")
    project = civiqhub.connect(source=FileSource(path)).project()
    assert project.dataset.exposure is Exposure.AGGREGATED
    assert project.dataset.source == "file d.json"


# Criterion 8: no token in the repr.


def test_the_repr_of_a_client_holds_no_token() -> None:
    client = civiqhub.connect(TOKEN)
    assert (
        repr(client) == "Client(api https://api.civiqhub.com/v1, token civ_pat_...1234, aggregated)"
    )
    assert TOKEN not in repr(client)
    memory = civiqhub.connect(source=MemorySource(reference_rows()), exposure="pseudonymised")
    assert repr(memory) == "Client(memory, pseudonymised)"


def test_connect_reads_nothing_before_a_project_is_asked_for() -> None:
    source = CountingSource(reference_rows())
    civiqhub.connect(source=source)
    assert source.reads == 0
