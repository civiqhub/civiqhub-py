# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Paragraph and Placement: the tree of an article version and where its Proposals sit."""

import dataclasses
import random
from pathlib import Path
from typing import Any

import pytest

from civiqhub.dataset import Dataset
from civiqhub.entities import Paragraph, Placement
from civiqhub.errors import NotFoundError, ValidationError
from civiqhub.listing import Listing
from support import paragraph_rows, reference_rows


@pytest.fixture
def dataset() -> Dataset:
    return Dataset(paragraph_rows())


def ids(items: Any) -> list[str]:
    return [item.paragraph_id if isinstance(item, Paragraph) else item.id for item in items]


# Criterion 1: the tree of paragraphs is walked by level.


def test_the_top_of_the_tree_holds_the_paragraphs_of_the_first_level(dataset: Dataset) -> None:
    article = dataset.articles["art-1"]
    assert isinstance(article.paragraphs, Listing)
    assert ids(article.paragraphs) == ["3f2a", "b5d2"]
    assert [paragraph.level for paragraph in article.paragraphs] == [1, 1]
    assert article.paragraphs == article.current_version.paragraphs


def test_each_paragraph_holds_the_deeper_ones_that_follow_it(dataset: Dataset) -> None:
    trees, water = dataset.articles["art-1"].paragraphs
    assert ids(trees.children) == ["8c1d", "9e0b"]
    parks, streets = trees.children
    assert ids(parks.children) == []
    assert ids(streets.children) == ["a7c4"]
    assert streets.children[0].level == 3
    assert ids(water.children) == []
    assert streets.children[0].parent is streets
    assert streets.parent is trees
    assert trees.parent is None


def test_walking_the_tree_by_level_gives_the_order_of_the_text(dataset: Dataset) -> None:
    article = dataset.articles["art-1"]

    def walk(paragraphs: Listing[Paragraph]) -> list[str]:
        found = []
        for paragraph in paragraphs:
            assert all(child.level == paragraph.level + 1 for child in paragraph.children)
            found += [paragraph.paragraph_id, *walk(paragraph.children)]
        return found

    assert walk(article.paragraphs) == ["3f2a", "8c1d", "9e0b", "a7c4", "b5d2"]
    assert ids(article.walk_paragraphs()) == ["3f2a", "8c1d", "9e0b", "a7c4", "b5d2"]
    assert [paragraph.number for paragraph in article.walk_paragraphs()] == [
        "1",
        "1.1",
        "1.2",
        "1.2.1",
        "2",
    ]


def test_a_skipped_level_still_has_the_nearest_higher_paragraph_as_parent() -> None:
    rows = paragraph_rows()
    rows["paragraphs"].append(
        {"article_id": "art-2", "version_number": 1, "paragraph_id": "d1", "level": 3}
    )
    culture = Dataset(rows).articles["art-2"]
    assert ids(culture.paragraphs) == ["c0f1"]
    assert ids(culture.paragraphs[0].children) == ["d1"]


def test_each_version_has_its_own_tree(dataset: Dataset) -> None:
    second = dataset.article_versions["art-1.v2"]
    assert ids(second.paragraphs) == ["3f2a"]
    assert ids(second.walk_paragraphs()) == ["3f2a", "8c1d"]
    assert dataset.paragraphs["art-1.v2#3f2a"] != dataset.paragraphs["art-1.v3#3f2a"]
    assert dataset.paragraphs["art-1.v2#3f2a"].version is second
    assert dataset.paragraphs["art-1.v3#3f2a"].article is dataset.articles["art-1"]


def test_a_paragraph_shows_its_number_and_title(dataset: Dataset) -> None:
    parks = dataset.paragraphs["art-1.v3#8c1d"]
    assert repr(parks) == "Paragraph('art-1.v3#8c1d', '1.1 Parks')"
    assert parks.title == "Parks"
    assert Paragraph.noun == "paragraph"
    culture = dataset.articles["art-2"].paragraphs[0]
    assert culture.number == "1"


