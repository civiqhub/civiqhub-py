# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Article and ArticleVersion: the articles of a Project, in frozen numbered versions."""

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from civiqhub.dataset import Dataset
from civiqhub.entities import Article, ArticleVersion
from civiqhub.errors import ValidationError
from civiqhub.listing import Listing
from support import PARTICIPATION, article_rows, minimal_rows, reference_rows


@pytest.fixture
def dataset() -> Dataset:
    return Dataset(article_rows())


# Criterion 1: the articles of a Project are ordered, and the order is stable.


def test_the_articles_of_a_project_follow_their_positions(dataset: Dataset) -> None:
    project = dataset.project()
    assert [article.id for article in project.articles] == ["art-1", "art-2"]
    assert [article.position for article in project.articles] == [1, 2]
    assert [article.id for article in dataset.articles] == ["art-2", "art-1"]


@pytest.mark.parametrize("pseudonymised", [False, True], ids=["aggregated", "pseudonymised"])
def test_the_order_of_the_articles_is_stable_from_one_load_to_another(
    pseudonymised: bool, tmp_path: Path
) -> None:
    first = Dataset(article_rows(pseudonymised=pseudonymised))
    second = Dataset(article_rows(pseudonymised=pseudonymised))
    reopened = Dataset.from_file(first.save(tmp_path / "d.json"))
    orders = [[article.id for article in load.project().articles] for load in (first, second)]
    assert orders == [["art-1", "art-2"]] * 2
    assert [article.id for article in reopened.project().articles] == ["art-1", "art-2"]
    assert reopened.fingerprint() == first.fingerprint()


def test_a_project_without_articles_has_an_empty_listing() -> None:
    articles = Dataset(reference_rows()).project().articles
    assert isinstance(articles, Listing)
    assert len(articles) == 0


# Criterion 2: a version, and an article, cannot be changed.


def test_an_article_version_cannot_be_changed(dataset: Dataset) -> None:
    version = dataset.project().articles[0].current_version
    with pytest.raises(dataclasses.FrozenInstanceError):
        version.body = "Another text."  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        del version.number
    assert version.body == "Third version on green spaces."


