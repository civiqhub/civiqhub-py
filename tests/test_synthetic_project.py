# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The business SDK on a synthetic Project: navigation, exposure, sources, analysis.

The 23 tests of the v6 prototype, as they were. The synthetic Project comes from the
generator of the analysis engine, so the whole module is skipped where the engine or
NumPy is not installed. The core is tested without them in the other test modules.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

import civiqhub

pytest.importorskip("numpy", reason="the synthetic Project needs NumPy, which is not installed")
pytest.importorskip(
    "civiqhub_selene.blocks",
    reason="the synthetic Project needs the analysis engine (civiqhub_selene), not installed",
)

from civiqhub.synthetic import synthetic_payload

TOKEN = "civ_pat_synthetic0000"


@pytest.fixture(scope="module")
def project() -> civiqhub.Project:
    return civiqhub.synthetic_project()


@pytest.fixture(scope="module")
def analysis(project: civiqhub.Project) -> civiqhub.Coclustering:
    return project.cocluster(groups=3, blocks=2)


def fake_api(payload: dict[str, Any], *, detailed: bool = True, page: int = 100) -> Any:
    """A stand-in for the product API that serves a payload page by page."""
    calls: list[str] = []

    def transport(url: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], bytes]:
        calls.append(url)
        if headers.get("Authorization") != f"Bearer {TOKEN}":
            return 401, {}, b"{}"
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        parts = parsed.path.removeprefix("/v1").strip("/").split("/")
        if parts == ["token"]:
            return 200, {}, json.dumps({"kind": "project", "id": "demo", "as_of": "T0"}).encode()
        if parts[0] != "projects" or parts[1] != "demo":
            return 404, {}, b"{}"
        if len(parts) == 2:
            return 200, {}, json.dumps(payload["projects"][0]).encode()
        section = {"votes/aggregates": "tallies"}.get("/".join(parts[2:]), parts[2])
        if section in ("votes", "members") and not detailed:
            return 403, {}, b"{}"
        if section == "participation":
            return 200, {}, json.dumps(payload["participation"][0]).encode()
        start = int(query.get("cursor", ["0"])[0])
        rows = payload[section][start : start + page]
        more = start + page < len(payload[section])
        body = {"data": rows, "next_cursor": str(start + page) if more else None}
        return 200, {}, json.dumps(body).encode()

    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def test_three_lines_from_a_token_to_a_project() -> None:
    payload, _ = synthetic_payload()
    source = civiqhub.ApiSource(TOKEN, transport=fake_api(payload))
    project = civiqhub.connect(source=source, exposure="pseudonymised").project()
    assert len(project.proposals) == 14
    assert len(project.votes) == len(payload["votes"])
    assert project.as_of == "T0"
    assert TOKEN not in repr(source)
    assert TOKEN not in project.snapshot.source


def test_the_api_source_only_reads_what_the_exposure_allows() -> None:
    payload, _ = synthetic_payload()
    transport = fake_api(payload, detailed=False)
    aggregated = civiqhub.connect(source=civiqhub.ApiSource(TOKEN, transport=transport)).project()
    assert aggregated.proposals["p-01"].tally.total == 28
    assert not any("/members" in url or url.endswith("/votes") for url in transport.calls)
    refused = civiqhub.connect(
        source=civiqhub.ApiSource(TOKEN, transport=transport), exposure="pseudonymised"
    )
    with pytest.raises(civiqhub.ExposureError, match="administrator"):
        refused.project()


def test_token_errors_say_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIVIQHUB_TOKEN", raising=False)
    with pytest.raises(civiqhub.AuthenticationError, match="CIVIQHUB_TOKEN"):
        civiqhub.connect()
    with pytest.raises(civiqhub.AuthenticationError, match="civ_pat_"):
        civiqhub.connect("not-a-token")
    payload, _ = synthetic_payload()
    wrong = civiqhub.ApiSource("civ_pat_revoked", transport=fake_api(payload))
    with pytest.raises(civiqhub.AuthenticationError, match="expired or revoked"):
        civiqhub.connect(source=wrong).project()


def test_navigation_follows_the_product_grammar(project: civiqhub.Project) -> None:
    proposal = project.proposals["p-01"]
    assert [r.number for r in proposal.revisions] == [1, 2]
    assert proposal.current.is_current
    assert not proposal.revisions[0].is_current
    assert proposal.project == project
    assert project.group is not None
    assert project.group.projects == civiqhub.Listing([project])
    vote = proposal.votes[0]
    assert vote.revision == proposal.current
    assert vote.proposal == proposal
    assert vote in vote.member.votes
    assert vote.member.vote_on(proposal) == vote
    assert all(v.revision_id == "p-01.r1" for v in proposal.revisions[0].votes)
    assert proposal.tally == civiqhub.VoteTally.of(v.score for v in proposal.votes)
    reply = proposal.arguments["arg-4"]
    assert reply.parent == proposal.arguments["arg-1"]
    assert reply.depth == 1
    assert reply in proposal.arguments["arg-1"].replies


