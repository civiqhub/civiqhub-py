# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A synthetic Project, made up from a seed, to test, document and show the SDK.

The data are synthetic: they describe nobody. The Project has a planted structure,
which :func:`make_truth` gives: three opinion groups of Actants (the first 20, the next
16, the last 12) and two blocks of Proposals (``p-01`` to ``p-07``, then ``p-08`` to
``p-14``). Each opinion group votes in its own way on each block.

Everything is drawn from ``random.Random(seed)``, in a fixed order: the same seed gives
the same rows on every system. Neither the engine nor NumPy is needed.
"""

import random
from typing import Any

from .client import connect
from .dataset import FORMAT
from .entities import Project
from .errors import ValidationError
from .sources import MemorySource
from .values import SCORES, Exposure

__all__ = ["make_project", "make_rows", "make_truth"]

# The instant of the synthetic Project.
_AS_OF = "2026-01-01T00:00:00Z"

# The sizes of the planted opinion groups, in the order of the pseudonyms.
_OPINION_GROUPS = (20, 16, 12)

# The number of Proposals in each planted block, in the order of their ids.
_BLOCK_SIZE = 7

# For each opinion group and each block: how likely a vote is.
_RATES = ((0.85, 0.45), (0.55, 0.90), (0.40, 0.40))

# For each opinion group and each block: how the scores of the votes are shared, from
# -2 to +2.
_FOR = (0.02, 0.03, 0.05, 0.30, 0.60)
_AGAINST = (0.60, 0.30, 0.05, 0.03, 0.02)
_SPLIT = (0.10, 0.20, 0.40, 0.20, 0.10)
_SHARES = ((_FOR, _AGAINST), (_AGAINST, _FOR), (_SPLIT, _SPLIT))

# How likely a Revision without a vote was shown, when impressions are recorded.
_SHOWN = 0.5


def make_rows(*, seed: int = 0, impressions: bool = False) -> dict[str, Any]:
    """Return the rows of a synthetic Project, at the pseudonymised level.

    The data are synthetic and describe nobody. The rows hold one Group ``g-demo`` and
    one Project ``pr-demo`` (slug ``demo-project``); 48 Actants ``m-001`` to ``m-048``;
    14 Proposals ``p-01`` to ``p-14`` with one Revision each; a Proposal ``p-15`` with
    two Revisions, the second produced by the adopted Amendment ``p-16``; an open
    Amendment ``p-17`` to ``p-02``; six Arguments on ``p-01``, in two threads; and the
    votes on ``p-01`` to ``p-14``, drawn for each Actant and each Proposal from the
    planted structure (see :func:`make_truth`).

    Args:
        seed: The seed of the draws. The same seed gives the same rows.
        impressions: Whether the rows say which Revisions were shown to which Actants.
            Every vote is an impression, and a Revision without a vote was shown with
            the probability 0.5.

    Returns:
        Rows in the format :data:`~civiqhub.dataset.FORMAT`.

    Raises:
        ValidationError: The seed is not an integer.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValidationError(f"The seed of a synthetic Project is an integer; got {seed!r}.")
    draws = random.Random(seed)
    actants = _pseudonyms()
    voted = [f"p-{number:02d}" for number in range(1, 2 * _BLOCK_SIZE + 1)]
    truth = make_truth()
    votes: list[dict[str, Any]] = []
    cells: list[tuple[str, str, bool]] = []
    for actant in actants:
        group = truth["opinion_groups"][actant]
        for proposal in voted:
            block = truth["proposal_blocks"][proposal]
            # Two draws per cell, always: the existence of the vote, then its score.
            exists = draws.random() < _RATES[group][block]
            score = draws.choices(SCORES, weights=_SHARES[group][block])[0]
            cells.append((actant, f"{proposal}-r1", exists))
            if exists:
                votes.append(
                    {
                        "actant": actant,
                        "revision_id": f"{proposal}-r1",
                        "score": score,
                        "cast_at": _AS_OF,
                    }
                )
    rows: dict[str, Any] = {
        "format": FORMAT,
        "as_of": _AS_OF,
        "exposure": Exposure.PSEUDONYMISED.value,
        "groups": [{"id": "g-demo", "slug": "demo-group", "name": "Demo group (synthetic)"}],
        "projects": [
            {
                "id": "pr-demo",
                "slug": "demo-project",
                "name": "Demo project (synthetic)",
                "group_id": "g-demo",
            }
        ],
        "participation": [
            {
                "project_id": "pr-demo",
                "n_proposals": 15,
                "n_amendments": 2,
                "n_arguments": 6,
                "n_votes": len(votes),
                "n_actants": len(actants),
                "n_voters": len({vote["actant"] for vote in votes}),
            }
        ],
        "proposals": _proposals(),
        "revisions": _revisions(),
        "vote_counts": _vote_counts(votes),
        "amendments": _amendments(),
        "arguments": _arguments(),
        "actants": [
            {"pseudonym": actant, "kind": "human", "role": "participant"} for actant in actants
        ],
        "votes": votes,
    }
    if impressions:
        # A third draw per cell, after all the others, so that the votes stay the same.
        rows["impressions"] = [
            {"actant": actant, "revision_id": revision_id}
            for actant, revision_id, exists in cells
            if draws.random() < _SHOWN or exists
        ]
    return rows


