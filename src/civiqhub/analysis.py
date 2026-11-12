# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The bridge to the analysis layer: product objects in, product objects out.

This is the only module that touches the engine, and it is imported only when an
analysis is asked for: ``import civiqhub`` works without it. It turns a Project into
the table of votes the engine reads, runs an estimator, and hands the answer back as
members, proposals and votes. It computes nothing and decides nothing: every analysis
keeps the engine's result as it is, with its uncertainty, its provenance and, when the
Project cannot carry the analysis, the explicit reason why.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence, Set
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, overload

__all__ = [
    "Analysis",
    "Citation",
    "Coclustering",
    "ConsensusRanking",
    "EntityCluster",
    "OpinionGroup",
    "ProposalBlock",
    "Stance",
    "cocluster",
    "consensus",
    "vote_matrix",
]

from ._selene import require
from .citation import Analysis, Citation
from .errors import ValidationError
from .model import Actant, Entity, Listing, Project, Proposal, Vote, VoteTally

if TYPE_CHECKING:
    import civiqhub_selene as selene
    from civiqhub_selene import blocks as selene_blocks
else:
    selene, selene_blocks = require()

E = TypeVar("E", bound=Entity)
Membership = Literal["single", "mixed"]
Count = int | Iterable[int] | Literal["auto"]


def vote_matrix(
    project: Project, *, proposals: Iterable[Proposal] | None = None
) -> selene_blocks.VoteMatrix:
    """Members in rows, the current revision of each proposal in columns.

    A cell holds a vote or stays empty. With recorded impressions an empty cell is an
    abstention when the revision was shown and missing data when it was not; without
    them every empty cell counts as shown, which the result reports. The engine sees
    pseudonyms and revision ids as opaque strings and nothing else of the Project.
    """
    snapshot = project.snapshot
    snapshot.require_votes("a vote matrix")
    chosen = project.proposals if proposals is None else Listing(proposals)
    members = project.members
    columns = [proposal.current for proposal in chosen]
    row_of = {member.id: i for i, member in enumerate(members)}
    levels = [[0] * len(columns) for _ in members]
    shown = [[not snapshot.records_impressions] * len(columns) for _ in members]
    for j, revision in enumerate(columns):
        for vote in revision.votes:
            levels[row_of[vote.member_id]][j] = vote.score + 3  # -2..+2 becomes 1..5
            shown[row_of[vote.member_id]][j] = True
    if snapshot._impressions is not None:
        col_of = {revision.id: j for j, revision in enumerate(columns)}
        for member_id, revision_id in snapshot._impressions:
            if member_id in row_of and revision_id in col_of:
                shown[row_of[member_id]][col_of[revision_id]] = True
    return selene_blocks.VoteMatrix.from_levels(
        levels,
        shown=shown,
        voters=members.ids,
        subjects=tuple(r.id for r in columns),
    )


# -- clusters of product objects -----------------------------------------------------


@dataclass(frozen=True, eq=False)
class EntityCluster(Set[E], Generic[E]):
    """A set of members or of proposals that an analysis found to go together."""

    index: int
    items: Listing[E]
    share: float  # share of the members (or proposals) the method puts here

    def __contains__(self, item: object) -> bool:
        return item in self.items

    def __iter__(self) -> Iterator[E]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @classmethod
    def _from_iterable(cls, it: Iterable[Any]) -> frozenset[Any]:
        return frozenset(it)  # set algebra returns plain sets, not clusters

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EntityCluster):
            return type(self) is type(other) and self.items == other.items
        return Set.__eq__(self, other)

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.items.ids))


class OpinionGroup(EntityCluster[Actant]):
    """Members who vote alike. Not a Group of the product: nobody joined it."""

    @property
    def members(self) -> Listing[Actant]:
        return self.items

    def votes_on(self, proposals: Iterable[Proposal]) -> Listing[Vote]:
        """The votes of these members on the current revision of these proposals."""
        return _votes_between(self.items, proposals)

    def tally_on(self, proposals: Iterable[Proposal]) -> VoteTally:
        return VoteTally.of(vote.score for vote in self.votes_on(proposals))

    def __repr__(self) -> str:
        return f"OpinionGroup {self.index + 1}: {len(self)} members ({self.share:.0%})"