def test_an_amendment_is_a_proposal_that_targets_another(project: civiqhub.Project) -> None:
    adopted, pending = project.amendments
    assert isinstance(adopted, civiqhub.Proposal)
    assert adopted.is_amendment
    assert adopted in project.proposals
    assert adopted.target == project.proposals["p-01"]
    assert adopted.target_revision.number == 1
    assert adopted.is_adopted
    assert adopted.adopted_revision == adopted.target.current
    assert adopted.adopted_revision is not None
    assert adopted.adopted_revision.from_amendment == adopted
    assert adopted.votes  # it receives votes like any proposal
    assert pending.status is civiqhub.AmendmentStatus.OPEN
    assert pending.adopted_revision is None
    assert [(d, p.id) for d, p in adopted.target.walk()] == [(0, "p-01"), (1, "a-01")]
    assert len(project.proposals.where(is_amendment=False)) == 12


def test_a_vote_tally_is_a_mapping_over_the_five_scores() -> None:
    tally = civiqhub.VoteTally.of([2, 2, 1, -2])
    assert dict(tally) == {-2: 1, -1: 0, 0: 0, 1: 1, 2: 2}
    assert tally.total == 4
    assert tally.shares == (0.25, 0.0, 0.0, 0.25, 0.5)
    assert not hasattr(tally, "mean")  # no formula lives in the SDK
    assert not hasattr(tally, "entropy")
    assert (tally + tally)[2] == 4
    with pytest.raises(KeyError, match="-2 to \\+2"):
        tally[3]


def test_an_empty_cell_is_never_a_vote() -> None:
    blind = civiqhub.synthetic_project()
    member, proposal = next(
        (m, p) for m in blind.members for p in blind.proposals if m.vote_on(p) is None
    )
    assert member.state_on(proposal) is civiqhub.CellState.UNKNOWN
    seen = civiqhub.synthetic_project(impressions=True)
    states = {m.state_on(p) for m in seen.members for p in seen.proposals}
    assert states == {
        civiqhub.CellState.VOTED,
        civiqhub.CellState.ABSTAINED,
        civiqhub.CellState.NOT_SHOWN,
    }
    matrix = seen.vote_matrix()
    assert matrix.n_shown < matrix.levels.size
    assert matrix.n_voted == blind.vote_matrix().n_voted


def test_aggregated_snapshots_hold_counts_and_nothing_about_who(tmp_path: Path) -> None:
    project = civiqhub.synthetic_project(exposure="aggregated")
    assert project.proposals["p-02"].tally.total > 0
    assert project.participation.n_members == 48
    assert project.proposals["p-02"].author is None
    assert "m-0" not in json.dumps(project.snapshot.to_payload())
    for read in (lambda: project.votes, lambda: project.members, project.cocluster):
        with pytest.raises(civiqhub.ExposureError, match="pseudonymised"):
            read()
    payload, _ = synthetic_payload()
    with pytest.raises(civiqhub.ValidationError, match="aggregated snapshot"):
        civiqhub.Snapshot({**payload, "exposure": "aggregated"})


def test_a_saved_snapshot_replays_identically(tmp_path: Path, project: civiqhub.Project) -> None:
    path = project.save(tmp_path / "demo.json")
    again = civiqhub.load(path).project()
    assert again.snapshot.fingerprint() == project.snapshot.fingerprint()
    assert again.proposals.ids == project.proposals.ids
    replay = civiqhub.connect(source=civiqhub.FileSource(path), exposure="pseudonymised")
    assert replay.project("demo-project") == project
    with pytest.raises(civiqhub.NotFoundError, match="demo-project"):
        replay.project("budget")


def test_invariants_are_checked_at_the_door() -> None:
    payload, _ = synthetic_payload()
    bad = json.loads(json.dumps(payload))
    bad["votes"][0]["score"] = 3
    with pytest.raises(civiqhub.ValidationError, match="-2 to \\+2"):
        civiqhub.Snapshot(bad)
    bad = json.loads(json.dumps(payload))
    bad["votes"].append(dict(bad["votes"][0]))
    with pytest.raises(civiqhub.ValidationError, match="two votes"):
        civiqhub.Snapshot(bad)
    with pytest.raises(civiqhub.ValidationError, match="not a CiviqHub snapshot"):
        civiqhub.Snapshot({"format": "other"})


