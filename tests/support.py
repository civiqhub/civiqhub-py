# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""A small hand-written Project shared by the tests of the core.

Everything here is made up. It needs neither the analysis engine nor NumPy, so the
tests built on it run wherever the package installs.

    demo-collective (g-1)
      budget-circle (g-2)
      demo-project (demo)
        p-1   two revisions: r1, then r2 produced by the adoption of a-1
        p-2   one revision
        a-1   amendment to p-1 on r1, adopted
        a-2   amendment to p-2 on r1, open
        a-3   amendment to a-2, draft and stale, no vote
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from civiqhub.model import FORMAT

TOKEN = "civ_pat_synthetic0000"  # made up: no such token was ever issued

AS_OF = "2026-01-01T00:00:00Z"
MEMBERS = ("ps-ana", "ps-ben", "ps-chloe", "ps-dan")

# (member, revision, score)
VOTES: tuple[tuple[str, str, int], ...] = (
    ("ps-ana", "p-1.r1", 1),  # cast before a-1 was adopted: they stay on r1
    ("ps-ben", "p-1.r1", -1),
    ("ps-ana", "p-1.r2", 2),
    ("ps-ben", "p-1.r2", 1),
    ("ps-chloe", "p-1.r2", -2),
    ("ps-ana", "p-2.r1", 0),  # a chosen neutral, not an abstention
    ("ps-dan", "p-2.r1", -1),
    ("ps-ben", "a-1.r1", 2),
    ("ps-chloe", "a-1.r1", 2),
    ("ps-dan", "a-2.r1", -1),
)

# Shown without a vote: an abstention. Every other empty cell was not shown.
SHOWN_WITHOUT_VOTE: tuple[tuple[str, str], ...] = (
    ("ps-chloe", "p-2.r1"),
    ("ps-ana", "a-1.r1"),
)


def small_payload(*, impressions: bool = False) -> dict[str, Any]:
    """A fresh pseudonymised payload in the snapshot format; callers may change it."""
    counts: dict[str, list[int]] = {}
    for _, revision, score in VOTES:
        counts.setdefault(revision, [0, 0, 0, 0, 0])[score + 2] += 1
    payload: dict[str, Any] = {
        "format": FORMAT,
        "as_of": AS_OF,
        "exposure": "pseudonymised",
        "groups": [
            {"id": "g-1", "slug": "demo-collective", "name": "Demo collective"},
            {"id": "g-2", "slug": "budget-circle", "name": "Budget circle", "parent_id": "g-1"},
        ],
        "projects": [
            {"id": "demo", "slug": "demo-project", "name": "Demo project", "group_id": "g-1"}
        ],
        "proposals": [
            {
                "id": "p-1",
                "project_id": "demo",
                "author_id": "ps-ana",
                "current_revision_id": "p-1.r2",
            },
            {"id": "p-2", "project_id": "demo", "author_id": "ps-ben"},
            {"id": "a-1", "project_id": "demo", "author_id": "ps-ben"},
            {"id": "a-2", "project_id": "demo", "author_id": "ps-chloe"},
            {"id": "a-3", "project_id": "demo", "author_id": "ps-dan"},
        ],
        "revisions": [
            {  # listed before r1 on purpose: a snapshot orders revisions by number
                "id": "p-1.r2",
                "proposal_id": "p-1",
                "number": 2,
                "affirmation": "Synthetic proposal one, as amended",
                "amendment_id": "amd-1",
            },
            {
                "id": "p-1.r1",
                "proposal_id": "p-1",
                "number": 1,
                "affirmation": "Synthetic proposal one",
            },
            {"id": "p-2.r1", "proposal_id": "p-2", "affirmation": "Synthetic proposal two"},
            {"id": "a-1.r1", "proposal_id": "a-1", "affirmation": "Synthetic amendment to p-1"},
            {"id": "a-2.r1", "proposal_id": "a-2", "affirmation": "Synthetic amendment to p-2"},
            {"id": "a-3.r1", "proposal_id": "a-3", "affirmation": "Synthetic amendment to a-2"},
        ],
        "amendments": [
            {
                "id": "amd-1",
                "proposal_id": "a-1",
                "target_proposal_id": "p-1",
                "target_revision_id": "p-1.r1",
                "status": "adopted",
                "adopted_revision_id": "p-1.r2",
            },
            {
                "id": "amd-2",
                "proposal_id": "a-2",
                "target_proposal_id": "p-2",
                "target_revision_id": "p-2.r1",
            },
            {
                "id": "amd-3",
                "proposal_id": "a-3",
                "target_proposal_id": "a-2",
                "target_revision_id": "a-2.r1",
                "status": "draft",
                "stale": True,
            },
        ],
        "arguments": [
            {
                "id": "arg-1",
                "proposal_id": "p-1",
                "revision_id": "p-1.r2",
                "author_id": "ps-ana",
                "position": "pro",
                "text": "Synthetic argument one",
                "score": 2,
                "n_supports": 3,
            },
            {
                "id": "arg-2",
                "proposal_id": "p-1",
                "revision_id": "p-1.r2",
                "author_id": "ps-chloe",
                "position": "CON",
                "text": "Synthetic reply to argument one",
                "score": -2,
                "parent_id": "arg-1",
            },
            {
                "id": "arg-3",
                "proposal_id": "p-2",
                "author_id": "ps-dan",
                "position": "neutral",
                "text": "Synthetic argument three",
            },
        ],
        "tallies": [{"revision_id": r, "counts": c} for r, c in counts.items()],
        "participation": [{"project_id": "demo", "n_members": 4, "n_voters": 4}],
        "members": [
            {"pseudonym": "ps-ana", "kind": "human", "role": "participant"},
            {"pseudonym": "ps-ben", "kind": "human", "role": "moderator"},
            {"pseudonym": "ps-chloe"},
            {"pseudonym": "ps-dan", "kind": "agent", "role": "participant"},
        ],
        "votes": [{"member": m, "revision_id": r, "score": s} for m, r, s in VOTES],
    }
    if impressions:
        shown = [(member, revision) for member, revision, _ in VOTES] + list(SHOWN_WITHOUT_VOTE)
        payload["impressions"] = [{"member": m, "revision_id": r} for m, r in shown]
    return payload


