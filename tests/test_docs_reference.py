# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Every public module of the SDK has a page in the reference, and only they have.

The reference is generated from the docstrings, one page per public module. These tests
read the files only: they import neither the SDK nor Sphinx. The build of the site
(``sphinx-build -W``) checks the content of the pages.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "civiqhub"
REFERENCE = ROOT / "docs" / "reference"

# The source distribution ships the tests without the pages.
pytestmark = pytest.mark.skipif(not REFERENCE.is_dir(), reason="this checkout has no docs")

HOW = "See 'The reference' in docs/README.md."


def public_modules() -> dict[str, Path]:
    """Return the file of each module whose dotted name has no underscore-led part."""
    modules = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE.parent).with_suffix("")
        parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
        if not any(part.startswith("_") for part in parts):
            modules[".".join(parts)] = path
    return modules


def declares_exports(path: Path) -> bool:
    """Tell whether a module assigns ``__all__`` at its top level."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
        for node in tree.body
    )


MODULES = public_modules()
DOCUMENTED = sorted(name for name, path in MODULES.items() if declares_exports(path))


def test_the_public_modules_are_found() -> None:
    assert "civiqhub" in DOCUMENTED
    assert not any("._" in name for name in MODULES)


@pytest.mark.parametrize("name", DOCUMENTED)
def test_a_public_module_has_a_reference_page(name: str) -> None:
    page = REFERENCE / f"{name}.md"
    assert page.is_file(), (
        f"{name} has no page in the reference: create docs/reference/{name}.md. {HOW}"
    )
    lines = page.read_text(encoding="utf-8").splitlines()
    assert lines[0] == f"# `{name}`", f"{page.name} must start with the title '# `{name}`'"
    assert f".. automodule:: {name}" in lines, (
        f"{page.name} must hold the line '.. automodule:: {name}'. {HOW}"
    )


@pytest.mark.parametrize("name", DOCUMENTED)
def test_a_reference_page_is_listed_in_a_table_of_contents(name: str) -> None:
    listed = any(
        name in page.read_text(encoding="utf-8").splitlines()
        for page in REFERENCE.glob("*.md")
        if page.stem != name
    )
    assert listed, (
        f"docs/reference/{name}.md is in no table of contents: add the line '{name}' to the "
        f"toctree of the page of its package. {HOW}"
    )


def test_a_reference_page_documents_an_existing_public_module() -> None:
    pages = {page.stem for page in REFERENCE.glob("*.md")} - {"index"}
    stale = sorted(pages - set(DOCUMENTED))
    assert not stale, (
        f"these pages of docs/reference match no public module: {stale}. Remove or rename them."
    )


@pytest.mark.parametrize("name", sorted(set(MODULES) - set(DOCUMENTED)))
def test_a_public_module_without_exports_is_an_empty_namespace(name: str) -> None:
    # A reserved namespace holds a docstring and nothing else. Any other public module
    # declares __all__: the reference documents exactly the names it lists.
    body = ast.parse(MODULES[name].read_text(encoding="utf-8")).body
    only_a_docstring = (
        len(body) == 1
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )
    assert only_a_docstring, (
        f"{name} is public and holds code: declare its __all__, or start its name with an "
        f"underscore. {HOW}"
    )
