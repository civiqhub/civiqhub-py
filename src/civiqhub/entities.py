# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of the product.

:class:`Entity` is what every object of the product shares: a frozen value, known by its
id, tied to the :class:`~civiqhub.dataset.Dataset` it comes from. :class:`Group`,
:class:`Project`, :class:`Proposal` and :class:`Revision` are written; Amendment, Argument,
Actant and Vote are not written yet.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .listing import Listing
from .values import Exposure, Participation, VoteCounts

if TYPE_CHECKING:
    from .dataset import Dataset

__all__ = ["Entity", "Group", "Project", "Proposal", "Revision"]


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Entity:
    """An object of the product: frozen, known by its id, tied to its dataset.

    Two entities are equal when they are of the same class exactly, have the same id and
    come from the same dataset object. Two loads of the same Project therefore give
    entities that differ: to compare contents, compare the fingerprints of the datasets.

    An entity keeps only the ids of the entities it links to. These entities are read
    through properties that query its dataset.

    A subclass is declared with ``@dataclass(frozen=True, kw_only=True, eq=False,
    repr=False)``, so that it keeps the equality, the hash and the representation defined
    here.

    Args:
        id: The id of the entity.
        dataset: The dataset that the entity comes from. It is not shown by ``repr``.
    """

    id: str
    dataset: "Dataset" = field(repr=False)

    #: The name of the entity in messages, such as ``"proposal"``.
    noun: ClassVar[str] = "entity"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id and self.dataset is other.dataset

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))

    def _label(self) -> str:
        """Return a short readable label, which ``repr`` shows after the id.

        It is empty here. A subclass overrides it, for instance to return the name of a
        Project.
        """
        return ""

    def __repr__(self) -> str:
        label = self._label()
        shown = f"{self.id!r}, {label!r}" if label else repr(self.id)
        return f"{type(self).__name__}({shown})"


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Group(Entity):
    """A community on CiviqHub. It holds Groups and Projects.

    ``repr`` shows its id and its name, such as ``Group('g-1', 'Demo collective')``.

    Args:
        id: The id of the Group.
        dataset: The dataset that the Group comes from.
        slug: The short name of the Group in addresses, unique in its dataset.
        name: The name of the Group.
        description: The description of the Group.
        parent_id: The id of the Group that holds this one, or ``None`` at the top.
    """

    slug: str
    name: str = ""
    description: str = ""
    parent_id: str | None = None

    #: The name of a Group in messages.
    noun: ClassVar[str] = "group"

    def _label(self) -> str:
        return self.name

    @property
    def parent(self) -> "Group | None":
        """The Group that holds this one, or ``None`` at the top."""
        return None if self.parent_id is None else self.dataset.groups[self.parent_id]

    @property
    def groups(self) -> Listing["Group"]:
        """The Groups that this Group holds directly, in the order of the rows."""
        return self.dataset._groups_in(self.id)

    @property
    def projects(self) -> "Listing[Project]":
        """The Projects of this Group, in the order of the rows."""
        return self.dataset._projects_in(self.id)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Project(Entity):
    """A Project of a Group: the set of its articles and of their versions.

    Every proposal of a Project has a parent article. This version of the SDK does not
    read the articles yet.

    ``repr`` shows its id and its name, such as
    ``Project('budget-2027', 'Budget participatif')``.

    Args:
        id: The id of the Project.
        dataset: The dataset that the Project comes from.
        slug: The short name of the Project in addresses, unique in its dataset.
        name: The name of the Project.
        description: The description of the Project.
        group_id: The id of the Group of the Project, or ``None`` when the data does not
            say.
    """

    slug: str
    name: str = ""
    description: str = ""
    group_id: str | None = None

    #: The name of a Project in messages.
    noun: ClassVar[str] = "project"

    def _label(self) -> str:
        return self.name

    @property
    def group(self) -> Group | None:
        """The Group of the Project, or ``None`` when the data does not say."""
        return None if self.group_id is None else self.dataset.groups[self.group_id]

    @property
    def as_of(self) -> str:
        """The instant that the data describes, the one of the dataset."""
        return self.dataset.as_of

    @property
    def exposure(self) -> Exposure:
        """The level of detail of the data, the one of the dataset."""
        return self.dataset.exposure

    @property
    def participation(self) -> Participation:
        """The counts of what happened in the Project, as the source gave them."""
        return self.dataset._participation_of(self.id)

    @property
    def proposals(self) -> "Listing[Proposal]":
        """The Proposals of the Project that are not Amendments, in the order of the rows."""
        return self.dataset._proposals_in(self.id)

    @property
    def revisions(self) -> "Listing[Revision]":
        """The Revisions of every Proposal of the Project, Amendments included.

        They come by Proposal, in the order of the rows, then by number.
        """
        return self.dataset._revisions_in(self.id)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Proposal(Entity):
    """A statement put to the collective of a Project.

    A Proposal changes through numbered Revisions, one of which is current. A vote is on
    one Revision: the vote counts of a Proposal are those of its current Revision, not a
    sum over its Revisions.

    ``repr`` shows its id and the first 60 characters of its text, such as
    ``Proposal('p-01', 'Plant 150 trees in the parks.')``.

    Args:
        id: The id of the Proposal.
        dataset: The dataset that the Proposal comes from.
        project_id: The id of the Project of the Proposal.
        article_id: The id of the parent article of the Proposal, kept as the source gave
            it, or ``None``.
        author_id: The pseudonym of the author. It is ``None`` in an aggregated dataset.
        created_at: When the Proposal was created, in ISO 8601, or ``None``.
        current_revision_id: The id of the current Revision. Without it, the Revision
            with the highest number is current.
    """

    project_id: str
    article_id: str | None = None
    author_id: str | None = None
    created_at: str | None = None
    current_revision_id: str | None = None

    #: The name of a Proposal in messages.
    noun: ClassVar[str] = "proposal"

    def _label(self) -> str:
        return self.text[:60]

    @property
    def project(self) -> Project:
        """The Project of the Proposal."""
        return self.dataset.projects[self.project_id]

    @property
    def revisions(self) -> "Listing[Revision]":
        """The Revisions of the Proposal, by increasing number."""
        return self.dataset._revisions_of(self.id)

    @property
    def current_revision(self) -> "Revision":
        """The Revision in force."""
        return self.dataset._current_revision_of(self.id)

    @property
    def text(self) -> str:
        """The affirmation of the current Revision."""
        return self.current_revision.affirmation

    @property
    def vote_counts(self) -> VoteCounts:
        """The vote counts of the current Revision."""
        return self.current_revision.vote_counts

    @property
    def is_amendment(self) -> bool:
        """Whether the Proposal is an Amendment: never for a plain Proposal."""
        return False


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Revision(Entity):
    """One numbered version of a Proposal. Votes are cast on a Revision.

    ``repr`` shows its id and its number, such as ``Revision('p-01.r2', 'r2')``.

    Args:
        id: The id of the Revision.
        dataset: The dataset that the Revision comes from.
        proposal_id: The id of the Proposal of the Revision.
        number: The number of the Revision, from 1, unique within its Proposal.
        affirmation: The text of the Proposal in this Revision.
        description: The description of the Proposal in this Revision.
        created_at: When the Revision was created, in ISO 8601, or ``None``.
        content_hash: The digest of the content that the source gave, or ``None``.
        amendment_id: The id of the amendment whose adoption produced this Revision, or
            ``None``.
    """

    proposal_id: str
    number: int = 1
    affirmation: str = ""
    description: str = ""
    created_at: str | None = None
    content_hash: str | None = None
    amendment_id: str | None = None

    #: The name of a Revision in messages.
    noun: ClassVar[str] = "revision"

    def _label(self) -> str:
        return f"r{self.number}"

    @property
    def proposal(self) -> Proposal:
        """The Proposal of the Revision."""
        return self.dataset.proposals[self.proposal_id]

    @property
    def is_current(self) -> bool:
        """Whether the Revision is the one in force for its Proposal."""
        return self.dataset._current_revision_of(self.proposal_id) is self

    @property
    def vote_counts(self) -> VoteCounts:
        """The five vote counts of the Revision, all zero when the source gave none."""
        return self.dataset._vote_counts_of(self.id)
