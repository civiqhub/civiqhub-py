# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of the product.

:class:`Entity` is what every object of the product shares: a frozen value, known by its
id, tied to the :class:`~civiqhub.dataset.Dataset` it comes from. :class:`Group`,
:class:`Project`, :class:`Article` (with its :class:`ArticleVersion`, its
:class:`Paragraph`, the :class:`Placement` of its Proposals and its :class:`Citation` of
other Proposals), :class:`Proposal`,
:class:`Amendment`, :class:`Revision`, :class:`Argument`, :class:`Actant` (with
:class:`Member` and :class:`Agent`) and :class:`Vote` are the objects of the product.

Actants and votes exist only in a pseudonymised dataset. In an aggregated one, reading
them raises :class:`~civiqhub.errors.ExposureError`.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from .listing import Listing
from .values import (
    ActantKind,
    AmendmentStatus,
    DeprecatedValue,
    Exposure,
    Participation,
    Position,
    Role,
    VoteCounts,
    VoteState,
)

if TYPE_CHECKING:
    from .dataset import Dataset

__all__ = [
    "Actant",
    "Agent",
    "Amendment",
    "Argument",
    "Article",
    "ArticleVersion",
    "Citation",
    "Entity",
    "Group",
    "Member",
    "Paragraph",
    "Placement",
    "Project",
    "Proposal",
    "Revision",
    "Vote",
]


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

    Every proposal of a Project has a parent article. :attr:`articles` gives the articles
    in the order of the Project.

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
    def articles(self) -> "Listing[Article]":
        """The articles of the Project, in the order of their positions.

        The order is the one the source gives in the key ``position`` of the rows: the
        same rows give the same order, load after load.
        """
        return self.dataset._articles_in(self.id)

    @property
    def citations(self) -> "Listing[Citation]":
        """The citations made in the version in force of each article of the Project.

        They come by article, in the order of the positions, then in the order of the text.
        """
        return Listing(citation for article in self.articles for citation in article.citations)

    def to_citation_edges(self) -> list[tuple[str, str]]:
        """Return the graph of the citations of the Project as a list of edges.

        Each edge is ``(article id, proposal id)``: the article cites the Proposal in its
        version in force. The ids are opaque strings, and no object of the SDK is in the
        list, so that a graph library reads it as it is. The edges come in the order of
        :attr:`citations`.
        """
        return [(citation.article_id, citation.proposal_id) for citation in self.citations]

    @property
    def deprecated(self) -> tuple[DeprecatedValue, ...]:
        """The deprecated values read in the row of the Project, such as the trace of a fork.

        It is empty for a Project of the current model. See
        :class:`~civiqhub.values.DeprecatedValue`.
        """
        return self.dataset._deprecated_of("project", self.id)

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

    @property
    def amendments(self) -> "Listing[Amendment]":
        """The Amendments of the Project, in the order of the rows."""
        return self.dataset._amendments_in(self.id)

    @property
    def arguments(self) -> "Listing[Argument]":
        """The Arguments on the Proposals of the Project, Amendments included.

        They come by Proposal, in the order of the rows, each Proposal with its Arguments
        in depth-first order.
        """
        return self.dataset._arguments_in(self.id)

    @property
    def actants(self) -> "Listing[Actant]":
        """The Actants of the dataset, in the order of the rows.

        A row of actants names no Project: these are all the Actants that the source gave.

        Raises:
            ExposureError: The dataset is aggregated.
        """
        self.dataset.require_individual_votes("project.actants")
        return self.dataset.actants

    @property
    def votes(self) -> "Listing[Vote]":
        """The votes on the Revisions of the Project, Amendments included.

        Raises:
            ExposureError: The dataset is aggregated.
        """
        self.dataset.require_individual_votes("project.votes")
        return self.dataset._votes_in(self.id)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Article(Entity):
    """An article of a Project: a text in numbered versions, which Proposals belong to.

    A Project is the set of its articles and of their versions. An article keeps every
    version it had; :attr:`current_version` is the one in force.

    ``repr`` shows its id and its title, such as ``Article('art-1', 'Green spaces')``.

    Args:
        id: The id of the article.
        dataset: The dataset that the article comes from.
        project_id: The id of the Project of the article.
        position: The place of the article in its Project, from 1, unique within the
            Project.
        title: The title of the article.
        description: The description of the article.
        current_version_number: The number of the version in force.
        published_at: When the version in force was published, in ISO 8601, or ``None``.
    """

    project_id: str
    position: int = 1
    title: str = ""
    description: str = ""
    current_version_number: int = 1
    published_at: str | None = None

    #: The name of an article in messages.
    noun: ClassVar[str] = "article"

    def _label(self) -> str:
        return self.title

    @property
    def project(self) -> Project:
        """The Project of the article."""
        return self.dataset.projects[self.project_id]

    @property
    def versions(self) -> "Listing[ArticleVersion]":
        """Every version of the article, by number."""
        return self.dataset._versions_of(self.id)

    @property
    def current_version(self) -> "ArticleVersion":
        """The version in force, the one numbered ``current_version_number``."""
        return self.dataset._current_version_of(self.id)

    @property
    def paragraphs(self) -> "Listing[Paragraph]":
        """The top of the tree of paragraphs of the version in force.

        These are the paragraphs that no other holds, in the order of the text. Each one
        gives its :attr:`~Paragraph.children`. :meth:`walk_paragraphs` gives them all.
        """
        return self.current_version.paragraphs

    def walk_paragraphs(self) -> "Iterator[Paragraph]":
        """Walk every paragraph of the version in force, in the order of the text.

        It is the tree read depth first: each paragraph, then the paragraphs it holds.
        """
        return self.current_version.walk_paragraphs()

    @property
    def proposals(self) -> "Listing[Proposal]":
        """The Proposals placed in the version in force, in the order of the text.

        A Proposal outside any paragraph comes first; then the Proposals of each
        paragraph, in the order of the text and of their ranks.
        """
        return self.current_version.proposals

    @property
    def citations(self) -> "Listing[Citation]":
        """The citations made in the version in force, in the order of the text."""
        return self.current_version.citations


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class ArticleVersion(Entity):
    """One numbered version of an article, frozen as it was published.

    A version never changes: a new text is a new version. The rows of versions carry no
    id of their own, so the id of a version is the id of its article and its number,
    such as ``art-1.v3``.

    ``repr`` shows its id and its number, such as ``ArticleVersion('art-1.v3', 'v3')``.

    Args:
        id: The id of the version.
        dataset: The dataset that the version comes from.
        article_id: The id of the article of the version.
        number: The number of the version, from 1, unique within its article.
        title: The title of the article in this version.
        body: The text of the article in this version.
        published_at: When the version was published, in ISO 8601, or ``None``.
    """

    article_id: str
    number: int = 1
    title: str = ""
    body: str = ""
    published_at: str | None = None

    #: The name of an article version in messages.
    noun: ClassVar[str] = "article version"

    def _label(self) -> str:
        return f"v{self.number}"

    @property
    def article(self) -> Article:
        """The article of the version."""
        return self.dataset.articles[self.article_id]

    @property
    def is_current(self) -> bool:
        """Whether the version is the one in force for its article."""
        return self.dataset._current_version_of(self.article_id) is self

    @property
    def paragraphs(self) -> "Listing[Paragraph]":
        """The top of the tree of paragraphs of the version, in the order of the text."""
        return self.dataset._top_paragraphs_of(self.id)

    def walk_paragraphs(self) -> "Iterator[Paragraph]":
        """Walk every paragraph of the version, in the order of the text.

        It is the tree read depth first: each paragraph, then the paragraphs it holds.
        """
        return iter(self.dataset._paragraphs_of(self.id))

    @property
    def placements(self) -> "Listing[Placement]":
        """Where each Proposal sits in the version, in the order of the text and of ranks."""
        return self.dataset._placements_of(self.id)

    @property
    def proposals(self) -> "Listing[Proposal]":
        """The Proposals placed in the version, in the order of :attr:`placements`."""
        return Listing(placement.proposal for placement in self.placements)

    @property
    def citations(self) -> "Listing[Citation]":
        """The citations made in the version, in the order of the text and of ranks."""
        return self.dataset._citations_in(self.id)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Paragraph(Entity):
    """A numbered division of an article version, made by a heading of level 1 to 4.

    The paragraphs of a version form a tree: a paragraph holds the paragraphs of a deeper
    level that follow it, up to the next paragraph of its level or of a higher one. The
    rows give no parent: the tree comes from the levels, in the order of the text.

    ``paragraph_id`` is the id that the source gives, never prefixed: the prefix
    ``p-`` belongs to the anchors of the text, and is left out when a row carries it. The
    same paragraph can keep its id from one version to the next, so the id of the entity
    also names its version, such as ``art-1.v3#3f2a``.

    ``repr`` shows its id and its number and title, such as
    ``Paragraph('art-1.v3#8c1d', '1.1 Parks')``.

    Args:
        id: The id of the paragraph.
        dataset: The dataset that the paragraph comes from.
        article_id: The id of the article of the paragraph.
        version_number: The number of the version of the paragraph.
        paragraph_id: The id of the paragraph within its version, without prefix.
        level: The level of its heading, from 1 to 4.
        number: The number of the paragraph, such as ``"1.2"``, as the source gives it.
        title: The title of the paragraph.
        parent_id: The id of the paragraph that holds this one, or ``None`` at the top.
    """

    article_id: str
    version_number: int = 1
    paragraph_id: str
    level: int = 1
    number: str = ""
    title: str = ""
    parent_id: str | None = None

    #: The name of a paragraph in messages.
    noun: ClassVar[str] = "paragraph"

    def _label(self) -> str:
        return " ".join(part for part in (self.number, self.title) if part)

    @property
    def version(self) -> ArticleVersion:
        """The article version of the paragraph."""
        return self.dataset.article_versions[f"{self.article_id}.v{self.version_number}"]

    @property
    def article(self) -> Article:
        """The article of the paragraph."""
        return self.dataset.articles[self.article_id]

    @property
    def parent(self) -> "Paragraph | None":
        """The paragraph that holds this one, or ``None`` at the top of the tree."""
        return None if self.parent_id is None else self.dataset.paragraphs[self.parent_id]

    @property
    def children(self) -> "Listing[Paragraph]":
        """The paragraphs that this one holds directly, in the order of the text."""
        return self.dataset._children_of_paragraph(self.id)

    @property
    def placements(self) -> "Listing[Placement]":
        """The placements in this paragraph, by rank."""
        return self.dataset._placements_in_paragraph(self.id)

    @property
    def proposals(self) -> "Listing[Proposal]":
        """The Proposals placed in this paragraph, by rank."""
        return Listing(placement.proposal for placement in self.placements)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Placement(Entity):
    """Where a Proposal sits in a version of its parent article: a paragraph and a rank.

    A Proposal is placed in its parent article only, and once per version; elsewhere it
    appears as a citation. A Proposal written before the first heading of the text sits
    outside any paragraph: its :attr:`paragraph` is ``None``. The id of a placement names
    the Proposal and the version, such as ``p-01@art-1.v3``.

    Args:
        id: The id of the placement.
        dataset: The dataset that the placement comes from.
        proposal_id: The id of the placed Proposal.
        article_id: The id of the article.
        version_number: The number of the version of the article.
        paragraph_id: The id of the paragraph within its version, without prefix, or
            ``None`` outside any paragraph.
        rank: The rank of the Proposal in its paragraph, as the source gives it: the
            Proposals of a paragraph come by rank, then in the order of the rows.
    """

    proposal_id: str
    article_id: str
    version_number: int = 1
    paragraph_id: str | None = None
    rank: int = 0

    #: The name of a placement in messages.
    noun: ClassVar[str] = "placement"

    @property
    def proposal(self) -> "Proposal":
        """The placed Proposal."""
        return self.dataset.proposals[self.proposal_id]

    @property
    def version(self) -> ArticleVersion:
        """The article version that the Proposal is placed in."""
        return self.dataset.article_versions[f"{self.article_id}.v{self.version_number}"]

    @property
    def paragraph(self) -> Paragraph | None:
        """The paragraph that the Proposal is placed in, or ``None`` outside any."""
        if self.paragraph_id is None:
            return None
        key = f"{self.article_id}.v{self.version_number}#{self.paragraph_id}"
        return self.dataset.paragraphs[key]


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Citation(Entity):
    """A Proposal cited in the text of an article that is not its parent article.

    A Proposal has one parent article, where it is placed; any other article can cite
    it, in a paragraph or before the first heading, even an article of another Project.
    The source of a citation is the article version that cites, its target is the cited
    Proposal, and the cited Revision is the one in force of that Proposal: the text cites
    the Proposal, never a Revision, and always shows its last adopted Revision.

    The cited Proposal may belong to a Project that the dataset does not hold: its id is
    kept, and reading the Proposal then raises :class:`~civiqhub.errors.NotFoundError`.
    The id of a citation names the Proposal and the version, such as ``p-01@art-2.v1``.

    Args:
        id: The id of the citation.
        dataset: The dataset that the citation comes from.
        proposal_id: The id of the cited Proposal.
        article_id: The id of the article that cites it.
        version_number: The number of the version of the article.
        paragraph_id: The id of the paragraph within its version, without prefix, or
            ``None`` outside any paragraph.
        rank: The rank of the citation in its paragraph, as the source gives it.
    """

    proposal_id: str
    article_id: str
    version_number: int = 1
    paragraph_id: str | None = None
    rank: int = 0

    #: The name of a citation in messages.
    noun: ClassVar[str] = "citation"

    @property
    def proposal(self) -> "Proposal":
        """The cited Proposal, the target of the citation.

        Raises:
            NotFoundError: The Proposal belongs to a Project that the dataset does not hold.
        """
        return self.dataset.proposals[self.proposal_id]

    @property
    def version(self) -> ArticleVersion:
        """The article version that cites the Proposal, the source of the citation."""
        return self.dataset.article_versions[f"{self.article_id}.v{self.version_number}"]

    @property
    def article(self) -> Article:
        """The article that cites the Proposal."""
        return self.dataset.articles[self.article_id]

    @property
    def paragraph(self) -> Paragraph | None:
        """The paragraph where the Proposal is cited, or ``None`` outside any."""
        if self.paragraph_id is None:
            return None
        key = f"{self.article_id}.v{self.version_number}#{self.paragraph_id}"
        return self.dataset.paragraphs[key]

    @property
    def cited_revision(self) -> "Revision":
        """The Revision that the citation shows: the one in force of the cited Proposal.

        It is read, never stored: when an Amendment is adopted, the citation shows the new
        Revision.

        Raises:
            NotFoundError: The Proposal belongs to a Project that the dataset does not hold.
        """
        return self.proposal.current_revision


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
    def article(self) -> Article | None:
        """The parent article of the Proposal, or ``None`` for a Proposal of a Group.

        Raises:
            NotFoundError: The Proposal names a parent article that the dataset does not
                hold, as when the source gives no articles.
        """
        return None if self.article_id is None else self.dataset.articles[self.article_id]

    @property
    def placement(self) -> Placement | None:
        """Where the Proposal sits in the version in force of its parent article.

        It is ``None`` for a Proposal of a Group, and when the source gives no placement
        of the Proposal in that version.

        Raises:
            NotFoundError: The Proposal names a parent article that the dataset does not
                hold.
        """
        article = self.article
        if article is None:
            return None
        return self.dataset._placement_of(self.id, article.current_version.id)

    @property
    def citations(self) -> "Listing[Citation]":
        """The citations of this Proposal in the version in force of each citing article.

        A citation is made by an article, not by a Proposal: these are the citations that
        come to this Proposal. To read what an article cites, use
        :attr:`Article.citations`.
        """
        return self.dataset._citations_of(self.id)

    @property
    def deprecated(self) -> tuple[DeprecatedValue, ...]:
        """The deprecated values read in the rows of this Proposal.

        They come from its row of ``proposals``, then from the rows of ``amendments`` for
        it: the status ``DRAFT`` or the kind ``SYNC`` of an Amendment, or a creation, a
        removal or a pending change, which builds no Amendment. It is empty for a Proposal
        of the current model. See :class:`~civiqhub.values.DeprecatedValue`.
        """
        return self.dataset._deprecated_of("proposal", self.id)

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
        """Whether the Proposal is an Amendment."""
        return False

    @property
    def amendments(self) -> "Listing[Amendment]":
        """The Amendments that target this Proposal directly, in the order of the rows."""
        return self.dataset._amendments_of(self.id)

    def walk_amendments(self) -> Iterator[tuple[int, "Proposal"]]:
        """Walk the tree of the Amendments of this Proposal, depth first.

        Yields:
            ``(0, self)`` first, then each Amendment with its depth: 1 for an Amendment
            to this Proposal, 2 for an Amendment to such an Amendment, and so on.
        """
        stack: list[tuple[int, Proposal]] = [(0, self)]
        while stack:
            depth, proposal = stack.pop()
            yield depth, proposal
            stack.extend((depth + 1, child) for child in reversed(proposal.amendments))

    @property
    def arguments(self) -> "Listing[Argument]":
        """The Arguments on this Proposal, depth first: each one, then its replies."""
        return self.dataset._arguments_of(self.id)

    @property
    def votes(self) -> "Listing[Vote]":
        """The votes on the current Revision.

        Raises:
            ExposureError: The dataset is aggregated.
        """
        self.dataset.require_individual_votes("proposal.votes")
        return self.dataset._votes_on(self.current_revision.id)

    @property
    def author(self) -> "Actant | None":
        """The Actant who wrote the Proposal, or ``None`` when the source does not say.

        Raises:
            ExposureError: The dataset is aggregated.
        """
        self.dataset.require_individual_votes("proposal.author")
        return None if self.author_id is None else self.dataset.actants[self.author_id]


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

    @property
    def amendment(self) -> "Amendment | None":
        """The Amendment whose adoption produced this Revision, or ``None``.

        It is also ``None`` when ``amendment_id`` names a row of ``amendments`` that builds
        no Amendment: a deprecated creation or removal, marked in
        :attr:`Dataset.deprecated <civiqhub.dataset.Dataset.deprecated>`.
        """
        if self.amendment_id is None:
            return None
        return self.dataset._amendment_by_row(self.amendment_id)

    @property
    def votes(self) -> "Listing[Vote]":
        """The votes on the Revision, in the order of the rows.

        Raises:
            ExposureError: The dataset is aggregated. ``vote_counts`` stays readable.
        """
        self.dataset.require_individual_votes("revision.votes")
        return self.dataset._votes_on(self.id)


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Amendment(Proposal):
    """A Proposal that amends another Proposal, on one Revision of it.

    An Amendment has its own Revisions, votes and vote counts, as every Proposal. Once
    adopted, it produces a new Revision of the Proposal it targets. Only the local change
    of a Proposal exists: an Amendment has no type.

    An old row can hold the deprecated status ``DRAFT``, read as ``OPEN``, or the
    deprecated kind ``SYNC`` of a cascade. The Amendment is built, and
    :attr:`~Proposal.deprecated` marks these values.

    Args:
        id: The id of the Proposal that is an Amendment.
        dataset: The dataset that the Amendment comes from.
        project_id: The id of the Project of the Amendment.
        article_id: The id of the parent article, or ``None``.
        author_id: The pseudonym of the author. It is ``None`` in an aggregated dataset.
        created_at: When the Amendment was created, in ISO 8601, or ``None``.
        current_revision_id: The id of the current Revision of the Amendment.
        amendment_id: The id of the row of the section ``amendments``.
        target_id: The id of the Proposal that the Amendment targets.
        target_revision_id: The id of the Revision of the target that it amends.
        status: Whether the Amendment is open, adopted or rejected.
        adopted_revision_id: The id of the Revision of the target that its adoption
            produced, or ``None``.
        is_stale: Whether the target changed since the Amendment was written.
    """

    amendment_id: str
    target_id: str
    target_revision_id: str
    status: AmendmentStatus = AmendmentStatus.OPEN
    adopted_revision_id: str | None = None
    is_stale: bool = False

    #: The name of an Amendment in messages.
    noun: ClassVar[str] = "amendment"

    @property
    def is_amendment(self) -> bool:
        """Whether the Proposal is an Amendment: always for an Amendment."""
        return True

    @property
    def target(self) -> Proposal:
        """The Proposal that the Amendment targets."""
        return self.dataset.proposals[self.target_id]

    @property
    def target_revision(self) -> Revision:
        """The Revision of the target that the Amendment amends."""
        return self.dataset.revisions[self.target_revision_id]

    @property
    def is_adopted(self) -> bool:
        """Whether the Amendment was adopted."""
        return self.status is AmendmentStatus.ADOPTED

    @property
    def adopted_revision(self) -> Revision | None:
        """The Revision of the target that the adoption produced, or ``None``."""
        if self.adopted_revision_id is None:
            return None
        return self.dataset.revisions[self.adopted_revision_id]

    @property
    def root(self) -> Proposal:
        """The first Proposal that is not an Amendment, following the targets."""
        proposal: Proposal = self
        while isinstance(proposal, Amendment):
            proposal = proposal.target
        return proposal


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Argument(Entity):
    """A reasoned stance on a Proposal. Arguments reply to each other as a tree.

    ``repr`` shows its id and the first 60 characters of its text.

    Args:
        id: The id of the Argument.
        dataset: The dataset that the Argument comes from.
        proposal_id: The id of the Proposal that the Argument is about.
        revision_id: The id of the Revision of that Proposal it was written on, or
            ``None``.
        author_id: The pseudonym of the author. It is ``None`` in an aggregated dataset.
        position: For, against or neither, or ``None`` when the source does not say.
        text: The text of the Argument.
        score: The score, from -2 to +2, when the source gives one, or ``None``.
        parent_id: The id of the Argument that this one replies to, or ``None``.
        n_supports: How many times the Argument was supported.
    """

    proposal_id: str
    revision_id: str | None = None
    author_id: str | None = None
    position: Position | None = None
    text: str = ""
    score: int | None = None
    parent_id: str | None = None
    n_supports: int = 0

    #: The name of an Argument in messages.
    noun: ClassVar[str] = "argument"

    def _label(self) -> str:
        return self.text[:60]

    @property
    def proposal(self) -> Proposal:
        """The Proposal that the Argument is about."""
        return self.dataset.proposals[self.proposal_id]

    @property
    def revision(self) -> Revision | None:
        """The Revision that the Argument was written on, or ``None``."""
        if self.revision_id is None:
            return None
        return self.dataset.revisions[self.revision_id]

    @property
    def parent(self) -> "Argument | None":
        """The Argument that this one replies to, or ``None`` at the top of a thread."""
        if self.parent_id is None:
            return None
        return self.dataset.arguments[self.parent_id]

    @property
    def replies(self) -> "Listing[Argument]":
        """The Arguments that reply to this one directly, in the order of the rows."""
        return self.dataset._replies_to(self.id)

    @property
    def depth(self) -> int:
        """How deep the Argument is in its thread: 0 at the top."""
        return self.dataset._depth_of(self.id)

    @property
    def author(self) -> "Actant | None":
        """The Actant who wrote the Argument, or ``None`` when the source does not say.

        Raises:
            ExposureError: The dataset is aggregated.
        """
        self.dataset.require_individual_votes("argument.author")
        return None if self.author_id is None else self.dataset.actants[self.author_id]


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Actant(Entity):
    """Anyone who acts in a Project: a human member or an agent.

    The SDK knows an Actant by its pseudonym only, which is its id: never by a name, a
    display name, an e-mail address or an internal id. A pseudonym is valid in its
    dataset only. Two Actants from two datasets are never equal, even with the same
    pseudonym: an Actant cannot be followed from one load to the next.

    The dataset builds a :class:`Member` for a human, an :class:`Agent` for an agent, and
    an Actant of kind ``other`` otherwise.

    Args:
        id: The pseudonym of the Actant.
        dataset: The dataset that the Actant comes from.
        kind: Human, agent or other.
        role: The role of the Actant in the Project, or ``None`` when the source does not
            say.
    """

    kind: ActantKind = ActantKind.HUMAN
    role: Role | None = None

    #: The name of an Actant in messages.
    noun: ClassVar[str] = "actant"

    @property
    def pseudonym(self) -> str:
        """The pseudonym of the Actant: its id."""
        return self.id

    @property
    def votes(self) -> "Listing[Vote]":
        """The votes of the Actant, in the order of the rows."""
        return self.dataset._votes_of(self.id)

    @property
    def arguments(self) -> "Listing[Argument]":
        """The Arguments that the Actant wrote, in the order of the rows."""
        return self.dataset._arguments_by(self.id)

    def vote_on(self, target: Proposal | Revision) -> "Vote | None":
        """Return the vote of the Actant on a Revision, or ``None``.

        Args:
            target: A Revision, or a Proposal, for its current Revision. A vote on an
                older Revision of the Proposal is not returned.
        """
        revision = target.current_revision if isinstance(target, Proposal) else target
        return self.dataset._vote_of(self.id, revision.id)

    def vote_state_on(self, target: Proposal | Revision) -> VoteState:
        """Say whether the Actant voted on a Revision, abstained, or did not see it.

        The rule has three steps. A vote exists: ``VOTED``. Otherwise, when the dataset
        records impressions: ``ABSTAINED`` if the Revision was shown to the Actant,
        ``NOT_SHOWN`` if not. Otherwise: ``UNKNOWN``. A missing vote is never read as a
        neutral vote, nor as an abstention when the impressions are not recorded.

        Args:
            target: A Revision, or a Proposal, for its current Revision.
        """
        revision = target.current_revision if isinstance(target, Proposal) else target
        if self.dataset._vote_of(self.id, revision.id) is not None:
            return VoteState.VOTED
        if not self.dataset.has_impressions:
            return VoteState.UNKNOWN
        if self.dataset._was_shown(self.id, revision.id):
            return VoteState.ABSTAINED
        return VoteState.NOT_SHOWN


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Member(Actant):
    """A human member of a Project, known by a pseudonym."""


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Agent(Actant):
    """A software agent that takes part with the same grammar as a member."""


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Vote(Entity):
    """The vote of one Actant on one Revision, from -2 to +2.

    0 is a deliberate choice, not an abstention: an abstention is the absence of a vote.
    ``repr`` shows its id and its signed score, such as ``Vote('m-001@p-01.r2', '+2')``.

    Args:
        id: ``"{actant_id}@{revision_id}"``.
        dataset: The dataset that the vote comes from.
        actant_id: The pseudonym of the Actant who voted.
        revision_id: The id of the Revision voted on.
        score: The score, from -2 to +2.
        cast_at: When the vote was cast, in ISO 8601, or ``None``.
    """

    actant_id: str
    revision_id: str
    score: int
    cast_at: str | None = None

    #: The name of a vote in messages.
    noun: ClassVar[str] = "vote"

    def _label(self) -> str:
        return f"{self.score:+d}" if self.score else "0"

    @property
    def actant(self) -> Actant:
        """The Actant who voted."""
        return self.dataset.actants[self.actant_id]

    @property
    def revision(self) -> Revision:
        """The Revision voted on."""
        return self.dataset.revisions[self.revision_id]

    @property
    def proposal(self) -> Proposal:
        """The Proposal of the Revision voted on."""
        return self.revision.proposal

    def to_record(self) -> tuple[str, str, int]:
        """Return ``(actant_id, revision_id, score)``."""
        return (self.actant_id, self.revision_id, self.score)
