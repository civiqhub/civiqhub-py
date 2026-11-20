# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Vote: the vote of one Actant on one Revision, at the pseudonymised level only."""

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Vote
from civiqhub.errors import ValidationError
from civiqhub.values import VoteCounts
from support import VOTE_COUNTS, VOTES, pseudonymised_rows


def pseudonymised() -> Dataset:
    """Return a new dataset built from the pseudonymised reference rows."""
    return Dataset(pseudonymised_rows())


def test_vote_is_exported_by_the_package() -> None:
    assert civiqhub.Vote is Vote
    assert "Vote" in civiqhub.__all__


def test_a_vote_links_its_actant_its_revision_and_its_proposal() -> None:
    dataset = pseudonymised()
    assert len(dataset.votes) == len(VOTES)
    for vote in dataset.votes:
        assert vote in vote.actant.votes
        assert vote in vote.revision.votes
        assert vote.proposal is vote.revision.proposal


def test_the_id_the_record_and_the_repr_of_a_vote() -> None:
    dataset = pseudonymised()
    vote = dataset.votes["m-001@p-01.r2"]
    assert vote.to_record() == ("m-001", "p-01.r2", 2)
    assert vote.cast_at == "2026-11-16T09:00:00Z"
    assert repr(vote) == "Vote('m-001@p-01.r2', '+2')"
    assert repr(dataset.votes["m-002@p-01.r2"]) == "Vote('m-002@p-01.r2', '-2')"
    assert repr(dataset.votes["m-001@p-02.r1"]) == "Vote('m-001@p-02.r1', '0')"


def test_the_votes_of_a_proposal_are_those_of_its_current_revision() -> None:
    p01 = pseudonymised().proposals["p-01"]
    assert p01.votes == p01.current_revision.votes
    assert p01.votes.ids == ("m-001@p-01.r2", "m-002@p-01.r2", "g-001@p-01.r2")


def test_the_votes_of_a_project_are_on_its_revisions_amendments_included() -> None:
    dataset = pseudonymised()
    assert set(dataset.project().votes.ids) == set(dataset.votes.ids)
    assert "g-001@p-06.r1" in dataset.project().votes.ids


def test_the_counts_from_the_votes_equal_the_vote_counts() -> None:
    dataset = pseudonymised()
    for revision in dataset.revisions:
        counted = VoteCounts.from_scores(vote.score for vote in revision.votes)
        assert revision.vote_counts == counted
        expected = VOTE_COUNTS.get(revision.id, [0, 0, 0, 0, 0])
        assert revision.vote_counts == VoteCounts(tuple(expected))  # type: ignore[arg-type]


def test_a_revision_without_a_row_of_counts_takes_the_counts_of_its_votes() -> None:
    rows = pseudonymised_rows()
    rows["vote_counts"] = [row for row in rows["vote_counts"] if row["revision_id"] != "p-01.r2"]
    assert Dataset(rows).revisions["p-01.r2"].vote_counts == VoteCounts((1, 0, 0, 1, 1))


def test_counts_that_differ_from_the_votes_are_refused() -> None:
    rows = pseudonymised_rows()
    rows["vote_counts"][1]["counts"] = [0, 0, 0, 0, 3]
    with pytest.raises(ValidationError, match=r"revision 'p-01.r2' are .* its votes give"):
        Dataset(rows)


@pytest.mark.parametrize("score", [3, -3, True, 1.5, None, "2"])
def test_a_score_is_an_integer_from_minus_two_to_two(score: object) -> None:
    rows = pseudonymised_rows()
    rows["votes"][0]["score"] = score
    with pytest.raises(ValidationError, match=r"votes\[0\].*abstention is the absence of a vote"):
        Dataset(rows)


def test_an_actant_has_one_vote_per_revision() -> None:
    rows = pseudonymised_rows()
    rows["votes"].append({**rows["votes"][2], "score": 1})
    with pytest.raises(ValidationError, match=r"votes\[2\] and votes\[16\].*Keep the latest"):
        Dataset(rows)


@pytest.mark.parametrize(("key", "value"), [("actant", "m-999"), ("revision_id", "p-99.r1")])
def test_a_vote_names_a_known_actant_and_revision(key: str, value: str) -> None:
    rows = pseudonymised_rows()
    rows["votes"][0][key] = value
    with pytest.raises(ValidationError, match=rf"votes\[0\] has the {key} '{value}'"):
        Dataset(rows)
