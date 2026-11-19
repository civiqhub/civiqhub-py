# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The published site: which versions it holds, in which order, and what lists them.

These tests cover the decisions of ``.github/scripts/build-docs-site.py``. The build of
each version (a clone, an environment, Sphinx) is exercised by the ``documentation`` job
of the CI, which runs the script itself.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

import civiqhub

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "build-docs-site.py"

# The source distribution ships the tests without the scripts of the CI.
pytestmark = pytest.mark.skipif(not SCRIPT.is_file(), reason="this checkout has no CI scripts")


@pytest.fixture(scope="module")
def site() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_docs_site", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look their module up by name while the class is being created.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def test_releases_come_first_latest_on_top_then_the_development_branch(site: ModuleType) -> None:
    versions = site.select_versions(
        site.Source("origin/develop", "0.3.0.dev0"),
        [
            site.Source("origin/main", "0.2.0"),
            site.Source("v0.2.0", "0.2.0"),
            site.Source("v0.10.0", "0.10.0"),
            site.Source("v0.1.0", "0.1.0"),
        ],
    )
    assert [version.slug for version in versions] == ["0.10.0", "0.2.0", "0.1.0", "dev"]
    assert [version.label for version in versions] == [
        "0.10.0 (latest release)",
        "0.2.0",
        "0.1.0",
        "dev (development branch)",
    ]
    assert [version.channel for version in versions] == ["release", "release", "release", "dev"]
    assert [version.path for version in versions] == ["0.10.0/", "0.2.0/", "0.1.0/", "dev/"]


def test_the_release_branch_wins_over_the_tag_of_the_same_version(site: ModuleType) -> None:
    versions = site.select_versions(
        None, [site.Source("origin/main", "0.1.0"), site.Source("v0.1.0", "0.1.0")]
    )
    assert [(version.slug, version.ref) for version in versions] == [("0.1.0", "origin/main")]


@pytest.mark.parametrize("version", ["0.1.0.dev0", "0.1.0rc1", "1.0", "v0.1.0", ""])
def test_a_version_that_is_not_a_release_number_is_left_out(site: ModuleType, version: str) -> None:
    assert site.select_versions(None, [site.Source("origin/main", version)]) == []


def test_before_the_first_release_the_site_holds_the_development_branch_alone(
    site: ModuleType,
) -> None:
    versions = site.select_versions(site.Source("origin/develop", "0.1.0.dev0"), [])
    assert [version.slug for version in versions] == ["dev"]
    assert json.loads(site.versions_document(versions))["default"] == "dev"


def test_the_versions_document_lists_each_folder_and_names_the_default(site: ModuleType) -> None:
    versions = site.select_versions(
        site.Source("origin/develop", "0.2.0.dev0"), [site.Source("origin/main", "0.1.0")]
    )
    document = site.versions_document(versions)
    assert document.endswith("\n")
    assert json.loads(document) == {
        "default": "0.1.0",
        "versions": [
            {"slug": "0.1.0", "label": "0.1.0 (latest release)", "path": "0.1.0/"},
            {"slug": "dev", "label": "dev (development branch)", "path": "dev/"},
        ],
    }


def test_the_home_page_sends_to_the_default_version(site: ModuleType) -> None:
    (version,) = site.select_versions(None, [site.Source("origin/main", "0.1.0")])
    page = site.redirection_page(version, "https://example.org/docs/")
    assert '<meta http-equiv="refresh" content="0; url=0.1.0/">' in page
    assert '<link rel="canonical" href="https://example.org/docs/0.1.0/">' in page
    assert '<a href="0.1.0/">' in page
    assert "canonical" not in site.redirection_page(version, "")


def test_a_reference_without_documentation_is_left_out(site: ModuleType) -> None:
    # The first release holds no docs/conf.py; a name git does not know holds nothing.
    assert site.source_at("v0.0.1") is None
    assert site.source_at("a-reference-that-does-not-exist") is None


def test_the_workflows_run_the_script_that_is_tested_here() -> None:
    workflows = ROOT / ".github" / "workflows"
    command = "python .github/scripts/build-docs-site.py"
    assert command in (workflows / "docs.yml").read_text(encoding="utf-8")
    assert command in (workflows / "test.yml").read_text(encoding="utf-8")


def test_the_version_of_a_commit_is_read_from_the_package(site: ModuleType) -> None:
    source = site.source_at("HEAD")
    assert source is not None
    assert source.version == civiqhub.__version__
