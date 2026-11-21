# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""ApiSource: the reading of the public API by token, against a fake API, without network."""

import email.message
import io
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from civiqhub.dataset import Dataset
from civiqhub.errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from civiqhub.sources import DEFAULT_URL, TOKEN_PREFIX, TOKEN_VARIABLE, ApiSource
from civiqhub.values import Exposure
from support import AS_OF, PARTICIPATION, TOKEN, FakeApi, api_rows, contract_route

AGGREGATED = Exposure.AGGREGATED
PSEUDONYMISED = Exposure.PSEUDONYMISED


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to open a connection fail, and forget the token of the machine."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test of the SDK tried to open a connection")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)


def source_for(fake: FakeApi, token: str = TOKEN) -> ApiSource:
    return ApiSource(token, transport=fake)


def two_projects(*, pseudonymised: bool = False) -> dict[str, Any]:
    """Return the API rows with a second, empty Project in the Group g-1."""
    rows = api_rows(pseudonymised=pseudonymised)
    rows["projects"].append(
        {"id": "pr-2", "slug": "transport-2027", "name": "Transport", "group_id": "g-1"}
    )
    rows["participation"].append({**PARTICIPATION, "project_id": "pr-2"})
    return rows


# Criterion 1: the same dataset as the reference rows.


@pytest.mark.parametrize("level", [AGGREGATED, PSEUDONYMISED], ids=lambda level: level.value)
def test_the_api_gives_the_reference_dataset(level: Exposure) -> None:
    rows = api_rows(pseudonymised=level is PSEUDONYMISED)
    source = source_for(FakeApi(rows))
    fetched = source.fetch(exposure=level)
    assert fetched == rows
    dataset = Dataset(fetched, source=source.describe())
    assert dataset.fingerprint() == Dataset(rows).fingerprint()
    assert dataset.source == "api https://api.civiqhub.com/v1, token civ_pat_...1234"


# Criterion 2: the pages are followed, in order.


