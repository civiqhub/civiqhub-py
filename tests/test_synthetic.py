# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The synthetic Project: made up from a seed, with a planted structure, without engine."""

import json
import re
import subprocess
import sys
from collections import Counter
from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.errors import ExposureError, ValidationError
from civiqhub.values import Exposure, VoteState


def fingerprint_in_a_new_process(seed: int) -> str:
    code = (
        f"import civiqhub\nprint(civiqhub.Dataset(civiqhub.make_rows(seed={seed})).fingerprint())\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return done.stdout.strip()


# Criterion 1: every invariant of the model holds.


@pytest.mark.parametrize("impressions", [False, True])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_the_rows_build_a_dataset(seed: int, impressions: bool) -> None:
    dataset = Dataset(civiqhub.make_rows(seed=seed, impressions=impressions))
    assert dataset.exposure is Exposure.PSEUDONYMISED
    assert dataset.as_of == "2026-01-01T00:00:00Z"


# Criterion 2: the same seed gives the same rows, in another process too.


def test_the_same_seed_gives_the_same_dataset_in_two_processes() -> None:
    here = Dataset(civiqhub.make_rows(seed=0)).fingerprint()
    assert fingerprint_in_a_new_process(0) == here
    assert fingerprint_in_a_new_process(0) == here
    assert fingerprint_in_a_new_process(1) != here


def test_the_rows_are_fresh_each_time() -> None:
    rows = civiqhub.make_rows()
    rows["votes"].clear()
    assert civiqhub.make_rows()["votes"]


# Criterion 3: the shape of the Project.


def test_the_project_has_the_planned_shape() -> None:
    project = civiqhub.make_project()
    assert project.slug == "demo-project"
    assert project.id == "pr-demo"
    assert project.group is not None
    assert project.group.slug == "demo-group"
    assert len(project.proposals) == 15
    assert len(project.amendments) == 2
    assert len(project.actants) == 48
    assert len(project.arguments) == 6
    p15 = next(proposal for proposal in project.proposals if proposal.id == "p-15")
    assert p15.current_revision.id == "p-15-r2"
    amendment = p15.current_revision.amendment
    assert amendment is not None
    assert amendment.id == "p-16"
    assert amendment.is_adopted


def test_the_open_amendment_targets_p02() -> None:
    project = civiqhub.make_project()
    p17 = next(amendment for amendment in project.amendments if amendment.id == "p-17")
    assert not p17.is_adopted
    assert p17.target.id == "p-02"
    assert p17.target_revision.id == "p-02-r1"


def test_the_arguments_form_two_threads() -> None:
    arguments = civiqhub.make_project().arguments
    assert [argument.id for argument in arguments] == [f"arg-{n}" for n in range(1, 7)]
    assert [argument.depth for argument in arguments] == [0, 1, 2, 0, 1, 1]
    assert [str(argument.position) for argument in arguments] == ["pro", "con"] * 3
    assert {argument.proposal.id for argument in arguments} == {"p-01"}
    assert all(argument.author is not None for argument in arguments)


def test_the_votes_fall_on_the_fourteen_planted_proposals_only() -> None:
    rows = civiqhub.make_rows()
    revisions = {vote["revision_id"] for vote in rows["votes"]}
    assert revisions <= {f"p-{n:02d}-r1" for n in range(1, 15)}
    participation = rows["participation"][0]
    assert participation["n_votes"] == len(rows["votes"])
    assert participation["n_proposals"] == 15
    assert participation["n_amendments"] == 2
    assert participation["n_actants"] == 48


def test_the_vote_counts_are_counted_from_the_votes() -> None:
    dataset = Dataset(civiqhub.make_rows(seed=3))
    for revision in dataset.revisions:
        scores = [vote.score for vote in revision.votes]
        assert revision.vote_counts == civiqhub.VoteCounts.from_scores(scores)


def test_the_truth_gives_the_planted_structure() -> None:
    truth = civiqhub.make_truth()
    groups = truth["opinion_groups"]
    assert Counter(groups.values()) == {0: 20, 1: 16, 2: 12}
    assert groups["m-001"] == 0
    assert groups["m-021"] == 1
    assert groups["m-048"] == 2
    blocks = truth["proposal_blocks"]
    assert blocks == {f"p-{n:02d}": 0 if n <= 7 else 1 for n in range(1, 15)}
    assert set(groups) == {actant.pseudonym for actant in civiqhub.make_project().actants}


# Criterion 4: the planted opinions show in the votes.


def test_the_planted_opinion_groups_disagree_on_p01() -> None:
    truth = civiqhub.make_truth()["opinion_groups"]
    revision = civiqhub.make_project(seed=0).proposals[0].revisions[0]
    assert revision.id == "p-01-r1"
    by_group: dict[int, list[int]] = {0: [], 1: [], 2: []}
    for vote in revision.votes:
        by_group[truth[vote.actant.pseudonym]].append(vote.score)
    first, second = by_group[0], by_group[1]
    assert sum(score > 0 for score in first) > len(first) / 2
    assert sum(score < 0 for score in second) > len(second) / 2


def test_the_votes_follow_the_planted_rates() -> None:
    rows = civiqhub.make_rows(seed=0)
    truth = civiqhub.make_truth()
    cells: Counter[tuple[int, int]] = Counter()
    for vote in rows["votes"]:
        proposal = vote["revision_id"].removesuffix("-r1")
        cells[truth["opinion_groups"][vote["actant"]], truth["proposal_blocks"][proposal]] += 1
    rate = {key: count / ((20, 16, 12)[key[0]] * 7) for key, count in cells.items()}
    assert rate[0, 0] > rate[0, 1]
    assert rate[1, 1] > rate[1, 0]
    assert rate[2, 0] < 0.6


# Criterion 5: the aggregated level.


def test_the_aggregated_project_has_vote_counts_and_no_actants() -> None:
    project = civiqhub.make_project(exposure="aggregated")
    assert project.dataset.exposure is Exposure.AGGREGATED
    assert project.proposals[0].current_revision.vote_counts.total > 0
    with pytest.raises(ExposureError):
        _ = project.actants


# Criterion 6: the impressions.


def test_with_impressions_the_three_states_exist() -> None:
    project = civiqhub.make_project(impressions=True)
    assert project.dataset.has_impressions
    states = {
        actant.vote_state_on(revision)
        for actant in project.actants
        for revision in project.revisions
    }
    assert {VoteState.VOTED, VoteState.ABSTAINED, VoteState.NOT_SHOWN} <= states
    assert VoteState.UNKNOWN not in states


def test_without_impressions_a_state_without_a_vote_is_unknown() -> None:
    project = civiqhub.make_project()
    assert not project.dataset.has_impressions
    states = {
        actant.vote_state_on(revision)
        for actant in project.actants
        for revision in project.revisions
    }
    assert states == {VoteState.VOTED, VoteState.UNKNOWN}


def test_impressions_do_not_change_the_votes() -> None:
    plain = civiqhub.make_rows(seed=5)
    shown = civiqhub.make_rows(seed=5, impressions=True)
    assert shown["votes"] == plain["votes"]
    assert {key: value for key, value in shown.items() if key != "impressions"} == plain
    every_vote = {(vote["actant"], vote["revision_id"]) for vote in shown["votes"]}
    impressions = {(row["actant"], row["revision_id"]) for row in shown["impressions"]}
    assert every_vote <= impressions
    cells = 48 * 14
    assert len(every_vote) < len(impressions) < cells


# Criterion 7: neither the engine nor NumPy.


def test_a_synthetic_project_needs_neither_the_engine_nor_numpy() -> None:
    code = (
        "import sys\n"
        "import civiqhub\n"
        "civiqhub.make_project()\n"
        "print(sorted(m for m in ('numpy', 'civiqhub_selene') if m in sys.modules))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "[]"


# Criterion 8: nothing looks like real data.

ALLOWED = re.compile(
    r"^(?:"
    r"m-0[0-4]\d|g-demo|pr-demo|p-\d{2}|p-\d{2}-r\d|a-0[12]|arg-\d"  # ids and pseudonyms
    r"|demo-group|demo-project|Demo group \(synthetic\)|Demo project \(synthetic\)"
    r"|Synthetic (?:proposal|amendment|argument) \d{1,2}(?:, as amended by 16)?\."
    r"|2026-01-01T00:00:00Z|civiqhub\.dataset/0|pseudonymised|human|participant"
    r"|adopted|open|pro|con"
    r")$"
)


def strings_of(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in strings_of(item)]
    if isinstance(value, list):
        return [text for item in value for text in strings_of(item)]
    return []


def test_nothing_looks_like_real_data() -> None:
    rows = civiqhub.make_rows(impressions=True)
    strange = sorted({text for text in strings_of(rows) if not ALLOWED.match(text)})
    assert strange == []
    assert "@" not in json.dumps(rows)


def test_the_docstrings_say_that_the_data_are_synthetic() -> None:
    for function in (civiqhub.make_rows, civiqhub.make_project, civiqhub.synthetic):
        assert "synthetic" in (function.__doc__ or "").lower()
    assert "describe nobody" in (civiqhub.make_rows.__doc__ or "")


# The arguments.


@pytest.mark.parametrize("seed", ["0", 1.5, None, True])
def test_a_seed_that_is_not_an_integer_is_refused(seed: Any) -> None:
    with pytest.raises(ValidationError, match="The seed of a synthetic Project is an integer"):
        civiqhub.make_rows(seed=seed)


def test_make_project_reads_the_rows_through_a_memory_source() -> None:
    project = civiqhub.make_project(seed=2)
    assert project.dataset.source == "memory"
    assert project.dataset.fingerprint() == Dataset(civiqhub.make_rows(seed=2)).fingerprint()
