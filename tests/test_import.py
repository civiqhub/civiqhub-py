# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from importlib.metadata import version

import civiqhub


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
    "Participation",
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
]


def test_the_public_names_are_the_expected_ones() -> None:
    assert sorted(civiqhub.__all__) == EXPECTED


def test_every_public_name_is_importable() -> None:
    for name in civiqhub.__all__:
        assert getattr(civiqhub, name) is not None, name