@pytest.mark.parametrize("page_size", [1, 2, 100])
def test_every_page_is_read_in_order(page_size: int) -> None:
    rows = api_rows(pseudonymised=True)
    fake = FakeApi(rows, page_size=page_size)
    fetched = source_for(fake).fetch(exposure=PSEUDONYMISED)
    for section in ("proposals", "revisions", "arguments", "votes", "actants"):
        assert fetched[section] == rows[section], section
    reads = fake.paths.count("/projects/budget-2027/proposals")
    assert reads == -(-len(rows["proposals"]) // page_size)


def test_a_page_is_asked_for_by_its_cursor() -> None:
    fake = FakeApi(api_rows(), page_size=2)
    source_for(fake).fetch(exposure=AGGREGATED)
    cursors = [
        parse_qs(urlsplit(url).query).get("cursor")
        for url, _ in fake.requests
        if urlsplit(url).path.endswith("/proposals")
    ]
    assert cursors == [None, ["2"], ["4"]]


# Criterion 3: one instant, GET only, the token in the header.


def test_every_read_after_the_scope_carries_the_same_instant() -> None:
    fake = FakeApi(api_rows(pseudonymised=True))
    source_for(fake).fetch(exposure=PSEUDONYMISED)
    first, *others = fake.requests
    assert urlsplit(first[0]).path.endswith("/token")
    assert urlsplit(first[0]).query == ""
    assert others
    for (url, _), path in zip(others, fake.paths[1:], strict=True):
        query = parse_qs(urlsplit(url).query)
        if contract_route(path) is not None:
            # The routes of the articles take no instant: see tests/test_api_articles.py.
            assert "as_of" not in query, url
            continue
        assert query["as_of"] == [AS_OF], url


def test_every_request_carries_the_token_in_its_header() -> None:
    fake = FakeApi(api_rows())
    source_for(fake).fetch(exposure=AGGREGATED)
    for url, headers in fake.requests:
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert headers["Accept"] == "application/json"
        assert TOKEN not in url


class FakeAnswer:
    """What urllib.request.urlopen returns, served by a fake API."""

    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeAnswer":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_the_default_transport_sends_only_get(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeApi(api_rows())
    sent: list[tuple[urllib.request.Request, float]] = []

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeAnswer:
        sent.append((request, timeout))
        return FakeAnswer(*fake(request.full_url, dict(request.header_items())))

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    rows = ApiSource(TOKEN, timeout=5).fetch(exposure=AGGREGATED)
    assert rows == api_rows()
    assert sent
    for request, timeout in sent:
        assert request.get_method() == "GET"
        assert request.data is None
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        assert timeout == 5.0


def test_the_default_transport_turns_an_http_error_into_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeAnswer:
        headers = email.message.Message()
        headers["Retry-After"] = "7"
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", headers, io.BytesIO())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(RateLimitedError) as raised:
        ApiSource(TOKEN).fetch(exposure=AGGREGATED)
    assert raised.value.retry_after == 7.0


@pytest.mark.parametrize(
    "failure",
    [urllib.error.URLError("name not resolved"), TimeoutError("timed out")],
    ids=["unreachable", "timeout"],
)
def test_an_unreachable_api_raises_a_civiqhub_error(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeAnswer:
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(CiviqHubError, match=re.escape(f"Could not reach {DEFAULT_URL}")):
        ApiSource(TOKEN).fetch(exposure=AGGREGATED)


# Criterion 4: the aggregated level reads neither votes nor actants.


def test_the_aggregated_level_reads_neither_votes_nor_actants() -> None:
    fake = FakeApi(api_rows(pseudonymised=True))
    fetched = source_for(fake).fetch(exposure=AGGREGATED)
    assert not [path for path in fake.paths if path.endswith(("/votes", "/actants"))]
    assert "/projects/budget-2027/votes/aggregates" in fake.paths
    assert not {"actants", "votes", "impressions"} & set(fetched)


def test_the_pseudonymised_level_asks_for_it() -> None:
    fake = FakeApi(api_rows(pseudonymised=True))
    source_for(fake).fetch(exposure=PSEUDONYMISED)
    detailed = [url for url in (url for url, _ in fake.requests) if "/votes?" in url]
    detailed += [url for url, _ in fake.requests if "/actants?" in url]
    assert detailed
    for url in detailed:
        assert parse_qs(urlsplit(url).query)["exposure"] == ["pseudonymised"]


# Criterion 5: a container of a Group token.


@pytest.mark.parametrize("container", ["budget-2027", "transport-2027", "pr-2"])
def test_a_group_token_with_a_container_reads_one_project(container: str) -> None:
    fake = FakeApi(two_projects())
    fetched = source_for(fake).fetch(container, exposure=AGGREGATED)
    assert len(fetched["projects"]) == 1
    assert container in (fetched["projects"][0]["id"], fetched["projects"][0]["slug"])
    read = {path.split("/")[2] for path in fake.paths if path.startswith("/projects/")}
    assert read == {fetched["projects"][0]["id"]}
    assert Dataset(fetched).project().slug == fetched["projects"][0]["slug"]


def test_a_group_token_without_a_container_reads_every_project() -> None:
    fetched = source_for(FakeApi(two_projects())).fetch(exposure=AGGREGATED)
    assert [row["id"] for row in fetched["projects"]] == ["budget-2027", "pr-2"]
    assert len(Dataset(fetched).group().projects) == 2


def test_the_actants_of_several_projects_are_merged_by_pseudonym() -> None:
    rows = two_projects(pseudonymised=True)
    fetched = source_for(FakeApi(rows)).fetch(exposure=PSEUDONYMISED)
    assert fetched["actants"] == rows["actants"]
    assert len(Dataset(fetched).actants) == 4


def test_a_container_that_the_group_token_does_not_cover_is_not_found() -> None:
    with pytest.raises(NotFoundError, match="no Project with the id or slug 'elsewhere'"):
        source_for(FakeApi(two_projects())).fetch("elsewhere", exposure=AGGREGATED)


def test_a_project_token_reads_its_project_without_its_group() -> None:
    fake = FakeApi(api_rows(), kind="project", container_id="budget-2027")
    fetched = source_for(fake).fetch(exposure=AGGREGATED)
    assert fetched["groups"] == []
    assert "group_id" not in fetched["projects"][0]
    assert not [path for path in fake.paths if path.startswith("/groups/")]
    project = Dataset(fetched).project()
    assert project.group is None
    assert len(project.proposals) == 3


@pytest.mark.parametrize("container", ["budget-2027"])
def test_a_project_token_accepts_its_own_project(container: str) -> None:
    fake = FakeApi(api_rows(), kind="project", container_id="budget-2027")
    assert len(source_for(fake).fetch(container, exposure=AGGREGATED)["projects"]) == 1


def test_a_project_token_refuses_another_project() -> None:
    fake = FakeApi(api_rows(), kind="project", container_id="budget-2027")
    with pytest.raises(NotFoundError, match="covers the Project 'budget-2027', not 'other'"):
        source_for(fake).fetch("other", exposure=AGGREGATED)


def test_a_group_whose_parent_is_not_covered_loses_the_link() -> None:
    rows = api_rows()
    rows["groups"][0]["parent_id"] = "g-0"
    fetched = source_for(FakeApi(rows)).fetch(exposure=AGGREGATED)
    assert "parent_id" not in fetched["groups"][0]
    assert Dataset(fetched).group().parent is None


@pytest.mark.parametrize("container", ["", 3])
def test_a_container_that_is_not_an_id_is_refused(container: Any) -> None:
    with pytest.raises(ValidationError, match="The container is the id or the slug"):
        source_for(FakeApi(api_rows())).fetch(container, exposure=AGGREGATED)


# Criterion 6: the token.


def test_without_a_token_the_source_cannot_be_built() -> None:
    with pytest.raises(AuthenticationError, match=f"the variable {TOKEN_VARIABLE} is not set"):
        ApiSource()


def test_the_token_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    source = ApiSource(transport=FakeApi(api_rows()))
    assert source.describe().endswith("token civ_pat_...1234")
    assert source.fetch(exposure=AGGREGATED) == api_rows()


@pytest.mark.parametrize("token", ["abc", "pat_civ_123456", "CIV_PAT_123456"])
def test_a_token_that_does_not_look_like_one_is_refused_without_being_repeated(
    token: str,
) -> None:
    with pytest.raises(AuthenticationError, match="does not look like a CiviqHub token") as raised:
        ApiSource(token)
    error = raised.value
    assert token not in str(error)
    assert token not in error.hint
    assert TOKEN_PREFIX in str(error)


# Criterion 7: the status codes.


@pytest.mark.parametrize(
    ("status", "error_type", "message"),
    [
        (401, AuthenticationError, "refused the token at /token: it is expired or revoked"),
        (403, ExposureError, "does not allow /token"),
        (404, NotFoundError, "nothing at /token for this token"),
        (429, RateLimitedError, "asks to slow down at /token: wait 12 seconds"),
        (500, CiviqHubError, "answered 500 at /token"),
    ],
)
def test_a_status_code_becomes_an_error_of_the_sdk(
    status: int, error_type: type[CiviqHubError], message: str
) -> None:
    fake = FakeApi(api_rows())
    fake.answers["/token"] = (status, {"Retry-After": "12"}, b"{}")
    with pytest.raises(error_type, match=message) as raised:
        source_for(fake).fetch(exposure=AGGREGATED)
    assert type(raised.value) is error_type


def test_a_rate_limit_says_how_long_to_wait() -> None:
    fake = FakeApi(api_rows())
    fake.answers["/token"] = (429, {"Retry-After": "12"}, b"")
    with pytest.raises(RateLimitedError) as raised:
        source_for(fake).fetch(exposure=AGGREGATED)
    assert raised.value.retry_after == 12.0


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, None),
        ({"retry-after": "3.5"}, 3.5),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ({"Retry-After": "-1"}, None),
        ({"Retry-After": "inf"}, None),
    ],
    ids=["absent", "lower-case", "date", "negative", "infinite"],
)
def test_a_rate_limit_without_a_usable_delay(
    headers: dict[str, str], expected: float | None
) -> None:
    fake = FakeApi(api_rows())
    fake.answers["/token"] = (429, headers, b"")
    with pytest.raises(RateLimitedError, match="asks to slow down") as raised:
        source_for(fake).fetch(exposure=AGGREGATED)
    assert raised.value.retry_after == expected


