# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The values that the Articles model deprecated: read without failing, marked, never made.

An old dataset can hold the status DRAFT, the types CREATE and REMOVE, the pending changes
PENDING_CREATE and PENDING_REMOVE, the kind SYNC and the traces of forks (DY116, DY118,
DY132, DY160, DY176). The rows are synthetic.
"""

import dataclasses
import json
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from civiqhub import values
from civiqhub.dataset import Dataset
from civiqhub.entities import Amendment, Proposal
from civiqhub.errors import ValidationError
from civiqhub.sources import at_exposure
from civiqhub.synthetic import make_rows
from civiqhub.values import AmendmentStatus, DeprecatedValue, Exposure
from support import (
    OLD_MARKS,
    article_rows,
    citation_rows,
    old_rows,
    paragraph_rows,
    pseudonymised_rows,
    reference_rows,
)

# The deprecated values, in lower case, and the keys that only a fork or an uplink filled.
DEPRECATED = {"draft", "create", "remove", "pending_create", "pending_remove", "sync"}
FORK_KEYS = {"parent_project_id", "parent_root_id", "originating_project_id"}


@pytest.fixture
def old() -> Dataset:
    return Dataset(old_rows())


def marks(items: Any) -> list[tuple[str, int, str, str, str]]:
    return [(m.section, m.index, m.row_id, m.key, m.value) for m in items]


def amendment_row(rows: dict[str, Any], id: str) -> dict[str, Any]:
    return next(row for row in rows["amendments"] if row["id"] == id)


# Criterion 1: an old dataset loads without error.


def test_an_old_dataset_loads_without_error(old: Dataset) -> None:
    project = old.project()
    assert project.id == "budget-2027"
    assert old.proposals.ids == ("p-01", "p-02", "p-03", "p-04", "p-05", "p-06")
    assert project.amendments.ids == ("p-04", "p-05", "p-06")


@pytest.mark.parametrize("status", ["DRAFT", "draft", "Draft"])
def test_a_draft_amendment_is_read_as_open(status: str) -> None:
    rows = old_rows()
    amendment_row(rows, "am-05")["status"] = status
    p05 = Dataset(rows).proposals["p-05"]
    assert isinstance(p05, Amendment)
    assert p05.status is AmendmentStatus.OPEN
    assert not p05.is_adopted


def test_a_cascade_of_kind_sync_stays_an_amendment(old: Dataset) -> None:
    p04 = old.proposals["p-04"]
    assert isinstance(p04, Amendment)
    assert p04.is_adopted
    assert old.revisions["p-01.r2"].amendment is p04


def test_a_creation_a_removal_or_a_pending_change_builds_no_amendment(old: Dataset) -> None:
    for id in ("p-01", "p-02", "p-03"):
        proposal = old.proposals[id]
        assert type(proposal) is Proposal
        assert not proposal.is_amendment
    assert old.proposals["p-02"].amendments.ids == ()


def test_a_revision_produced_by_a_removal_has_no_amendment(old: Dataset) -> None:
    revision = old.revisions["p-02.r2"]
    assert revision.amendment_id == "am-07"
    assert revision.amendment is None


def test_a_proposal_may_have_several_pending_changes() -> None:
    rows = old_rows()
    rows["amendments"].append(
        {"id": "pc-3", "proposal_id": "p-02", "item_type": "pending_remove", "status": "open"}
    )
    assert len(Dataset(rows).proposals["p-02"].deprecated) == 4


def test_the_rules_of_a_local_change_still_hold() -> None:
    rows = old_rows()
    amendment_row(rows, "am-05")["adopted_revision_id"] = "p-01.r2"
    with pytest.raises(ValidationError, match=r"amendments\[1\] \(id 'am-05'\) has an adopted"):
        Dataset(rows)
    rows = old_rows()
    rows["revisions"][3]["amendment_id"] = "am-99"
    with pytest.raises(ValidationError, match="no row of the section 'amendments' has this id"):
        Dataset(rows)
    rows = old_rows()
    rows["amendments"].append({"id": "pc-1", "proposal_id": "p-06", "type": "CREATE"})
    with pytest.raises(ValidationError, match="have the same id 'pc-1'"):
        Dataset(rows)


def test_an_old_dataset_comes_back_from_a_file(old: Dataset, tmp_path: Path) -> None:
    reopened = Dataset.from_file(old.save(tmp_path / "old.json"))
    assert reopened.fingerprint() == old.fingerprint()
    assert marks(reopened.deprecated) == list(OLD_MARKS)


# Criterion 2: each deprecated value read is marked.


def test_each_deprecated_value_is_marked(old: Dataset) -> None:
    assert isinstance(old.deprecated, tuple)
    assert all(type(mark) is DeprecatedValue for mark in old.deprecated)
    assert marks(old.deprecated) == list(OLD_MARKS)


def test_the_project_and_the_proposals_carry_their_marks(old: Dataset) -> None:
    assert marks(old.project().deprecated) == [OLD_MARKS[0]]
    assert marks(old.proposals["p-03"].deprecated) == [OLD_MARKS[1], OLD_MARKS[11]]
    assert marks(old.proposals["p-04"].deprecated) == [OLD_MARKS[2], OLD_MARKS[3]]
    assert marks(old.proposals["p-05"].deprecated) == [OLD_MARKS[4]]
    assert marks(old.proposals["p-02"].deprecated) == list(OLD_MARKS[5:8])
    assert marks(old.proposals["p-01"].deprecated) == list(OLD_MARKS[8:11])
    assert old.proposals["p-06"].deprecated == ()


def test_a_mark_reads_as_a_sentence_and_cannot_be_changed(old: Dataset) -> None:
    mark = old.deprecated[4]
    assert str(mark) == "amendments[1] (id 'am-05'): the status 'DRAFT' is deprecated"
    assert mark == DeprecatedValue(
        section="amendments", index=1, row_id="am-05", key="status", value="DRAFT"
    )
    assert len({mark, old.deprecated[4]}) == 1
    with pytest.raises(dataclasses.FrozenInstanceError):
        mark.value = "OPEN"  # type: ignore[misc]


def test_a_value_is_marked_in_any_case_as_the_row_gives_it() -> None:
    rows = old_rows()
    amendment_row(rows, "am-04")["kind"] = "Sync"
    amendment_row(rows, "pc-1")["item_type"] = "pending_create"
    found = marks(Dataset(rows).deprecated)
    assert ("amendments", 0, "am-04", "kind", "Sync") in found
    assert ("amendments", 3, "pc-1", "item_type", "pending_create") in found


def test_a_value_of_the_current_model_is_not_marked() -> None:
    rows = reference_rows()
    amendment_row(rows, "am-04").update(
        type="UPDATE", item_type="PROPOSAL_AMENDMENT", kind="USER", status="adopted"
    )
    rows["projects"][0]["parent_project_id"] = None
    rows["proposals"][0]["parent_root_id"] = ""
    dataset = Dataset(rows)
    assert dataset.deprecated == ()
    assert isinstance(dataset.proposals["p-04"], Amendment)


@pytest.mark.parametrize(
    "rows", [reference_rows, pseudonymised_rows, citation_rows, paragraph_rows]
)
def test_a_dataset_of_the_current_model_has_no_mark(rows: Any) -> None:
    assert Dataset(rows()).deprecated == ()


def test_draft_stays_a_state_of_an_article() -> None:
    rows = article_rows()
    rows["articles"][0]["state"] = "DRAFT"
    rows["articles"][0]["status"] = "DRAFT"
    rows["article_versions"][0]["status"] = "DRAFT"
    assert Dataset(rows).deprecated == ()


def test_an_amendment_still_has_no_type(old: Dataset) -> None:
    p04 = old.proposals["p-04"]
    for name in ("type", "item_type", "change_type", "kind", "originating_project_id"):
        assert not hasattr(p04, name)


# Criterion 3: civiqhub-py produces none of these values.


def strings(node: Any) -> Iterator[tuple[str | None, str]]:
    """Yield every (key, string) of a JSON value, with None as the key of a list item."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                yield key, value
            else:
                yield from strings(value)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                yield None, item
            else:
                yield from strings(item)


