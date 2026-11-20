# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The sources: the port through which rows enter the SDK, in memory and from a file."""

import json
from pathlib import Path
from typing import Any

import pytest

from civiqhub.dataset import Dataset
from civiqhub.errors import ExposureError, NotFoundError, ValidationError
from civiqhub.sources import FileSource, MemorySource, Source, at_exposure
from civiqhub.values import Exposure, VoteCounts
from support import VOTES, pseudonymised_rows, reference_rows

AGGREGATED = Exposure.AGGREGATED
PSEUDONYMISED = Exposure.PSEUDONYMISED


def counts_of_votes(revision_id: str) -> VoteCounts:
    return VoteCounts.from_scores(score for _, voted, score in VOTES if voted == revision_id)


def test_pseudonymised_rows_come_back_with_the_same_fingerprint() -> None:
    rows = pseudonymised_rows()
    fetched = MemorySource(rows).fetch(exposure=PSEUDONYMISED)
    assert Dataset(fetched).fingerprint() == Dataset(rows).fingerprint()
    assert fetched == rows


@pytest.mark.parametrize("with_vote_counts", [True, False], ids=["given", "counted"])
def test_pseudonymised_rows_are_reduced_at_the_aggregated_level(with_vote_counts: bool) -> None:
    rows = pseudonymised_rows()
    if not with_vote_counts:
        del rows["vote_counts"]
    fetched = MemorySource(rows).fetch(exposure=AGGREGATED)
    dataset = Dataset(fetched)
    assert dataset.exposure is AGGREGATED
    assert fetched["exposure"] == "aggregated"
    assert not dataset.has_individual_votes
    assert not set(fetched) & {"actants", "votes", "impressions"}
    assert "author_id" not in json.dumps(fetched)
    for revision in dataset.revisions:
        assert revision.vote_counts == counts_of_votes(revision.id), revision.id
    with pytest.raises(ExposureError):
        _ = dataset.project().actants


def test_the_counted_rows_follow_the_order_of_the_revisions() -> None:
    rows = pseudonymised_rows()
    del rows["vote_counts"]
    reduced = at_exposure(rows, AGGREGATED)
    voted = [
        revision["id"] for revision in rows["revisions"] if counts_of_votes(revision["id"]).total
    ]
    assert [row["revision_id"] for row in reduced["vote_counts"]] == voted
    assert reduced["vote_counts"][0] == {"revision_id": "p-01.r1", "counts": [0, 1, 0, 1, 0]}


def test_a_given_row_of_vote_counts_is_kept_and_a_missing_one_is_added() -> None:
    rows = pseudonymised_rows()
    rows["vote_counts"] = [row for row in rows["vote_counts"] if row["revision_id"] != "p-02.r2"]
    kept = list(rows["vote_counts"])
    reduced = at_exposure(rows, AGGREGATED)
    assert reduced["vote_counts"] == [*kept, {"revision_id": "p-02.r2", "counts": [0, 1, 1, 1, 0]}]


def test_aggregated_rows_never_gain_detail() -> None:
    with pytest.raises(
        ExposureError, match="cannot be served at the pseudonymised level"
    ) as raised:
        MemorySource(reference_rows()).fetch(exposure=PSEUDONYMISED)
    assert "aggregated level" in raised.value.hint


def test_aggregated_rows_come_back_as_a_copy() -> None:
    rows = reference_rows()
    fetched = at_exposure(rows, AGGREGATED)
    assert fetched == rows
    fetched["proposals"].clear()
    assert rows["proposals"]


def test_at_exposure_does_not_change_the_rows() -> None:
    rows = pseudonymised_rows()
    before = json.dumps(rows, sort_keys=True)
    at_exposure(rows, AGGREGATED)
    assert json.dumps(rows, sort_keys=True) == before


def test_a_memory_source_keeps_its_own_copy() -> None:
    rows = pseudonymised_rows()
    source = MemorySource(rows)
    expected = Dataset(rows).fingerprint()
    rows["proposals"].clear()
    rows["votes"][0]["score"] = -2
    rows["exposure"] = "aggregated"
    assert Dataset(source.fetch(exposure=PSEUDONYMISED)).fingerprint() == expected
    fetched = source.fetch(exposure=PSEUDONYMISED)
    fetched["votes"].clear()
    assert source.fetch(exposure=PSEUDONYMISED)["votes"]


def test_a_memory_source_ignores_the_container() -> None:
    source = MemorySource(reference_rows())
    assert source.fetch("anything", exposure=AGGREGATED) == source.fetch(exposure=AGGREGATED)


def test_a_file_source_reads_a_saved_dataset(tmp_path: Path) -> None:
    for rows in (reference_rows(), pseudonymised_rows()):
        dataset = Dataset(rows)
        level = dataset.exposure
        source = FileSource(dataset.save(tmp_path / "d.json"))
        assert source.fetch(exposure=level) == dataset.to_dict()
        assert Dataset(source.fetch(exposure=level)).fingerprint() == dataset.fingerprint()