class ProposalBlock(EntityCluster[Proposal]):
    """Proposals that receive similar votes from the same members. Not a theme:
    nothing here reads the text."""

    @property
    def proposals(self) -> Listing[Proposal]:
        return self.items

    def votes_of(self, members: Iterable[Actant]) -> Listing[Vote]:
        """The votes of these members on the current revision of these proposals."""
        return _votes_between(members, self.items)

    def tally_of(self, members: Iterable[Actant]) -> VoteTally:
        return VoteTally.of(vote.score for vote in self.votes_of(members))

    def __repr__(self) -> str:
        return f"ProposalBlock {self.index + 1}: {len(self)} proposals ({self.share:.0%})"


def _votes_between(members: Iterable[Actant], proposals: Iterable[Proposal]) -> Listing[Vote]:
    targets = list(proposals)
    cast = (member.vote_on(proposal) for member in members for proposal in targets)
    return Listing(vote for vote in cast if vote is not None)


@dataclass(frozen=True)
class Stance:
    """How one opinion group votes on one block of proposals."""

    group: OpinionGroup
    block: ProposalBlock
    vote_rate: float  # estimated chance that a member of the group votes on the block
    shares: tuple[float, ...]  # estimated share of each score from -2 to +2
    n_votes: float
    typical_score: int  # the most likely score, from -2 to +2, as the engine reports it

    @property
    def votes(self) -> Listing[Vote]:
        """The votes actually cast by the group on the block."""
        return self.group.votes_on(self.block)

    @property
    def tally(self) -> VoteTally:
        """What was observed, next to ``shares``, which is what the model estimates."""
        return self.group.tally_on(self.block)

    def __str__(self) -> str:
        return (
            f"group {self.group.index + 1} on block {self.block.index + 1}: "
            f"typical score {self.typical_score:+d}, votes {self.vote_rate:.0%} of the time"
        )

    def __repr__(self) -> str:
        return f"Stance({self})"


@dataclass(frozen=True, eq=False)
class Coclustering(Analysis):
    """Opinion groups of members, blocks of proposals, and how each group votes on each block."""

    project: Project
    engine: selene.Result[selene_blocks.CoclusteringFit]
    matrix: selene_blocks.VoteMatrix
    groups: tuple[OpinionGroup, ...]  # empty when the analysis is unavailable
    blocks: tuple[ProposalBlock, ...]

    @property
    def fit(self) -> selene_blocks.CoclusteringFit:
        """The engine's value, for whoever needs the arrays."""
        self._require("the fit")
        return self.engine.unwrap()

    def group_of(self, member: Actant | str) -> OpinionGroup:
        """The opinion group of a member (the main one when memberships are mixed)."""
        key = member.id if isinstance(member, Actant) else member
        return self.groups[self.fit.group_of(key).index]

    def block_of(self, proposal: Proposal | str) -> ProposalBlock:
        target = self.project.proposals[proposal] if isinstance(proposal, str) else proposal
        return self.blocks[self.fit.block_of(target.current.id).index]

    def memberships_of(self, member: Actant | str) -> tuple[float, ...]:
        """How strongly the member belongs to each group; the weights sum to one."""
        key = member.id if isinstance(member, Actant) else member
        fit = self.fit
        return tuple(float(w) for w in fit.group_weights[fit.voters.index(key)])

    def __getitem__(self, key: tuple[OpinionGroup | int, ProposalBlock | int]) -> Stance:
        g = key[0].index if isinstance(key[0], OpinionGroup) else key[0]
        b = key[1].index if isinstance(key[1], ProposalBlock) else key[1]
        fit = self.fit
        cell = fit[g, b]
        return Stance(
            self.groups[g],
            self.blocks[b],
            cell.vote_rate,
            cell.vote_shares,
            cell.n_votes,
            fit.scale.labels[cell.typical_level - 1],
        )

    def stances(self) -> Iterator[Stance]:
        """Every (group, block) pair, group by group."""
        return (self[g, b] for g in range(len(self.groups)) for b in range(len(self.blocks)))

    def summary(self) -> str:
        absent = self.unavailable
        if absent is not None:
            return f"no co-clustering of project {self.project.slug!r}: {absent}\n  {self.citation}"
        lines = [
            f"{len(self.groups)} opinion groups and {len(self.blocks)} blocks of proposals "
            f"in project {self.project.slug!r} ({self.matrix.n_voted} votes)",
            *(f"  {group!r}" for group in self.groups),
            *(f"  {block!r}" for block in self.blocks),
            *(f"  {stance}" for stance in self.stances()),
            f"  {self.citation}",
        ]
        if not self.citation.impressions_recorded:
            lines.append("  impressions are not recorded: every empty cell was read as shown")
        return "\n".join(lines)

    def __repr__(self) -> str:
        absent = self.unavailable
        if absent is not None:
            return (
                f"Coclustering(unavailable: {absent.reason.value}, project {self.project.slug!r})"
            )
        return (
            f"Coclustering({len(self.groups)} opinion groups x {len(self.blocks)} blocks, "
            f"project {self.project.slug!r})"
        )


