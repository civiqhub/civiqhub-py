# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The four promises of the SDK, checked so that a change that breaks one fails here.

1. The core imports the standard library only: no engine, no NumPy, no third party.
2. A token never leaks: no repr, file, source or error holds it.
3. No personal data enters an object: an Actant is known by its pseudonym only.
4. The SDK holds no formula: no module but the synthetic Project imports ``math``,
   ``statistics`` or ``random``, and the counts expose counts, shares and turnout only.
"""

import ast
import dataclasses
import json
import socket
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.errors import CiviqHubError, ValidationError
from civiqhub.sources import TOKEN_VARIABLE, ApiSource
from support import FakeApi, api_rows, pseudonymised_rows

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "civiqhub"

# --- 1. Independence --------------------------------------------------------------------

THIRD_PARTIES = ("numpy", "scipy", "pandas", "civiqhub_selene")


def modules_after(code: str) -> set[str]:
    """Return the modules loaded by a new interpreter after it runs ``code``."""
    report = "import sys\nprint('\\n'.join(sys.modules))\n"
    done = subprocess.run(
        [sys.executable, "-c", code + "\n" + report],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return set(done.stdout.split())


@pytest.mark.parametrize(
    "code",
    ["import civiqhub", "import civiqhub\nciviqhub.make_project().proposals[0].vote_counts"],
    ids=["import", "synthetic-project"],
)
def test_the_core_loads_the_standard_library_only(code: str) -> None:
    added = modules_after(code) - modules_after("")
    assert "civiqhub" in added
    for name in THIRD_PARTIES:
        assert name not in added
    foreign = sorted(
        name
        for name in added
        if name.split(".")[0] not in sys.stdlib_module_names and name.split(".")[0] != "civiqhub"
    )
    assert foreign == []


def test_the_package_declares_no_dependency() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []


# --- 2. The token -----------------------------------------------------------------------

SECRET = "SECRETSECRET"
TOKEN = f"civ_pat_{SECRET}1234"


def errors_of_the_api(monkeypatch: pytest.MonkeyPatch) -> Iterator[CiviqHubError]:
    """Raise each error that ApiSource can raise, and give it."""
    for status in (401, 403, 404, 429, 500):
        fake = FakeApi(api_rows())
        fake.answers["/projects/budget-2027/proposals"] = (status, {"Retry-After": "3"}, b"")
        with pytest.raises(CiviqHubError) as raised:
            ApiSource(TOKEN, transport=fake).fetch(exposure=civiqhub.Exposure.AGGREGATED)
        yield raised.value

    def unreachable(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
    with pytest.raises(CiviqHubError) as raised:
        ApiSource(TOKEN).fetch(exposure=civiqhub.Exposure.AGGREGATED)
    yield raised.value


def test_the_token_leaks_nowhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a test of the SDK tried to open a connection")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setenv(TOKEN_VARIABLE, TOKEN)
    source = ApiSource(transport=FakeApi(api_rows()))
    client = civiqhub.connect(source=source)
    project = client.project()
    dataset = project.dataset
    path = dataset.save(tmp_path / "d.json")
    texts = [
        repr(client),
        str(client),
        repr(source),
        str(source),
        source.describe(),
        repr(dataset),
        str(dataset),
        dataset.source,
        repr(project),
        str(project),
        path.read_text(encoding="utf-8"),
        json.dumps(dataset.to_dict()),
    ]
    errors = list(errors_of_the_api(monkeypatch))
    assert len(errors) == 6
    for error in errors:
        texts += [str(error), error.hint, *getattr(error, "__notes__", [])]
    leaking = [text for text in texts if SECRET in text]
    assert leaking == []
    assert dataset.source.endswith("civ_pat_...1234")


# --- 3. Personal data -------------------------------------------------------------------

PERSONAL = ("name", "email", "handle", "username", "user_id", "first_name", "last_name")


@pytest.mark.parametrize("cls", [civiqhub.Actant, civiqhub.Member, civiqhub.Agent, civiqhub.Vote])
def test_an_actant_and_a_vote_have_no_personal_field(cls: type) -> None:
    names = {field.name for field in dataclasses.fields(cls)}
    assert names.isdisjoint(PERSONAL), names & set(PERSONAL)


@pytest.mark.parametrize("key", PERSONAL)
def test_a_row_of_actant_with_personal_data_is_refused(key: str) -> None:
    rows = pseudonymised_rows()
    rows["actants"][0][key] = "made-up"
    with pytest.raises(ValidationError, match=f"has the key '{key}'"):
        Dataset(rows)


# --- 4. No formula ----------------------------------------------------------------------

FORBIDDEN = {"math", "statistics", "random"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def modules_of_the_package() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if path.name != "synthetic.py")


def test_the_modules_of_the_package_are_found() -> None:
    names = {path.name for path in modules_of_the_package()}
    assert {"__init__.py", "values.py", "dataset.py", "sources.py", "client.py"} <= names


@pytest.mark.parametrize("path", modules_of_the_package(), ids=lambda path: path.name)
def test_no_module_imports_a_tool_of_computation(path: Path) -> None:
    assert imported_modules(path).isdisjoint(FORBIDDEN), imported_modules(path) & FORBIDDEN


def public_names(cls: type) -> set[str]:
    return {name for name in dir(cls) if not name.startswith("_")}


def test_vote_counts_expose_counts_and_shares_only() -> None:
    mapping = {"get", "items", "keys", "values"}
    assert public_names(civiqhub.VoteCounts) == {"counts", "total", "shares", "from_scores"} | (
        mapping
    )


def test_participation_exposes_counts_and_turnout_only() -> None:
    participation = civiqhub.make_project().participation
    names = {name for name in dir(participation) if not name.startswith("_")}
    fields = {field.name for field in dataclasses.fields(civiqhub.Participation)}
    assert names == fields | {"turnout"}
    assert all(name.startswith("n_") for name in fields)


def test_the_forbidden_imports_are_seen(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text("import json, math\nfrom random import choice\n", encoding="utf-8")
    assert imported_modules(sample) == {"json", "math", "random"}
