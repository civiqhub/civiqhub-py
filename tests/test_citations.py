# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Citation: a Proposal cited in an article that is not its parent, and the graph of them.

This is the citation of the product, between an article and a Proposal. It is unrelated
to tests/test_citation.py, which checks the file CITATION.cff of the repository.
"""

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from civiqhub.dataset import Dataset
from civiqhub.entities import Citation
from civiqhub.errors import NotFoundError, ValidationError
from civiqhub.listing import Listing
from support import citation_rows, paragraph_rows


@pytest.fixture
def dataset() -> Dataset:
    return Dataset(citation_rows())


def ids(items: Any) -> list[str]:
    return [item.id for item in items]


# Criterion 1: a citation carries its source, its target and the cited Revision.


def test_a_citation_carries_its_source_its_target_and_its_cited_revision(
    dataset: Dataset,
) -> None:
    citation = dataset.citations["p-01@art-2.v1"]
    assert isinstance(citation, Citation)
    assert citation.version is dataset.articles["art-2"].current_version
    assert citation.article is dataset.articles["art-2"]
    assert citation.paragraph is dataset.paragraphs["art-2.v1#c0f1"]
    assert citation.rank == 0
    assert citation.proposal is dataset.proposals["p-01"]
    assert citation.cited_revision is dataset.proposals["p-01"].current_revision
    assert citation.cited_revision.id == "p-01.r2"


def test_the_cited_revision_is_the_one_in_force_never_a_stored_one() -> None:
    rows = citation_rows()
    for row in rows["citations"]:
        row["revision_id"] = "p-01.r1"
    proposal = Dataset(rows).proposals["p-01"]
    citation = proposal.citations[0]
    assert citation.cited_revision is proposal.current_revision
    assert citation.cited_revision.number == 2


def test_a_citation_outside_any_paragraph_has_none(dataset: Dataset) -> None:
    citation = dataset.citations["p-03@art-2.v1"]
    assert citation.paragraph_id is None
    assert citation.paragraph is None


def test_a_proposal_of_another_project_is_kept_by_its_id(dataset: Dataset) -> None:
    citation = dataset.citations["ext-7@art-2.v1"]
    assert citation.proposal_id == "ext-7"
    with pytest.raises(NotFoundError, match="ext-7"):
        _ = citation.proposal
    with pytest.raises(NotFoundError, match="ext-7"):
        _ = citation.cited_revision


def test_a_citation_cannot_be_changed(dataset: Dataset) -> None:
    citation = dataset.citations["p-01@art-2.v1"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        citation.proposal_id = "p-02"  # type: ignore[misc]


# Criterion 2: the name Citation, and where the citations are read.


def test_the_object_is_named_citation(dataset: Dataset) -> None:
    citation = dataset.citations["p-01@art-2.v1"]
    assert type(citation).__name__ == "Citation"
    assert Citation.noun == "citation"
    assert repr(citation) == "Citation('p-01@art-2.v1')"


def test_a_proposal_reads_the_citations_that_come_to_it(dataset: Dataset) -> None:
    group_proposal = dataset.proposals["p-03"]
    assert isinstance(group_proposal.citations, Listing)
    assert ids(group_proposal.citations) == ["p-03@art-2.v1", "p-03@art-1.v3"]
    assert ids(dataset.proposals["p-01"].citations) == ["p-01@art-2.v1"]
    assert ids(dataset.proposals["p-02"].citations) == []


def test_a_citation_in_an_old_version_does_not_count_for_the_proposal(dataset: Dataset) -> None:
    assert "p-03@art-1.v2" in dataset.citations
    assert "p-03@art-1.v2" not in dataset.proposals["p-03"].citations
    assert ids(dataset.article_versions["art-1.v2"].citations) == ["p-03@art-1.v2"]


def test_an_article_reads_the_citations_of_its_text(dataset: Dataset) -> None:
    culture = dataset.articles["art-2"]
    assert ids(culture.citations) == ["p-03@art-2.v1", "p-01@art-2.v1", "ext-7@art-2.v1"]
    assert ids(dataset.articles["art-1"].citations) == ["p-03@art-1.v3"]


def test_a_project_reads_the_citations_of_its_articles(dataset: Dataset) -> None:
    project = dataset.project()
    assert ids(project.citations) == [
        "p-03@art-1.v3",
        "p-03@art-2.v1",
        "p-01@art-2.v1",
        "ext-7@art-2.v1",
    ]


def test_every_citation_of_the_dataset_comes_by_version(dataset: Dataset) -> None:
    assert ids(dataset.citations) == [
        "p-03@art-2.v1",
        "p-01@art-2.v1",
        "ext-7@art-2.v1",
        "p-03@art-1.v2",
        "p-03@art-1.v3",
    ]


def test_without_citations_everything_is_empty() -> None:
    dataset = Dataset(paragraph_rows())
    assert len(dataset.citations) == 0
    assert len(dataset.project().citations) == 0
    assert dataset.project().to_citation_edges() == []
    assert len(dataset.proposals["p-01"].citations) == 0


# Criterion 3: the graph is exported as opaque edges, without objects of the SDK.


def test_the_graph_is_a_list_of_edges_of_opaque_ids(dataset: Dataset) -> None:
    edges = dataset.project().to_citation_edges()
    assert edges == [
        ("art-1", "p-03"),
        ("art-2", "p-03"),
        ("art-2", "p-01"),
        ("art-2", "ext-7"),
    ]
    assert all(type(edge) is tuple and len(edge) == 2 for edge in edges)
    assert all(type(end) is str for edge in edges for end in edge)
    assert json.loads(json.dumps(edges)) == [list(edge) for edge in edges]


def test_the_graph_is_stable_from_one_load_to_another(tmp_path: Path) -> None:
    first = Dataset(citation_rows())
    shuffled = citation_rows()
    shuffled["citations"].reverse()
    reopened = Dataset.from_file(first.save(tmp_path / "d.json"))
    expected = first.project().to_citation_edges()
    assert Dataset(shuffled).project().to_citation_edges() == expected
    assert reopened.project().to_citation_edges() == expected


# The rules of the rows.


def broken(change: Any) -> dict[str, Any]:
    rows = citation_rows()
    change(rows)
    return rows


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda rows: rows["citations"][1].update(
                article_id="art-1", version_number=3, paragraph_id="3f2a"
            ),
            r"citations\[1\] cites the proposal 'p-01' in the article 'art-1', which is its "
            r"parent article: there, a proposal is placed",
        ),
        (
            lambda rows: rows["citations"][0].update(version_number=4),
            r"citations\[0\] cites the proposal 'ext-7' in the version 4 of the article "
            r"'art-2', and the dataset has no such version",
        ),
        (
            lambda rows: rows["citations"][0].update(paragraph_id="ffff"),
            r"in the paragraph 'ffff' of the version 1 of the article 'art-2', and this version "
            r"has no such paragraph",
        ),
        (
            lambda rows: rows["citations"].append(
                {"proposal_id": "p-01", "article_id": "art-2", "version_number": 1, "rank": 4}
            ),
            r"citations\[1\] and citations\[5\] both cite the proposal 'p-01' in the version 1 "
            r"of the article 'art-2': a proposal appears once in an article",
        ),
        (
            lambda rows: rows["citations"][0].update(rank=-2),
            r"citations\[0\] has no valid 'rank'",
        ),
        (
            lambda rows: rows["citations"][0].pop("proposal_id"),
            r"citations\[0\] has no valid 'proposal_id'",
        ),
        (
            lambda rows: rows["citations"][0].update(paragraph_id="p-"),
            r"has the paragraph_id 'p-'",
        ),
    ],
    ids=[
        "cited-in-its-parent",
        "unknown-version",
        "unknown-paragraph",
        "cited-twice",
        "negative-rank",
        "no-proposal",
        "only-a-prefix",
    ],
)
def test_a_row_that_breaks_a_rule_is_refused(change: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Dataset(broken(change))


def test_a_paragraph_named_with_its_prefix_is_found() -> None:
    rows = citation_rows()
    rows["citations"][1]["paragraph_id"] = "p-c0f1"
    citation = Dataset(rows).citations["p-01@art-2.v1"]
    assert citation.paragraph_id == "c0f1"


def test_the_citations_count_in_the_fingerprint() -> None:
    plain = Dataset(citation_rows()).fingerprint()
    rows = citation_rows()
    rows["citations"].pop()
    assert Dataset(rows).fingerprint() != plain
