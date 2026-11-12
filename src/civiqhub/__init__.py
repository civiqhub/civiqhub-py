# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""CiviqHub for Python: read a Project with a token, navigate it, analyse it.

    import civiqhub

    project = civiqhub.connect(exposure="pseudonymised").project()
    print(project.cocluster().summary())      # needs: pip install "civiqhub[selene]"

Exploratory port of the v6 prototype, not a release: the public names are provisional,
the API that ``civiqhub.connect`` reads does not exist yet, and neither does the
``civiqhub[selene]`` extra.
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
    from .analysis import (
        Coclustering,
        ConsensusRanking,
        EntityCluster,
        OpinionGroup,
        ProposalBlock,
        Stance,
    )
    from .citation import Analysis, Citation
    from .regimes import ProposalRegime, Regimes

__version__ = "0.0.1"

# Names that need the analysis layer. They are resolved on first use, so that
# ``import civiqhub`` works, and stays light, when the extra is not installed.
_NEEDS_SELENE = {
    "Analysis": "citation",
    "Citation": "citation",
    "ProposalRegime": "regimes",
    "Regimes": "regimes",
    "Coclustering": "analysis",
    "ConsensusRanking": "analysis",
    "EntityCluster": "analysis",
    "OpinionGroup": "analysis",
    "ProposalBlock": "analysis",
    "Stance": "analysis",
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
    "Coclustering",
    "ConsensusRanking",
    "Entity",
    "EntityCluster",
    "Exposure",
    "ExposureError",
    "FileSource",
    "Group",
    "Listing",
    "Member",
    "MemorySource",
    "MissingExtraError",
    "NotFoundError",
    "OpinionGroup",
    "Participation",
    "Position",
    "Project",
    "Proposal",
    "ProposalBlock",
    "ProposalRegime",
    "RateLimitedError",
    "Regimes",
    "Revision",
    "Role",
    "Snapshot",
    "Source",
    "Stance",
    "UnavailableError",
    "ValidationError",
    "Vote",
    "VoteTally",
    "__version__",
    "connect",
    "load",
]