def test_a_forbidden_read_of_votes_says_that_the_aggregated_level_stays() -> None:
    fake = FakeApi(api_rows(pseudonymised=True))
    fake.answers["/projects/budget-2027/votes"] = (403, {}, b"")
    with pytest.raises(ExposureError, match="does not allow /projects/budget-2027/votes") as error:
        source_for(fake).fetch(exposure=PSEUDONYMISED)
    assert 'exposure="aggregated"' in error.value.hint


@pytest.mark.parametrize(
    ("path", "answer", "message"),
    [
        ("/token", (200, {}, b"not json"), "body that is not JSON"),
        ("/token", (200, {}, b'{"kind": "user"}'), "without saying what the token covers"),
        ("/token", (200, {}, b"[]"), "without saying what the token covers"),
        ("/groups/g-1", (200, {}, b"[1]"), "rows of 'groups' that are not JSON objects"),
        ("/projects/budget-2027/proposals", (200, {}, b"{}"), "a page that has no list"),
        (
            "/projects/budget-2027/proposals",
            (200, {}, b'{"data": [], "next_cursor": 2}'),
            "a cursor that does not move forward",
        ),
    ],
    ids=["not-json", "unknown-kind", "list-scope", "not-rows", "no-data", "bad-cursor"],
)
def test_an_unexpected_answer_raises_a_civiqhub_error(
    path: str, answer: tuple[int, dict[str, str], bytes], message: str
) -> None:
    fake = FakeApi(api_rows())
    fake.answers[path] = answer
    with pytest.raises(CiviqHubError, match=message):
        source_for(fake).fetch(exposure=AGGREGATED)


