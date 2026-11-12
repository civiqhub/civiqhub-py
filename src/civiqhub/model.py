# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of a CiviqHub Project, as plain immutable Python objects.

Everything is loaded once into a ``Snapshot``; navigating from one object to another
(``proposal.revisions``, ``vote.member``, ``amendment.target``) reads that snapshot and
never touches the network. No object ever carries a real name, a handle, an email or
an internal user id: a member is known by a pseudonym, and only when the snapshot was
taken at the pseudonymised level.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, overload

from .errors import ExposureError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from civiqhub_selene.blocks import VoteMatrix

    from .analysis import Coclustering, ConsensusRanking, Count, Membership

FORMAT = "civiqhub.snapshot/0"
SCORES: tuple[int, ...] = (-2, -1, 0, 1, 2)
Record = Mapping[str, Any]


class Exposure(StrEnum):
    """How much detail a snapshot holds."""

    AGGREGATED = "aggregated"  # vote counts per revision, nothing about who voted
    PSEUDONYMISED = "pseudonymised"  # one row per vote, members known by a pseudonym


class Role(IntEnum):
    """The ladder of roles in a Group or a Project; a higher role includes the lower ones."""

    READER = 1
    PARTICIPANT = 2
    REPRESENTATIVE = 3
    MODERATOR = 4
    ADMINISTRATOR = 5


class ActantKind(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    OTHER = "other"


class AmendmentStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class Position(StrEnum):
    PRO = "pro"
    CON = "con"
    NEUTRAL = "neutral"


class CellState(StrEnum):
    """What happened between one member and one revision. An empty cell is never a vote."""

    VOTED = "voted"
    ABSTAINED = "abstained"  # shown, no vote
    NOT_SHOWN = "not shown"  # missing data
    UNKNOWN = "unknown"  # no vote, and the snapshot does not record what was shown


# -- collections -------------------------------------------------------------------


class Entity:
    """Anything with an identity inside a snapshot. Equal when same kind and same id."""

    id: str
    snapshot: Snapshot
    noun: ClassVar[str] = "entity"

    def _label(self) -> str:
        return repr(self.id)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._label()})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.noun == other.noun and self.id == other.id

    def __hash__(self) -> int:
        return hash((self.noun, self.id))


E = TypeVar("E", bound=Entity)


class Listing(Sequence[E]):
    """An ordered, immutable collection of objects, indexed by position or by id."""

    __slots__ = ("_by_id", "_items")

    def __init__(self, items: Iterable[E] = ()) -> None:
        self._items: tuple[E, ...] = tuple(items)
        self._by_id: dict[str, E] = {item.id: item for item in self._items}

    @overload
    def __getitem__(self, key: int) -> E: ...
    @overload
    def __getitem__(self, key: str) -> E: ...
    @overload
    def __getitem__(self, key: slice) -> Listing[E]: ...
    def __getitem__(self, key: int | str | slice) -> E | Listing[E]:
        if isinstance(key, str):
            if key not in self._by_id:
                known = ", ".join(list(self._by_id)[:5])
                raise NotFoundError(f"no {key!r} here; the first ids are: {known}")
            return self._by_id[key]
        if isinstance(key, slice):
            return Listing(self._items[key])
        return self._items[key]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[E]:
        return iter(self._items)

    def __contains__(self, item: object) -> bool:
        key = item.id if isinstance(item, Entity) else item
        return isinstance(key, str) and key in self._by_id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Listing) and self._items == other._items

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        head = ", ".join(repr(item) for item in self._items[:3])
        more = f", ... {len(self) - 3} more" if len(self) > 3 else ""
        return f"[{head}{more}]"

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def get(self, id: str) -> E | None:
        """The object with this id, or ``None``."""
        return self._by_id.get(id)

    def where(self, test: Callable[[E], bool] | None = None, /, **equals: object) -> Listing[E]:
        """Keep the objects that pass ``test`` and whose attributes equal ``equals``.

        ``project.proposals.where(is_amendment=False)``,
        ``project.votes.where(lambda vote: vote.score > 0)``.
        """
        kept = [
            item
            for item in self._items
            if (test is None or test(item))
            and all(getattr(item, name) == value for name, value in equals.items())
        ]
        return Listing(kept)


# -- value object ------------------------------------------------------------------