def make_truth() -> dict[str, dict[str, int]]:
    """Return the planted structure of the synthetic Project, to test what finds it.

    Returns:
        ``{"opinion_groups": {pseudonym: index}, "proposal_blocks": {id: index}}``: the
        opinion group (0, 1 or 2) of each Actant, and the block (0 or 1) of each Proposal
        that has votes.
    """
    groups: dict[str, int] = {}
    pseudonyms = iter(_pseudonyms())
    for index, size in enumerate(_OPINION_GROUPS):
        for _ in range(size):
            groups[next(pseudonyms)] = index
    blocks = {
        f"p-{number:02d}": (number - 1) // _BLOCK_SIZE for number in range(1, 2 * _BLOCK_SIZE + 1)
    }
    return {"opinion_groups": groups, "proposal_blocks": blocks}


def make_project(
    *,
    seed: int = 0,
    impressions: bool = False,
    exposure: Exposure | str = Exposure.PSEUDONYMISED,
) -> Project:
    """Return a synthetic Project, to try the SDK without a token and without network.

    The data are synthetic and describe nobody: they are the rows of :func:`make_rows`,
    read through a :class:`~civiqhub.sources.MemorySource`.

    Args:
        seed: The seed of the draws. The same seed gives the same Project.
        impressions: Whether the Project records which Revisions were shown.
        exposure: The level of detail: ``"pseudonymised"`` (the default here) or
            ``"aggregated"``.
    """
    source = MemorySource(make_rows(seed=seed, impressions=impressions))
    return connect(source=source, exposure=exposure).project()


def _pseudonyms() -> list[str]:
    return [f"m-{number:03d}" for number in range(1, sum(_OPINION_GROUPS) + 1)]


def _proposals() -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = [
        {"id": f"p-{number:02d}", "project_id": "pr-demo"} for number in range(1, 18)
    ]
    proposals[14]["current_revision_id"] = "p-15-r2"
    return proposals


def _revisions() -> list[dict[str, Any]]:
    revisions: list[dict[str, Any]] = []
    for number in range(1, 18):
        if number <= 15:
            text = f"Synthetic proposal {number:02d}."
        else:
            text = f"Synthetic amendment {number:02d}."
        revisions.append(
            {
                "id": f"p-{number:02d}-r1",
                "proposal_id": f"p-{number:02d}",
                "number": 1,
                "affirmation": text,
            }
        )
        if number == 15:
            revisions.append(
                {
                    "id": "p-15-r2",
                    "proposal_id": "p-15",
                    "number": 2,
                    "affirmation": "Synthetic proposal 15, as amended by 16.",
                    "amendment_id": "a-01",
                }
            )
    return revisions


def _amendments() -> list[dict[str, Any]]:
    return [
        {
            "id": "a-01",
            "proposal_id": "p-16",
            "target_proposal_id": "p-15",
            "target_revision_id": "p-15-r1",
            "status": "adopted",
            "adopted_revision_id": "p-15-r2",
        },
        {
            "id": "a-02",
            "proposal_id": "p-17",
            "target_proposal_id": "p-02",
            "target_revision_id": "p-02-r1",
            "status": "open",
        },
    ]


def _arguments() -> list[dict[str, Any]]:
    # Two threads on p-01: depths 0, 1, 2, then 0, 1, 1. One author from each opinion
    # group in turn, and positions that alternate.
    parents = (None, "arg-1", "arg-2", None, "arg-4", "arg-4")
    authors = ("m-001", "m-021", "m-037", "m-002", "m-022", "m-038")
    return [
        {
            "id": f"arg-{index}",
            "proposal_id": "p-01",
            "revision_id": "p-01-r1",
            "author_id": author,
            "position": "pro" if index % 2 else "con",
            "text": f"Synthetic argument {index}.",
            **({"parent_id": parent} if parent else {}),
        }
        for index, (parent, author) in enumerate(zip(parents, authors, strict=True), start=1)
    ]


def _vote_counts(votes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counted: dict[str, list[int]] = {}
    for vote in votes:
        counts = counted.setdefault(vote["revision_id"], [0] * len(SCORES))
        counts[SCORES.index(vote["score"])] += 1
    return [
        {"revision_id": revision_id, "counts": counts}
        for revision_id, counts in sorted(counted.items())
    ]
