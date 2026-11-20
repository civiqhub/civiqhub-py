# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Hand-written rows of a small Project, shared by the tests of the model.

Everything here is made up: no row describes a real Group, Project or person. Each
ticket of the model adds the sections it builds.

    demo-collective (g-1)
      budget-circle (g-2)
        budget-2027: Budget participatif
          p-01  r1, then r2 (current_revision_id given), produced by the adoption of p-04
            p-04  amendment on p-01.r1, adopted
            p-05  amendment on p-01.r2, open
              p-06  amendment on p-05.r1, open and stale
          p-02  r1, then r2 (no current_revision_id: r2 is current)
          p-03  r1, without a row of vote counts

    Arguments on p-01, in two threads:
      arg-1          depth 0
        arg-2        depth 1
          arg-3      depth 2
      arg-4          depth 0
        arg-5        depth 1
        arg-6        depth 1

    At the pseudonymised level, four actants: the members m-001, m-002 and m-003, and
    the agent g-001. m-003 voted only on p-01.r1, the old revision of p-01; p-01.r2 was
    shown to m-003, who did not vote on it.

FakeApi serves such rows as the public API would, for the tests of ApiSource; it opens
no socket.
"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

from civiqhub.dataset import FORMAT
from civiqhub.sources import DEFAULT_URL

AS_OF = "2026-11-16T09:00:00Z"

#: The participation of the reference Project: 3 voters out of 4 actants.
PARTICIPATION: dict[str, Any] = {
    "project_id": "budget-2027",
    "n_proposals": 3,
    "n_amendments": 3,
    "n_arguments": 6,
    "n_votes": 12,
    "n_actants": 4,
    "n_voters": 3,
}
TURNOUT = 0.75

# (id, project, article, created at, current revision)
PROPOSALS: tuple[tuple[str, str, str | None, str, str | None], ...] = (
    ("p-01", "budget-2027", "art-1", "2026-10-01T08:00:00Z", "p-01.r2"),
    ("p-02", "budget-2027", "art-1", "2026-10-02T08:00:00Z", None),
    ("p-03", "budget-2027", None, "2026-10-03T08:00:00Z", None),
    ("p-04", "budget-2027", None, "2026-10-04T08:00:00Z", None),
    ("p-05", "budget-2027", None, "2026-10-05T08:00:00Z", None),
    ("p-06", "budget-2027", None, "2026-10-06T08:00:00Z", None),
)

# (id, proposal, number, affirmation, amendment whose adoption produced it)
REVISIONS: tuple[tuple[str, str, int, str, str | None], ...] = (
    ("p-01.r1", "p-01", 1, "Plant 100 trees in the parks.", None),
    ("p-01.r2", "p-01", 2, "Plant 150 trees in the parks.", "am-04"),
    ("p-02.r1", "p-02", 1, "Open the library on Sundays.", None),
    ("p-02.r2", "p-02", 2, "Open the library on Sundays and holidays.", None),
    ("p-03.r1", "p-03", 1, "Light the cycle paths at night.", None),
    ("p-04.r1", "p-04", 1, "Raise the number of trees to 150.", None),
    ("p-05.r1", "p-05", 1, "Plant the trees along the river.", None),
    ("p-06.r1", "p-06", 1, "Plant them on both banks.", None),
)

# The counts of each revision, from score -2 to score +2. p-03.r1 has no row.
VOTE_COUNTS: dict[str, list[int]] = {
    "p-01.r1": [0, 1, 0, 1, 0],
    "p-01.r2": [1, 0, 0, 1, 1],
    "p-02.r1": [0, 0, 1, 1, 0],
    "p-02.r2": [0, 1, 1, 1, 0],
    "p-04.r1": [0, 0, 0, 1, 2],
    "p-05.r1": [1, 1, 0, 0, 0],
    "p-06.r1": [0, 0, 1, 0, 0],
}

AMENDMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "am-04",
        "proposal_id": "p-04",
        "target_proposal_id": "p-01",
        "target_revision_id": "p-01.r1",
        "status": "adopted",
        "adopted_revision_id": "p-01.r2",
    },
    {
        "id": "am-05",
        "proposal_id": "p-05",
        "target_proposal_id": "p-01",
        "target_revision_id": "p-01.r2",
        "status": "OPEN",
    },
    {
        "id": "am-06",
        "proposal_id": "p-06",
        "target_proposal_id": "p-05",
        "target_revision_id": "p-05.r1",
        "status": "open",
        "stale": True,
    },
)