@dataclass(frozen=True)
class VoteTally(Mapping[int, int]):
    """How many votes a revision received at each score from -2 to +2. Safe to publish."""

    counts: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)
    consensus: str | None = None  # the label computed by the product, when it sent one

    @classmethod
    def of(cls, scores: Iterable[int]) -> VoteTally:
        counts = [0, 0, 0, 0, 0]
        for score in scores:
            counts[score + 2] += 1
        return cls((counts[0], counts[1], counts[2], counts[3], counts[4]))

    def __getitem__(self, score: int) -> int:
        if score not in SCORES:
            raise KeyError(f"{score!r} is not a score; scores go from -2 to +2")
        return self.counts[score + 2]

    def __iter__(self) -> Iterator[int]:
        return iter(SCORES)

    def __len__(self) -> int:
        return len(SCORES)

    def __add__(self, other: VoteTally) -> VoteTally:
        a, b = self.counts, other.counts
        return VoteTally((a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3], a[4] + b[4]))

    @property
    def total(self) -> int:
        return sum(self.counts)

    @property
    def shares(self) -> tuple[float, ...]:
        """Share of the votes at each score; all zero when nobody voted."""
        total = self.total
        return tuple(count / total if total else 0.0 for count in self.counts)

    def __repr__(self) -> str:
        cells = "  ".join(f"{score:+d}: {count}" for score, count in self.items())
        return f"VoteTally({cells})"


# -- who ---------------------------------------------------------------------------


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Actant(Entity):
    """Whoever votes and argues: a human member, an agent, or anything else.

    ``id`` is a pseudonym. It is stable inside one snapshot and says nothing about
    the person or the agent behind it.
    """

    id: str
    snapshot: Snapshot = field(repr=False)
    kind: ActantKind = ActantKind.HUMAN
    role: Role | None = None
    noun: ClassVar[str] = "actant"

    @property
    def pseudonym(self) -> str:
        return self.id

    @property
    def votes(self) -> Listing[Vote]:
        return self.snapshot._votes_by_member.get(self.id, Listing())

    @property
    def arguments(self) -> Listing[Argument]:
        return self.snapshot.arguments.where(author_id=self.id)

    def vote_on(self, target: Proposal | Revision) -> Vote | None:
        """The vote of this actant on a revision (the current one for a proposal)."""
        revision = target.current if isinstance(target, Proposal) else target
        return self.snapshot.votes.get(f"{self.id}@{revision.id}")

    def state_on(self, target: Proposal | Revision) -> CellState:
        """Voted, abstained, not shown, or unknown when impressions are not recorded."""
        revision = target.current if isinstance(target, Proposal) else target
        if self.vote_on(revision) is not None:
            return CellState.VOTED
        shown = self.snapshot._impressions
        if shown is None:
            return CellState.UNKNOWN
        return CellState.ABSTAINED if (self.id, revision.id) in shown else CellState.NOT_SHOWN


class Member(Actant):
    """A human member of the Project, known by a pseudonym."""


class Agent(Actant):
    """A software agent taking part with the same grammar as a member."""


# -- where -------------------------------------------------------------------------


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Group(Entity):
    """A community on CiviqHub. It contains Groups and Projects."""

    id: str
    snapshot: Snapshot = field(repr=False)
    slug: str
    name: str = ""
    description: str = ""
    parent_id: str | None = None
    noun: ClassVar[str] = "group"

    def _label(self) -> str:
        return repr(self.slug)

    @property
    def parent(self) -> Group | None:
        return self.snapshot.groups.get(self.parent_id) if self.parent_id else None

    @property
    def groups(self) -> Listing[Group]:
        return self.snapshot.groups.where(parent_id=self.id)

    @property
    def projects(self) -> Listing[Project]:
        return self.snapshot.projects.where(group_id=self.id)


