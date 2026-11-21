# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import tomllib
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import civiqhub

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_exposed() -> None:
    assert civiqhub.__version__ == version("civiqhub")


#: The public names of the package, written by hand: a change to them is a change of the
#: public interface, which this list makes visible in a review.
EXPECTED = [
    "Actant",
    "ActantKind",
    "Agent",
    "Amendment",
    "AmendmentStatus",
    "ApiSource",
    "Argument",
    "Article",
    "ArticleVersion",
    "AuthenticationError",
    "CiviqHubError",
    "Client",
    "Dataset",
    "Entity",
    "Exposure",
    "ExposureError",
    "FileSource",
    "Group",
    "Listing",
    "Member",
    "MemorySource",
    "MissingExtraError",
    "NotFoundError",
    "Paragraph",
    "Participation",
    "Placement",
    "Position",
    "Project",
    "Proposal",
    "RateLimitedError",
    "Revision",
    "Role",
    "Source",
    "UnavailableError",
    "ValidationError",
    "Vote",
    "VoteCounts",
    "VoteState",
    "__version__",
    "connect",
    "load",
    "make_project",
    "make_rows",
    "make_truth",
]


def test_the_public_names_are_the_expected_ones() -> None:
    assert sorted(civiqhub.__all__) == EXPECTED


def test_every_public_name_is_importable() -> None:
    for name in civiqhub.__all__:
        assert getattr(civiqhub, name) is not None, name


def test_the_installed_package_holds_py_typed() -> None:
    assert files("civiqhub").joinpath("py.typed").is_file()


def test_the_wheel_ships_the_whole_package_folder_with_py_typed() -> None:
    """The wheel takes every file of src/civiqhub; nothing in the configuration drops one."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel == {"packages": ["src/civiqhub"]}
    assert (ROOT / "src" / "civiqhub" / "py.typed").is_file()
