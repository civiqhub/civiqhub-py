# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Actant: anyone who acts in a Project, known by a pseudonym only."""

from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Actant, Agent, Member
from civiqhub.errors import ExposureError, ValidationError
from civiqhub.values import ActantKind, Role, VoteState
from support import IMPRESSIONS, pseudonymised_rows, reference_rows


def pseudonymised(*, impressions: bool = True) -> Dataset:
    """Return a new dataset built from the pseudonymised reference rows."""
    return Dataset(pseudonymised_rows(impressions=impressions))


def actant_row(rows: dict[str, Any], pseudonym: str) -> dict[str, Any]:
    """Return the row of the actant with this pseudonym."""
    row: dict[str, Any] = next(row for row in rows["actants"] if row["pseudonym"] == pseudonym)
    return row


def test_the_actants_are_exported_by_the_package() -> None:
    assert (civiqhub.Actant, civiqhub.Member, civiqhub.Agent) == (Actant, Member, Agent)
    assert {"Actant", "Agent", "Member"} <= set(civiqhub.__all__)


def test_the_class_of_an_actant_follows_its_kind() -> None:
    actants = pseudonymised().actants
    assert isinstance(actants["m-001"], Member)
    assert isinstance(actants["g-001"], Agent)
    assert isinstance(actants["g-001"], Actant)
    assert actants["m-001"].pseudonym == "m-001"
    assert actants["m-001"].kind is ActantKind.HUMAN
    assert actants["g-001"].kind is ActantKind.AGENT
    assert actants.ids == ("m-001", "m-002", "m-003", "g-001")


def test_an_actant_of_another_kind_is_a_plain_actant() -> None:
    rows = pseudonymised_rows()
    actant_row(rows, "m-003")["kind"] = "Other"
    actant = Dataset(rows).actants["m-003"]
    assert type(actant) is Actant
    assert actant.kind is ActantKind.OTHER


def test_an_actant_without_kind_is_a_member() -> None:
    rows = pseudonymised_rows()
    del actant_row(rows, "m-003")["kind"]
    assert type(Dataset(rows).actants["m-003"]) is Member


def test_the_role_is_read_from_its_name_in_any_case() -> None:
    actants = pseudonymised().actants
    assert actants["m-001"].role is Role.PARTICIPANT
    assert actants["m-002"].role is Role.MODERATOR
    assert actants["m-003"].role is None


def test_an_actant_knows_its_votes_and_its_arguments() -> None:
    dataset = pseudonymised()
    m001, m002 = dataset.actants["m-001"], dataset.actants["m-002"]
    assert len(m001.votes) == 6
    assert all(vote.actant is m001 for vote in m001.votes)
    assert m002.arguments.ids == ("arg-1",)
    assert dataset.actants["m-003"].arguments.ids == ()


def test_the_vote_on_a_proposal_is_the_vote_on_its_current_revision() -> None:
    dataset = pseudonymised()
    p01 = dataset.proposals["p-01"]
    m001, m003 = dataset.actants["m-001"], dataset.actants["m-003"]
    vote = m001.vote_on(p01)
    assert vote is not None
    assert vote.revision is p01.current_revision
    assert m003.vote_on(p01) is None
    old = m003.vote_on(p01.revisions[0])
    assert old is not None
    assert old.score == -1


def test_the_four_vote_states() -> None:
    dataset = pseudonymised()
    m001, m003 = dataset.actants["m-001"], dataset.actants["m-003"]
    p01, p03 = dataset.proposals["p-01"], dataset.proposals["p-03"]
    assert m001.vote_state_on(p01) is VoteState.VOTED
    assert m003.vote_state_on(p01) is VoteState.ABSTAINED
    assert m003.vote_state_on(p03) is VoteState.NOT_SHOWN
    assert m001.vote_state_on(dataset.revisions["p-02.r1"]) is VoteState.VOTED
    blind = pseudonymised(impressions=False)
    assert blind.has_impressions is False
    assert blind.actants["m-003"].vote_state_on(blind.proposals["p-01"]) is VoteState.UNKNOWN
    assert blind.actants["m-001"].vote_state_on(blind.proposals["p-01"]) is VoteState.VOTED