@dataclass(frozen=True)
class Participation:
    """How much a Project was used. Counts only, safe to publish."""

    n_proposals: int
    n_amendments: int
    n_arguments: int
    n_votes: int
    n_members: int | None  # None when the snapshot does not say
    n_voters: int | None

    @property
    def coverage(self) -> float | None:
        """Share of the member x proposal cells that hold a vote on a current revision."""
        cells = (self.n_members or 0) * (self.n_proposals + self.n_amendments)
        return self.n_votes / cells if cells else None


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Project(Entity):
    """A corpus of Proposals that a Group writes, amends and votes on."""

    id: str
    snapshot: Snapshot = field(repr=False)
    slug: str
    name: str = ""
    description: str = ""
    group_id: str | None = None
    noun: ClassVar[str] = "project"

    def _label(self) -> str:
        return f"{self.slug!r}, {len(self.proposals)} proposals, as of {self.as_of}"

    # where it sits ---------------------------------------------------------------
    @property
    def group(self) -> Group | None:
        return self.snapshot.groups.get(self.group_id) if self.group_id else None

    @property
    def as_of(self) -> str:
        """The instant the data describes; quote it with ``fingerprint`` to cite a result."""
        return self.snapshot.as_of

    @property
    def exposure(self) -> Exposure:
        return self.snapshot.exposure

    # what it holds ---------------------------------------------------------------
    @property
    def proposals(self) -> Listing[Proposal]:
        """Every Proposal of the Project, amendments included (an Amendment is a Proposal)."""
        return self.snapshot._proposals_by_project.get(self.id, Listing())

    @property
    def amendments(self) -> Listing[Amendment]:
        return Listing(p for p in self.proposals if isinstance(p, Amendment))

    @property
    def revisions(self) -> Listing[Revision]:
        return Listing(r for p in self.proposals for r in p.revisions)

    @property
    def arguments(self) -> Listing[Argument]:
        return Listing(a for p in self.proposals for a in p.arguments)

    @property
    def votes(self) -> Listing[Vote]:
        """Every vote, one per member and revision. Needs a pseudonymised snapshot."""
        self.snapshot.require_votes("project.votes")
        return Listing(v for r in self.revisions for v in r.votes)

    @property
    def members(self) -> Listing[Actant]:
        """The members who appear in the snapshot. Needs a pseudonymised snapshot."""
        self.snapshot.require_votes("project.members")
        return self.snapshot.members

    @property
    def participation(self) -> Participation:
        sent = self.snapshot._participation.get(self.id, {})
        detailed = self.snapshot.has_votes
        current = [p.current for p in self.proposals]
        return Participation(
            n_proposals=len(self.proposals) - len(self.amendments),
            n_amendments=len(self.amendments),
            n_arguments=len(self.arguments),
            n_votes=sum(r.tally.total for r in current),
            n_members=len(self.snapshot.members) if detailed else sent.get("n_members"),
            n_voters=(
                len({v.member_id for r in current for v in r.votes})
                if detailed
                else sent.get("n_voters")
            ),
        )

    # what it computes: thin doors onto the analysis layer --------------------------
    def vote_matrix(self, *, proposals: Iterable[Proposal] | None = None) -> VoteMatrix:
        """The member x revision table of votes the analysis layer works on.

        One column per proposal, on its current revision. An empty cell stays empty:
        it is told apart as abstention or non-exposure when impressions are recorded.
        """
        from .analysis import vote_matrix

        return vote_matrix(self, proposals=proposals)

    def cocluster(
        self,
        *,
        membership: Membership = "single",
        groups: Count = "auto",
        blocks: Count = "auto",
        seed: int = 0,
        proposals: Iterable[Proposal] | None = None,
    ) -> Coclustering:
        """Find the opinion groups of members and the blocks of proposals they vote alike on.

        ``membership="single"``: each member belongs to one group. ``"mixed"``: a member
        may side with different groups on different blocks. Needs the analysis layer
        (``pip install "civiqhub[selene]"``). Always returns a ``Coclustering``: when
        the Project cannot carry one, ``is_available()`` is false and it says why.
        """
        from .analysis import cocluster

        return cocluster(
            self,
            membership=membership,
            groups=groups,
            blocks=blocks,
            seed=seed,
            proposals=proposals,
        )

    def consensus(self, *, across: Coclustering) -> ConsensusRanking:
        """Rank the proposals by how far every opinion group of ``across`` agrees with them."""
        from .analysis import consensus

        return consensus(self, across=across)

    def save(self, path: str | Path) -> Path:
        """Write the snapshot behind this Project to a file that ``civiqhub.load`` reads back."""
        return self.snapshot.save(path)


