# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of a Project and the snapshot that holds them, on hand-written data."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from support import AS_OF, MEMBERS, VOTES, aggregated_payload, small_payload

from civiqhub.errors import ExposureError, NotFoundError, ValidationError
from civiqhub.model import (
    ActantKind,
    Agent,
    Amendment,
    AmendmentStatus,
    CellState,
    Exposure,
    Listing,
    Member,
    Position,
    Project,
    Proposal,
    Role,
    Snapshot,
    VoteTally,
)


@pytest.fixture
def snapshot() -> Snapshot:
    return Snapshot(small_payload())


@pytest.fixture
def project(snapshot: Snapshot) -> Project:
    return snapshot.project()


def test_navigation_follows_the_product_grammar(project: Project) -> None:
    proposal = project.proposals["p-1"]
    assert [r.number for r in proposal.revisions] == [1, 2]
    assert proposal.current.is_current
    assert not proposal.revisions[0].is_current
    assert proposal.text == "Synthetic proposal one, as amended"
    assert proposal.project == project
    assert project.group is not None
    assert project.group.projects == Listing([project])
    assert [g.slug for g in project.group.groups] == ["budget-circle"]
    assert project.group.groups[0].parent == project.group
    vote = proposal.votes[0]
    assert vote.revision == proposal.current
    assert vote.proposal == proposal
    assert vote in vote.member.votes
    assert vote.member.vote_on(proposal) == vote
    assert vote.to_record() == ("ps-ana", "p-1.r2", 2)
    assert all(v.revision_id == "p-1.r1" for v in proposal.revisions[0].votes)
    assert proposal.tally == VoteTally.of(v.score for v in proposal.votes)
    reply = proposal.arguments["arg-2"]
    assert reply.parent == proposal.arguments["arg-1"]
    assert reply.depth == 1
    assert reply in proposal.arguments["arg-1"].replies
    assert reply.position is Position.CON  # the wire value may be upper case
    assert reply.revision == proposal.current
    assert project.proposals["p-2"].arguments[0].revision is None
    assert len(project.arguments) == 3
    assert len(project.revisions) == 6
    assert len(project.votes) == len(VOTES)


def test_votes_stay_on_the_revision_they_were_cast_on(project: Project) -> None:
    proposal = project.proposals["p-1"]
    old, current = proposal.revisions
    assert dict(old.tally) == {-2: 0, -1: 1, 0: 0, 1: 1, 2: 0}
    assert dict(current.tally) == {-2: 1, -1: 0, 0: 0, 1: 1, 2: 1}
    assert proposal.tally == current.tally
    assert {v.member_id for v in old.votes} == {"ps-ana", "ps-ben"}


def test_an_amendment_is_a_proposal_that_targets_another(project: Project) -> None:
    adopted, pending, draft = project.amendments
    assert isinstance(adopted, Proposal)
    assert adopted.is_amendment
    assert adopted in project.proposals
    assert adopted.target == project.proposals["p-1"]
    assert adopted.target_revision.number == 1
    assert adopted.is_adopted
    assert adopted.adopted_revision == adopted.target.current
    assert adopted.adopted_revision is not None
    assert adopted.adopted_revision.from_amendment == adopted
    assert adopted.votes  # it receives votes like any proposal
    assert pending.status is AmendmentStatus.OPEN  # the default when the row gives none
    assert pending.adopted_revision is None
    assert not pending.is_stale
    assert draft.status is AmendmentStatus.DRAFT
    assert draft.is_stale
    assert draft.target == pending  # an amendment can itself be amended
    assert draft.root == project.proposals["p-2"]
    assert [(d, p.id) for d, p in adopted.target.walk()] == [(0, "p-1"), (1, "a-1")]
    assert [(d, p.id) for d, p in draft.root.walk()] == [(0, "p-2"), (1, "a-2"), (2, "a-3")]
    assert len(project.proposals.where(is_amendment=False)) == 2
    assert project.proposals["p-1"].amendments == Listing([adopted])
    assert project.proposals["p-1"].revisions[0].from_amendment is None


def test_a_vote_tally_is_a_mapping_over_the_five_scores() -> None:
    tally = VoteTally.of([2, 2, 1, -2])
    assert dict(tally) == {-2: 1, -1: 0, 0: 0, 1: 1, 2: 2}
    assert tally.total == 4
    assert tally.shares == (0.25, 0.0, 0.0, 0.25, 0.5)
    assert not hasattr(tally, "mean")  # no formula lives in the SDK
    assert not hasattr(tally, "entropy")
    assert (tally + tally)[2] == 4
    assert VoteTally().shares == (0.0, 0.0, 0.0, 0.0, 0.0)  # nobody voted: no division
    assert repr(tally) == "VoteTally(-2: 1  -1: 0  +0: 0  +1: 1  +2: 2)"
    with pytest.raises(KeyError, match="-2 to \\+2"):
        tally[3]


