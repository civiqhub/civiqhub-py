# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The data of a source at one instant, as one frozen graph of objects.

A :class:`Dataset` is built from rows in the format :data:`FORMAT`: a dictionary that JSON
can write, with an entry ``format``, an instant ``as_of``, a level of ``exposure`` and one
list of rows per section. A missing section is an empty list, and a key that a row does
not need is ignored.

This version builds six sections: ``groups``, ``projects``, ``participation``,
``proposals``, ``revisions`` and ``vote_counts``. The other sections of the format
(``articles``, ``article_versions``, ``paragraphs``, ``placements``, ``citations``,
``amendments``, ``arguments``, ``actants``, ``votes`` and ``impressions``) are kept as
they are. They count in the fingerprint and come back from :meth:`Dataset.to_dict`, but no
object is built from them yet.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import fields
from datetime import datetime, timedelta
from typing import Any, TypeVar

from .entities import Entity, Group, Project, Proposal, Revision
from .errors import ExposureError, NotFoundError, ValidationError
from .listing import Listing
from .values import Exposure, Participation, VoteCounts

__all__ = ["FORMAT", "Dataset"]

#: The format of the rows that a :class:`Dataset` is built from and gives back.
FORMAT = "civiqhub.dataset/0"

# Every section of the format. A section built by a later version is only checked to be
# a list of rows.
_SECTIONS = (
    "groups",
    "projects",
    "participation",
    "articles",
    "article_versions",
    "paragraphs",
    "placements",
    "citations",
    "proposals",
    "revisions",
    "vote_counts",
    "amendments",
    "arguments",
    "actants",
    "votes",
    "impressions",
)

# The sections that describe individuals; an aggregated dataset leaves them empty.
_INDIVIDUAL = ("actants", "votes", "impressions")

# How many slugs a message cites at most.
_CITED = 8

_Row = dict[str, Any]
_SluggedT = TypeVar("_SluggedT", Group, Project)
_EntityT = TypeVar("_EntityT", bound=Entity)

# The vote counts of a revision without a row of vote counts.
_NO_VOTE = VoteCounts()