# -- what --------------------------------------------------------------------------


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Proposal(Entity):
    """A statement put to the Project. Its text lives in an ordered list of Revisions."""

    id: str
    snapshot: Snapshot = field(repr=False)
    project_id: str
    author_id: str | None = None
    created_at: str | None = None
    current_revision_id: str | None = None
    noun: ClassVar[str] = "proposal"

    def _label(self) -> str:
        text = self.text if len(self.text) <= 48 else self.text[:45] + "..."
        return f"{self.id!r}, {text!r}"

    @property
    def is_amendment(self) -> bool:
        return False

    @property
    def project(self) -> Project:
        return self.snapshot.projects[self.project_id]

    @property
    def author(self) -> Actant | None:
        """Who wrote it, as a pseudonym; ``None`` in an aggregated snapshot."""
        return self.snapshot.members.get(self.author_id) if self.author_id else None

    @property
    def revisions(self) -> Listing[Revision]:
        """Every version of the text, oldest first. A Revision never changes."""
        return self.snapshot._revisions_by_proposal.get(self.id, Listing())

    @property
    def current(self) -> Revision:
        """The revision in force: the one votes are now cast on."""
        if self.current_revision_id:
            return self.snapshot.revisions[self.current_revision_id]
        if not self.revisions:
            raise ValidationError(f"proposal {self.id!r} has no revision; reload the snapshot")
        return self.revisions[-1]

    @property
    def text(self) -> str:
        return self.current.affirmation

    @property
    def votes(self) -> Listing[Vote]:
        """Votes on the current revision. Votes on older revisions stay on those revisions."""
        return self.current.votes

    @property
    def tally(self) -> VoteTally:
        return self.current.tally

    @property
    def amendments(self) -> Listing[Amendment]:
        """The Amendments that target this Proposal, on any of its revisions."""
        return self.snapshot._amendments_by_target.get(self.id, Listing())

    @property
    def arguments(self) -> Listing[Argument]:
        return self.snapshot._arguments_by_proposal.get(self.id, Listing())

    def walk(self) -> Iterator[tuple[int, Proposal]]:
        """This proposal, then its amendments, then theirs: ``(depth, proposal)`` pairs."""
        stack: list[tuple[int, Proposal]] = [(0, self)]
        while stack:
            depth, node = stack.pop()
            yield depth, node
            stack.extend((depth + 1, child) for child in reversed(node.amendments))


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Amendment(Proposal):
    """A Proposal that targets another one, on a precise revision, and may replace its text.

    It is a Proposal in full: it has revisions, receives votes and arguments, and can
    itself be amended.
    """

    amendment_id: str
    target_id: str
    target_revision_id: str
    status: AmendmentStatus = AmendmentStatus.OPEN
    adopted_revision_id: str | None = None
    is_stale: bool = False  # the target moved on since this amendment was written

    @property
    def is_amendment(self) -> bool:
        return True

    @property
    def target(self) -> Proposal:
        return self.snapshot.proposals[self.target_id]

    @property
    def target_revision(self) -> Revision:
        return self.snapshot.revisions[self.target_revision_id]

    @property
    def is_adopted(self) -> bool:
        return self.status is AmendmentStatus.ADOPTED

    @property
    def adopted_revision(self) -> Revision | None:
        """The revision of the target that adopting this amendment produced."""
        if self.adopted_revision_id is None:
            return None
        return self.snapshot.revisions[self.adopted_revision_id]

    @property
    def root(self) -> Proposal:
        """The Proposal at the top of the chain of amendments."""
        node: Proposal = self
        while isinstance(node, Amendment):
            node = node.target
        return node


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Revision(Entity):
    """One immutable version of the text of a Proposal. Votes are cast on a Revision."""

    id: str
    snapshot: Snapshot = field(repr=False)
    proposal_id: str
    number: int = 1
    affirmation: str = ""
    description: str = ""
    created_at: str | None = None
    content_hash: str | None = None
    amendment_id: str | None = None
    noun: ClassVar[str] = "revision"

    def _label(self) -> str:
        return f"{self.id!r}, version {self.number} of {self.proposal_id!r}"

    @property
    def proposal(self) -> Proposal:
        return self.snapshot.proposals[self.proposal_id]

    @property
    def is_current(self) -> bool:
        return self.proposal.current == self

    @property
    def from_amendment(self) -> Amendment | None:
        """The Amendment whose adoption produced this revision, if any."""
        if self.amendment_id is None:
            return None
        return self.snapshot._amendments_by_row.get(self.amendment_id)

    @property
    def votes(self) -> Listing[Vote]:
        """One vote per member. Needs a pseudonymised snapshot."""
        self.snapshot.require_votes("revision.votes")
        return self.snapshot._votes_by_revision.get(self.id, Listing())

    @property
    def tally(self) -> VoteTally:
        """Counts per score. Available at every exposure level."""
        return self.snapshot._tallies.get(self.id, VoteTally())


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Vote(Entity):
    """One actant, one revision, one score from -2 to +2. Zero is a chosen neutral."""

    id: str
    snapshot: Snapshot = field(repr=False)
    member_id: str
    revision_id: str
    score: int
    cast_at: str | None = None
    noun: ClassVar[str] = "vote"

    def _label(self) -> str:
        return f"{self.member_id!r} on {self.revision_id!r}: {self.score:+d}"

    @property
    def member(self) -> Actant:
        return self.snapshot.members[self.member_id]

    @property
    def revision(self) -> Revision:
        return self.snapshot.revisions[self.revision_id]

    @property
    def proposal(self) -> Proposal:
        return self.revision.proposal

    def to_record(self) -> tuple[str, str, int]:
        """``(member, revision, score)``, the plain record the analysis layer reads."""
        return (self.member_id, self.revision_id, self.score)


