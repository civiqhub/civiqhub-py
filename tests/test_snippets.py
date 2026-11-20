# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The snippets of docs/snippets.md and of the README run, each on its own, without network.

The snippets that call ``civiqhub.connect()`` without a source read a fake API: a fake
token is set in ``CIVIQHUB_TOKEN``, and the ``ApiSource`` that ``connect`` builds is
replaced by one that reads :class:`support.FakeApi`. Any attempt to open a connection
fails the test.
"""

import contextlib
import io
import keyword
import re
import socket
import tokenize
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

import civiqhub.client
from civiqhub.sources import DEFAULT_URL, TOKEN_VARIABLE, ApiSource, Transport
from support import TOKEN, FakeApi, api_rows
from test_docs_examples import RUN_ELSEWHERE, Block, blocks_of

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SNIPPETS = ROOT / "docs" / "snippets.md"

# The source distribution ships the tests without the pages of docs/.
needs_docs = pytest.mark.skipif(not SNIPPETS.is_file(), reason="this checkout has no docs")


def snippets_of(page: Path) -> list[Block]:
    return [block for block in blocks_of(page.read_text(encoding="utf-8")) if block.run]


def cases() -> list[Any]:
    found: list[Any] = []
    for page in (README, SNIPPETS):
        if page.is_file():
            for block in snippets_of(page):
                where = f"{page.relative_to(ROOT).as_posix()}:{block.line}"
                found.append(pytest.param(page, block, id=where))
    return found


class FakeApiSource(ApiSource):
    """An ApiSource that reads the fake API, whatever transport it is given."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_URL,
        transport: Transport | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(token, base_url=base_url, transport=FakeApi(api_rows()), timeout=timeout)


@pytest.fixture
def fake_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Serve the fake API to connect(), refuse any connection, and work in a new folder."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a snippet tried to open a connection")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    monkeypatch.setattr(civiqhub.client, "ApiSource", FakeApiSource)
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("fake_api")
@pytest.mark.parametrize(("page", "block"), cases())
def test_a_snippet_runs_on_its_own_and_prints_what_the_page_shows(page: Path, block: Block) -> None:
    namespace: dict[str, object] = {"__name__": "__snippet__"}
    where = f"{page.relative_to(ROOT).as_posix()}:{block.line}"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exec(compile(block.code, where, "exec"), namespace)
    assert printed.getvalue(), f"the snippet at {where} prints nothing"
    if block.output is not None:
        assert printed.getvalue() == block.output, (
            f"the snippet at {where} does not print the text block that follows it"
        )


@needs_docs
def test_there_are_nine_snippets_of_eight_lines_at_most() -> None:
    snippets = snippets_of(SNIPPETS)
    assert len(snippets) == 9
    for block in snippets:
        assert len(block.code.splitlines()) <= 8, f"docs/snippets.md:{block.line}"
        assert block.code.startswith("import civiqhub\n"), f"docs/snippets.md:{block.line}"


@needs_docs
def test_each_snippet_says_whether_it_reads_alone() -> None:
    text = SNIPPETS.read_text(encoding="utf-8")
    titles = re.findall(r"^## (S\d)\. ", text, flags=re.MULTILINE)
    assert titles == [f"S{number}" for number in range(1, 10)]
    for section in text.split("\n## ")[1:]:
        assert re.search(r"^Reads alone: (yes\.|no\. .+)$", section, flags=re.MULTILINE), (
            section.splitlines()[0]
        )


@needs_docs
def test_the_readme_shows_the_snippets_s1_s2_and_s7() -> None:
    by_title = dict(
        zip(
            re.findall(r"^## (S\d)\. ", SNIPPETS.read_text(encoding="utf-8"), flags=re.M),
            (block.code for block in snippets_of(SNIPPETS)),
            strict=True,
        )
    )
    assert [block.code for block in snippets_of(README)] == [
        by_title["S1"],
        by_title["S2"],
        by_title["S7"],
    ]


# Short names that are words of the product, not abbreviations.
WORDS = {"id"}


def names_of(code: str) -> list[str]:
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    return [token.string for token in tokens if token.type == tokenize.NAME]


@pytest.mark.parametrize(("page", "block"), cases())
def test_a_snippet_uses_no_dunder_no_greek_letter_and_no_abbreviation(
    page: Path, block: Block
) -> None:
    assert not re.search(r"__\w+__", block.code)
    assert not re.search("[Ͱ-Ͽἀ-῿]", block.code)
    short = [
        name
        for name in names_of(block.code)
        if len(name) <= 2 and not keyword.iskeyword(name) and name not in WORDS
    ]
    assert short == [], f"abbreviated names: {short}"
    abbreviated = [
        name
        for name in names_of(block.code)
        if "_" in name and name.split("_")[0] in {"nb", "num", "cnt", "idx", "ref", "rev"}
    ]
    assert abbreviated == []


def test_the_readme_holds_no_token_and_no_address_of_a_person() -> None:
    text = README.read_text(encoding="utf-8")
    assert "civ_pat_..." in text
    assert not re.search(r"civ_pat_(?!\.\.\.)", text), "write a token as civ_pat_..."
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    assert "preview, not functional yet" not in text.lower()
    assert "selene]" not in text, "the extra is not published yet"


@needs_docs
def test_the_snippets_run_here_and_only_here() -> None:
    assert {"README.md", "docs/snippets.md"} <= RUN_ELSEWHERE


def test_the_fake_api_is_what_connect_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    monkeypatch.setattr(civiqhub.client, "ApiSource", FakeApiSource)
    rows: Mapping[str, object] = api_rows()
    assert civiqhub.connect().load().to_dict() == rows