class Dataset:
    """Everything a source gave at one instant, at one level of exposure, frozen.

    A dataset checks its rows once, when it is built, and then holds frozen objects:
    nothing can be added, removed or changed, and no navigation reads the network. Two
    datasets built from the same rows have the same :meth:`fingerprint`, but their
    objects differ, since an object of the product belongs to its dataset.

    Args:
        rows: The rows, in the format :data:`FORMAT`. They are copied: changing them
            afterwards does not change the dataset.
        source: Where the rows come from, such as ``"memory"``. It is shown by ``repr``
            and must never hold a secret.

    Raises:
        ValidationError: The rows are not in the format :data:`FORMAT`, or break a rule
            of the model. The message names the row and the rule.
    """

    __slots__ = (
        "_as_of",
        "_children",
        "_current_revisions",
        "_exposure",
        "_groups",
        "_participation",
        "_projects",
        "_projects_by_group",
        "_proposals",
        "_proposals_by_project",
        "_revisions",
        "_revisions_by_project",
        "_revisions_by_proposal",
        "_rows",
        "_source",
        "_vote_counts",
    )

    _as_of: str
    _children: dict[str, Listing[Group]]
    _current_revisions: dict[str, Revision]
    _exposure: Exposure
    _groups: Listing[Group]
    _participation: dict[str, Participation]
    _projects: Listing[Project]
    _projects_by_group: dict[str, Listing[Project]]
    _proposals: Listing[Proposal]
    _proposals_by_project: dict[str, Listing[Proposal]]
    _revisions: Listing[Revision]
    _revisions_by_project: dict[str, Listing[Revision]]
    _revisions_by_proposal: dict[str, Listing[Revision]]
    _rows: _Row
    _source: str
    _vote_counts: dict[str, VoteCounts]

    def __init__(self, rows: Mapping[str, Any], *, source: str = "memory") -> None:
        if not isinstance(source, str):
            raise ValidationError(f"The source of a dataset is a string; got {source!r}.")
        data = _copy(rows)
        received = data.get("format")
        if received != FORMAT:
            raise ValidationError(
                f"These rows are not a CiviqHub dataset: their format is {received!r}, "
                f"and the expected format is {FORMAT!r}."
            )
        sections = {name: _section(data, name) for name in _SECTIONS}
        exposure = _read_exposure(data.get("exposure"))
        if exposure is Exposure.AGGREGATED:
            for name in _INDIVIDUAL:
                if sections[name]:
                    raise ValidationError(
                        f"An aggregated dataset holds no individual rows, and its section "
                        f"{name!r} has {len(sections[name])}. Set exposure to "
                        f"'pseudonymised', or leave the section out."
                    )
        _set = object.__setattr__
        _set(self, "_rows", data)
        _set(self, "_source", source)
        _set(self, "_as_of", _read_as_of(data.get("as_of")))
        _set(self, "_exposure", exposure)
        projects = self._build_groups(sections)
        self._build_proposals(sections, projects)

    def _build_groups(self, sections: Mapping[str, list[_Row]]) -> list[Project]:
        groups = [
            self._group(row, f"groups[{index}]") for index, row in enumerate(sections["groups"])
        ]
        projects = [
            self._project(row, f"projects[{index}]")
            for index, row in enumerate(sections["projects"])
        ]
        _check_unique(groups, "groups")
        _check_unique(projects, "projects")
        known_groups = {group.id for group in groups}
        for index, group in enumerate(groups):
            if group.parent_id is not None and group.parent_id not in known_groups:
                raise ValidationError(
                    f"The row groups[{index}] (id {group.id!r}) has the parent_id "
                    f"{group.parent_id!r}, and no group has this id: parent_id names a group "
                    f"of the dataset."
                )
        _check_tree(groups)
        for index, project in enumerate(projects):
            if project.group_id is not None and project.group_id not in known_groups:
                raise ValidationError(
                    f"The row projects[{index}] (id {project.id!r}) has the group_id "
                    f"{project.group_id!r}, and no group has this id: group_id names a group "
                    f"of the dataset."
                )
        children: dict[str, list[Group]] = {}
        for group in groups:
            if group.parent_id is not None:
                children.setdefault(group.parent_id, []).append(group)
        by_group: dict[str, list[Project]] = {}
        for project in projects:
            if project.group_id is not None:
                by_group.setdefault(project.group_id, []).append(project)
        _set = object.__setattr__
        _set(self, "_groups", Listing(groups))
        _set(self, "_projects", Listing(projects))
        _set(self, "_children", {key: Listing(items) for key, items in children.items()})
        _set(self, "_projects_by_group", {key: Listing(items) for key, items in by_group.items()})
        _set(self, "_participation", _read_participation(sections["participation"], projects))
        return projects

    def _build_proposals(self, sections: Mapping[str, list[_Row]], projects: list[Project]) -> None:
        proposals = [
            self._proposal(row, f"proposals[{index}]")
            for index, row in enumerate(sections["proposals"])
        ]
        _check_unique(proposals, "proposals", ("id",))
        known_projects = {project.id for project in projects}
        for index, proposal in enumerate(proposals):
            if proposal.project_id not in known_projects:
                raise ValidationError(
                    f"The row proposals[{index}] (id {proposal.id!r}) has the project_id "
                    f"{proposal.project_id!r}, and no project has this id: project_id names a "
                    f"project of the dataset."
                )
        revisions = [
            self._revision(row, f"revisions[{index}]")
            for index, row in enumerate(sections["revisions"])
        ]
        _check_unique(revisions, "revisions", ("id",))
        rank = {proposal.id: index for index, proposal in enumerate(proposals)}
        numbers: dict[tuple[str, int], int] = {}
        for index, revision in enumerate(revisions):
            if revision.proposal_id not in rank:
                raise ValidationError(
                    f"The row revisions[{index}] (id {revision.id!r}) has the proposal_id "
                    f"{revision.proposal_id!r}, and no proposal has this id: proposal_id names "
                    f"a proposal of the dataset."
                )
            key = (revision.proposal_id, revision.number)
            if key in numbers:
                raise ValidationError(
                    f"The rows revisions[{numbers[key]}] and revisions[{index}] are both the "
                    f"revision number {revision.number} of the proposal "
                    f"{revision.proposal_id!r}: the numbers of the revisions of a proposal "
                    f"differ."
                )
            numbers[key] = index
        revisions.sort(key=lambda revision: (rank[revision.proposal_id], revision.number))
        by_proposal: dict[str, list[Revision]] = {}
        for revision in revisions:
            by_proposal.setdefault(revision.proposal_id, []).append(revision)
        current: dict[str, Revision] = {}
        for index, proposal in enumerate(proposals):
            own = by_proposal.get(proposal.id)
            if not own:
                raise ValidationError(
                    f"The proposal {proposal.id!r} (proposals[{index}]) has no revision: a "
                    f"proposal has at least one, in the section 'revisions'."
                )
            if proposal.current_revision_id is None:
                current[proposal.id] = own[-1]
                continue
            found = next((r for r in own if r.id == proposal.current_revision_id), None)
            if found is None:
                raise ValidationError(
                    f"The row proposals[{index}] (id {proposal.id!r}) has the "
                    f"current_revision_id {proposal.current_revision_id!r}, which is not a "
                    f"revision of this proposal."
                )
            current[proposal.id] = found
        by_project: dict[str, list[Proposal]] = {}
        revisions_by_project: dict[str, list[Revision]] = {}
        for proposal in proposals:
            if not proposal.is_amendment:
                by_project.setdefault(proposal.project_id, []).append(proposal)
            revisions_by_project.setdefault(proposal.project_id, []).extend(
                by_proposal[proposal.id]
            )
        _set = object.__setattr__
        _set(self, "_proposals", Listing(proposals))
        _set(self, "_revisions", Listing(revisions))
        _set(self, "_current_revisions", current)
        _set(self, "_revisions_by_proposal", _freeze(by_proposal))
        _set(self, "_proposals_by_project", _freeze(by_project))
        _set(self, "_revisions_by_project", _freeze(revisions_by_project))
        _set(self, "_vote_counts", _read_vote_counts(sections["vote_counts"], revisions))

    def _group(self, row: _Row, where: str) -> Group:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        return Group(
            id=id,
            dataset=self,
            slug=_identifier(row, "slug", where),
            name=_text(row, "name", where),
            description=_text(row, "description", where),
            parent_id=_optional_identifier(row, "parent_id", where),
        )

    def _project(self, row: _Row, where: str) -> Project:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        return Project(
            id=id,
            dataset=self,
            slug=_identifier(row, "slug", where),
            name=_text(row, "name", where),
            description=_text(row, "description", where),
            group_id=_optional_identifier(row, "group_id", where),
        )

    def _proposal(self, row: _Row, where: str) -> Proposal:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        author_id = _optional_identifier(row, "author_id", where)
        if author_id is not None and self._exposure is Exposure.AGGREGATED:
            raise ValidationError(
                f"The row {where} has an author_id, and an aggregated dataset holds no "
                f"pseudonym. Set exposure to 'pseudonymised', or leave author_id out."
            )
        return Proposal(
            id=id,
            dataset=self,
            project_id=_identifier(row, "project_id", where),
            article_id=_optional_identifier(row, "article_id", where),
            author_id=author_id,
            created_at=_optional_text(row, "created_at", where),
            current_revision_id=_optional_identifier(row, "current_revision_id", where),
        )

    def _revision(self, row: _Row, where: str) -> Revision:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        return Revision(
            id=id,
            dataset=self,
            proposal_id=_identifier(row, "proposal_id", where),
            number=_number(row, where),
            affirmation=_text(row, "affirmation", where),
            description=_text(row, "description", where),
            created_at=_optional_text(row, "created_at", where),
            content_hash=_optional_text(row, "content_hash", where),
            amendment_id=_optional_identifier(row, "amendment_id", where),
        )

    @classmethod
    def from_dict(cls, rows: Mapping[str, Any], *, source: str = "memory") -> "Dataset":
        """Build a dataset from rows in the format :data:`FORMAT`.

        It is the same as calling :class:`Dataset`.

        Args:
            rows: The rows. They are copied.
            source: Where the rows come from, never a secret.

        Raises:
            ValidationError: The rows are not in the format, or break a rule of the model.
        """
        return cls(rows, source=source)

    @property
    def as_of(self) -> str:
        """The instant that the data describes, in ISO 8601 and in UTC."""
        return self._as_of

    @property
    def exposure(self) -> Exposure:
        """The level of detail of the data: aggregated or pseudonymised."""
        return self._exposure

    @property
    def source(self) -> str:
        """Where the rows come from, such as ``"memory"``. It never holds a secret."""
        return self._source

    @property
    def groups(self) -> Listing[Group]:
        """Every Group of the dataset, in the order of the rows."""
        return self._groups

    @property
    def projects(self) -> Listing[Project]:
        """Every Project of the dataset, in the order of the rows."""
        return self._projects

    @property
    def proposals(self) -> Listing[Proposal]:
        """Every Proposal of the dataset, in the order of the rows."""
        return self._proposals

    @property
    def revisions(self) -> Listing[Revision]:
        """Every Revision of the dataset, by Proposal, then by number.

        The Proposals come in the order of their rows.
        """
        return self._revisions

    def project(self, ref: str | None = None) -> Project:
        """Return the Project with this id or slug, or the only Project.

        Args:
            ref: The id or the slug of the Project. Without it, the dataset must hold
                exactly one Project.

        Raises:
            NotFoundError: No Project has this id or slug, or ``ref`` is left out and the
                dataset holds no Project or several. The message lists up to eight slugs.
        """
        return _find(self.projects, ref, "project")

    def group(self, ref: str | None = None) -> Group:
        """Return the Group with this id or slug, or the only Group.

        Args:
            ref: The id or the slug of the Group. Without it, the dataset must hold
                exactly one Group.

        Raises:
            NotFoundError: No Group has this id or slug, or ``ref`` is left out and the
                dataset holds no Group or several. The message lists up to eight slugs.
        """
        return _find(self.groups, ref, "group")

    @property
    def has_individual_votes(self) -> bool:
        """Whether the dataset holds individual votes, which the pseudonymised level does."""
        return self.exposure is Exposure.PSEUDONYMISED

    def require_individual_votes(self, what: str) -> None:
        """Check that the dataset holds individual votes, before reading them.

        Args:
            what: What needs the individual votes, such as ``"the vote matrix"``. The
                message of the error starts with it.

        Raises:
            ExposureError: The dataset is aggregated. Its hint says how to get the
                pseudonymised level.
        """
        if not self.has_individual_votes:
            raise ExposureError(
                f"{what[:1].upper()}{what[1:]} needs individual votes, and this dataset is "
                f"aggregated: it holds the vote counts of each revision and no individual vote."
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a copy of the rows, ready for ``json.dump``."""
        return _copy(self._rows)

    def fingerprint(self) -> str:
        """Return a short digest of the rows: the same rows give the same fingerprint.

        It is the first 16 hexadecimal characters of the SHA-256 of the rows written in
        JSON, with sorted keys and without spaces. Every section counts, including those
        that this version does not build. The source does not count.
        """
        text = json.dumps(self._rows, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def __repr__(self) -> str:
        return (
            f"Dataset({_count(len(self.projects), 'project')}, "
            f"{_count(len(self.proposals), 'proposal')}, {self.exposure.value}, "
            f"as of {self.as_of}, from {self.source})"
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"A Dataset cannot be changed, so {name!r} cannot be set. Build a new Dataset "
            f"from new rows."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"A Dataset cannot be changed, so {name!r} cannot be deleted. Build a new Dataset "
            f"from new rows."
        )

    # Navigation for the entities, which read their links through these indexes.

    def _groups_in(self, group_id: str) -> Listing[Group]:
        return self._children.get(group_id, Listing())

    def _projects_in(self, group_id: str) -> Listing[Project]:
        return self._projects_by_group.get(group_id, Listing())

    def _participation_of(self, project_id: str) -> Participation:
        return self._participation[project_id]

    def _proposals_in(self, project_id: str) -> Listing[Proposal]:
        return self._proposals_by_project.get(project_id, Listing())

    def _revisions_in(self, project_id: str) -> Listing[Revision]:
        return self._revisions_by_project.get(project_id, Listing())

    def _revisions_of(self, proposal_id: str) -> Listing[Revision]:
        return self._revisions_by_proposal[proposal_id]

    def _current_revision_of(self, proposal_id: str) -> Revision:
        return self._current_revisions[proposal_id]

    def _vote_counts_of(self, revision_id: str) -> VoteCounts:
        return self._vote_counts.get(revision_id, _NO_VOTE)


def _copy(rows: object) -> _Row:
    if not isinstance(rows, Mapping):
        raise ValidationError(
            f"The rows of a dataset are a dictionary of sections; got {type(rows).__name__}."
        )
    try:
        text = json.dumps(dict(rows), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"The rows of a dataset are JSON data: {error}.") from None
    copy: _Row = json.loads(text)
    return copy


def _section(data: _Row, name: str) -> list[_Row]:
    rows = data.get(name, [])
    if not isinstance(rows, list):
        raise ValidationError(f"The section {name!r} is a list of rows; got {type(rows).__name__}.")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValidationError(
                f"The row {name}[{index}] is not a JSON object, as every row is; got {row!r}."
            )
    return rows


def _read_as_of(value: object) -> str:
    message = (
        f"The rows have no valid 'as_of': it is an instant in ISO 8601 and in UTC, such as "
        f"'2026-11-16T09:00:00Z'; got {value!r}."
    )
    if not isinstance(value, str):
        raise ValidationError(message)
    try:
        instant = datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(message) from None
    if instant.utcoffset() != timedelta(0):
        raise ValidationError(message)
    return value


def _read_exposure(value: object) -> Exposure:
    if isinstance(value, str) and value in {kind.value for kind in Exposure}:
        return Exposure(value)
    raise ValidationError(
        f"The rows have no valid 'exposure': it is 'aggregated' or 'pseudonymised'; got {value!r}."
    )


def _identifier(row: _Row, key: str, where: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError(
            f"The row {where} has no valid {key!r}: it is a non-empty string; got {value!r}."
        )
    return value


def _optional_identifier(row: _Row, key: str, where: str) -> str | None:
    if row.get(key) is None:
        return None
    return _identifier(row, key, where)


def _text(row: _Row, key: str, where: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"The row {where} has a {key!r} that is not a string: {value!r}.")
    return value


def _optional_text(row: _Row, key: str, where: str) -> str | None:
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        raise ValidationError(f"The row {where} has a {key!r} that is not a string: {value!r}.")
    return value


def _number(row: _Row, where: str) -> int:
    value = row.get("number")
    if value is None:
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationError(
            f"The row {where} has the number {value!r}: the number of a revision is a "
            f"positive integer."
        )
    return value


def _freeze(groups: Mapping[str, list[_EntityT]]) -> dict[str, Listing[_EntityT]]:
    return {key: Listing(items) for key, items in groups.items()}


def _read_vote_counts(rows: list[_Row], revisions: list[Revision]) -> dict[str, VoteCounts]:
    known = {revision.id for revision in revisions}
    seen: dict[str, int] = {}
    vote_counts: dict[str, VoteCounts] = {}
    for index, row in enumerate(rows):
        revision_id = _identifier(row, "revision_id", f"vote_counts[{index}]")
        if revision_id not in known:
            raise ValidationError(
                f"The row vote_counts[{index}] has the revision_id {revision_id!r}, and no "
                f"revision has this id: revision_id names a revision of the dataset."
            )
        if revision_id in seen:
            raise ValidationError(
                f"The rows vote_counts[{seen[revision_id]}] and vote_counts[{index}] are both "
                f"for the revision {revision_id!r}: a revision has one row of vote counts."
            )
        seen[revision_id] = index
        counts = row.get("counts")
        # VoteCounts checks the five counts and says what it received.
        received: Any = tuple(counts) if isinstance(counts, list) else counts
        try:
            vote_counts[revision_id] = VoteCounts(received)
        except ValidationError as error:
            raise ValidationError(
                f"The row vote_counts[{index}] (revision {revision_id!r}) breaks a rule. {error}"
            ) from None
    return vote_counts


def _check_unique(
    items: Sequence[Entity], section: str, keys: tuple[str, ...] = ("id", "slug")
) -> None:
    for key in keys:
        seen: dict[str, int] = {}
        for index, item in enumerate(items):
            value: str = getattr(item, key)
            if value in seen:
                raise ValidationError(
                    f"The rows {section}[{seen[value]}] and {section}[{index}] have the same "
                    f"{key} {value!r}: a {key} appears once in the section {section!r}."
                )
            seen[value] = index


def _check_tree(groups: list[Group]) -> None:
    parent_of = {group.id: group.parent_id for group in groups}
    for index, group in enumerate(groups):
        path = [group.id]
        parent = group.parent_id
        while parent is not None:
            path.append(parent)
            if parent == group.id:
                raise ValidationError(
                    f"The row groups[{index}] (id {group.id!r}) is its own ancestor: "
                    f"{' -> '.join(path)}. The groups form a tree, through parent_id."
                )
            if len(path) > len(groups) + 1:
                break  # a cycle above this group, reported from a group inside it
            parent = parent_of.get(parent)


def _read_participation(rows: list[_Row], projects: list[Project]) -> dict[str, Participation]:
    known = {project.id for project in projects}
    names = [field.name for field in fields(Participation)]
    seen: dict[str, int] = {}
    participation: dict[str, Participation] = {}
    for index, row in enumerate(rows):
        project_id = _identifier(row, "project_id", f"participation[{index}]")
        if project_id not in known:
            raise ValidationError(
                f"The row participation[{index}] has the project_id {project_id!r}, and no "
                f"project has this id: project_id names a project of the dataset."
            )
        if project_id in seen:
            raise ValidationError(
                f"The rows participation[{seen[project_id]}] and participation[{index}] are "
                f"both for the project {project_id!r}: a project has one row of participation."
            )
        seen[project_id] = index
        try:
            counts: dict[str, Any] = {name: row.get(name) for name in names}
            participation[project_id] = Participation(**counts)
        except ValidationError as error:
            raise ValidationError(
                f"The row participation[{index}] (project {project_id!r}) breaks a rule. {error}"
            ) from None
    for index, project in enumerate(projects):
        if project.id not in participation:
            raise ValidationError(
                f"The project {project.id!r} (projects[{index}]) has no row in the section "
                f"'participation': each project has one."
            )
    return participation


def _find(items: Listing[_SluggedT], ref: str | None, noun: str) -> _SluggedT:
    if ref is None:
        if len(items) == 1:
            return items[0]
        if not items:
            raise NotFoundError(f"This dataset holds no {noun}.")
        raise NotFoundError(
            f"This dataset holds {len(items)} {noun}s; name one by its id or its slug: "
            f"{_slugs(items)}."
        )
    found = items.get(ref)
    if found is None:
        found = next((item for item in items if item.slug == ref), None)
    if found is None:
        held = f"Its {noun}s are: {_slugs(items)}." if items else f"It holds no {noun}."
        raise NotFoundError(f"No {noun} has the id or the slug {ref!r} in this dataset. {held}")
    return found


def _slugs(items: Listing[_SluggedT]) -> str:
    shown = ", ".join(item.slug for item in items[:_CITED])
    more = len(items) - _CITED
    return f"{shown}, and {more} more" if more > 0 else shown


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"