def test_a_cursor_that_comes_back_stops_the_reading() -> None:
    fake = FakeApi(api_rows())
    fake.answers["/projects/budget-2027/proposals"] = (
        200,
        {},
        b'{"data": [], "next_cursor": "again"}',
    )
    with pytest.raises(CiviqHubError, match="does not move forward"):
        source_for(fake).fetch(exposure=AGGREGATED)
    assert fake.paths.count("/projects/budget-2027/proposals") == 2


# Criterion 8: the token appears nowhere.


def errors_of_every_path() -> Iterator[CiviqHubError]:
    for status in (401, 403, 404, 429, 418):
        fake = FakeApi(api_rows())
        fake.answers["/projects/budget-2027/arguments"] = (status, {"Retry-After": "1"}, b"")
        try:
            source_for(fake).fetch(exposure=AGGREGATED)
        except CiviqHubError as error:
            yield error
    answers: list[tuple[int, dict[str, str], bytes]] = [(200, {}, b"not json"), (200, {}, b"{}")]
    for answer in answers:
        fake = FakeApi(api_rows())
        fake.answers["/token"] = answer
        try:
            source_for(fake).fetch(exposure=AGGREGATED)
        except CiviqHubError as error:
            yield error
    try:
        source_for(FakeApi(two_projects())).fetch("nowhere", exposure=AGGREGATED)
    except CiviqHubError as error:
        yield error


def test_the_token_is_in_no_repr_description_message_nor_hint() -> None:
    source = source_for(FakeApi(api_rows()))
    assert TOKEN not in repr(source)
    assert TOKEN not in source.describe()
    assert repr(source) == "ApiSource('api https://api.civiqhub.com/v1, token civ_pat_...1234')"
    errors = list(errors_of_every_path())
    assert len(errors) == 8
    for error in errors:
        for text in (str(error), error.hint, *getattr(error, "__notes__", [])):
            assert TOKEN not in text
            assert "test1234" not in text
            assert "as_of=" not in text
            assert DEFAULT_URL not in text


@pytest.mark.parametrize(
    ("token", "shown"),
    [
        ("civ_pat_test1234", "civ_pat_...1234"),
        ("civ_pat_abc", "civ_pat_...c"),
        ("civ_pat_", "civ_pat_..."),
    ],
)
def test_a_short_token_shows_less_than_half_of_its_secret(token: str, shown: str) -> None:
    assert ApiSource(token).describe() == f"api {DEFAULT_URL}, token {shown}"


# The other arguments.


def test_the_base_address_loses_its_final_slash() -> None:
    fake = FakeApi(api_rows())
    source = ApiSource(TOKEN, base_url=DEFAULT_URL + "/", transport=fake)
    assert source.base_url == DEFAULT_URL
    source.fetch(exposure=AGGREGATED)
    assert fake.requests[0][0] == DEFAULT_URL + "/token"


@pytest.mark.parametrize("base_url", ["ftp://api.civiqhub.com", "file:///etc", "api.civiqhub.com"])
def test_a_base_address_that_is_not_http_is_refused(base_url: str) -> None:
    with pytest.raises(ValidationError, match="starts with 'https://'"):
        ApiSource(TOKEN, base_url=base_url)


@pytest.mark.parametrize("timeout", [0, -1, True, "30"])
def test_a_timeout_that_is_not_a_positive_number_is_refused(timeout: Any) -> None:
    with pytest.raises(ValidationError, match="positive number of seconds"):
        ApiSource(TOKEN, timeout=timeout)


def test_an_unknown_level_is_refused() -> None:
    with pytest.raises(ValidationError, match="The level asked for"):
        source_for(FakeApi(api_rows())).fetch(exposure="secret")  # type: ignore[arg-type]


def test_the_paths_are_the_assumptions_of_the_prototype() -> None:
    """The paths outside the articles; those of the articles are of the contract."""
    assert ApiSource.name == "api"
    assert ApiSource.PATHS["scope"] == "/token"
    assert ApiSource.PATHS["vote_counts"] == "/projects/{id}/votes/aggregates"
    assert set(ApiSource.PATHS) == {
        "scope",
        "group",
        "group_projects",
        "project",
        "proposals",
        "revisions",
        "amendments",
        "arguments",
        "vote_counts",
        "participation",
        "actants",
        "votes",
        "articles",
        "article_versions",
        "article_version",
    }


def test_an_id_is_quoted_in_a_path() -> None:
    rows = api_rows()
    fake = FakeApi(rows, kind="project", container_id="budget 2027/x")
    with pytest.raises(NotFoundError, match="nothing at /projects/budget%202027%2Fx"):
        source_for(fake).fetch(exposure=AGGREGATED)