def deprecated_in(rows: Any) -> list[tuple[str | None, str]]:
    text = json.dumps(rows)
    found = [
        (key, value)
        for key, value in strings(json.loads(text))
        if value.lower() in DEPRECATED or key in FORK_KEYS
    ]
    return sorted(found, key=str)


def test_no_value_of_the_sdk_is_deprecated() -> None:
    for name in values.__all__:
        member = getattr(values, name)
        if isinstance(member, type) and issubclass(member, Enum):
            for choice in member:
                assert choice.name.lower() not in DEPRECATED, choice
                assert str(choice.value).lower() not in DEPRECATED, choice
    assert [status.name for status in AmendmentStatus] == ["OPEN", "ADOPTED", "REJECTED"]


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("impressions", [False, True])
def test_the_synthetic_rows_hold_no_deprecated_value(seed: int, impressions: bool) -> None:
    rows = make_rows(seed=seed, impressions=impressions)
    assert deprecated_in(rows) == []
    assert deprecated_in(at_exposure(rows, Exposure.AGGREGATED)) == []
    dataset = Dataset(rows)
    assert dataset.deprecated == ()
    assert deprecated_in(dataset.to_dict()) == []


def test_an_old_dataset_gives_back_what_it_read_and_adds_nothing(old: Dataset) -> None:
    read = old_rows()
    assert old.to_dict() == read
    assert deprecated_in(old.to_dict()) == deprecated_in(read)
    assert deprecated_in(at_exposure(read, Exposure.AGGREGATED)) == deprecated_in(read)
