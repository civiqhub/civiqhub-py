# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""CiviqHub for Python: read a Project with a token and navigate it.

    import civiqhub

    project = civiqhub.connect().project()        # the token is read from CIVIQHUB_TOKEN
    print(project.proposals["p-01"].tally)

Exploratory port of the v6 prototype, not a release: the public names are provisional,
and the API that ``civiqhub.connect`` reads does not exist yet.
"""

from typing import TYPE_CHECKING

from .client import Client, connect, load
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
from .model import (
    Actant,
    ActantKind,
    Agent,
    Amendment,
    AmendmentStatus,
    Argument,
    CellState,
    Entity,
    Exposure,
    Group,
    Listing,
    Member,
    Participation,
    Position,
    Project,
    Proposal,
    Revision,
    Role,
    Snapshot,
    Vote,
    VoteTally,
)
from .sources import ApiSource, FileSource, MemorySource, Source

if TYPE_CHECKING:
    from .citation import Analysis, Citation

__version__ = "0.0.1"

# Names that need the analysis layer. They are resolved on first use, so that
# ``import civiqhub`` works, and stays light, when the extra is not installed.
_NEEDS_SELENE = {
    "Analysis": "citation",
    "Citation": "citation",
}


def __getattr__(name: str) -> object:
    if name in _NEEDS_SELENE:
        from importlib import import_module

        value = getattr(import_module(f".{_NEEDS_SELENE[name]}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Actant",
    "ActantKind",
    "Agent",
    "Amendment",
    "AmendmentStatus",
    "Analysis",
    "ApiSource",
    "Argument",
    "AuthenticationError",
    "CellState",
    "Citation",
    "CiviqHubError",
    "Client",
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
    "Snapshot",
    "Source",
    "UnavailableError",
    "ValidationError",
    "Vote",
    "VoteTally",
    "__version__",
    "connect",
    "load",
]