def aggregated_payload() -> dict[str, Any]:
    """The same Project as the product serves it by default: counts, nobody behind them."""
    payload = small_payload()
    del payload["members"], payload["votes"]
    payload["exposure"] = "aggregated"
    for section in ("proposals", "arguments"):
        for row in payload[section]:
            del row["author_id"]
    return payload


class FakeApi:
    """A stand-in for the product API: it serves a payload page by page, in memory.

    It follows the provisional paths of ``ApiSource`` and records every URL asked.
    ``answers`` forces a status, by path, to play a refusal or an outage.
    """

    def __init__(
        self,
        payload: Mapping[str, Any],
        *,
        scope: str = "project",
        detailed: bool = True,
        page: int = 100,
        answers: Mapping[str, tuple[int, Mapping[str, str]]] | None = None,
    ) -> None:
        self.payload = payload
        self.scope = scope
        self.detailed = detailed
        self.page = page
        self.answers = dict(answers or {})
        self.calls: list[str] = []
        self.queries: list[dict[str, str]] = []

    def __call__(
        self, url: str, headers: Mapping[str, str]
    ) -> tuple[int, Mapping[str, str], bytes]:
        parsed = urlparse(url)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        self.calls.append(url)
        self.queries.append(query)
        if headers.get("Authorization") != f"Bearer {TOKEN}":
            return 401, {}, b"{}"
        path = parsed.path.removeprefix("/v1")
        if path in self.answers:
            status, answered = self.answers[path]
            return status, answered, b"{}"
        parts = path.strip("/").split("/")
        if parts == ["token"]:
            held = "g-1" if self.scope == "group" else "demo"
            return self._json({"kind": self.scope, "id": held, "as_of": "T0"})
        if parts[0] == "groups" and parts[1] == "g-1":
            if len(parts) == 2:
                return self._json(self.payload["groups"][0])
            return self._rows(self.payload["projects"], query)
        if parts[0] != "projects" or parts[1] != "demo":
            return 404, {}, b"{}"
        if len(parts) == 2:
            return self._json(self.payload["projects"][0])
        section = {"votes/aggregates": "tallies"}.get("/".join(parts[2:]), parts[2])
        if section in ("votes", "members") and not self.detailed:
            return 403, {}, b"{}"
        if section == "participation":
            return self._json(self.payload["participation"][0])
        return self._rows(self.payload[section], query)

    def _rows(
        self, rows: list[Any], query: Mapping[str, str]
    ) -> tuple[int, Mapping[str, str], bytes]:
        start = int(query.get("cursor", "0"))
        more = start + self.page < len(rows)
        return self._json(
            {
                "data": rows[start : start + self.page],
                "next_cursor": str(start + self.page) if more else None,
            }
        )

    @staticmethod
    def _json(body: Any) -> tuple[int, Mapping[str, str], bytes]:
        return 200, {}, json.dumps(body).encode()