# The rows are not in depth-first order: the dataset puts them in it.
ARGUMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "arg-1",
        "proposal_id": "p-01",
        "revision_id": "p-01.r1",
        "position": "PRO",
        "text": "More shade in the summer.",
        "score": 2,
        "n_supports": 3,
    },
    {"id": "arg-4", "proposal_id": "p-01", "position": "con", "text": "The budget is tight."},
    {
        "id": "arg-2",
        "proposal_id": "p-01",
        "position": "Con",
        "text": "Trees take years to grow.",
        "parent_id": "arg-1",
    },
    {
        "id": "arg-5",
        "proposal_id": "p-01",
        "position": "pro",
        "text": "Trees cost little.",
        "parent_id": "arg-4",
    },
    {
        "id": "arg-6",
        "proposal_id": "p-01",
        "position": "neutral",
        "text": "It depends on the species.",
        "parent_id": "arg-4",
    },
    {
        "id": "arg-3",
        "proposal_id": "p-01",
        "position": "pro",
        "text": "Planting now helps later.",
        "parent_id": "arg-2",
    },
)


# (pseudonym, kind, role)
ACTANTS: tuple[tuple[str, str, str | None], ...] = (
    ("m-001", "human", "participant"),
    ("m-002", "human", "Moderator"),
    ("m-003", "human", None),
    ("g-001", "agent", "participant"),
)

# (actant, revision, score): they give the vote counts above, revision by revision.
VOTES: tuple[tuple[str, str, int], ...] = (
    ("m-001", "p-01.r1", 1),
    ("m-003", "p-01.r1", -1),
    ("m-001", "p-01.r2", 2),
    ("m-002", "p-01.r2", -2),
    ("g-001", "p-01.r2", 1),
    ("m-001", "p-02.r1", 0),
    ("m-002", "p-02.r1", 1),
    ("m-001", "p-02.r2", 1),
    ("m-002", "p-02.r2", 0),
    ("g-001", "p-02.r2", -1),
    ("m-001", "p-04.r1", 2),
    ("m-002", "p-04.r1", 2),
    ("g-001", "p-04.r1", 1),
    ("m-001", "p-05.r1", -2),
    ("m-002", "p-05.r1", -1),
    ("g-001", "p-06.r1", 0),
)

# The revisions shown to an actant. A vote counts as shown even when it is not listed.
IMPRESSIONS: tuple[tuple[str, str], ...] = (
    ("m-001", "p-01.r2"),
    ("m-003", "p-01.r2"),
    ("m-003", "p-02.r2"),
)