def test_coclustering_speaks_in_members_and_proposals(
    project: civiqhub.Project, analysis: civiqhub.Coclustering
) -> None:
    _, truth = synthetic_payload()
    assert len(analysis.groups) == 3
    assert len(analysis.blocks) == 2
    assert sum(len(g) for g in analysis.groups) == 48
    for block in analysis.blocks:
        assert len({truth["blocks"][p.id] for p in block}) == 1
    agreeing = sum(
        max(sum(truth["groups"][m.id] == q for m in group) for q in range(3))
        for group in analysis.groups
    )
    assert agreeing >= 45
    member = project.members["m-001"]
    group = analysis.group_of(member)
    assert member in group
    assert isinstance(group & set(project.members), frozenset)
    assert sum(analysis.memberships_of(member)) == pytest.approx(1.0)
    block = analysis.block_of("p-01")
    assert project.proposals["p-01"] in block
    stance = analysis[group, block]
    assert stance.votes == block.votes_of(group)
    assert stance.tally.total == len(stance.votes)
    assert stance.typical_score in (-2, -1, 0, 1, 2)
    assert sum(stance.shares) == pytest.approx(1.0)
    assert len(list(analysis.stances())) == 6


def test_every_result_can_be_cited_and_recomputed(
    project: civiqhub.Project, analysis: civiqhub.Coclustering
) -> None:
    citation = analysis.citation
    assert citation.snapshot == project.snapshot.fingerprint()
    assert citation.as_of == project.as_of
    assert citation.seed == 0
    assert (citation.method, citation.version) == ("latent_block_cem", "0.1.0")
    assert citation.parameters["n_groups"] == 3
    assert "numpy" in citation.dependencies
    assert citation.computation == analysis.engine.fingerprint()
    assert not citation.impressions_recorded
    assert analysis.is_available()
    assert analysis.unavailable is None
    again = project.cocluster(groups=3, blocks=2)
    assert [g.members.ids for g in again.groups] == [g.members.ids for g in analysis.groups]
    assert "impressions are not recorded" in analysis.summary()


def test_consensus_ranks_proposals_across_the_opinion_groups(
    project: civiqhub.Project, analysis: civiqhub.Coclustering
) -> None:
    ranking = project.consensus(across=analysis)
    assert len(ranking) == 14
    best, score = ranking[0]
    assert isinstance(best, civiqhub.Proposal)
    assert score == max(ranking.scores)
    assert ranking.score_of(best) == score
    assert ranking.citation.method != analysis.citation.method


def test_an_analysis_the_project_cannot_carry_says_why() -> None:
    payload, _ = synthetic_payload()
    payload = {**payload, "votes": [], "impressions": None}
    project = civiqhub.connect(
        source=civiqhub.MemorySource(payload), exposure="pseudonymised"
    ).project()
    analysis = project.cocluster()
    assert isinstance(analysis, civiqhub.Coclustering)
    assert not analysis.is_available()
    assert analysis.unavailable is not None
    assert analysis.unavailable.reason == "no_votes"
    assert analysis.groups == ()
    assert repr(analysis) == "Coclustering(unavailable: no_votes, project 'demo-project')"
    assert analysis.summary().startswith(
        "no co-clustering of project 'demo-project': unavailable (no_votes)"
    )
    assert analysis.citation.method == "latent_block_cem"  # absence keeps its provenance
    with pytest.raises(civiqhub.UnavailableError, match="no_votes") as absent:
        analysis[0, 0]
    assert isinstance(absent.value, LookupError)
    assert "is_available" in absent.value.__notes__[0]
    with pytest.raises(civiqhub.UnavailableError):
        project.consensus(across=analysis)


def test_errors_carry_a_next_step_and_a_standard_base() -> None:
    with pytest.raises(LookupError) as missing:
        civiqhub.synthetic_project().proposals["nope"]
    assert missing.value.__notes__  # the note says what to do
    assert issubclass(civiqhub.ValidationError, ValueError)
    assert issubclass(civiqhub.MissingExtraError, ImportError)
    assert not issubclass(civiqhub.ExposureError, OSError)
    with pytest.raises(TypeError, match="must declare a class attribute `hint`"):
        type("Silent", (civiqhub.CiviqHubError,), {})


def _python(code: str) -> str:
    import subprocess
    import sys

    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def test_the_sdk_imports_without_the_analysis_layer() -> None:
    out = _python(
        "import sys, civiqhub\n"
        "print('civiqhub_selene' in sys.modules, 'numpy' in sys.modules, "
        "'civiqhub.analysis' in sys.modules)"
    )
    assert out == "False False False"


