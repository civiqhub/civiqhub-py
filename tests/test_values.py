# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The values of the SDK: closed choices, raw vote counts, participation."""

import dataclasses
from enum import Enum

import pytest

import civiqhub
import civiqhub.values
from civiqhub.errors import ValidationError
from civiqhub.values import (
    SCORES,
    ActantKind,
    AmendmentStatus,
    Exposure,
    Participation,
    Position,
    Role,
    VoteCounts,
    VoteState,
)

ENUMERATIONS: list[type[Enum]] = [
    Exposure,
    Role,
    ActantKind,
    AmendmentStatus,
    Position,
    VoteState,
]


def make_participation(**changes: int | None) -> Participation:
    counts: dict[str, int | None] = {
        "n_proposals": 14,
        "n_amendments": 2,
        "n_arguments": 6,
        "n_votes": 420,
        "n_actants": 48,
        "n_voters": 36,
    }
    counts.update(changes)
    return Participation(**counts)  # type: ignore[arg-type]


def test_the_values_are_exported_by_the_package() -> None:
    for name in civiqhub.values.__all__:
        if name != "SCORES":
            assert name in civiqhub.__all__
            assert getattr(civiqhub, name) is getattr(civiqhub.values, name)


def test_the_scores_go_from_minus_two_to_plus_two() -> None:
    assert SCORES == (-2, -1, 0, 1, 2)


# -- VoteCounts --------------------------------------------------------------------


def test_vote_counts_read_as_a_mapping_from_score_to_count() -> None:
    vote_counts = VoteCounts((0, 0, 10, 0, 10))
    assert vote_counts[2] == 10
    assert vote_counts[0] == 10
    assert vote_counts[-2] == 0
    assert vote_counts.total == 20
    assert vote_counts.shares == (0.0, 0.0, 0.5, 0.0, 0.5)
    assert list(vote_counts) == [-2, -1, 0, 1, 2]
    assert len(vote_counts) == 5
    assert dict(vote_counts) == {-2: 0, -1: 0, 0: 10, 1: 0, 2: 10}


def test_a_score_outside_the_scale_is_not_a_key() -> None:
    vote_counts = VoteCounts((1, 2, 3, 4, 5))
    with pytest.raises(KeyError):
        vote_counts[3]
    text: object = "2"
    assert 3 not in vote_counts
    assert text not in vote_counts
    assert vote_counts.get(3) is None
    assert 2 in vote_counts


def test_vote_counts_are_counted_from_scores() -> None:
    assert VoteCounts.from_scores([2, 2, 0]) == VoteCounts((0, 0, 1, 0, 2))
    assert VoteCounts.from_scores(iter([-2, -1, 0, 1, 2])) == VoteCounts((1, 1, 1, 1, 1))
    assert VoteCounts.from_scores([]) == VoteCounts()


@pytest.mark.parametrize(
    "counts",
    [(1, 2, 3), (1, 2, 3, 4, 5, 6), (1, -1, 0, 0, 0), (1, 0.5, 0, 0, 0), (True, 0, 0, 0, 0)],
)
def test_vote_counts_are_five_non_negative_integers(counts: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="five non-negative integers"):
        VoteCounts(counts)  # type: ignore[arg-type]


def test_vote_counts_are_given_as_a_tuple() -> None:
    with pytest.raises(ValidationError, match=r"got \[0, 0, 1, 0, 2\]"):
        VoteCounts([0, 0, 1, 0, 2])  # type: ignore[arg-type]


@pytest.mark.parametrize("score", [3, -3, 1.0, True, "2"])
def test_a_score_outside_the_scale_cannot_be_counted(score: object) -> None:
    with pytest.raises(ValidationError, match="from -2 to \\+2"):
        VoteCounts.from_scores([2, score])  # type: ignore[list-item]


def test_no_vote_is_zero_everywhere() -> None:
    assert VoteCounts().total == 0
    assert VoteCounts().shares == (0.0,) * 5
    assert VoteCounts().counts == (0, 0, 0, 0, 0)


def test_vote_counts_hold_counts_and_no_other_statistic() -> None:
    for name in ("mean", "entropy", "consensus"):
        assert not hasattr(VoteCounts((0, 0, 10, 0, 10)), name)
        assert not hasattr(VoteCounts, name)


def test_vote_counts_show_each_score_with_its_count() -> None:
    assert repr(VoteCounts((0, 0, 10, 0, 10))) == "VoteCounts(-2: 0, -1: 0, 0: 10, +1: 0, +2: 10)"


# -- Participation -----------------------------------------------------------------


def test_turnout_is_the_share_of_actants_who_voted() -> None:
    assert make_participation().turnout == 0.75


@pytest.mark.parametrize(
    "changes", [{"n_actants": None}, {"n_voters": None}, {"n_actants": 0, "n_voters": 0}]
)
def test_turnout_is_none_when_it_cannot_be_computed(changes: dict[str, int | None]) -> None:
    assert make_participation(**changes).turnout is None


def test_participation_is_given_by_keyword_only() -> None:
    with pytest.raises(TypeError):
        Participation(14, 2, 6, 420, 48, 36)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "changes",
    [
        {"n_votes": -1},
        {"n_proposals": -14},
        {"n_actants": -48},
        {"n_voters": -1},
        {"n_arguments": None},
    ],
)
def test_participation_counts_are_zero_or_more(changes: dict[str, int | None]) -> None:
    name = next(iter(changes))
    with pytest.raises(ValidationError, match=f"got {name}="):
        make_participation(**changes)


# -- Enumerations ------------------------------------------------------------------


def test_roles_are_ordered_from_reader_to_administrator() -> None:
    assert Role.MODERATOR > Role.PARTICIPANT
    assert sorted(Role, reverse=True)[0] is Role.ADMINISTRATOR
    assert list(Role) == sorted(Role)


def test_an_enumeration_is_read_from_its_value() -> None:
    assert Exposure("aggregated") is Exposure.AGGREGATED
    assert Exposure("pseudonymised") is Exposure.PSEUDONYMISED
    assert VoteState.NOT_SHOWN.value == "not_shown"
    assert ActantKind("agent") is ActantKind.AGENT
    assert Position("neutral") is Position.NEUTRAL


def test_an_amendment_has_no_draft_status() -> None:
    assert [status.value for status in AmendmentStatus] == ["open", "adopted", "rejected"]
    assert not hasattr(AmendmentStatus, "DRAFT")
    with pytest.raises(ValueError, match="draft"):
        AmendmentStatus("draft")


# -- Frozen and hashable -----------------------------------------------------------


def test_vote_counts_and_participation_are_frozen_and_hashable() -> None:
    vote_counts = VoteCounts((0, 0, 10, 0, 10))
    participation = make_participation()
    with pytest.raises(dataclasses.FrozenInstanceError):
        vote_counts.counts = (0, 0, 0, 0, 0)  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        participation.n_votes = 0  # type: ignore[misc]
    assert hash(vote_counts) == hash(VoteCounts((0, 0, 10, 0, 10)))
    assert hash(participation) == hash(make_participation())
    assert len({vote_counts, VoteCounts((0, 0, 10, 0, 10)), VoteCounts()}) == 2
    assert len({participation, make_participation(), make_participation(n_votes=0)}) == 2


@pytest.mark.parametrize("enumeration", ENUMERATIONS)
def test_an_enumeration_is_frozen_and_hashable(enumeration: type[Enum]) -> None:
    member = next(iter(enumeration))
    assert {member: True}[member]
    with pytest.raises(AttributeError):
        member.value = "changed"  # type: ignore[misc]