def test_a_listing_is_read_by_position_by_id_and_by_filter(project: Project) -> None:
    proposals = project.proposals
    assert proposals.ids == ("p-1", "p-2", "a-1", "a-2", "a-3")
    assert proposals[0] == proposals["p-1"]
    assert proposals[1:3].ids == ("p-2", "a-1")
    assert isinstance(proposals[1:3], Listing)
    assert proposals.get("nope") is None
    assert "p-2" in proposals
    assert proposals["p-2"] in proposals
    assert 3 not in proposals
    assert proposals.where(lambda p: p.tally.total > 2).ids == ("p-1",)
    assert proposals.where(lambda p: p.is_amendment, author_id="ps-ben").ids == ("a-1",)
    assert repr(project.snapshot.groups) == "[Group('demo-collective'), Group('budget-circle')]"
    assert repr(proposals).endswith(", ... 2 more]")
    with pytest.raises(NotFoundError, match="the first ids are: p-1, p-2") as missing:
        proposals["nope"]
    assert isinstance(missing.value, LookupError)


def test_objects_are_equal_by_kind_and_id_and_cannot_be_changed(project: Project) -> None:
    again = Snapshot(small_payload()).project()
    assert again == project
    assert again.proposals["p-1"] == project.proposals["p-1"]
    assert hash(again.proposals["p-1"]) == hash(project.proposals["p-1"])
    assert project.proposals["p-1"] != project.proposals["p-1"].current  # not the same kind
    assert len({*project.proposals, *again.proposals}) == 5
    with pytest.raises(dataclasses.FrozenInstanceError):
        project.proposals["p-1"].project_id = "other"  # type: ignore[misc]
    assert repr(project) == f"Project('demo-project', 5 proposals, as of {AS_OF})"
    assert repr(project.proposals["p-2"]) == "Proposal('p-2', 'Synthetic proposal two')"
    assert repr(project.proposals["a-1"]).startswith("Amendment('a-1', ")


def test_a_member_is_a_pseudonym_with_a_kind_and_a_role(project: Project) -> None:
    ana, ben, chloe, dan = project.members
    assert project.members.ids == MEMBERS
    assert isinstance(ana, Member)
    assert ana.kind is ActantKind.HUMAN
    assert ana.pseudonym == "ps-ana"
    assert isinstance(dan, Agent)
    assert dan.kind is ActantKind.AGENT
    assert ana.role is Role.PARTICIPANT
    assert ben.role is not None
    assert ben.role > ana.role  # the ladder of roles compares
    assert chloe.role is None
    assert chloe.kind is ActantKind.HUMAN  # the default
    assert [a.id for a in ana.arguments] == ["arg-1"]
    assert project.proposals["p-1"].author == ana
    assert project.proposals["p-1"].arguments["arg-2"].author == chloe


def test_an_empty_cell_is_never_a_vote(project: Project) -> None:
    ana, _, chloe, dan = project.members
    budget, amended = project.proposals["p-2"], project.proposals["p-1"]
    assert chloe.vote_on(budget) is None
    assert not project.snapshot.records_impressions
    assert ana.state_on(budget) is CellState.VOTED  # a neutral vote is a vote
    assert chloe.state_on(budget) is CellState.UNKNOWN  # nothing says what was shown

    seen = Snapshot(small_payload(impressions=True)).project()
    assert seen.snapshot.records_impressions
    assert seen.members["ps-ana"].state_on(budget) is CellState.VOTED
    assert seen.members["ps-chloe"].state_on(budget) is CellState.ABSTAINED
    assert seen.members["ps-dan"].state_on(amended) is CellState.NOT_SHOWN
    assert dan.state_on(amended.revisions[0]) is CellState.UNKNOWN  # on a given revision too
    states = {m.state_on(p) for m in seen.members for p in seen.proposals}
    assert states == {CellState.VOTED, CellState.ABSTAINED, CellState.NOT_SHOWN}


def test_participation_counts_what_the_snapshot_holds(project: Project) -> None:
    usage = project.participation
    assert (usage.n_proposals, usage.n_amendments, usage.n_arguments) == (2, 3, 3)
    assert usage.n_votes == 8  # votes on current revisions: the two on p-1.r1 are not counted
    assert (usage.n_members, usage.n_voters) == (4, 4)
    assert usage.coverage == pytest.approx(8 / 20)


