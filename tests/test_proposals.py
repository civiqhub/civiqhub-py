# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Proposal, Revision and their vote counts, built from hand-written rows."""

from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Proposal, Revision
from civiqhub.errors import ValidationError
from civiqhub.values import VoteCounts
from support import PARTICIPATION, VOTE_COUNTS, reference_rows


def reference() -> Dataset:
    """Return a new dataset built from the reference rows."""
    return Dataset(reference_rows())


def revision_row(rows: dict[str, Any], id: str) -> dict[str, Any]:
    """Return the row of the revision with this id."""
    row: dict[str, Any] = next(row for row in rows["revisions"] if row["id"] == id)
    return row


def test_proposal_and_revision_are_exported_by_the_package() -> None:
    assert civiqhub.Proposal is Proposal
    assert civiqhub.Revision is Revision
    assert {"Proposal", "Revision"} <= set(civiqhub.__all__)


def test_a_proposal_has_its_revisions_in_order_and_one_is_current() -> None:
    project = reference().project()
    proposal = project.proposals["p-01"]
    assert [revision.number for revision in proposal.revisions] == [1, 2]
    assert proposal.revisions.ids == ("p-01.r1", "p-01.r2")
    assert proposal.current_revision.number == 2
    assert proposal.revisions[0].is_current is False
    assert proposal.revisions[1].is_current is True


def test_the_revisions_are_ordered_whatever_the_order_of_their_rows() -> None:
    rows = reference_rows()
    rows["revisions"].reverse()
    dataset = Dataset(rows)
    assert dataset.proposals["p-02"].revisions.ids == ("p-02.r1", "p-02.r2")
    assert dataset.revisions.ids[:4] == ("p-01.r1", "p-01.r2", "p-02.r1", "p-02.r2")


def test_the_vote_counts_of_a_proposal_are_those_of_its_current_revision() -> None:
    proposal = reference().proposals["p-01"]
    assert proposal.vote_counts == VoteCounts((1, 0, 1, 2, 2))
    assert proposal.vote_counts is proposal.current_revision.vote_counts
    total = sum(revision.vote_counts.total for revision in proposal.revisions)
    assert proposal.vote_counts.total != total


def test_a_revision_without_a_row_of_vote_counts_has_none() -> None:
    revision = reference().revisions["p-03.r1"]
    assert "p-03.r1" not in VOTE_COUNTS
    assert revision.vote_counts.total == 0
    assert revision.vote_counts == VoteCounts()


def test_without_a_current_revision_id_the_highest_number_is_current() -> None:
    proposal = reference().proposals["p-02"]
    assert proposal.current_revision_id is None
    assert proposal.current_revision.id == "p-02.r2"


def test_the_links_go_both_ways() -> None:
    dataset = reference()
    project = dataset.project()
    proposal = dataset.proposals["p-01"]
    for revision in dataset.revisions:
        assert revision.proposal.project is project
        assert revision in revision.proposal.revisions
    assert proposal.project is project
    assert proposal in project.proposals
    assert proposal.text == "Plant 150 trees in the parks."
    assert proposal.text == proposal.current_revision.affirmation


def test_a_project_holds_the_revisions_of_its_proposals_and_no_other() -> None:
    rows = reference_rows()
    rows["projects"].append({"id": "parks", "slug": "parks-2027", "group_id": "g-1"})
    rows["participation"].append({**PARTICIPATION, "project_id": "parks"})
    rows["proposals"].append({"id": "q-01", "project_id": "parks"})
    rows["revisions"].append({"id": "q-01.r1", "proposal_id": "q-01", "affirmation": "Benches."})
    dataset = Dataset(rows)
    budget, parks = dataset.projects
    expected = {
        r.id for p in dataset.proposals if p.project_id == "budget-2027" for r in p.revisions
    }
    assert set(budget.revisions.ids) == expected
    assert len(budget.revisions) == 7
    assert parks.revisions.ids == ("q-01.r1",)
    assert parks.proposals.ids == ("q-01",)
    assert "q-01" not in budget.proposals.ids


def test_an_aggregated_dataset_holds_no_author() -> None:
    dataset = reference()
    assert all(proposal.author_id is None for proposal in dataset.proposals)
    rows = reference_rows()
    rows["proposals"][0]["author_id"] = "ps-ana"
    with pytest.raises(ValidationError, match=r"proposals\[0\] \(id 'p-01'\) has an author_id"):
        Dataset(rows)


def test_a_pseudonymised_dataset_keeps_the_author() -> None:
    rows = reference_rows()
    rows["exposure"] = "pseudonymised"
    rows["proposals"][0]["author_id"] = "ps-ana"
    assert Dataset(rows).proposals["p-01"].author_id == "ps-ana"