@dataclass(frozen=True, eq=False, repr=False, kw_only=True)
class Argument(Entity):
    """A published reason for or against a Proposal. Publishing it reveals the author's vote."""

    id: str
    snapshot: Snapshot = field(repr=False)
    proposal_id: str
    revision_id: str | None = None
    author_id: str | None = None
    position: Position | None = None
    text: str = ""
    score: int | None = None  # the vote the author chose to reveal
    parent_id: str | None = None
    n_supports: int = 0
    noun: ClassVar[str] = "argument"

    @property
    def proposal(self) -> Proposal:
        return self.snapshot.proposals[self.proposal_id]

    @property
    def revision(self) -> Revision | None:
        return self.snapshot.revisions.get(self.revision_id) if self.revision_id else None

    @property
    def author(self) -> Actant | None:
        return self.snapshot.members.get(self.author_id) if self.author_id else None

    @property
    def parent(self) -> Argument | None:
        return self.snapshot.arguments.get(self.parent_id) if self.parent_id else None

    @property
    def replies(self) -> Listing[Argument]:
        return self.snapshot._replies.get(self.id, Listing())

    @property
    def depth(self) -> int:
        return 0 if self.parent is None else 1 + self.parent.depth


# -- the snapshot ------------------------------------------------------------------

G = TypeVar("G", bound=Entity)


class _Index(Generic[G]):
    """Group entities by a key, keeping insertion order."""

    def __init__(self) -> None:
        self._groups: dict[str, list[G]] = defaultdict(list)

    def add(self, key: str | None, item: G) -> None:
        if key is not None:
            self._groups[key].append(item)

    def freeze(self) -> dict[str, Listing[G]]:
        return {key: Listing(items) for key, items in self._groups.items()}