# The authors, at the pseudonymised level only.
AUTHORS: dict[str, str] = {
    "p-01": "m-001",
    "p-04": "m-002",
    "p-05": "m-003",
    "arg-1": "m-002",
    "arg-4": "g-001",
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
    """Return fresh reference rows: two Groups, one Project, its Proposals and Arguments."""
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
    rows["amendments"] = [dict(row) for row in AMENDMENTS]
    rows["arguments"] = [dict(row) for row in ARGUMENTS]
    return rows


def pseudonymised_rows(*, impressions: bool = True) -> dict[str, Any]:
    """Return fresh reference rows at the pseudonymised level, with actants and votes.

    Args:
        impressions: Whether the rows say which revisions were shown to which actants.
    """
    rows = reference_rows()
    rows["exposure"] = "pseudonymised"
    for section in ("proposals", "arguments"):
        for row in rows[section]:
            if row["id"] in AUTHORS:
                row["author_id"] = AUTHORS[row["id"]]
    rows["actants"] = [
        {"pseudonym": pseudonym, "kind": kind, **({"role": role} if role else {})}
        for pseudonym, kind, role in ACTANTS
    ]
    rows["votes"] = [
        {"actant": actant, "revision_id": revision_id, "score": score, "cast_at": AS_OF}
        for actant, revision_id, score in VOTES
    ]
    if impressions:
        rows["impressions"] = [
            {"actant": actant, "revision_id": revision_id} for actant, revision_id in IMPRESSIONS
        ]
    return rows


def api_rows(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return the reference rows as a token of the Group g-1 reads them from the API.

    The API lists the Projects of a Group, not its sub-groups: here, the reference
    Project sits right in g-1. The API records no impressions.

    Args:
        pseudonymised: Whether the rows are at the pseudonymised level.
    """
    rows = pseudonymised_rows(impressions=False) if pseudonymised else reference_rows()
    rows["groups"] = [group for group in rows["groups"] if group["id"] == "g-1"]
    rows["projects"][0]["group_id"] = "g-1"
    return rows


#: The fake token of the tests.
TOKEN = "civ_pat_test1234"

Answer = tuple[int, dict[str, str], bytes]


class FakeApi:
    """A fake of the public API: it serves rows, notes each request and opens no socket.

    It answers the paths of ``ApiSource.PATHS`` under ``DEFAULT_URL``. A path set in
    :attr:`answers` gets that answer instead; any other path gets a 404.

    Args:
        rows: The rows it serves, in the format of a dataset.
        kind: What the token covers: ``"group"`` or ``"project"``.
        container_id: The id of the Group or of the Project that the token covers.
        page_size: How many rows a page holds.
    """

    def __init__(
        self,
        rows: dict[str, Any],
        *,
        kind: str = "group",
        container_id: str = "g-1",
        page_size: int = 2,
    ) -> None:
        self.rows = rows
        self.kind = kind
        self.container_id = container_id
        self.page_size = page_size
        #: Each request, as (address, headers), in order.
        self.requests: list[tuple[str, dict[str, str]]] = []
        #: Forced answers, by path.
        self.answers: dict[str, Answer] = {}

    @property
    def paths(self) -> list[str]:
        """The path of each request, in order, without the base address and the query."""
        return [_split(url)[0] for url, _ in self.requests]

    def __call__(self, url: str, headers: Mapping[str, str]) -> Answer:
        self.requests.append((url, dict(headers)))
        path, query = _split(url)
        if path in self.answers:
            return self.answers[path]
        body = self._answer(path, query)
        if body is None:
            return 404, {}, b'{"error": "not_found"}'
        return 200, {"Content-Type": "application/json"}, json.dumps(body).encode()

    def _answer(self, path: str, query: dict[str, str]) -> Any:
        rows = self.rows
        if path == "/token":
            return {"kind": self.kind, "id": self.container_id, "as_of": rows["as_of"]}
        parts = path.strip("/").split("/")
        if parts[0] == "groups" and len(parts) >= 2:
            if len(parts) == 2:
                return _first(rows.get("groups", []), "id", parts[1])
            if parts[2:] == ["projects"]:
                projects = [row for row in rows["projects"] if row.get("group_id") == parts[1]]
                return self._page(projects, query)
        if parts[0] == "projects" and len(parts) >= 2:
            project_id, rest = parts[1], "/".join(parts[2:])
            if not rest:
                return _first(rows["projects"], "id", project_id)
            if rest == "participation":
                return _first(rows.get("participation", []), "project_id", project_id)
            proposals = [
                row for row in rows.get("proposals", []) if row["project_id"] == project_id
            ]
            ids = {row["id"] for row in proposals}
            revisions = [row for row in rows.get("revisions", []) if row["proposal_id"] in ids]
            revision_ids = {row["id"] for row in revisions}
            sections = {
                "proposals": proposals,
                "revisions": revisions,
                "amendments": [
                    row for row in rows.get("amendments", []) if row["proposal_id"] in ids
                ],
                "arguments": [
                    row for row in rows.get("arguments", []) if row["proposal_id"] in ids
                ],
                "votes/aggregates": [
                    row for row in rows.get("vote_counts", []) if row["revision_id"] in revision_ids
                ],
                "votes": [
                    row for row in rows.get("votes", []) if row["revision_id"] in revision_ids
                ],
                "actants": rows.get("actants", []),
            }
            if rest in sections:
                return self._page(sections[rest], query)
        return None

    def _page(self, items: list[Any], query: dict[str, str]) -> dict[str, Any]:
        start = int(query.get("cursor", "0"))
        end = start + self.page_size
        page: dict[str, Any] = {"data": items[start:end]}
        if end < len(items):
            page["next_cursor"] = str(end)
        return page


def _split(url: str) -> tuple[str, dict[str, str]]:
    parts = urlsplit(url)
    base = urlsplit(DEFAULT_URL).path
    query = {key: values[0] for key, values in parse_qs(parts.query).items()}
    return parts.path.removeprefix(base), query


def _first(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get(key) == value), None)