def test_a_paragraph_cannot_be_changed(dataset: Dataset) -> None:
    parks = dataset.paragraphs["art-1.v3#8c1d"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        parks.level = 1  # type: ignore[misc]


# Criterion 2: the id of a paragraph is read without prefix.


def test_the_id_of_a_paragraph_is_read_without_prefix(dataset: Dataset) -> None:
    parks = dataset.paragraphs["art-1.v2#8c1d"]
    assert parks.paragraph_id == "8c1d"
    assert parks.id == "art-1.v2#8c1d"
    assert dataset.paragraphs.get("art-1.v2#p-8c1d") is None
    assert all(not paragraph.paragraph_id.startswith("p-") for paragraph in dataset.paragraphs)


def test_a_placement_finds_a_paragraph_named_with_its_prefix(dataset: Dataset) -> None:
    placement = dataset.placements["p-01@art-1.v2"]
    assert placement.paragraph_id == "8c1d"
    assert placement.paragraph is dataset.paragraphs["art-1.v2#8c1d"]


# Criterion 3: a Proposal of a Group has no article.


def test_a_proposal_of_a_group_has_no_article(dataset: Dataset) -> None:
    group_proposal = dataset.proposals["p-03"]
    assert group_proposal.article_id is None
    assert group_proposal.article is None
    assert group_proposal.placement is None
    assert dataset.proposals["p-04"].article is None


def test_a_proposal_reads_its_parent_article_and_its_placement(dataset: Dataset) -> None:
    proposal = dataset.proposals["p-01"]
    assert proposal.article is dataset.articles["art-1"]
    placement = proposal.placement
    assert isinstance(placement, Placement)
    assert placement.id == "p-01@art-1.v3"
    assert placement.version is dataset.articles["art-1"].current_version
    assert placement.paragraph is dataset.paragraphs["art-1.v3#8c1d"]
    assert placement.rank == 1
    assert placement.proposal is proposal


def test_a_parent_article_that_the_dataset_does_not_hold_is_not_found() -> None:
    proposal = Dataset(reference_rows()).proposals["p-01"]
    assert proposal.article_id == "art-1"
    with pytest.raises(NotFoundError, match="art-1"):
        _ = proposal.article
    with pytest.raises(NotFoundError, match="art-1"):
        _ = proposal.placement


def test_a_proposal_without_a_placement_in_the_current_version_has_none() -> None:
    rows = paragraph_rows()
    rows["placements"] = [row for row in rows["placements"] if row["version_number"] == 2]
    proposal = Dataset(rows).proposals["p-01"]
    assert proposal.article is not None
    assert proposal.placement is None


# Criterion 4: the order of the placements is stable.


def test_the_proposals_of_an_article_come_in_the_order_of_the_text_and_of_ranks(
    dataset: Dataset,
) -> None:
    article = dataset.articles["art-1"]
    assert ids(article.proposals) == ["p-02", "p-01"]
    parks = dataset.paragraphs["art-1.v3#8c1d"]
    assert [placement.rank for placement in parks.placements] == [0, 1]
    assert ids(parks.proposals) == ["p-02", "p-01"]
    second = dataset.article_versions["art-1.v2"]
    assert ids(second.proposals) == ["p-02", "p-01"]
    assert second.placements[0].paragraph is None


@pytest.mark.parametrize("seed", range(5))
def test_the_order_of_the_placements_is_stable_from_one_load_to_another(
    seed: int, tmp_path: Path
) -> None:
    first = Dataset(paragraph_rows())
    shuffled_rows = paragraph_rows()
    random.Random(seed).shuffle(shuffled_rows["placements"])
    shuffled = Dataset(shuffled_rows)
    reopened = Dataset.from_file(first.save(tmp_path / "d.json"))
    for load in (first, shuffled, reopened):
        assert ids(load.articles["art-1"].proposals) == ["p-02", "p-01"]
        assert ids(load.placements) == [
            "p-02@art-1.v2",
            "p-01@art-1.v2",
            "p-02@art-1.v3",
            "p-01@art-1.v3",
        ]


def test_equal_ranks_keep_the_order_of_the_rows() -> None:
    rows = paragraph_rows()
    for row in rows["placements"]:
        row["rank"] = 0
    article = Dataset(rows).articles["art-1"]
    assert ids(article.proposals) == ["p-01", "p-02"]


def test_an_article_without_paragraphs_has_an_empty_tree() -> None:
    from support import article_rows

    article = Dataset(article_rows()).articles["art-1"]
    assert len(article.paragraphs) == 0
    assert list(article.walk_paragraphs()) == []
    assert len(article.proposals) == 0


# The rules of the rows.


def broken(change: Any) -> dict[str, Any]:
    rows = paragraph_rows()
    change(rows)
    return rows


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda rows: rows["paragraphs"][0].update(version_number=9),
            r"paragraphs\[0\] is in the version 9 of the article 'art-1', and the dataset has "
            r"no such version",
        ),
        (
            lambda rows: rows["paragraphs"][1].update(paragraph_id="p-3f2a"),
            r"paragraphs\[0\] and paragraphs\[1\] are both the paragraph '3f2a'",
        ),
        (
            lambda rows: rows["paragraphs"][0].update(level=0),
            r"paragraphs\[0\] has the level 0: the level of a paragraph is an integer from 1 to 4",
        ),
        (
            lambda rows: rows["paragraphs"][0].update(level=5),
            r"has the level 5",
        ),
        (
            lambda rows: rows["paragraphs"][0].update(level=True),
            r"has the level True",
        ),
        (
            lambda rows: rows["paragraphs"][0].update(number=["1"]),
            r"paragraphs\[0\] has the number \['1'\]",
        ),
        (
            lambda rows: rows["paragraphs"][0].update(paragraph_id="p-"),
            r"has the paragraph_id 'p-': once the prefix 'p-' of the anchors is left out",
        ),
        (
            lambda rows: rows["paragraphs"][0].pop("paragraph_id"),
            r"paragraphs\[0\] has no valid 'paragraph_id'",
        ),
        (
            lambda rows: rows["placements"][0].update(proposal_id="p-99"),
            r"placements\[0\] has the proposal_id 'p-99', and no proposal has this id",
        ),
        (
            lambda rows: rows["placements"][0].update(version_number=7),
            r"places the proposal 'p-01' in the version 7 of the article 'art-1', and the "
            r"dataset has no such version",
        ),
        (
            lambda rows: rows["placements"][0].update(paragraph_id="ffff"),
            r"in the paragraph 'ffff' of the version 3 of the article 'art-1', and this version "
            r"has no such paragraph",
        ),
        (
            lambda rows: rows["placements"][0].update(paragraph_id="c0f1"),
            r"in the paragraph 'c0f1' of the version 3",
        ),
        (
            lambda rows: rows["placements"][0].update(article_id="art-2", version_number=1),
            r"places the proposal 'p-01' in the article 'art-2', and its parent article is "
            r"'art-1': a proposal is placed in its parent article only",
        ),
        (
            lambda rows: rows["placements"].append(
                {"proposal_id": "p-03", "article_id": "art-1", "version_number": 3, "rank": 2}
            ),
            r"places the proposal 'p-03' in the article 'art-1', and its parent article is None",
        ),
        (
            lambda rows: rows["placements"].append(
                {"proposal_id": "p-01", "article_id": "art-1", "version_number": 3, "rank": 5}
            ),
            r"placements\[0\] and placements\[4\] both place the proposal 'p-01' in the version 3",
        ),
        (
            lambda rows: rows["placements"][0].update(rank=-1),
            r"placements\[0\] has no valid 'rank': it is an integer, zero or more; got -1",
        ),
        (
            lambda rows: rows["placements"][0].pop("rank"),
            r"placements\[0\] has no valid 'rank'",
        ),
    ],
    ids=[
        "unknown-version",
        "same-id-once-unprefixed",
        "level-zero",
        "level-five",
        "level-boolean",
        "number-list",
        "only-a-prefix",
        "no-id",
        "unknown-proposal",
        "placement-unknown-version",
        "unknown-paragraph",
        "paragraph-of-another-article",
        "another-article",
        "proposal-of-a-group",
        "placed-twice",
        "negative-rank",
        "no-rank",
    ],
)
def test_a_row_that_breaks_a_rule_is_refused(change: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Dataset(broken(change))


def test_the_paragraphs_and_placements_count_in_the_fingerprint() -> None:
    plain = Dataset(paragraph_rows()).fingerprint()
    rows = paragraph_rows()
    rows["placements"][0]["rank"] = 3
    assert Dataset(rows).fingerprint() != plain