def test_an_article_cannot_be_changed(dataset: Dataset) -> None:
    article = dataset.project().articles[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        article.current_version_number = 1  # type: ignore[misc]
    assert article.current_version.number == 3


def test_changing_the_rows_does_not_change_the_versions() -> None:
    rows = article_rows()
    dataset = Dataset(rows)
    rows["article_versions"][3]["body"] = "Changed."
    assert dataset.articles["art-1"].current_version.body == "Third version on green spaces."


# Criterion 3: listings and equality.


def test_the_articles_and_their_versions_are_listings(dataset: Dataset) -> None:
    project = dataset.project()
    assert isinstance(project.articles, Listing)
    assert isinstance(dataset.article_versions, Listing)
    article = project.articles["art-1"]
    assert project.articles.get("art-1") is article
    assert project.articles.get("art-9") is None
    assert "art-2" in project.articles
    assert isinstance(article.versions, Listing)
    assert [version.number for version in article.versions] == [1, 2, 3]
    assert article.versions["art-1.v2"].title == "Green spaces"
    assert [version.id for version in dataset.article_versions] == [
        "art-2.v1",
        "art-1.v1",
        "art-1.v2",
        "art-1.v3",
    ]


def test_an_article_equals_itself_in_its_own_dataset_only() -> None:
    rows = article_rows()
    first, second = Dataset(rows), Dataset(rows)
    article = first.articles["art-1"]
    assert article == first.project().articles[0]
    assert hash(article) == hash(first.project().articles[0])
    assert article != second.articles["art-1"]
    assert article != article.current_version
    assert article.current_version == first.article_versions["art-1.v3"]
    assert article.current_version != second.article_versions["art-1.v3"]
    assert len({article, first.project().articles[0], second.articles["art-1"]}) == 2


def test_an_article_and_a_version_show_their_id_and_label(dataset: Dataset) -> None:
    article = dataset.articles["art-1"]
    assert repr(article) == "Article('art-1', 'Green spaces')"
    assert repr(article.current_version) == "ArticleVersion('art-1.v3', 'v3')"
    assert Article.noun == "article"
    assert ArticleVersion.noun == "article version"


# Navigation.


def test_an_article_reads_its_project_and_its_versions(dataset: Dataset) -> None:
    project = dataset.project()
    article = project.articles[0]
    assert article.project is project
    assert article.title == "Green spaces"
    assert article.description == "Trees, parks and gardens."
    assert article.published_at == "2026-11-10T08:00:00Z"
    current = article.current_version
    assert current.number == article.current_version_number == 3
    assert current.is_current
    assert not article.versions[0].is_current
    assert current.article is article
    assert [version.article for version in article.versions] == [article] * 3
    assert article.versions[0].title == "Parks"
    assert article.versions[0].published_at == "2026-10-01T08:00:00Z"


def test_an_article_without_description_has_an_empty_one(dataset: Dataset) -> None:
    culture = dataset.articles["art-2"]
    assert culture.description == ""
    assert culture.current_version.number == 1


def test_the_articles_are_read_at_both_levels() -> None:
    aggregated = Dataset(article_rows())
    pseudonymised = Dataset(article_rows(pseudonymised=True))
    for dataset in (aggregated, pseudonymised):
        assert [article.id for article in dataset.project().articles] == ["art-1", "art-2"]


def test_the_articles_of_two_projects_stay_apart() -> None:
    rows = article_rows()
    rows["projects"].append({"id": "pr-2", "slug": "transport", "group_id": "g-2"})
    rows["participation"].append({**PARTICIPATION, "project_id": "pr-2"})
    rows["articles"].append(
        {"id": "art-3", "project_id": "pr-2", "position": 1, "current_version_number": 1}
    )
    rows["article_versions"].append({"article_id": "art-3", "version_number": 1})
    dataset = Dataset(rows)
    assert [article.id for article in dataset.project("budget-2027").articles] == [
        "art-1",
        "art-2",
    ]
    assert [article.id for article in dataset.project("transport").articles] == ["art-3"]


# The rules of the rows.


def broken(change: Any) -> dict[str, Any]:
    rows = article_rows()
    change(rows)
    return rows


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda rows: rows["articles"][0].update(project_id="elsewhere"),
            r"articles\[0\] \(id 'art-2'\) has the project_id 'elsewhere', and no project",
        ),
        (
            lambda rows: rows["articles"][1].update(id="art-2"),
            r"articles\[0\] and articles\[1\] have the same id 'art-2'",
        ),
        (
            lambda rows: rows["articles"][1].update(position=2),
            r"articles\[0\] and articles\[1\] are both at the position 2 of the project",
        ),
        (
            lambda rows: rows["articles"][0].pop("position"),
            r"articles\[0\] \(id 'art-2'\) has no valid 'position': it is a positive integer",
        ),
        (
            lambda rows: rows["articles"][0].update(position=0),
            r"no valid 'position': it is a positive integer; got 0",
        ),
        (
            lambda rows: rows["articles"][0].update(position=True),
            r"no valid 'position': it is a positive integer; got True",
        ),
        (
            lambda rows: rows["articles"][1].update(current_version_number=4),
            r"articles\[1\] \(id 'art-1'\) has the current_version_number 4, and the article has "
            r"no version with this number",
        ),
        (
            lambda rows: rows["articles"][1].update(current_version_number="3"),
            r"no valid 'current_version_number': it is a positive integer; got '3'",
        ),
        (
            lambda rows: rows["article_versions"][0].update(article_id="art-9"),
            r"article_versions\[0\] has the article_id 'art-9', and no article has this id",
        ),
        (
            lambda rows: rows["article_versions"][1].update(version_number=2),
            r"article_versions\[0\] and article_versions\[1\] are both the version number 2 of "
            r"the article 'art-1'",
        ),
        (
            lambda rows: rows["article_versions"][0].pop("version_number"),
            r"article_versions\[0\] has no valid 'version_number'",
        ),
        (
            lambda rows: rows["article_versions"][0].update(body=12),
            r"article_versions\[0\] has a 'body' that is not a string",
        ),
        (
            lambda rows: rows["articles"][0].update(title=["Culture"]),
            r"articles\[0\] \(id 'art-2'\) has a 'title' that is not a string",
        ),
    ],
    ids=[
        "unknown-project",
        "same-id",
        "same-position",
        "no-position",
        "zero-position",
        "boolean-position",
        "missing-current-version",
        "text-current-version",
        "unknown-article",
        "same-version-number",
        "no-version-number",
        "body-not-text",
        "title-not-text",
    ],
)
def test_a_row_that_breaks_a_rule_is_refused(change: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Dataset(broken(change))


def test_an_article_without_any_version_is_refused() -> None:
    rows = minimal_rows()
    rows["articles"] = [
        {"id": "art-1", "project_id": "budget-2027", "position": 1, "current_version_number": 1}
    ]
    with pytest.raises(ValidationError, match="has no version with this number"):
        Dataset(rows)