class Snapshot:
    """Everything one token gave access to, at one instant, as one immutable graph.

    It is the unit of reproducibility: ``as_of`` and ``fingerprint()`` identify the
    data a result was computed on, ``save`` and ``civiqhub.load`` replay it offline.
    """

    as_of: str  # the instant the data describes
    exposure: Exposure
    source: str  # where it came from; never a secret
    groups: Listing[Group]
    projects: Listing[Project]
    proposals: Listing[Proposal]  # amendments included
    revisions: Listing[Revision]
    members: Listing[Actant]  # empty in an aggregated snapshot
    votes: Listing[Vote]  # empty in an aggregated snapshot
    arguments: Listing[Argument]

    def __init__(self, payload: Record, *, source: str = "memory") -> None:
        if payload.get("format") != FORMAT:
            raise ValidationError(
                f"this is not a CiviqHub snapshot (format {payload.get('format')!r}); "
                f"expected {FORMAT!r}. Fetch it again with civiqhub.connect()."
            )
        self._payload: dict[str, Any] = json.loads(json.dumps(payload))
        self.source = source
        self.as_of = str(payload.get("as_of", ""))
        self.exposure = Exposure(payload.get("exposure", "aggregated"))
        self._build(self._payload)

    # construction ------------------------------------------------------------------
    def _build(self, data: Record) -> None:
        rows = {key: list(data.get(key, ())) for key in _SECTIONS}
        if self.exposure is Exposure.AGGREGATED and (rows["votes"] or rows["members"]):
            raise ValidationError(
                "an aggregated snapshot cannot hold member-level rows; "
                "set exposure to 'pseudonymised' or drop the votes and members sections"
            )
        self.groups = Listing(Group(snapshot=self, **_pick(r, Group)) for r in rows["groups"])
        self.projects = Listing(
            Project(snapshot=self, **_pick(r, Project)) for r in rows["projects"]
        )
        self.members = Listing(self._actant(r) for r in rows["members"])

        amended = {r["proposal_id"]: r for r in rows["amendments"]}
        proposals: list[Proposal] = []
        for r in rows["proposals"]:
            self._known(r["project_id"], self.projects, "proposal", r["id"], "project")
            link = amended.get(r["id"])
            if link is None:
                proposals.append(Proposal(snapshot=self, **_pick(r, Proposal)))
            else:
                proposals.append(
                    Amendment(
                        snapshot=self,
                        **_pick(r, Proposal),
                        amendment_id=link["id"],
                        target_id=link["target_proposal_id"],
                        target_revision_id=link["target_revision_id"],
                        status=AmendmentStatus(link.get("status", "open")),
                        adopted_revision_id=link.get("adopted_revision_id"),
                        is_stale=bool(link.get("stale", False)),
                    )
                )
        self.proposals = Listing(proposals)
        self.revisions = Listing(
            Revision(snapshot=self, **_pick(r, Revision))
            for r in sorted(rows["revisions"], key=lambda r: (r["proposal_id"], r.get("number", 1)))
        )
        for revision in self.revisions:
            self._known(revision.proposal_id, self.proposals, "revision", revision.id, "proposal")
        for p in proposals:
            if isinstance(p, Amendment):
                self._known(p.target_id, self.proposals, "amendment", p.id, "target proposal")
                self._known(p.target_revision_id, self.revisions, "amendment", p.id, "revision")

        votes: list[Vote] = []
        for r in rows["votes"]:
            if r["score"] not in SCORES:
                raise ValidationError(
                    f"vote of {r['member']!r} on {r['revision_id']!r} has score {r['score']!r}; "
                    "scores go from -2 to +2, and an abstention is the absence of a vote"
                )
            self._known(r["revision_id"], self.revisions, "vote", r["member"], "revision")
            self._known(r["member"], self.members, "vote", r["revision_id"], "member")
            votes.append(
                Vote(
                    snapshot=self,
                    id=f"{r['member']}@{r['revision_id']}",
                    member_id=r["member"],
                    revision_id=r["revision_id"],
                    score=int(r["score"]),
                    cast_at=r.get("cast_at"),
                )
            )
        self.votes = Listing(votes)
        if len(self.votes.ids) != len(votes):
            raise ValidationError("a member has two votes on the same revision; keep the latest")
        self.arguments = Listing(
            Argument(
                snapshot=self,
                **{**_pick(r, Argument), "position": _enum(Position, r.get("position"))},
            )
            for r in rows["arguments"]
        )

        by_project: _Index[Proposal] = _Index()
        by_target: _Index[Amendment] = _Index()
        for p in proposals:
            by_project.add(p.project_id, p)
            if isinstance(p, Amendment):
                by_target.add(p.target_id, p)
        by_proposal: _Index[Revision] = _Index()
        for revision in self.revisions:
            by_proposal.add(revision.proposal_id, revision)
        by_revision: _Index[Vote] = _Index()
        by_member: _Index[Vote] = _Index()
        for vote in votes:
            by_revision.add(vote.revision_id, vote)
            by_member.add(vote.member_id, vote)
        args_of: _Index[Argument] = _Index()
        replies: _Index[Argument] = _Index()
        for argument in self.arguments:
            args_of.add(argument.proposal_id, argument)
            replies.add(argument.parent_id, argument)

        self._proposals_by_project = by_project.freeze()
        self._amendments_by_target = by_target.freeze()
        self._amendments_by_row = {p.amendment_id: p for p in proposals if isinstance(p, Amendment)}
        self._revisions_by_proposal = by_proposal.freeze()
        self._votes_by_revision = by_revision.freeze()
        self._votes_by_member = by_member.freeze()
        self._arguments_by_proposal = args_of.freeze()
        self._replies = replies.freeze()
        self._tallies: dict[str, VoteTally] = {
            r["revision_id"]: VoteTally(_five(r["counts"]), r.get("consensus"))
            for r in rows["tallies"]
        }
        for revision_id, cast in self._votes_by_revision.items():
            self._tallies.setdefault(revision_id, VoteTally.of(v.score for v in cast))
        seen = data.get("impressions")
        self._impressions: frozenset[tuple[str, str]] | None = (
            None if seen is None else frozenset((r["member"], r["revision_id"]) for r in seen)
        )
        self._participation: dict[str, Record] = {r["project_id"]: r for r in rows["participation"]}

    def _actant(self, row: Record) -> Actant:
        kind = ActantKind(row.get("kind", "human"))
        cls = {ActantKind.HUMAN: Member, ActantKind.AGENT: Agent}.get(kind, Actant)
        role = row.get("role")
        return cls(
            snapshot=self,
            id=row["pseudonym"],
            kind=kind,
            role=Role[role.upper()] if role else None,
        )

    @staticmethod
    def _known(key: str, where: Listing[Any], what: str, of: str, noun: str) -> None:
        if key not in where:
            raise ValidationError(
                f"{what} {of!r} points to the {noun} {key!r}, which is not in the snapshot; "
                "the snapshot is incomplete, fetch it again"
            )

    # reading -----------------------------------------------------------------------
    @classmethod
    def from_payload(cls, payload: Record, *, source: str = "memory") -> Snapshot:
        return cls(payload, source=source)

    @property
    def has_votes(self) -> bool:
        """True when the snapshot holds one row per vote (pseudonymised exposure)."""
        return self.exposure is Exposure.PSEUDONYMISED

    @property
    def records_impressions(self) -> bool:
        """True when the snapshot says which revisions were shown to which member."""
        return self._impressions is not None

    def require_votes(self, what: str) -> None:
        if not self.has_votes:
            raise ExposureError(
                f"{what} needs one row per vote, and this snapshot is aggregated: it holds "
                "vote counts per revision (revision.tally) and nothing about who voted. "
                "Ask an administrator of the Project to enable pseudonymised access, then "
                "connect with civiqhub.connect(exposure='pseudonymised')."
            )

    def project(self, ref: str | None = None) -> Project:
        """The Project with this id or slug; the only one when ``ref`` is omitted."""
        return _one(self.projects, ref, "project")

    def group(self, ref: str | None = None) -> Group:
        return _one(self.groups, ref, "group")

    # reproducibility -----------------------------------------------------------------
    def to_payload(self) -> dict[str, Any]:
        """The plain data behind the snapshot, ready for ``json.dump``."""
        copy: dict[str, Any] = json.loads(json.dumps(self._payload))
        return copy

    def fingerprint(self) -> str:
        """A stable digest of the content: same data, same fingerprint."""
        text = json.dumps(self._payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(json.dumps(self._payload, indent=1, sort_keys=True), encoding="utf-8")
        return target

    def __repr__(self) -> str:
        return (
            f"Snapshot({len(self.projects)} projects, {len(self.proposals)} proposals, "
            f"{self.exposure.value}, as of {self.as_of}, from {self.source})"
        )


_SECTIONS = (
    "groups",
    "projects",
    "proposals",
    "revisions",
    "amendments",
    "arguments",
    "tallies",
    "participation",
    "members",
    "votes",
)


def _pick(row: Record, cls: type) -> dict[str, Any]:
    """Keep the keys of a wire row that the class declares; unknown keys are ignored."""
    names = set(cls.__dataclass_fields__) - {"snapshot"}  # type: ignore[attr-defined]
    return {name: row[name] for name in names if name in row}


def _enum(kind: type[Position], value: str | None) -> Position | None:
    return kind(value.lower()) if value else None


def _five(counts: Sequence[int]) -> tuple[int, int, int, int, int]:
    if len(counts) != 5 or any(count < 0 for count in counts):
        raise ValidationError(f"a tally has five non-negative counts, from -2 to +2; got {counts}")
    return (int(counts[0]), int(counts[1]), int(counts[2]), int(counts[3]), int(counts[4]))


def _one(items: Listing[E], ref: str | None, noun: str) -> E:
    if ref is None:
        if len(items) == 1:
            return items[0]
        names = ", ".join(repr(getattr(item, "slug", item.id)) for item in items[:8])
        raise NotFoundError(
            f"this token covers {len(items)} {noun}s; name one of: {names}"
            if items
            else f"this token covers no {noun}; check what the token was issued for"
        )
    for item in items:
        if ref in (item.id, getattr(item, "slug", None)):
            return item
    names = ", ".join(repr(getattr(item, "slug", item.id)) for item in items[:8])
    raise NotFoundError(f"no {noun} {ref!r} under this token; it covers: {names}")
