# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Python package by CiviqHub: preview, not functional yet.

The SDK is being written. It exposes ``__version__``, the errors of the SDK, defined in
:mod:`civiqhub.errors`, the values that the objects of a Project carry, defined in
:mod:`civiqhub.values`, and the two bricks that every object of the product shares:
:class:`~civiqhub.listing.Listing` and :class:`~civiqhub.entities.Entity`.
"""

from .entities import Entity
from .errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    MissingExtraError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
    ValidationError,
)
from .listing import Listing
from .values import (
    ActantKind,
    AmendmentStatus,
    Exposure,
    Participation,
    Position,
    Role,
    VoteCounts,
    VoteState,
)

__all__ = [
    "ActantKind",
    "AmendmentStatus",
    "AuthenticationError",
    "CiviqHubError",
    "Entity",
    "Exposure",
    "ExposureError",
    "Listing",
    "MissingExtraError",
    "NotFoundError",
    "Participation",
    "Position",
    "RateLimitedError",
    "Role",
    "UnavailableError",
    "ValidationError",
    "VoteCounts",
    "VoteState",
    "__version__",
]

#: Version of the package, in PEP 440 notation.
__version__ = "0.0.1"