def test_an_aggregated_snapshot_holds_counts_and_nothing_about_who() -> None:
    project = Snapshot(aggregated_payload()).project()
    assert project.exposure is Exposure.AGGREGATED
    assert not project.snapshot.has_votes
    assert project.proposals["p-1"].tally.total == 3
    assert project.participation.n_members == 4  # as the product sent it
    assert project.participation.n_votes == 8
    assert project.proposals["p-1"].author is None
    assert project.snapshot.members == Listing()
    dumped = json.dumps(project.snapshot.to_payload())
    assert not any(pseudonym in dumped for pseudonym in MEMBERS)
    readers = (
        lambda: project.votes,
        lambda: project.members,
        lambda: project.proposals["p-1"].votes,
        lambda: project.revisions[0].votes,
    )
    for read in readers:
        with pytest.raises(ExposureError, match="pseudonymised") as refused:
            read()
        assert "exposure" in refused.value.__notes__[0]
    with pytest.raises(ValidationError, match="aggregated snapshot"):
        Snapshot({**small_payload(), "exposure": "aggregated"})


def test_a_snapshot_identifies_its_data_and_replays_it(tmp_path: Path, snapshot: Snapshot) -> None:
    assert snapshot.as_of == AS_OF
    assert snapshot.exposure is Exposure.PSEUDONYMISED
    assert snapshot.fingerprint() == Snapshot(small_payload()).fingerprint()
    assert len(snapshot.fingerprint()) == 16
    changed = small_payload()
    changed["votes"][0]["score"] = 2
    assert Snapshot(changed).fingerprint() != snapshot.fingerprint()

    copy = snapshot.to_payload()
    copy["votes"].clear()  # the payload handed out is a copy: the snapshot does not move
    assert len(snapshot.votes) == len(VOTES)
    assert len(snapshot.to_payload()["votes"]) == len(VOTES)

    path = snapshot.project().save(tmp_path / "demo.json")
    again = Snapshot.from_payload(json.loads(path.read_text(encoding="utf-8")), source="file")
    assert again.fingerprint() == snapshot.fingerprint()
    assert again.proposals.ids == snapshot.proposals.ids
    assert repr(again) == (
        f"Snapshot(1 projects, 5 proposals, pseudonymised, as of {AS_OF}, from file)"
    )


def test_a_project_is_found_by_id_or_slug_and_a_miss_says_what_exists(snapshot: Snapshot) -> None:
    assert snapshot.project("demo") == snapshot.project("demo-project") == snapshot.project()
    with pytest.raises(NotFoundError, match="it covers: 'demo-project'"):
        snapshot.project("budget")
    assert snapshot.group("budget-circle").parent == snapshot.group("g-1")
    with pytest.raises(NotFoundError, match="covers 2 groups; name one of: 'demo-collective'"):
        snapshot.group()
    empty = Snapshot({"format": small_payload()["format"]})
    with pytest.raises(NotFoundError, match="covers no project"):
        empty.project()


def test_invariants_are_checked_at_the_door() -> None:
    bad = small_payload()
    bad["votes"][0]["score"] = 3
    with pytest.raises(ValidationError, match="-2 to \\+2"):
        Snapshot(bad)
    bad = small_payload()
    bad["votes"].append(dict(bad["votes"][0]))
    with pytest.raises(ValidationError, match="two votes"):
        Snapshot(bad)
    with pytest.raises(ValidationError, match="not a CiviqHub snapshot"):
        Snapshot({"format": "other"})
    bad = small_payload()
    bad["tallies"][0]["counts"] = [1, 2, 3, 4]
    with pytest.raises(ValidationError, match="five non-negative counts"):
        Snapshot(bad)


@pytest.mark.parametrize(
    ("section", "field", "dangling"),
    [
        ("proposals", "project_id", "the project 'gone'"),
        ("revisions", "proposal_id", "the proposal 'gone'"),
        ("amendments", "target_proposal_id", "the target proposal 'gone'"),
        ("amendments", "target_revision_id", "the revision 'gone'"),
        ("votes", "revision_id", "the revision 'gone'"),
        ("votes", "member", "the member 'gone'"),
    ],
)
def test_a_reference_to_something_absent_is_refused(
    section: str, field: str, dangling: str
) -> None:
    bad = small_payload()
    bad[section][0][field] = "gone"
    with pytest.raises(ValidationError, match=dangling) as broken:
        Snapshot(bad)
    assert isinstance(broken.value, ValueError)
    assert "which is not in the snapshot" in str(broken.value)


def test_a_proposal_without_a_revision_says_so_when_read() -> None:
    payload = small_payload()
    payload["proposals"].append({"id": "p-3", "project_id": "demo"})
    orphan = Snapshot(payload).proposals["p-3"]
    with pytest.raises(ValidationError, match="has no revision"):
        _ = orphan.current
    assert isinstance(orphan, Proposal)
    assert not isinstance(orphan, Amendment)
