# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Hand-written rows of a small Project, shared by the tests of the model.

Everything here is made up: no row describes a real Group, Project or person. Each
ticket of the model adds the sections it builds.

    demo-collective (g-1)
      budget-circle (g-2)
        budget-2027: Budget participatif
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
    "n_votes": 30,
    "n_actants": 8,
    "n_voters": 6,
}
TURNOUT = 0.75


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
    """Return fresh reference rows: two Groups, one inside the other, and one Project."""
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
    return rows