def test_asking_for_an_analysis_without_the_extra_gives_the_command() -> None:
    out = _python(
        "import sys, json, civiqhub\n"
        "sys.modules['civiqhub_selene'] = None\n"
        "payload = {'format': 'civiqhub.snapshot/0', 'as_of': 'T0', 'exposure': 'pseudonymised',\n"
        "  'projects': [{'id': 'p', 'slug': 'p', 'title': 'P'}], 'members': [], 'votes': []}\n"
        "project = civiqhub.connect(source=civiqhub.MemorySource(payload),\n"
        "  exposure='pseudonymised').project()\n"
        "print(len(project.proposals))\n"
        "try:\n"
        "    project.cocluster()\n"
        "except ImportError as error:\n"
        "    print(type(error).__name__, '|', error.__notes__[0])\n"
    )
    assert out.splitlines() == [
        "0",
        'MissingExtraError | Install it with: pip install "civiqhub[selene]"',
    ]


# -- collective regimes -----------------------------------------------------------------


def test_every_proposal_has_a_collective_regime(project: civiqhub.Project) -> None:
    regimes = project.regimes()
    assert len(regimes) == 14
    assert len(regimes.available()) == 14
    first = regimes["p-01"]
    assert isinstance(first, civiqhub.ProposalRegime)
    assert first.proposal == project.proposals["p-01"]
    assert first.revision == first.proposal.current
    assert first.label in ("C-2", "C-1", "C0", "C+1", "C+2", "M", "D")
    assert 0.0 <= first.omega <= 1.0
    assert sum(first.contributions) == pytest.approx(first.omega)
    assert first.tally == first.proposal.tally
    assert first.reading.dissensus.n == first.tally.total
    assert regimes[project.proposals["p-01"]] is first
    assert sum(len(regimes.labelled(label)) for label in ("C+2", "C-2", "M", "D")) <= 14
    assert first.label.value in str(first)
    assert "thresholds 0.25 and 0.5" in first.summary()
    # the planted collective opposes two groups on every proposal: none is a consensus
    assert not any(r.is_consensus for r in regimes)


def test_a_regime_is_cited_like_any_analysis(project: civiqhub.Project) -> None:
    proposal = project.proposals["p-03"]
    default, stricter = proposal.regime(), proposal.regime(low=0.1, high=0.9)
    assert default.citation.method == "phi_gamma"
    assert default.citation.seed is None  # nothing is drawn
    assert set(default.citation.dependencies) == {"python"}  # no NumPy in this family
    assert default.citation.parameters == {"gamma": 2 / 3, "high": 0.5, "low": 0.25}
    assert stricter.citation.parameters["high"] == 0.9
    assert stricter.citation.computation != default.citation.computation
    assert stricter.omega == default.omega  # thresholds move the label, not the index
    assert stricter.label == "M"


def test_regimes_need_counts_only() -> None:
    public = civiqhub.synthetic_project(exposure="aggregated")
    with pytest.raises(civiqhub.ExposureError):
        public.cocluster()
    regimes = public.regimes()  # five counters per revision are enough
    detailed = civiqhub.synthetic_project().regimes()
    assert [r.label for r in regimes] == [r.label for r in detailed]


def test_votes_stay_on_the_revision_they_were_cast_on(project: civiqhub.Project) -> None:
    proposal = project.proposals["p-01"]
    old, current = proposal.revisions[0], proposal.current
    assert old != current
    assert proposal.regime().revision == current
    assert old.regime().tally == old.tally
    assert old.regime().citation.computation != current.regime().citation.computation


def test_a_proposal_without_votes_has_no_regime() -> None:
    payload, _ = synthetic_payload()
    quiet = {**payload, "votes": [], "tallies": [], "impressions": None}
    project = civiqhub.connect(
        source=civiqhub.MemorySource(quiet), exposure="pseudonymised"
    ).project()
    reading = project.proposals["p-02"].regime()
    assert not reading.is_available()
    assert str(reading) == "p-02: unavailable (no_votes)"
    assert reading.summary().startswith("p-02: no regime, unavailable (no_votes)")
    with pytest.raises(civiqhub.UnavailableError, match="no_votes"):
        _ = reading.label
    assert len(project.regimes().available()) == 0
    assert repr(project.regimes()) == "Regimes(14 proposals, 0 with a label)"


def test_regimes_work_without_numpy(tmp_path: Path) -> None:
    path = civiqhub.synthetic_project(exposure="aggregated").save(tmp_path / "public.json")
    out = _python(
        "import sys\n"
        "sys.modules['numpy'] = None\n"
        "import civiqhub\n"
        f"project = civiqhub.load({str(path)!r}).project()\n"
        "regimes = project.regimes()\n"
        "print(len(regimes.available()), regimes['p-01'].label.value)\n"
    )
    expected = civiqhub.synthetic_project().proposals["p-01"].regime().label.value
    assert out == f"14 {expected}"
