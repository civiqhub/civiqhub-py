# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Python package by CiviqHub: preview, not functional yet.

The SDK is being written. It exposes ``__version__``, the errors of the SDK, defined in
:mod:`civiqhub.errors`, the values that the objects of a Project carry, defined in
:mod:`civiqhub.values`, and the two bricks that every object of the product shares:
:class:`~civiqhub.listing.Listing` and :class:`~civiqhub.entities.Entity`. A
:class:`~civiqhub.dataset.Dataset` is built from rows and holds the objects of the product
that are written so far: :class:`~civiqhub.entities.Group`,
:class:`~civiqhub.entities.Project`, :class:`~civiqhub.entities.Proposal`,
:class:`~civiqhub.entities.Amendment`, :class:`~civiqhub.entities.Revision`,
:class:`~civiqhub.entities.Argument`, :class:`~civiqhub.entities.Actant` (with
:class:`~civiqhub.entities.Member` and :class:`~civiqhub.entities.Agent`) and
:class:`~civiqhub.entities.Vote`.
"""

from .dataset import Dataset
from .entities import (
    Actant,
    Agent,
    Amendment,
    Argument,
    Entity,
    Group,
    Member,
    Project,
    Proposal,
    Revision,
    Vote,
)
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
    "Actant",
    "ActantKind",
    "Agent",
    "Amendment",
    "AmendmentStatus",
    "Argument",
    "AuthenticationError",
    "CiviqHubError",
    "Dataset",
    "Entity",
    "Exposure",
    "ExposureError",
    "Group",
    "Listing",
    "Member",
    "MissingExtraError",
    "NotFoundError",
    "Participation",
    "Position",
    "Project",
    "Proposal",
    "RateLimitedError",
    "Revision",
    "Role",
    "UnavailableError",
    "ValidationError",
    "Vote",
    "VoteCounts",
    "VoteState",
    "__version__",
]

#: Version of the package, in PEP 440 notation.
__version__ = "0.0.1"