def test_the_article_id_is_kept_as_given_or_none() -> None:
    dataset = reference()
    assert dataset.proposals["p-01"].article_id == "art-1"
    assert dataset.proposals["p-03"].article_id is None


def test_repr_of_a_proposal_and_a_revision() -> None:
    dataset = reference()
    assert repr(dataset.proposals["p-01"]) == "Proposal('p-01', 'Plant 150 trees in the parks.')"
    assert repr(dataset.revisions["p-01.r2"]) == "Revision('p-01.r2', 'r2')"
    rows = reference_rows()
    revision_row(rows, "p-03.r1")["affirmation"] = "x" * 80
    assert repr(Dataset(rows).proposals["p-03"]) == f"Proposal('p-03', '{'x' * 60}')"


def test_the_fields_of_a_revision_are_read() -> None:
    revision = reference().revisions["p-01.r2"]
    assert revision.amendment_id == "am-01"
    assert revision.description == ""
    assert revision.content_hash is None
    assert revision.created_at == "2026-11-16T09:00:00Z"


def test_a_revision_without_number_is_number_one() -> None:
    rows = reference_rows()
    del revision_row(rows, "p-03.r1")["number"]
    assert Dataset(rows).revisions["p-03.r1"].number == 1


# One test per invariant; each message names the faulty id.


def test_a_proposal_of_an_unknown_project_is_refused() -> None:
    rows = reference_rows()
    rows["proposals"][2]["project_id"] = "nowhere"
    with pytest.raises(ValidationError, match=r"proposals\[2\] \(id 'p-03'\).*'nowhere'"):
        Dataset(rows)


def test_a_revision_of_an_unknown_proposal_is_refused() -> None:
    rows = reference_rows()
    revision_row(rows, "p-03.r1")["proposal_id"] = "p-99"
    with pytest.raises(ValidationError, match=r"\(id 'p-03.r1'\) has the proposal_id 'p-99'"):
        Dataset(rows)


@pytest.mark.parametrize("current", ["p-02.r1", "p-99.r1"])
def test_a_current_revision_of_another_proposal_is_refused(current: str) -> None:
    rows = reference_rows()
    rows["proposals"][0]["current_revision_id"] = current
    with pytest.raises(ValidationError, match=rf"\(id 'p-01'\).*'{current}', which is not"):
        Dataset(rows)


@pytest.mark.parametrize("number", [0, -1, "2", True, 1.5])
def test_the_number_of_a_revision_is_a_positive_integer(number: object) -> None:
    rows = reference_rows()
    revision_row(rows, "p-03.r1")["number"] = number
    with pytest.raises(ValidationError, match=r"\(id 'p-03.r1'\) has the number"):
        Dataset(rows)


def test_two_revisions_of_a_proposal_have_different_numbers() -> None:
    rows = reference_rows()
    revision_row(rows, "p-01.r2")["number"] = 1
    with pytest.raises(ValidationError, match=r"both the revision number 1 of the proposal 'p-01'"):
        Dataset(rows)


def test_a_proposal_has_at_least_one_revision() -> None:
    rows = reference_rows()
    rows["revisions"] = [row for row in rows["revisions"] if row["proposal_id"] != "p-03"]
    with pytest.raises(
        ValidationError, match=r"proposal 'p-03' \(proposals\[2\]\) has no revision"
    ):
        Dataset(rows)


@pytest.mark.parametrize(
    "counts", [[1, 2, 3, 4], [0, 0, -1, 0, 0], "five", None, [0, 0, 1.0, 0, 0]]
)
def test_vote_counts_are_five_non_negative_integers(counts: object) -> None:
    rows = reference_rows()
    rows["vote_counts"][0]["counts"] = counts
    with pytest.raises(ValidationError, match=r"vote_counts\[0\] \(revision 'p-01.r1'\)"):
        Dataset(rows)


def test_vote_counts_are_for_a_known_revision() -> None:
    rows = reference_rows()
    rows["vote_counts"][1]["revision_id"] = "p-99.r1"
    with pytest.raises(ValidationError, match=r"vote_counts\[1\] has the revision_id 'p-99.r1'"):
        Dataset(rows)


def test_a_revision_has_one_row_of_vote_counts() -> None:
    rows = reference_rows()
    rows["vote_counts"].append({"revision_id": "p-01.r1", "counts": [0, 0, 0, 0, 1]})
    with pytest.raises(ValidationError, match=r"vote_counts\[0\] and vote_counts\[6\].*'p-01.r1'"):
        Dataset(rows)


@pytest.mark.parametrize("section", ["proposals", "revisions"])
def test_an_id_appears_once(section: str) -> None:
    rows = reference_rows()
    rows[section][1]["id"] = rows[section][0]["id"]
    with pytest.raises(
        ValidationError, match=rf"{section}\[0\] and {section}\[1\] have the same id"
    ):
        Dataset(rows)
