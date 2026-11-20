# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of a CiviqHub Project, in Python, from a token or a file::

    project = civiqhub.connect().project()            # the token is read in CIVIQHUB_TOKEN
    project = civiqhub.connect(source=civiqhub.MemorySource(rows)).project()
    project = civiqhub.load("consultation.json").project()

:func:`~civiqhub.client.connect` returns a :class:`~civiqhub.client.Client` of a
:class:`~civiqhub.sources.Source`: the API (:class:`~civiqhub.sources.ApiSource`), a file
(:class:`~civiqhub.sources.FileSource`) or memory (:class:`~civiqhub.sources.MemorySource`).
What a source gives is a :class:`~civiqhub.dataset.Dataset`: a frozen graph of the objects
of the product, :class:`~civiqhub.entities.Group`, :class:`~civiqhub.entities.Project`,
:class:`~civiqhub.entities.Proposal`, :class:`~civiqhub.entities.Amendment`,
:class:`~civiqhub.entities.Revision`, :class:`~civiqhub.entities.Argument`,
:class:`~civiqhub.entities.Actant` (with :class:`~civiqhub.entities.Member` and
:class:`~civiqhub.entities.Agent`) and :class:`~civiqhub.entities.Vote`. They share
:class:`~civiqhub.listing.Listing` and :class:`~civiqhub.entities.Entity`, carry the values
of :mod:`civiqhub.values`, and raise the errors of :mod:`civiqhub.errors`.
"""

from .client import Client, connect, load
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
from .sources import ApiSource, FileSource, MemorySource, Source
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

#: Version of the package, in PEP 440 notation.
__version__ = "0.0.1"
