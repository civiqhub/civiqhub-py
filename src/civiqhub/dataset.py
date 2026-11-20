# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The data of a source at one instant, as one frozen graph of objects.

A :class:`Dataset` is built from rows in the format :data:`FORMAT`: a dictionary that JSON
can write, with an entry ``format``, an instant ``as_of``, a level of ``exposure`` and one
list of rows per section. A missing section is an empty list, and a key that a row does
not need is ignored.

This version builds three sections: ``groups``, ``projects`` and ``participation``. The
other sections of the format (``articles``, ``article_versions``, ``paragraphs``,
``placements``, ``citations``, ``proposals``, ``revisions``, ``vote_counts``,
``amendments``, ``arguments``, ``actants``, ``votes`` and ``impressions``) are kept as
they are. They count in the fingerprint and come back from :meth:`Dataset.to_dict`, but no
object is built from them yet.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields
from datetime import datetime, timedelta
from typing import Any, TypeVar

from .entities import Group, Project
from .errors import ExposureError, NotFoundError, ValidationError
from .listing import Listing
from .values import Exposure, Participation

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
        "_exposure",
        "_groups",
        "_participation",
        "_projects",
        "_projects_by_group",
        "_rows",
        "_source",
    )

    _as_of: str
    _children: dict[str, Listing[Group]]
    _exposure: Exposure
    _groups: Listing[Group]
    _participation: dict[str, Participation]
    _projects: Listing[Project]
    _projects_by_group: dict[str, Listing[Project]]
    _rows: _Row
    _source: str

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
        self._build(sections)

    def _build(self, sections: Mapping[str, list[_Row]]) -> None:
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
        proposals = len(self._rows.get("proposals", []))
        return (
            f"Dataset({_count(len(self.projects), 'project')}, "
            f"{_count(proposals, 'proposal')}, {self.exposure.value}, as of {self.as_of}, "
            f"from {self.source})"
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


def _check_unique(items: list[_SluggedT], section: str) -> None:
    for key in ("id", "slug"):
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
