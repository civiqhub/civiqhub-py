# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Hand-written rows of a small Project, shared by the tests of the model.

Everything here is made up: no row describes a real Group, Project or person. Each
ticket of the model adds the sections it builds.

    demo-collective (g-1)
      budget-circle (g-2)
        budget-2027: Budget participatif
          p-01  r1, then r2 (current_revision_id given)
          p-02  r1, then r2 (no current_revision_id: r2 is current)
          p-03  r1, without a row of vote counts
          a-01  r1, to amend p-01
          a-02  r1, to amend p-02
"""

from typing import Any

from civiqhub.dataset import FORMAT

AS_OF = "2026-11-16T09:00:00Z"

#: The participation of the reference Project: 6 voters out of 8 actants.
PARTICIPATION: dict[str, Any] = {
    "project_id": "budget-2027",
    "n_proposals": 3,
    "n_amendments": 2,
    "n_arguments": 4,
    "n_votes": 15,
    "n_actants": 8,
    "n_voters": 6,
}
TURNOUT = 0.75

# (id, project, article, created at, current revision)
PROPOSALS: tuple[tuple[str, str, str | None, str, str | None], ...] = (
    ("p-01", "budget-2027", "art-1", "2026-10-01T08:00:00Z", "p-01.r2"),
    ("p-02", "budget-2027", "art-1", "2026-10-02T08:00:00Z", None),
    ("p-03", "budget-2027", None, "2026-10-03T08:00:00Z", None),
    ("a-01", "budget-2027", None, "2026-10-04T08:00:00Z", None),
    ("a-02", "budget-2027", None, "2026-10-05T08:00:00Z", None),
)

# (id, proposal, number, affirmation, amendment whose adoption produced it)
REVISIONS: tuple[tuple[str, str, int, str, str | None], ...] = (
    ("p-01.r1", "p-01", 1, "Plant 100 trees in the parks.", None),
    ("p-01.r2", "p-01", 2, "Plant 150 trees in the parks.", "am-01"),
    ("p-02.r1", "p-02", 1, "Open the library on Sundays.", None),
    ("p-02.r2", "p-02", 2, "Open the library on Sundays and holidays.", None),
    ("p-03.r1", "p-03", 1, "Light the cycle paths at night.", None),
    ("a-01.r1", "a-01", 1, "Raise the number of trees to 150.", None),
    ("a-02.r1", "a-02", 1, "Open the library on holidays too.", None),
)

# The counts of each revision, from score -2 to score +2. p-03.r1 has no row.
VOTE_COUNTS: dict[str, list[int]] = {
    "p-01.r1": [0, 1, 0, 1, 0],
    "p-01.r2": [1, 0, 1, 2, 2],
    "p-02.r1": [0, 0, 1, 1, 0],
    "p-02.r2": [0, 1, 1, 1, 1],
    "a-01.r1": [0, 0, 0, 1, 2],
    "a-02.r1": [1, 1, 0, 0, 0],
}


def minimal_rows() -> dict[str, Any]:
    """Return fresh minimal rows: one Group, one Project and its participation."""
    return {
        "format": FORMAT,
        "as_of": AS_OF,
        "exposure": "aggregated",
        "groups": [{"id": "g-1", "slug": "demo-collective", "name": "Demo collective"}],
        "projects": [
            {
                "id": "budget-2027",
                "slug": "budget-2027",
                "name": "Budget participatif",
                "group_id": "g-1",
            }
        ],
        "participation": [dict(PARTICIPATION)],
    }


def reference_rows() -> dict[str, Any]:
    """Return fresh reference rows: two Groups, one Project and its five Proposals."""
    rows = minimal_rows()
    rows["groups"].append(
        {
            "id": "g-2",
            "slug": "budget-circle",
            "name": "Budget circle",
            "description": "Writes the participatory budget.",
            "parent_id": "g-1",
        }
    )
    rows["projects"][0]["group_id"] = "g-2"
    rows["projects"][0]["description"] = "Proposals for the budget of 2027."
    rows["proposals"] = [
        {
            "id": id,
            "project_id": project_id,
            "created_at": created_at,
            **({"article_id": article_id} if article_id else {}),
            **({"current_revision_id": current} if current else {}),
        }
        for id, project_id, article_id, created_at, current in PROPOSALS
    ]
    rows["revisions"] = [
        {
            "id": id,
            "proposal_id": proposal_id,
            "number": number,
            "affirmation": affirmation,
            "created_at": AS_OF,
            **({"amendment_id": amendment_id} if amendment_id else {}),
        }
        for id, proposal_id, number, affirmation, amendment_id in REVISIONS
    ]
    rows["vote_counts"] = [
        {"revision_id": revision_id, "counts": list(counts)}
        for revision_id, counts in VOTE_COUNTS.items()
    ]
    return rows
