# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The small values that the objects of a Project carry.

The closed choices of the product are enumerations: :class:`Exposure`, :class:`Role`,
:class:`ActantKind`, :class:`AmendmentStatus`, :class:`Position` and :class:`VoteState`.
:class:`VoteCounts` holds the five vote counts of a Revision, and :class:`Participation`
the counts of a Project.

Every value is frozen and hashable. The counts are raw: no mean, no entropy and no
consensus label is computed from them.
"""

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, fields
from enum import IntEnum, StrEnum

from .errors import ValidationError

__all__ = [
    "SCORES",
    "ActantKind",
    "AmendmentStatus",
    "Exposure",
    "Participation",
    "Position",
    "Role",
    "VoteCounts",
    "VoteState",
]

#: The scores a vote can take, from -2 to +2.
SCORES = (-2, -1, 0, 1, 2)


class Exposure(StrEnum):
    """The level of detail that a dataset holds."""

    #: Vote counts per Revision and participation; nothing about who voted.
    AGGREGATED = "aggregated"
    #: One row per vote; an Actant is known by a pseudonym only.
    PSEUDONYMISED = "pseudonymised"


class Role(IntEnum):
    """The roles in a Group or a Project, from the lowest to the highest.

    A higher role includes the lower ones, so roles compare:
    ``Role.MODERATOR > Role.PARTICIPANT``.
    """

    #: The lowest role.
    READER = 1
    #: Above :attr:`READER`.
    PARTICIPANT = 2
    #: Above :attr:`PARTICIPANT`.
    REPRESENTATIVE = 3
    #: Above :attr:`REPRESENTATIVE`.
    MODERATOR = 4
    #: The highest role.
    ADMINISTRATOR = 5


class ActantKind(StrEnum):
    """What an Actant is."""

    #: A human member.
    HUMAN = "human"
    #: A software agent.
    AGENT = "agent"
    #: Anything else.
    OTHER = "other"


class AmendmentStatus(StrEnum):
    """Where an Amendment stands.

    There is no draft status. Like any unknown value, ``AmendmentStatus("draft")`` raises
    :class:`ValueError`.
    """

    #: Not decided yet.
    OPEN = "open"
    #: Adopted.
    ADOPTED = "adopted"
    #: Rejected.
    REJECTED = "rejected"


class Position(StrEnum):
    """The side that an Argument takes."""

    #: For.
    PRO = "pro"
    #: Against.
    CON = "con"
    #: Neither for nor against.
    NEUTRAL = "neutral"


class VoteState(StrEnum):
    """Where an Actant stands with a Revision.

    A missing vote is never a zero, nor a neutral vote.
    """

    #: The Actant voted.
    VOTED = "voted"
    #: The Revision was shown to the Actant, who did not vote.
    ABSTAINED = "abstained"
    #: The Revision was not shown to the Actant.
    NOT_SHOWN = "not_shown"
    #: The Actant did not vote, and the dataset does not record what was shown.
    UNKNOWN = "unknown"


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_score(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in SCORES


def _signed(score: int) -> str:
    return f"{score:+d}" if score else "0"


@dataclass(frozen=True, repr=False)
class VoteCounts(Mapping[int, int]):
    """The five vote counts of a Revision, from score -2 to score +2.

    It reads as a mapping from each score to its number of votes: ``vote_counts[2]`` is
    the number of votes at +2, and ``dict(vote_counts)`` gives the five counts. It holds
    counts and no other statistic. Zero everywhere means that nobody voted.

    Five counts that are not non-negative integers raise
    :class:`~civiqhub.errors.ValidationError`.

    Args:
        counts: The number of votes at each score, in the order of :data:`SCORES`:
            ``counts[k]`` is the number of votes at ``SCORES[k]``.
    """

    counts: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)

    def __post_init__(self) -> None:
        counts: object = self.counts
        if not (
            isinstance(counts, tuple)
            and len(counts) == len(SCORES)
            and all(_is_count(count) for count in counts)
        ):
            raise ValidationError(
                "Vote counts are five non-negative integers, from score -2 to score +2; "
                f"got {counts!r}."
            )

    @classmethod
    def from_scores(cls, scores: Iterable[int]) -> "VoteCounts":
        """Count the votes of a sequence of scores.

        A score outside :data:`SCORES` raises :class:`~civiqhub.errors.ValidationError`.

        Args:
            scores: One score per vote.
        """
        counts = [0] * len(SCORES)
        for score in scores:
            if not _is_score(score):
                raise ValidationError(f"A score is an integer from -2 to +2; got {score!r}.")
            counts[SCORES.index(score)] += 1
        return cls((counts[0], counts[1], counts[2], counts[3], counts[4]))

    def __getitem__(self, score: int) -> int:
        if not _is_score(score):
            raise KeyError(score)
        return self.counts[SCORES.index(score)]

    def __iter__(self) -> Iterator[int]:
        return iter(SCORES)

    def __len__(self) -> int:
        return len(SCORES)

    @property
    def total(self) -> int:
        """The number of votes."""
        return sum(self.counts)

    @property
    def shares(self) -> tuple[float, ...]:
        """The share of the votes at each score, in the order of :data:`SCORES`.

        Five zeros when nobody voted.
        """
        total = self.total
        return tuple(count / total if total else 0.0 for count in self.counts)

    def __repr__(self) -> str:
        cells = ", ".join(f"{_signed(score)}: {count}" for score, count in self.items())
        return f"{type(self).__name__}({cells})"


@dataclass(frozen=True, kw_only=True)
class Participation:
    """How much a Project is used, in counts.

    Every field is given by keyword. A negative count raises
    :class:`~civiqhub.errors.ValidationError`.

    Args:
        n_proposals: The number of Proposals.
        n_amendments: The number of Amendments.
        n_arguments: The number of Arguments.
        n_votes: The number of Votes.
        n_actants: The number of Actants, or ``None`` when the source does not say.
        n_voters: The number of Actants who voted, or ``None`` when the source does not
            say.
    """

    n_proposals: int
    n_amendments: int
    n_arguments: int
    n_votes: int
    n_actants: int | None
    n_voters: int | None

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None and field.name in ("n_actants", "n_voters"):
                continue
            if not _is_count(value):
                raise ValidationError(
                    f"Participation counts are integers, zero or more; got {field.name}={value!r}."
                )

    @property
    def turnout(self) -> float | None:
        """The share of the Actants who voted: ``n_voters / n_actants``.

        ``None`` when either number is missing, or when there is no Actant.
        """
        if self.n_voters is None or not self.n_actants:
            return None
        return self.n_voters / self.n_actants
