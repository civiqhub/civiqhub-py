# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Amendment: a Proposal that amends another one, built from hand-written rows."""

from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Amendment, Proposal
from civiqhub.errors import ValidationError
from civiqhub.values import AmendmentStatus, VoteCounts
from support import PARTICIPATION, reference_rows


def reference() -> Dataset:
    """Return a new dataset built from the reference rows."""
    return Dataset(reference_rows())


def amendment_row(rows: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    """Return the row of the section amendments for this proposal."""
    row: dict[str, Any] = next(
        row for row in rows["amendments"] if row["proposal_id"] == proposal_id
    )
    return row


def test_amendment_is_exported_by_the_package() -> None:
    assert civiqhub.Amendment is Amendment
    assert "Amendment" in civiqhub.__all__


def test_an_amendment_is_a_proposal_kept_apart_from_the_proposals_of_the_project() -> None:
    dataset = reference()
    project = dataset.project()
    p04 = dataset.proposals["p-04"]
    assert isinstance(p04, Amendment)
    assert isinstance(p04, Proposal)
    assert p04.is_amendment is True
    assert dataset.proposals["p-01"].is_amendment is False
    assert project.proposals.ids == ("p-01", "p-02", "p-03")
    assert project.amendments.ids == ("p-04", "p-05", "p-06")
    assert len(dataset.proposals) == 6


def test_an_adopted_amendment_produced_the_current_revision_of_its_target() -> None:
    dataset = reference()
    p01, p04 = dataset.proposals["p-01"], dataset.proposals["p-04"]
    assert isinstance(p04, Amendment)
    assert p04.target is p01
    assert p04.target_revision is p01.revisions[0]
    assert p04.is_adopted
    assert p04.status is AmendmentStatus.ADOPTED
    assert p04.adopted_revision is p01.current_revision
    assert p01.current_revision.amendment is p04
    assert p01.revisions[0].amendment is None
    assert p04.amendment_id == "am-04"


def test_an_open_amendment_has_no_adopted_revision() -> None:
    p05 = reference().proposals["p-05"]
    assert isinstance(p05, Amendment)
    assert p05.status is AmendmentStatus.OPEN
    assert not p05.is_adopted
    assert p05.adopted_revision is None
    assert p05.is_stale is False


def test_the_amendments_form_a_tree_walked_depth_first() -> None:
    dataset = reference()
    p01, p06 = dataset.proposals["p-01"], dataset.proposals["p-06"]
    walked = [(depth, proposal.id) for depth, proposal in p01.walk_amendments()]
    assert walked == [(0, "p-01"), (1, "p-04"), (1, "p-05"), (2, "p-06")]
    assert p01.amendments.ids == ("p-04", "p-05")
    assert isinstance(p06, Amendment)
    assert p06.root is p01
    assert p06.target is dataset.proposals["p-05"]
    assert p06.is_stale is True
    assert [(depth, p.id) for depth, p in dataset.proposals["p-02"].walk_amendments()] == [
        (0, "p-02")
    ]


def test_an_amendment_has_its_own_revisions_and_vote_counts() -> None:
    p04 = reference().proposals["p-04"]
    assert p04.revisions.ids == ("p-04.r1",)
    assert p04.text == "Raise the number of trees to 150."
    assert p04.vote_counts == VoteCounts((0, 0, 0, 1, 2))


def test_an_amendment_has_no_type() -> None:
    p04 = reference().proposals["p-04"]
    for name in ("type", "item_type", "kind"):
        assert not hasattr(p04, name)
    rows = reference_rows()
    amendment_row(rows, "p-04")["type"] = "UPDATE"
    assert isinstance(Dataset(rows).proposals["p-04"], Amendment)


# The deprecated status DRAFT is read and marked: see tests/test_deprecated.py.
@pytest.mark.parametrize("status", ["pending", "closed", "", 1])
def test_an_unknown_status_is_refused(status: object) -> None:
    rows = reference_rows()
    amendment_row(rows, "p-05")["status"] = status
    with pytest.raises(ValidationError, match=r"amendments\[1\] \(id 'am-05'\) has the status"):
        Dataset(rows)


def test_a_status_is_read_in_any_case_and_defaults_to_open() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-04")["status"] = "Adopted"
    del amendment_row(rows, "p-06")["status"]
    dataset = Dataset(rows)
    assert dataset.proposals["p-04"].is_adopted  # type: ignore[attr-defined]
    p06 = dataset.proposals["p-06"]
    assert isinstance(p06, Amendment)
    assert p06.status is AmendmentStatus.OPEN


def test_repr_of_an_amendment() -> None:
    assert repr(reference().proposals["p-04"]) == (
        "Amendment('p-04', 'Raise the number of trees to 150.')"
    )


# One test per invariant; each message names the faulty id.


def test_an_amendment_of_an_unknown_proposal_is_refused() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-06")["proposal_id"] = "p-99"
    with pytest.raises(ValidationError, match=r"amendments\[2\] has the proposal_id 'p-99'"):
        Dataset(rows)


def test_an_unknown_target_is_refused() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-05")["target_proposal_id"] = "p-99"
    with pytest.raises(ValidationError, match=r"\(id 'am-05'\) has the target_proposal_id 'p-99'"):
        Dataset(rows)


@pytest.mark.parametrize("revision", ["p-02.r1", "p-99.r1"])
def test_the_target_revision_is_a_revision_of_the_target(revision: str) -> None:
    rows = reference_rows()
    amendment_row(rows, "p-05")["target_revision_id"] = revision
    expected = rf"\(id 'am-05'\) has the target_revision_id '{revision}', which is not"
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


def test_the_adopted_revision_is_a_revision_of_the_target() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-04")["adopted_revision_id"] = "p-02.r2"
    with pytest.raises(ValidationError, match=r"\(id 'am-04'\) has the adopted_revision_id"):
        Dataset(rows)


def test_only_an_adopted_amendment_has_an_adopted_revision() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-04")["status"] = "rejected"
    with pytest.raises(ValidationError, match=r"\(id 'am-04'\) has an adopted_revision_id"):
        Dataset(rows)


def test_an_amendment_does_not_target_itself() -> None:
    rows = reference_rows()
    row = amendment_row(rows, "p-06")
    row.update({"target_proposal_id": "p-06", "target_revision_id": "p-06.r1"})
    with pytest.raises(ValidationError, match=r"makes the proposal 'p-06' target itself"):
        Dataset(rows)


def test_a_cycle_of_amendments_is_refused() -> None:
    rows = reference_rows()
    row = amendment_row(rows, "p-05")
    row.update({"target_proposal_id": "p-06", "target_revision_id": "p-06.r1"})
    expected = r"amendment 'p-05' \(amendments\[1\]\) targets itself through p-05 -> p-06 -> p-05"
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


def test_an_amendment_and_its_target_share_a_project() -> None:
    rows = reference_rows()
    rows["projects"].append({"id": "parks", "slug": "parks-2027"})
    rows["participation"].append({**PARTICIPATION, "project_id": "parks"})
    next(row for row in rows["proposals"] if row["id"] == "p-06")["project_id"] = "parks"
    with pytest.raises(ValidationError, match=r"\(id 'am-06'\) targets the proposal 'p-05'"):
        Dataset(rows)


def test_a_proposal_has_one_row_of_amendment_at_most() -> None:
    rows = reference_rows()
    rows["amendments"].append({**amendment_row(rows, "p-05"), "id": "am-07"})
    with pytest.raises(ValidationError, match=r"amendments\[1\] and amendments\[3\].*'p-05'"):
        Dataset(rows)


def test_an_amendment_row_has_its_own_id() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-06")["id"] = "am-05"
    with pytest.raises(
        ValidationError, match=r"amendments\[1\] and amendments\[2\] have the same id"
    ):
        Dataset(rows)


def test_a_revision_names_a_known_amendment() -> None:
    rows = reference_rows()
    next(row for row in rows["revisions"] if row["id"] == "p-01.r2")["amendment_id"] = "am-99"
    with pytest.raises(ValidationError, match=r"revision 'p-01.r2' has the amendment_id 'am-99'"):
        Dataset(rows)


def test_stale_is_true_or_false() -> None:
    rows = reference_rows()
    amendment_row(rows, "p-06")["stale"] = "yes"
    with pytest.raises(ValidationError, match=r"\(id 'am-06'\) has a 'stale' that is not true"):
        Dataset(rows)
