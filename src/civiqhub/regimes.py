# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The collective regime of a Proposal: product objects in, a label out.

The bridge to the ordinal family of the engine. It reads the five counters of a
revision, which are published at every exposure level, hands them to the engine and
presents the answer. It computes nothing: the index, the median and the label all come
from the engine, with their provenance. It needs neither member-level data nor NumPy.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, overload

from ._selene import require_ordinal
from .citation import Analysis
from .errors import NotFoundError
from .model import Project, Proposal, Revision, VoteTally

if TYPE_CHECKING:
    import civiqhub_selene as selene
    from civiqhub_selene import ordinal as selene_ordinal
else:
    selene, selene_ordinal = require_ordinal()


@dataclass(frozen=True, eq=False)
class ProposalRegime(Analysis):
    """Where a Proposal stands collectively: a directed consensus, the mixed zone or a
    dissensus, with the index behind the label and where on the scale the distance lies."""

    project: Project
    engine: selene.Result[selene_ordinal.RegimeReading]
    proposal: Proposal
    revision: Revision  # the votes read are those cast on this revision

    @property
    def id(self) -> str:
        return self.proposal.id

    @property
    def reading(self) -> selene_ordinal.RegimeReading:
        """The engine's value, for whoever needs every number."""
        self._require("the regime")
        return self.engine.unwrap()

    @property
    def label(self) -> selene_ordinal.Regime:
        """One of the seven regimes: C-2, C-1, C0, C+1, C+2, M or D."""
        return self.reading.regime

    @property
    def is_consensus(self) -> bool:
        return self.reading.regime.is_consensus

    @property
    def omega(self) -> float:
        """The dissensus index, from 0 (unanimous) to 1 (two equal camps at the extremes)."""
        return self.reading.omega

    @property
    def contributions(self) -> tuple[float, float, float, float]:
        """What each of the four cuts of the scale adds to the index."""
        return self.reading.dissensus.contributions

    @property
    def dominant_cuts(self) -> tuple[tuple[int, int], ...]:
        """Between which neighbouring scores most of the distance lies."""
        return self.reading.dissensus.dominant_cuts

    @property
    def median_score(self) -> int:
        return self.reading.median

    @property
    def margin(self) -> float:
        """How far the index is from the nearest threshold: small means a fragile label."""
        return self.reading.margin

    @property
    def tally(self) -> VoteTally:
        """The five counters the regime was read on."""
        return self.revision.tally

    def summary(self) -> str:
        absent = self.unavailable
        if absent is not None:
            return f"{self.proposal.id}: no regime, {absent}\n  {self.citation}"
        reading = self.reading
        signed = selene_ordinal.signed
        cuts = ", and ".join(f"between {signed(a)} and {signed(b)}" for a, b in self.dominant_cuts)
        where = f"the distance lies mostly {cuts}" if cuts else "the vote is unanimous"
        return (
            f"{self.proposal.id}: {reading.regime.value}, omega {reading.omega:.3f} "
            f"on {reading.dissensus.n} votes\n"
            f"  median score {signed(reading.median)}; {where}\n"
            f"  thresholds {reading.low:g} and {reading.high:g}, "
            f"{reading.margin:.3f} from the nearest\n"
            f"  {self.citation}"
        )

    def __str__(self) -> str:
        absent = self.unavailable
        if absent is not None:
            return f"{self.proposal.id}: unavailable ({absent.reason.value})"
        return f"{self.proposal.id}: {self.reading.regime.value} (omega {self.reading.omega:.3f})"

    def __repr__(self) -> str:
        return f"ProposalRegime({self})"


class Regimes(Sequence[ProposalRegime]):
    """The regimes of the Proposals of a Project, in the order of the Project."""

    __slots__ = ("_by_id", "_items")

    def __init__(self, items: Sequence[ProposalRegime]) -> None:
        self._items = tuple(items)
        self._by_id = {item.id: item for item in self._items}

    @overload
    def __getitem__(self, key: int | str | Proposal) -> ProposalRegime: ...
    @overload
    def __getitem__(self, key: slice) -> Regimes: ...
    def __getitem__(self, key: int | str | Proposal | slice) -> ProposalRegime | Regimes:
        if isinstance(key, slice):
            return Regimes(self._items[key])
        if isinstance(key, int):
            return self._items[key]
        wanted = key.id if isinstance(key, Proposal) else key
        try:
            return self._by_id[wanted]
        except KeyError:
            raise NotFoundError(f"no regime was read for proposal {wanted!r}") from None

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[ProposalRegime]:
        return iter(self._items)

    def available(self) -> Regimes:
        """Those that have a label: the Proposals that received at least one vote."""
        return Regimes([item for item in self._items if item.is_available()])

    def labelled(self, label: str) -> Regimes:
        """Those in one regime, named as the engine names it: "C+2", "M", "D"..."""
        return Regimes(
            [item for item in self._items if item.is_available() and item.label == label]
        )

    def summary(self) -> str:
        return "\n".join(str(item) for item in self._items)

    def __repr__(self) -> str:
        return f"Regimes({len(self._items)} proposals, {len(self.available())} with a label)"


def regime(
    revision: Revision,
    *,
    gamma: float | None = None,
    low: float | None = None,
    high: float | None = None,
) -> ProposalRegime:
    """Read the regime of a Proposal on the votes of one of its revisions.

    Parameters left out take the engine's defaults, which are the demonstration values
    of the note and not calibrated rules; whatever is used is recorded in the citation.
    """
    settings = {
        name: value
        for name, value in (("gamma", gamma), ("low", low), ("high", high))
        if value is not None
    }
    counts = selene_ordinal.LikertCounts(revision.tally.counts, subject=revision.id)
    result = selene_ordinal.regime(counts, **settings)
    proposal = revision.proposal
    return ProposalRegime(proposal.project, result, proposal, revision)


def regimes(
    project: Project,
    *,
    gamma: float | None = None,
    low: float | None = None,
    high: float | None = None,
) -> Regimes:
    """The regime of every Proposal of the Project, on its current revision."""
    return Regimes([regime(p.current, gamma=gamma, low=low, high=high) for p in project.proposals])
