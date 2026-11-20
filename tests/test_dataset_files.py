# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Save a Dataset to a JSON file and reopen it, without network and without token."""

import json
from pathlib import Path
from typing import Any

import pytest

from civiqhub.dataset import FORMAT, Dataset
from civiqhub.errors import NotFoundError, ValidationError
from support import pseudonymised_rows, reference_rows

# Made up: no such token was ever issued.
FAKE_TOKEN = "civ_pat_synthetic0000"


def with_articles(rows: dict[str, Any]) -> dict[str, Any]:
    """Add two articles to the rows, in versions 3 and 1, with their current versions."""
    rows["articles"] = [
        {
            "id": "art-1",
            "project_id": "budget-2027",
            "position": 1,
            "title": "Green spaces",
            "current_version_number": 3,
            "published_at": "2026-11-10T08:00:00Z",
        },
        {
            "id": "art-2",
            "project_id": "budget-2027",
            "position": 2,
            "title": "Culture",
            "current_version_number": 1,
            "published_at": "2026-11-12T08:00:00Z",
        },
    ]
    rows["article_versions"] = [
        {
            "article_id": "art-1",
            "version_number": 3,
            "title": "Green spaces",
            "body": "Third version of the article on green spaces.",
            "published_at": "2026-11-10T08:00:00Z",
        },
        {
            "article_id": "art-2",
            "version_number": 1,
            "title": "Culture",
            "body": "First version of the article on culture.",
            "published_at": "2026-11-12T08:00:00Z",
        },
    ]
    return rows


@pytest.mark.parametrize(
    "rows", [reference_rows(), pseudonymised_rows()], ids=["aggregated", "pseudonymised"]
)
def test_a_saved_dataset_reopens_with_the_same_fingerprint(
    rows: dict[str, Any], tmp_path: Path
) -> None:
    dataset = Dataset(rows)
    path = dataset.save(tmp_path / "d.json")
    assert path == tmp_path / "d.json"
    reopened = Dataset.from_file(path)
    assert reopened.fingerprint() == dataset.fingerprint()
    assert reopened.exposure is dataset.exposure
    assert reopened.to_dict() == dataset.to_dict()


def test_the_file_is_sorted_json_in_the_format(tmp_path: Path) -> None:
    dataset = Dataset(reference_rows())
    text = dataset.save(tmp_path / "d.json").read_text(encoding="utf-8")
    rows = json.loads(text)
    assert rows["format"] == FORMAT
    assert text == json.dumps(rows, indent=1, sort_keys=True)
    assert list(rows) == sorted(rows)


def test_the_file_has_the_same_bytes_on_every_system(tmp_path: Path) -> None:
    dataset = Dataset(reference_rows())
    first = dataset.save(tmp_path / "first.json").read_bytes()
    second = dataset.save(str(tmp_path / "second.json")).read_bytes()
    assert first == second
    assert b"\r\n" not in first


def test_a_reopened_dataset_is_walked_as_the_original(tmp_path: Path) -> None:
    dataset = Dataset(pseudonymised_rows())
    reopened = Dataset.from_file(dataset.save(tmp_path / "d.json"))
    assert reopened.source == "file d.json"
    assert repr(reopened).endswith("from file d.json)")
    project = reopened.project()
    assert project.group is not None
    assert project.group.projects[0] is project
    assert project.proposals.ids == dataset.project().proposals.ids
    assert reopened.revisions.ids == dataset.revisions.ids
    assert [a.depth for a in project.proposals["p-01"].arguments] == [0, 1, 2, 0, 1, 1]
    assert [r.vote_counts for r in reopened.revisions] == [r.vote_counts for r in dataset.revisions]
    assert reopened.votes.ids == dataset.votes.ids
    assert project != dataset.project()


def test_a_missing_file_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="There is no dataset file at") as caught:
        Dataset.from_file(tmp_path / "missing.json")
    assert "Dataset.save" in caught.value.hint
    with pytest.raises(NotFoundError):
        Dataset.from_file(tmp_path)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("not json at all", "it is not JSON"),
        ("[1, 2, 3]", "holds a JSON list"),
        ('{"format": "civiqhub.snapshot/0"}', "expected format is 'civiqhub.dataset/0'"),
    ],
)
def test_a_file_that_is_not_a_dataset_is_refused(
    content: str, expected: str, tmp_path: Path
) -> None:
    path = tmp_path / "d.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValidationError, match=expected):
        Dataset.from_file(path)


def test_a_file_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "d.json"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ValidationError, match="it is not JSON"):
        Dataset.from_file(path)


def test_the_file_holds_neither_the_token_nor_the_source(tmp_path: Path) -> None:
    dataset = Dataset(reference_rows(), source=f"api, token {FAKE_TOKEN}")
    text = dataset.save(tmp_path / "d.json").read_text(encoding="utf-8")
    assert "civ_pat_" not in text
    assert "api" not in text


def test_a_project_has_no_save_method() -> None:
    project = Dataset(reference_rows()).project()
    assert not hasattr(project, "save")
    assert hasattr(project.dataset, "save")


def test_the_articles_keep_their_versions(tmp_path: Path) -> None:
    dataset = Dataset(with_articles(reference_rows()))
    reopened = Dataset.from_file(dataset.save(tmp_path / "d.json")).to_dict()
    pairs = [(row["id"], row["current_version_number"]) for row in reopened["articles"]]
    assert pairs == [("art-1", 3), ("art-2", 1)]
    versions = {
        (row["article_id"], row["version_number"]): row["body"]
        for row in reopened["article_versions"]
    }
    assert versions == {
        ("art-1", 3): "Third version of the article on green spaces.",
        ("art-2", 1): "First version of the article on culture.",
    }
    assert reopened == dataset.to_dict()
