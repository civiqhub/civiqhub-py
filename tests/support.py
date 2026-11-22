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

    Articles, by position: art-1 (versions 1 to 3, the third in force), then art-2
    (version 1). Their rows come in another order; see article_rows().
    The current version of art-1 has five paragraphs, in two levels of headings and
    three; p-01 and p-02 are placed in its paragraph 1.1. See paragraph_rows().
    art-2 cites p-01 and p-03, and a Proposal of another Project; art-1 cites p-03.
    See citation_rows().

    At the pseudonymised level, four actants: the members m-001, m-002 and m-003, and
    the agent g-001. m-003 voted only on p-01.r1, the old revision of p-01; p-01.r2 was
    shown to m-003, who did not vote on it.

FakeApi serves such rows as the public API would, for the tests of ApiSource; it opens
no socket.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
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


# The articles of the reference Project. Their rows are not in the order of their
# positions: the Project puts them in it. art-1 is in its third version.
ARTICLES: tuple[dict[str, Any], ...] = (
    {
        "id": "art-2",
        "project_id": "budget-2027",
        "position": 2,
        "title": "Culture",
        "current_version_number": 1,
        "published_at": "2026-10-20T08:00:00Z",
    },
    {
        "id": "art-1",
        "project_id": "budget-2027",
        "position": 1,
        "title": "Green spaces",
        "description": "Trees, parks and gardens.",
        "current_version_number": 3,
        "published_at": "2026-11-10T08:00:00Z",
    },
)

# (article, number, title, body, published at). The rows of art-1 are not in order.
ARTICLE_VERSIONS: tuple[tuple[str, int, str, str, str], ...] = (
    ("art-1", 2, "Green spaces", "Second version on green spaces.", "2026-10-15T08:00:00Z"),
    ("art-1", 1, "Parks", "First version on parks.", "2026-10-01T08:00:00Z"),
    ("art-2", 1, "Culture", "First version on culture.", "2026-10-20T08:00:00Z"),
    ("art-1", 3, "Green spaces", "Third version on green spaces.", "2026-11-10T08:00:00Z"),
)


# (article, version, paragraph id, level, number, title), in the order of the text of each
# version. In version 2 of art-1, one id carries the prefix of the anchors, which is left
# out when it is read; art-2 gives its number as an integer.
PARAGRAPHS: tuple[tuple[str, int, str, int, str | int, str], ...] = (
    ("art-1", 3, "3f2a", 1, "1", "Trees"),
    ("art-1", 3, "8c1d", 2, "1.1", "Parks"),
    ("art-1", 3, "9e0b", 2, "1.2", "Streets"),
    ("art-1", 3, "a7c4", 3, "1.2.1", "Avenues"),
    ("art-1", 3, "b5d2", 1, "2", "Water"),
    ("art-2", 1, "c0f1", 1, 1, "Culture"),
    ("art-1", 2, "3f2a", 1, "1", "Trees"),
    ("art-1", 2, "p-8c1d", 2, "1.1", "Parks"),
)

# (proposal, article, version, paragraph id or None outside any, rank). p-03 and the
# Amendments have no parent article: they are not placed.
PLACEMENTS: tuple[tuple[str, str, int, str | None, int], ...] = (
    ("p-01", "art-1", 3, "8c1d", 1),
    ("p-02", "art-1", 3, "8c1d", 0),
    ("p-01", "art-1", 2, "p-8c1d", 0),
    ("p-02", "art-1", 2, None, 0),
)


# (cited proposal, citing article, version, paragraph id or None, rank). art-2 cites p-01,
# whose parent is art-1, and p-03, a Proposal of a Group; ext-7 belongs to a Project that
# the rows do not hold. Version 2 of art-1 cited p-03 too.
CITATIONS: tuple[tuple[str, str, int, str | None, int], ...] = (
    ("ext-7", "art-2", 1, "c0f1", 1),
    ("p-01", "art-2", 1, "c0f1", 0),
    ("p-03", "art-2", 1, None, 0),
    ("p-03", "art-1", 3, "b5d2", 0),
    ("p-03", "art-1", 2, "3f2a", 0),
)


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