def test_a_file_source_serves_the_aggregated_level_of_a_pseudonymised_file(
    tmp_path: Path,
) -> None:
    path = Dataset(pseudonymised_rows()).save(tmp_path / "d.json")
    fetched = FileSource(path).fetch(exposure=AGGREGATED)
    assert fetched == at_exposure(pseudonymised_rows(), AGGREGATED)
    assert Dataset(fetched).exposure is AGGREGATED


def test_a_file_source_describes_its_file(tmp_path: Path) -> None:
    source = FileSource(str(tmp_path / "consultation.json"))
    assert source.path == tmp_path / "consultation.json"
    assert source.describe() == "file consultation.json"
    assert repr(source) == "FileSource('file consultation.json')"
    assert FileSource.name == "file"
    assert MemorySource.name == "memory"
    assert MemorySource(reference_rows()).describe() == "memory"


def test_a_missing_file_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="There is no dataset file at"):
        FileSource(tmp_path / "missing.json").fetch(exposure=AGGREGATED)


@pytest.mark.parametrize(
    ("content", "message"),
    [("not json", "it is not JSON"), ("[1, 2]", "it holds a JSON list")],
    ids=["not-json", "list"],
)
def test_an_unreadable_file_is_refused(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError, match=message):
        FileSource(path).fetch(exposure=AGGREGATED)


def test_an_aggregated_file_is_not_served_pseudonymised(tmp_path: Path) -> None:
    path = Dataset(reference_rows()).save(tmp_path / "d.json")
    with pytest.raises(ExposureError):
        FileSource(path).fetch(exposure=PSEUDONYMISED)


class SpreadsheetSource(Source):
    """A source written outside the package, in ten lines."""

    name = "spreadsheet"

    def __init__(self, rows: dict[str, Any]) -> None:
        self.rows = rows

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        return at_exposure(self.rows, exposure)

    def describe(self) -> str:
        return "spreadsheet budget.ods"


def test_a_source_written_outside_the_package_works_with_a_dataset() -> None:
    source = SpreadsheetSource(pseudonymised_rows())
    dataset = Dataset(source.fetch(exposure=AGGREGATED), source=source.describe())
    assert dataset.source == "spreadsheet budget.ods"
    assert dataset.project().slug == "budget-2027"
    assert repr(source) == "SpreadsheetSource('spreadsheet budget.ods')"


def test_a_source_without_its_own_description_gives_its_name() -> None:
    class Bare(Source):
        name = "bare"

        def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
            return reference_rows()

    assert Bare().describe() == "bare"


def test_the_abstract_source_cannot_be_built() -> None:
    with pytest.raises(TypeError, match="abstract"):
        Source()  # type: ignore[abstract]


@pytest.mark.parametrize("level", ["secret", None, 1])
def test_an_unknown_level_is_refused(level: Any) -> None:
    with pytest.raises(ValidationError, match="The level asked for is 'aggregated'"):
        at_exposure(reference_rows(), level)


def test_a_level_given_as_a_string_is_read() -> None:
    assert at_exposure(reference_rows(), "aggregated")["exposure"] == "aggregated"  # type: ignore[arg-type]


@pytest.mark.parametrize("held", ["secret", None])
def test_rows_without_a_valid_level_are_refused(held: Any) -> None:
    rows = reference_rows()
    rows["exposure"] = held
    with pytest.raises(ValidationError, match=r"The level of the rows \('exposure'\)"):
        at_exposure(rows, AGGREGATED)


@pytest.mark.parametrize("rows", [[], "rows", None])
def test_rows_that_are_not_a_dictionary_are_refused(rows: Any) -> None:
    with pytest.raises(ValidationError, match="dictionary of sections"):
        at_exposure(rows, AGGREGATED)
    with pytest.raises(ValidationError, match="dictionary of sections"):
        MemorySource(rows)


@pytest.mark.parametrize(
    ("vote", "message"),
    [
        ({"actant": "m-001", "revision_id": "p-01.r1", "score": 3}, "has the score 3"),
        ({"actant": "m-001", "revision_id": "p-01.r1", "score": 1.0}, "has the score 1.0"),
        ({"actant": "m-001", "revision_id": "p-01.r1", "score": True}, "has the score True"),
        ({"actant": "m-001", "score": 1}, "no valid 'revision_id'"),
        ("m-001", "no valid 'revision_id'"),
    ],
    ids=["out-of-range", "float", "bool", "no-revision", "not-a-row"],
)
def test_a_vote_that_cannot_be_counted_is_refused(vote: Any, message: str) -> None:
    rows = pseudonymised_rows()
    rows["votes"].append(vote)
    with pytest.raises(ValidationError, match=message):
        at_exposure(rows, AGGREGATED)


def test_sections_that_are_not_lists_are_refused() -> None:
    rows = pseudonymised_rows()
    rows["votes"] = {}
    with pytest.raises(ValidationError, match="The section 'votes' is a list"):
        at_exposure(rows, AGGREGATED)
    rows = pseudonymised_rows()
    rows["vote_counts"] = {}
    with pytest.raises(ValidationError, match="The section 'vote_counts' is a list"):
        at_exposure(rows, AGGREGATED)
