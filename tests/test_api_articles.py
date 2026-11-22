# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The articles read from the API, by the routes of its contract only.

The fake API serves the articles from tests/contract/articles.json, the routes and fields
of the contract that ApiSource reads: an answer outside the contract fails, and a query
parameter that the contract does not give gets a 422. No socket is opened.
"""

import importlib.util
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from civiqhub.dataset import Dataset
from civiqhub.errors import CiviqHubError, NotFoundError
from civiqhub.sources import ApiSource
from civiqhub.values import Exposure
from support import (
    AS_OF,
    CONTRACT,
    TOKEN,
    FakeApi,
    api_rows,
    citation_rows,
    conforms,
    contract_route,
)

ARTICLE_SECTIONS = ("articles", "article_versions", "paragraphs", "placements", "citations")
ARTICLE_KEYS = ("articles", "article_versions", "article_version")
VERSION_3 = "/projects/budget-2027/articles/art-1/versions/3"


def fetch(fake: FakeApi, exposure: Exposure = Exposure.AGGREGATED) -> dict[str, Any]:
    return ApiSource(TOKEN, transport=fake).fetch(exposure=exposure)


def shape(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def article_requests(fake: FakeApi) -> list[tuple[str, dict[str, list[str]]]]:
    return [
        (path, parse_qs(urlsplit(url).query))
        for (url, _), path in zip(fake.requests, fake.paths, strict=True)
        if "/articles" in path
    ]


def answer(body: Any) -> tuple[int, dict[str, str], bytes]:
    return 200, {"Content-Type": "application/json"}, json.dumps(body).encode()


def version_3(**change: Any) -> dict[str, Any]:
    body = {
        "title": "Green spaces",
        "description": "Trees, parks and gardens.",
        "body": "Third version on green spaces.",
        "publishedAt": "2026-11-10T08:00:00Z",
        "outline": [{"paragraphId": "8c1d", "level": 1, "number": "1", "title": "Parks"}],
        "proposalBlocks": [{"proposalId": "p-01", "role": "PARENT", "paragraphId": "8c1d"}],
    }
    return {**body, **change}


# Criterion 1: only routes of the contract are called.


@pytest.mark.parametrize("key", ARTICLE_KEYS)
def test_each_path_of_the_articles_is_a_get_route_of_the_contract(key: str) -> None:
    routes = {shape(route["path"]): route for route in CONTRACT["routes"].values()}
    route = routes[shape(ApiSource.PATHS[key])]
    assert route["method"] == "get"


@pytest.mark.parametrize("level", list(Exposure), ids=lambda level: level.value)
def test_every_request_about_articles_is_a_route_of_the_contract(level: Exposure) -> None:
    fake = FakeApi(api_rows(pseudonymised=level is Exposure.PSEUDONYMISED), page_size=100)
    fetch(fake, level)
    requests = article_requests(fake)
    assert len(requests) == 1 + 2 + 4  # the list, two lists of versions, four versions
    for path, query in requests:
        found = contract_route(path)
        assert found is not None, path
        allowed = CONTRACT["routes"][found[0]]["query_parameters"]
        assert set(query) <= set(allowed), path


def test_the_lists_are_read_by_page_and_limit_and_a_version_without_query() -> None:
    fake = FakeApi(api_rows(), page_size=100)
    fetch(fake)
    for path, query in article_requests(fake):
        if path.endswith(("/articles", "/versions")):
            assert query == {"page": ["1"], "limit": ["50"]}, path
        else:
            assert query == {}, path


def test_every_page_of_the_articles_is_read_in_order() -> None:
    rows = api_rows()
    fake = FakeApi(rows, page_size=1)
    fetched = fetch(fake)
    for section in ARTICLE_SECTIONS:
        assert fetched[section] == rows[section], section
    pages = [query["page"] for path, query in article_requests(fake) if path.endswith("/articles")]
    assert pages == [["1"], ["2"]]


def test_a_parameter_outside_the_contract_is_refused_by_the_fake_api() -> None:
    fake = FakeApi(api_rows())
    for query in ("as_of=2026-11-16T09:00:00Z", "page=1&limit=51", "page=0"):
        status, _, _ = fake(
            f"https://api.civiqhub.com/v1/projects/budget-2027/articles?{query}", {}
        )
        assert status == 422, query


# Criterion 2: the fake API is generated from the contract.


def test_the_extract_comes_from_a_frozen_contract() -> None:
    assert CONTRACT["generated_from"]["version"] == "0.4.123"
    assert re.fullmatch(r"[0-9a-f]{64}", CONTRACT["generated_from"]["sha256"])
    assert sorted(CONTRACT["routes"]) == [
        "getArticleVersion",
        "listArticleVersions",
        "listProjectArticles",
    ]


def test_the_extract_keeps_only_the_routes_and_fields_that_are_read() -> None:
    path = Path(__file__).parent / "contract" / "extract.py"
    spec = importlib.util.spec_from_file_location("extract", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    item = {"type": "object", "description": "Secret note", "properties": {}}
    schemas = {
        name: {
            "required": list(keys),
            "description": "Secret note",
            "properties": {
                **{key: {"type": "string", "description": "Secret note"} for key in keys},
                "authorUserId": {"type": "string", "description": "Secret note"},
            },
        }
        for name, keys in module.FIELDS.items()
    }
    page = {
        "type": "object",
        "required": ["items", "meta"],
        "properties": {"items": {"type": "array", "items": item}, "meta": item},
    }
    contract = {
        "paths": {
            f"/route/{name}": {
                "get": {
                    "operationId": name,
                    "summary": "Secret note",
                    "parameters": [],
                    "responses": {"200": {"content": {"application/json": {"schema": page}}}},
                }
            }
            for name in (*module.ROUTES, "listSecretThings")
        },
        "components": {"schemas": schemas},
    }
    extracted = module.extract(contract)
    assert sorted(extracted["routes"]) == sorted(module.ROUTES)
    assert "Secret note" not in json.dumps(extracted)
    for name, fields in extracted["schemas"].items():
        assert tuple(fields) == module.FIELDS[name]


def test_the_fake_api_answers_in_the_shape_of_the_contract() -> None:
    page = {"schema": "ArticleListItemDto"}
    assert conforms({"id": "art-1"}, page)
    assert not conforms({"id": "art-1", "authorUserId": "u-1"}, page)
    assert not conforms({}, page)
    block = {"schema": "ArticleBodyProposalBlockDto"}
    assert conforms({"proposalId": "p-01", "role": "CITATION", "paragraphId": None}, block)
    assert not conforms({"proposalId": "p-01", "role": "QUOTE", "paragraphId": None}, block)
    fake = FakeApi(api_rows())
    for path in ("/projects/budget-2027/articles", VERSION_3):
        name, _ = contract_route(path) or ("", {})
        status, _, body = fake(f"https://api.civiqhub.com/v1{path}", {})
        assert status == 200
        assert conforms(json.loads(body), CONTRACT["routes"][name]["answer"])


# What the articles give.


def test_the_articles_of_the_api_build_the_same_objects_as_the_rows() -> None:
    fetched = fetch(FakeApi(api_rows()))
    assert {section: fetched[section] for section in ARTICLE_SECTIONS} == {
        section: api_rows()[section] for section in ARTICLE_SECTIONS
    }
    read, expected = Dataset(fetched), Dataset(citation_rows())
    for name in ("articles", "article_versions", "paragraphs", "placements", "citations"):
        assert sorted(getattr(read, name).ids) == sorted(getattr(expected, name).ids), name
    for name in ("placements", "citations"):
        ranks = {item.id: item.rank for item in getattr(read, name)}
        assert ranks == {item.id: item.rank for item in getattr(expected, name)}, name
    assert read.project().to_citation_edges() == expected.project().to_citation_edges()
    art1 = read.articles["art-1"]
    assert (art1.position, art1.current_version_number, art1.title) == (1, 3, "Green spaces")
    assert [paragraph.number for paragraph in art1.walk_paragraphs()] == [
        "1",
        "1.1",
        "1.2",
        "1.2.1",
        "2",
    ]


def test_the_rank_of_a_block_is_its_place_in_its_paragraph() -> None:
    fake = FakeApi(api_rows())
    fake.answers[VERSION_3] = answer(
        version_3(
            proposalBlocks=[
                {"proposalId": "p-03", "role": "CITATION", "paragraphId": None},
                {"proposalId": "p-02", "role": "PARENT", "paragraphId": "8c1d"},
                {"proposalId": "p-01", "role": "PARENT", "paragraphId": "8c1d"},
            ]
        )
    )
    fetched = fetch(fake)
    placed = [(row["proposal_id"], row["rank"]) for row in fetched["placements"]]
    assert placed[-2:] == [("p-02", 0), ("p-01", 1)]
    cited = [row for row in fetched["citations"] if row["version_number"] == 3]
    assert cited == [{"proposal_id": "p-03", "article_id": "art-1", "version_number": 3, "rank": 0}]


def test_a_version_published_after_the_instant_is_left_out() -> None:
    rows = api_rows()
    for version in rows["article_versions"]:
        if version["article_id"] == "art-1" and version["version_number"] == 3:
            version["published_at"] = "2026-11-20T08:00:00Z"
        if version["article_id"] == "art-2":
            version["published_at"] = "2026-11-16T09:00:01Z"
    fake = FakeApi(rows)
    fetched = fetch(fake)
    assert [row["id"] for row in fetched["articles"]] == ["art-1"]
    art1 = fetched["articles"][0]
    assert (art1["current_version_number"], art1["published_at"]) == (2, "2026-10-15T08:00:00Z")
    assert {row["version_number"] for row in fetched["article_versions"]} == {1, 2}
    assert VERSION_3 not in fake.paths
    assert all(row["version_number"] != 3 for row in fetched["paragraphs"])
    assert AS_OF == "2026-11-16T09:00:00Z"


def test_the_positions_follow_the_order_of_the_list() -> None:
    rows = api_rows()
    rows["articles"][0]["position"], rows["articles"][1]["position"] = 7, 3
    fetched = fetch(FakeApi(rows))
    assert [(row["id"], row["position"]) for row in fetched["articles"]] == [
        ("art-2", 1),
        ("art-1", 2),
    ]


def test_a_project_without_article_gives_empty_sections() -> None:
    rows = api_rows()
    for section in ARTICLE_SECTIONS:
        rows[section] = []
    fetched = fetch(FakeApi(rows))
    assert all(fetched[section] == [] for section in ARTICLE_SECTIONS)
    assert len(Dataset(fetched).articles) == 0


def test_no_field_outside_those_read_enters_the_rows() -> None:
    fake = FakeApi(api_rows())
    personal = {
        "authorUserId": "u-1",
        "publishedBy": {"name": "Jane Doe"},
        "holderUserId": "u-2",
        "viewerIsHolder": True,
    }
    fake.answers[VERSION_3] = answer(version_3(**personal))
    fake.answers["/projects/budget-2027/articles"] = answer(
        {
            "items": [{"id": "art-1", **personal}, {"id": "art-2", **personal}],
            "meta": {"hasNextPage": False},
        }
    )
    text = json.dumps(fetch(fake))
    for key in personal:
        assert key not in text
    assert "Jane Doe" not in text


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (version_3(title=None), "without a valid 'title'"),
        (
            version_3(outline=[{"paragraphId": "8c1d", "level": 1.5, "number": "1", "title": ""}]),
            "'level' that is not a whole number",
        ),
        (
            version_3(
                proposalBlocks=[{"proposalId": "p-01", "role": "QUOTE", "paragraphId": None}]
            ),
            "a block of role 'QUOTE'",
        ),
        (version_3(publishedAt=3), "without a valid 'publishedAt'"),
        ([], "without a valid 'description'"),
    ],
    ids=["no-title", "half-level", "unknown-role", "no-instant", "not-an-object"],
)
def test_an_answer_outside_the_contract_says_the_api_changed(body: Any, message: str) -> None:
    fake = FakeApi(api_rows())
    fake.answers[VERSION_3] = answer(body)
    with pytest.raises(CiviqHubError, match=message) as caught:
        fetch(fake)
    assert "may have changed" in (caught.value.hint or "")


def test_a_level_given_as_a_whole_float_is_read() -> None:
    fake = FakeApi(api_rows())
    fake.answers[VERSION_3] = answer(
        version_3(outline=[{"paragraphId": "8c1d", "level": 2.0, "number": "1", "title": "Parks"}])
    )
    levels = [row["level"] for row in fetch(fake)["paragraphs"] if row["version_number"] == 3]
    assert levels == [2]
    assert type(levels[0]) is int


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ({"items": [], "meta": {"hasNextPage": True}}, "empty page that announces another"),
        ({"items": []}, "no list 'items' and no 'meta'"),
        ({"data": [], "meta": {"hasNextPage": False}}, "no list 'items' and no 'meta'"),
        ({"items": [], "meta": {"hasNextPage": "no"}}, "without a valid 'hasNextPage'"),
    ],
)
def test_a_page_outside_the_contract_is_refused(page: dict[str, Any], message: str) -> None:
    fake = FakeApi(api_rows())
    fake.answers["/projects/budget-2027/articles"] = answer(page)
    with pytest.raises(CiviqHubError, match=message):
        fetch(fake)


def test_a_version_that_the_api_does_not_have_is_not_found() -> None:
    fake = FakeApi(api_rows())
    fake.answers[VERSION_3] = (404, {}, b"")
    with pytest.raises(NotFoundError, match="/articles/art-1/versions/3"):
        fetch(fake)
