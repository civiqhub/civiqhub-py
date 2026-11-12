# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A made-up Project with planted opinion groups, for demos, tests and tutorials.

No real participant appears here. The votes come from the planted collective of the
analysis layer: three groups of members, two blocks of proposals.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from civiqhub_selene.blocks.synthetic import hard_memberships, planted_collective

from .client import Client
from .model import FORMAT, Exposure, Project
from .sources import MemorySource

GROUP_SIZES = (20, 16, 12)
BLOCK_SIZES = (7, 7)  # in each block: six proposals, then one amendment to the first


def synthetic_payload(
    *, seed: int = 0, impressions: bool = False
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    """Build a snapshot payload and the planted truth ``{"groups": .., "blocks": ..}``."""
    rng = np.random.default_rng(seed)
    matrix, planted = planted_collective(
        hard_memberships(GROUP_SIZES), hard_memberships(BLOCK_SIZES), seed=seed
    )
    n_members, n_columns = matrix.shape
    members = [f"m-{i + 1:03d}" for i in range(n_members)]
    first_of_block = [0, BLOCK_SIZES[0]]
    amends = {BLOCK_SIZES[0] - 1: 0, n_columns - 1: BLOCK_SIZES[0]}  # column -> target column

    proposals, revisions, amendments, column_revision = [], [], [], []
    ids: list[str] = []
    n_plain = n_amend = 0
    for j in range(n_columns):
        if j in amends:
            n_amend += 1
            ids.append(f"a-{n_amend:02d}")
        else:
            n_plain += 1
            ids.append(f"p-{n_plain:02d}")
    for j, pid in enumerate(ids):
        text = (
            f"Synthetic amendment to {ids[amends[j]]}"
            if j in amends
            else f"Synthetic proposal {pid[2:]}"
        )
        revisions.append({"id": f"{pid}.r1", "proposal_id": pid, "number": 1, "affirmation": text})
        column_revision.append(f"{pid}.r1")
        proposals.append(
            {
                "id": pid,
                "project_id": "demo",
                "author_id": members[int(rng.integers(n_members))],
                "current_revision_id": f"{pid}.r1",
            }
        )
    # The first amendment was adopted: its target gains a second revision, now current,
    # and the planted votes of that column are cast on the new revision.
    adopted, open_ = sorted(amends)
    target = ids[amends[adopted]]
    revisions.append(
        {
            "id": f"{target}.r2",
            "proposal_id": target,
            "number": 2,
            "affirmation": f"Synthetic proposal {target[2:]}, as amended",
            "amendment_id": "amd-1",
        }
    )
    proposals[amends[adopted]]["current_revision_id"] = f"{target}.r2"
    column_revision[amends[adopted]] = f"{target}.r2"
    amendments.append(
        {
            "id": "amd-1",
            "proposal_id": ids[adopted],
            "target_proposal_id": target,
            "target_revision_id": f"{target}.r1",
            "status": "adopted",
            "adopted_revision_id": f"{target}.r2",
        }
    )
    amendments.append(
        {
            "id": "amd-2",
            "proposal_id": ids[open_],
            "target_proposal_id": ids[amends[open_]],
            "target_revision_id": f"{ids[amends[open_]]}.r1",
            "status": "open",
        }
    )

    levels = matrix.levels
    votes: list[dict[str, Any]] = [
        {"member": members[i], "revision_id": column_revision[j], "score": int(levels[i, j]) - 3}
        for i in range(n_members)
        for j in range(n_columns)
        if levels[i, j] > 0
    ]
    early = rng.choice(n_members, size=10, replace=False)
    votes += [
        {
            "member": members[int(i)],
            "revision_id": f"{target}.r1",
            "score": int(rng.integers(-2, 3)),
        }
        for i in sorted(early)
    ]
    counts: dict[str, list[int]] = {}
    for vote in votes:
        counts.setdefault(vote["revision_id"], [0, 0, 0, 0, 0])[vote["score"] + 2] += 1

    arguments = []
    voters = [v for v in votes if v["revision_id"] == column_revision[0]][:5]
    for n, vote in enumerate(voters, start=1):
        arguments.append(
            {
                "id": f"arg-{n}",
                "proposal_id": ids[0],
                "revision_id": vote["revision_id"],
                "author_id": vote["member"],
                "position": "pro"
                if vote["score"] > 0
                else "con"
                if vote["score"] < 0
                else "neutral",
                "text": f"Synthetic argument {n}",
                "score": vote["score"],
                "parent_id": "arg-1" if n == 4 else None,
                "n_supports": int(rng.integers(0, 6)),
            }
        )

    payload: dict[str, Any] = {
        "format": FORMAT,
        "as_of": "2026-01-01T00:00:00Z",
        "exposure": "pseudonymised",
        "groups": [{"id": "g-demo", "slug": "demo-collective", "name": "Demo collective"}],
        "projects": [
            {"id": "demo", "slug": "demo-project", "name": "Demo project", "group_id": "g-demo"}
        ],
        "proposals": proposals,
        "revisions": revisions,
        "amendments": amendments,
        "arguments": arguments,
        "tallies": [{"revision_id": r, "counts": c} for r, c in counts.items()],
        "participation": [
            {
                "project_id": "demo",
                "n_members": n_members,
                "n_voters": len({v["member"] for v in votes}),
            }
        ],
        "members": [{"pseudonym": m, "kind": "human", "role": "participant"} for m in members],
        "votes": votes,
    }
    if impressions:
        hidden = (levels == 0) & (rng.random(levels.shape) < 0.15)
        payload["impressions"] = [
            {"member": members[i], "revision_id": column_revision[j]}
            for i in range(n_members)
            for j in range(n_columns)
            if not hidden[i, j]
        ]
    truth = {
        "groups": {m: int(planted.roles[i, 0]) for i, m in enumerate(members)},
        "blocks": {pid: int(j >= first_of_block[1]) for j, pid in enumerate(ids)},
    }
    return payload, truth


def synthetic_project(
    *, seed: int = 0, impressions: bool = False, exposure: Exposure | str = "pseudonymised"
) -> Project:
    """A ready-made Project to try the library without a token."""
    payload, _ = synthetic_payload(seed=seed, impressions=impressions)
    return Client(MemorySource(payload), exposure=exposure).project()