def test_a_vote_counts_as_shown_even_when_not_listed() -> None:
    dataset = pseudonymised()
    g001 = dataset.actants["g-001"]
    assert ("g-001", "p-01.r2") not in IMPRESSIONS
    assert g001.vote_state_on(dataset.proposals["p-01"]) is VoteState.VOTED


def test_impressions_are_recorded_even_when_empty() -> None:
    rows = pseudonymised_rows()
    rows["impressions"] = []
    dataset = Dataset(rows)
    assert dataset.has_impressions is True
    assert dataset.actants["m-003"].vote_state_on(dataset.proposals["p-01"]) is (
        VoteState.NOT_SHOWN
    )


def test_the_authors_are_actants() -> None:
    dataset = pseudonymised()
    assert dataset.proposals["p-01"].author is dataset.actants["m-001"]
    assert dataset.proposals["p-02"].author is None
    assert dataset.arguments["arg-4"].author is dataset.actants["g-001"]
    assert dataset.arguments["arg-2"].author is None


def test_an_actant_is_valid_in_its_dataset_only() -> None:
    first, second = pseudonymised(), pseudonymised()
    assert first.actants["m-001"] != second.actants["m-001"]
    assert first.actants["m-001"] == first.actants["m-001"]


def test_project_actants_are_those_of_the_dataset() -> None:
    dataset = pseudonymised()
    assert dataset.project().actants == dataset.actants


@pytest.mark.parametrize(
    "read",
    [
        lambda d: d.project().actants,
        lambda d: d.project().votes,
        lambda d: d.revisions["p-01.r2"].votes,
        lambda d: d.proposals["p-01"].votes,
        lambda d: d.proposals["p-01"].author,
        lambda d: d.arguments["arg-1"].author,
    ],
    ids=[
        "project.actants",
        "project.votes",
        "revision.votes",
        "proposal.votes",
        "proposal.author",
        "argument.author",
    ],
)
def test_an_aggregated_dataset_refuses_the_individual_reads(read: Any) -> None:
    dataset = Dataset(reference_rows())
    with pytest.raises(ExposureError, match="needs individual votes") as caught:
        read(dataset)
    assert "pseudonymised" in caught.value.hint


def test_an_aggregated_dataset_still_gives_vote_counts() -> None:
    dataset = Dataset(reference_rows())
    assert dataset.revisions["p-01.r2"].vote_counts.total == 3
    assert dataset.actants.ids == ()
    assert dataset.votes.ids == ()
    assert dataset.has_impressions is False


# Each invariant raises ValidationError, and the message names the faulty row.


def test_a_pseudonym_appears_once() -> None:
    rows = pseudonymised_rows()
    rows["actants"].append({"pseudonym": "m-002"})
    with pytest.raises(ValidationError, match=r"actants\[1\] and actants\[4\].*'m-002'"):
        Dataset(rows)


@pytest.mark.parametrize("key", ["name", "email", "handle", "user_id"])
def test_an_actant_carries_no_personal_data(key: str) -> None:
    rows = pseudonymised_rows()
    actant_row(rows, "m-001")[key] = "not-a-real-value"
    with pytest.raises(ValidationError, match=rf"'m-001'\) has the key '{key}'.*personal data"):
        Dataset(rows)


@pytest.mark.parametrize(("key", "value"), [("kind", "robot"), ("role", "owner"), ("role", 3)])
def test_kind_and_role_are_known_values(key: str, value: object) -> None:
    rows = pseudonymised_rows()
    actant_row(rows, "m-003")[key] = value
    with pytest.raises(ValidationError, match=rf"\(pseudonym 'm-003'\) has the {key}"):
        Dataset(rows)


def test_an_author_is_a_known_actant() -> None:
    rows = pseudonymised_rows()
    rows["proposals"][1]["author_id"] = "m-999"
    with pytest.raises(ValidationError, match=r"proposal 'p-02' has the author_id 'm-999'"):
        Dataset(rows)


@pytest.mark.parametrize(("key", "value"), [("actant", "m-999"), ("revision_id", "p-99.r1")])
def test_an_impression_names_a_known_actant_and_revision(key: str, value: str) -> None:
    rows = pseudonymised_rows()
    rows["impressions"][0][key] = value
    with pytest.raises(ValidationError, match=rf"impressions\[0\] has the {key} '{value}'"):
        Dataset(rows)