@dataclass(frozen=True, eq=False)
class ConsensusRanking(Analysis, Sequence[tuple[Proposal, float]]):
    """Proposals ordered by how far every opinion group agrees with them."""

    project: Project
    engine: selene.Result[selene_blocks.ConsensusScores]
    proposals: Listing[Proposal]  # most agreed with across groups first
    scores: tuple[float, ...]

    @overload
    def __getitem__(self, key: int) -> tuple[Proposal, float]: ...
    @overload
    def __getitem__(self, key: slice) -> Sequence[tuple[Proposal, float]]: ...
    def __getitem__(
        self, key: int | slice
    ) -> tuple[Proposal, float] | Sequence[tuple[Proposal, float]]:
        pairs = tuple(zip(self.proposals, self.scores, strict=True))
        return pairs[key]

    def __len__(self) -> int:
        return len(self.proposals)

    def score_of(self, proposal: Proposal) -> float:
        return self.scores[self.proposals.ids.index(proposal.id)]

    def __repr__(self) -> str:
        if not self.proposals:
            return f"ConsensusRanking(unavailable, project {self.project.slug!r})"
        return f"ConsensusRanking({len(self)} proposals, first: {self.proposals[0].id!r})"


# -- the doors -----------------------------------------------------------------------


def cocluster(
    project: Project,
    *,
    membership: Membership | str = "single",
    groups: Count = "auto",
    blocks: Count = "auto",
    seed: int = 0,
    proposals: Iterable[Proposal] | None = None,
) -> Coclustering:
    """Run the co-clustering of the analysis layer on a Project.

    Always returns a ``Coclustering``. When the Project cannot carry one (no vote, too
    few voting members), ``is_available()`` is false and ``unavailable`` says why.
    """
    matrix = vote_matrix(project, proposals=proposals)
    result = selene_blocks.cocluster(
        matrix, membership=membership, groups=groups, blocks=blocks, seed=seed
    )
    if isinstance(result.value, selene.Unavailable):
        return Coclustering(project, result, matrix, (), ())
    snapshot = project.snapshot
    fit = result.value
    found_groups = tuple(
        OpinionGroup(g.index, Listing(snapshot.members[m] for m in g.ids), g.share)
        for g in fit.groups
    )
    found_blocks = tuple(
        ProposalBlock(b.index, Listing(snapshot.revisions[r].proposal for r in b.ids), b.share)
        for b in fit.blocks
    )
    return Coclustering(project, result, matrix, found_groups, found_blocks)


def consensus(project: Project, *, across: Coclustering) -> ConsensusRanking:
    """Rank the proposals of ``across`` by agreement shared by all its opinion groups."""
    if across.project != project:
        raise ValidationError(
            "this co-clustering was computed on another project; "
            "pass the result of project.cocluster() for the same project"
        )
    result = selene_blocks.consensus(across.matrix, across.fit.groups)
    if isinstance(result.value, selene.Unavailable):
        return ConsensusRanking(project, result, Listing(), ())
    scores = result.value
    score_of = dict(zip(scores.subjects, scores.scores, strict=True))
    order = scores.ranking()
    ranked = Listing(project.snapshot.revisions[r].proposal for r in order)
    return ConsensusRanking(project, result, ranked, tuple(float(score_of[r]) for r in order))