def article_rows(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return fresh reference rows with the articles of the Project and their versions.

    Args:
        pseudonymised: Whether the rows are at the pseudonymised level.
    """
    rows = pseudonymised_rows() if pseudonymised else reference_rows()
    rows["articles"] = [dict(row) for row in ARTICLES]
    rows["article_versions"] = [
        {
            "article_id": article_id,
            "version_number": number,
            "title": title,
            "body": body,
            "published_at": published_at,
        }
        for article_id, number, title, body, published_at in ARTICLE_VERSIONS
    ]
    return rows


def paragraph_rows(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return fresh article rows with the paragraphs of the versions and the placements.

    Args:
        pseudonymised: Whether the rows are at the pseudonymised level.
    """
    rows = article_rows(pseudonymised=pseudonymised)
    rows["paragraphs"] = [
        {
            "article_id": article_id,
            "version_number": version_number,
            "paragraph_id": paragraph_id,
            "level": level,
            "number": number,
            "title": title,
        }
        for article_id, version_number, paragraph_id, level, number, title in PARAGRAPHS
    ]
    rows["placements"] = [
        {
            "proposal_id": proposal_id,
            "article_id": article_id,
            "version_number": version_number,
            "rank": rank,
            **({"paragraph_id": paragraph_id} if paragraph_id is not None else {}),
        }
        for proposal_id, article_id, version_number, paragraph_id, rank in PLACEMENTS
    ]
    return rows


def citation_rows(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return fresh paragraph rows with the citations of Proposals in the articles.

    Args:
        pseudonymised: Whether the rows are at the pseudonymised level.
    """
    rows = paragraph_rows(pseudonymised=pseudonymised)
    rows["citations"] = [
        {
            "proposal_id": proposal_id,
            "article_id": article_id,
            "version_number": version_number,
            "rank": rank,
            **({"paragraph_id": paragraph_id} if paragraph_id is not None else {}),
        }
        for proposal_id, article_id, version_number, paragraph_id, rank in CITATIONS
    ]
    return rows


#: The rows of amendments that an old dataset adds: a creation, a removal and a pending
#: change, none of which builds an Amendment. am-07, a REMOVE written from p-03, produced
#: the revision p-02.r2.
OLD_AMENDMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "pc-1",
        "proposal_id": "p-02",
        "item_type": "PENDING_CREATE",
        "type": "CREATE",
        "change_type": "CREATE",
        "status": "ADOPTED",
    },
    {
        "id": "pc-2",
        "proposal_id": "p-01",
        "item_type": "PENDING_REMOVE",
        "type": "REMOVE",
        "change_type": "REMOVE",
        "status": "OPEN",
    },
    {
        "id": "am-07",
        "proposal_id": "p-03",
        "type": "REMOVE",
        "target_proposal_id": "p-02",
        "status": "ADOPTED",
    },
)

#: The marks of old_rows(), in the order of the sections and of the rows:
#: (section, index, row id, key, value).
OLD_MARKS: tuple[tuple[str, int, str, str, str], ...] = (
    ("projects", 0, "budget-2027", "parent_project_id", "budget-2026"),
    ("proposals", 2, "p-03", "parent_root_id", "p-00"),
    ("amendments", 0, "am-04", "kind", "SYNC"),
    ("amendments", 0, "am-04", "originating_project_id", "budget-2026"),
    ("amendments", 1, "am-05", "status", "DRAFT"),
    ("amendments", 3, "pc-1", "type", "CREATE"),
    ("amendments", 3, "pc-1", "change_type", "CREATE"),
    ("amendments", 3, "pc-1", "item_type", "PENDING_CREATE"),
    ("amendments", 4, "pc-2", "type", "REMOVE"),
    ("amendments", 4, "pc-2", "change_type", "REMOVE"),
    ("amendments", 4, "pc-2", "item_type", "PENDING_REMOVE"),
    ("amendments", 5, "am-07", "type", "REMOVE"),
)


def old_rows() -> dict[str, Any]:
    """Return fresh reference rows of an old dataset, with the values the model deprecated.

    The Project was forked from ``budget-2026``, and p-03 derives from ``p-00``. The
    amendment am-04 is a cascade of kind ``SYNC`` from ``budget-2026``, and am-05 is a
    ``DRAFT``. The rows of :data:`OLD_AMENDMENTS` follow. :data:`OLD_MARKS` lists what a
    dataset marks.
    """
    rows = reference_rows()
    rows["projects"][0]["parent_project_id"] = "budget-2026"
    by_id = {row["id"]: row for row in rows["proposals"]}
    by_id["p-03"]["parent_root_id"] = "p-00"
    amendments = {row["id"]: row for row in rows["amendments"]}
    amendments["am-04"].update(
        kind="SYNC",
        type="UPDATE",
        item_type="PROPOSAL_AMENDMENT",
        originating_project_id="budget-2026",
    )
    amendments["am-05"]["status"] = "DRAFT"
    rows["amendments"].extend(dict(row) for row in OLD_AMENDMENTS)
    revisions = {row["id"]: row for row in rows["revisions"]}
    revisions["p-02.r2"]["amendment_id"] = "am-07"
    return rows


def api_rows(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return the reference rows as a token of the Group g-1 reads them from the API.

    The API lists the Projects of a Group, not its sub-groups: here, the reference
    Project sits right in g-1. The API records no impressions. The articles are those of
    :func:`citation_rows`, as the routes of the contract give them back: in the order of
    the positions and of the versions, the ids of the paragraphs without prefix, their
    numbers as text, and the blocks of each version in the order of its text.

    Args:
        pseudonymised: Whether the rows are at the pseudonymised level.
    """
    rows = pseudonymised_rows(impressions=False) if pseudonymised else reference_rows()
    rows["groups"] = [group for group in rows["groups"] if group["id"] == "g-1"]
    rows["projects"][0]["group_id"] = "g-1"
    rows.update(_api_articles(citation_rows()))
    return rows


def _bare(paragraph_id: str | None) -> str | None:
    return None if paragraph_id is None else paragraph_id.removeprefix("p-")


def _api_articles(rows: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return the article sections of rows as ApiSource reads them back."""
    found: dict[str, list[dict[str, Any]]] = {
        "articles": [],
        "article_versions": [],
        "paragraphs": [],
        "placements": [],
        "citations": [],
    }
    for article in sorted(rows["articles"], key=lambda row: row["position"]):
        found["articles"].append(dict(article))
        versions = [row for row in rows["article_versions"] if row["article_id"] == article["id"]]
        for version in sorted(versions, key=lambda row: row["version_number"]):
            found["article_versions"].append(dict(version))
            for row in _version_paragraphs(rows, version):
                found["paragraphs"].append({**row, "paragraph_id": _bare(row["paragraph_id"])})
                found["paragraphs"][-1]["number"] = str(row["number"])
            for section, block in _version_blocks(rows, version):
                bare = _bare(block.get("paragraph_id"))
                found[section].append(
                    {
                        **{key: value for key, value in block.items() if key != "paragraph_id"},
                        **({"paragraph_id": bare} if bare is not None else {}),
                    }
                )
    return found


def _version_paragraphs(rows: dict[str, Any], version: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows.get("paragraphs", [])
        if (row["article_id"], row["version_number"])
        == (version["article_id"], version["version_number"])
    ]


def _version_blocks(
    rows: dict[str, Any], version: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """Return the placements and citations of a version, in the order of its text."""
    order = {
        _bare(row["paragraph_id"]): index
        for index, row in enumerate(_version_paragraphs(rows, version))
    }
    blocks = [
        (section, row)
        for section in ("placements", "citations")
        for row in rows.get(section, [])
        if (row["article_id"], row["version_number"])
        == (version["article_id"], version["version_number"])
    ]
    return sorted(
        blocks,
        key=lambda pair: (
            -1 if pair[1].get("paragraph_id") is None else order[_bare(pair[1]["paragraph_id"])],
            pair[1]["rank"],
        ),
    )


#: The routes and fields of the contract of the API that ApiSource reads, extracted by
#: tests/contract/extract.py. The fake API serves its articles from it.
CONTRACT: dict[str, Any] = json.loads(
    (Path(__file__).parent / "contract" / "articles.json").read_text(encoding="utf-8")
)


def contract_route(path: str) -> tuple[str, dict[str, str]] | None:
    """Return the operation of the contract that a path names, and its path parameters."""
    for name, route in CONTRACT["routes"].items():
        pattern = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", route["path"]) + "$"
        found = re.match(pattern, path)
        if found:
            return name, found.groupdict()
    return None


def conforms(value: Any, field: Mapping[str, Any]) -> bool:
    """Whether a value has the type that the contract gives a field or an answer."""
    if value is None:
        return bool(field.get("nullable"))
    if "schema" in field:
        schema = CONTRACT["schemas"][field["schema"]]
        return (
            isinstance(value, dict)
            and set(value) <= set(schema)
            and all(key in value for key, spec in schema.items() if spec["required"])
            and all(conforms(value[key], schema[key]) for key in value)
        )
    kind = field["type"]
    if kind == "array":
        return isinstance(value, list) and all(conforms(item, field["items"]) for item in value)
    if kind == "object":
        properties = field.get("properties", {})
        return (
            isinstance(value, dict)
            and set(value) <= set(properties)
            and all(key in value for key in field.get("required", []))
            and all(conforms(value[key], properties[key]) for key in value)
        )
    valid = {
        "string": isinstance(value, str),
        "number": isinstance(value, int | float) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }[kind]
    return valid and value in field.get("enum", [value])


#: The fake token of the tests.
TOKEN = "civ_pat_test1234"

Answer = tuple[int, dict[str, str], bytes]


class FakeApi:
    """A fake of the public API: it serves rows, notes each request and opens no socket.

    It answers the paths of ``ApiSource.PATHS`` under ``DEFAULT_URL``. A path set in
    :attr:`answers` gets that answer instead; any other path gets a 404.

    The routes of the articles are those of :data:`CONTRACT`. Their answers are built
    from the rows in the shape of the contract and checked against it, and a query
    parameter that the contract does not give the route gets a 422.

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
        route = contract_route(path)
        if route is not None:
            name, parameters = route
            allowed = CONTRACT["routes"][name]["query_parameters"]
            if not set(query) <= set(allowed) or not all(
                value.isdigit()
                and allowed[key].get("minimum", 0)
                <= int(value)
                <= allowed[key].get("maximum", int(value))
                for key, value in query.items()
            ):
                return 422, {}, b'{"error": "unprocessable"}'
            body = self._contract_answer(name, parameters, query)
            if body is not None:
                assert conforms(body, CONTRACT["routes"][name]["answer"]), (name, body)
        else:
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

    def _contract_answer(self, name: str, parameters: dict[str, str], query: dict[str, str]) -> Any:
        rows = self.rows
        project_id = parameters["projectId"]
        page = int(query.get("page", "1"))
        size = min(int(query.get("limit", "10")), self.page_size)
        articles = sorted(
            (row for row in rows.get("articles", []) if row["project_id"] == project_id),
            key=lambda row: row["position"],
        )
        if name == "listProjectArticles":
            return self._offset([{"id": row["id"]} for row in articles], page, size)
        article = next((row for row in articles if row["id"] == parameters["articleId"]), None)
        if article is None:
            return None
        versions = sorted(
            (row for row in rows.get("article_versions", []) if row["article_id"] == article["id"]),
            key=lambda row: -row["version_number"],
        )
        if name == "listArticleVersions":
            items = [
                {"versionNumber": row["version_number"], "publishedAt": row["published_at"]}
                for row in versions
            ]
            return self._offset(items, page, size)
        number = parameters["versionNumber"]
        version = next((row for row in versions if str(row["version_number"]) == number), None)
        if version is None:
            return None
        return {
            "title": version["title"],
            "description": article.get("description"),
            "body": version["body"],
            "publishedAt": version["published_at"],
            "outline": [
                {
                    "paragraphId": _bare(row["paragraph_id"]),
                    "level": row["level"],
                    "number": str(row["number"]),
                    "title": row["title"],
                }
                for row in _version_paragraphs(rows, version)
            ],
            "proposalBlocks": [
                {
                    "proposalId": row["proposal_id"],
                    "role": "PARENT" if section == "placements" else "CITATION",
                    "paragraphId": _bare(row.get("paragraph_id")),
                }
                for section, row in _version_blocks(rows, version)
            ],
        }

    def _offset(self, items: list[Any], page: int, size: int) -> dict[str, Any]:
        start = (page - 1) * size
        return {
            "items": items[start : start + size],
            "meta": {"hasNextPage": start + size < len(items)},
        }

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
