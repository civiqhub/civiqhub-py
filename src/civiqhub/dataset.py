# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The data of a source at one instant, as one frozen graph of objects.

A :class:`Dataset` is built from rows in the format :data:`FORMAT`: a dictionary that JSON
can write, with an entry ``format``, an instant ``as_of``, a level of ``exposure`` and one
list of rows per section. A missing section is an empty list, and a key that a row does
not need is ignored.

This version builds thirteen sections: ``groups``, ``projects``, ``participation``,
``articles``, ``article_versions``, ``proposals``, ``revisions``, ``vote_counts``,
``amendments``, ``arguments``, and, in a pseudonymised dataset only, ``actants``, ``votes``
and ``impressions``. The sections ``paragraphs``, ``placements`` and ``citations`` are kept
as they are: they count in the fingerprint and come back from :meth:`Dataset.to_dict`, but
no object is built from them yet.

:meth:`Dataset.save` writes the rows to a JSON file, and :meth:`Dataset.from_file` reopens
it, with the same fingerprint.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

from .entities import (
    Actant,
    Agent,
    Amendment,
    Argument,
    Article,
    ArticleVersion,
    Entity,
    Group,
    Member,
    Project,
    Proposal,
    Revision,
    Vote,
)
from .errors import ExposureError, NotFoundError, ValidationError
from .listing import Listing
from .values import (
    SCORES,
    ActantKind,
    AmendmentStatus,
    Exposure,
    Participation,
    Position,
    Role,
    VoteCounts,
)

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

# The keys that would bring personal data into a row of actants.
_PERSONAL = ("name", "email", "handle", "username", "user_id", "first_name", "last_name")

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
        "_actants",
        "_amendments_by_project",
        "_amendments_by_row",
        "_amendments_by_target",
        "_arguments",
        "_arguments_by_author",
        "_arguments_by_project",
        "_arguments_by_proposal",
        "_article_versions",
        "_articles",
        "_articles_by_project",
        "_as_of",
        "_children",
        "_current_revisions",
        "_current_versions",
        "_depths",
        "_exposure",
        "_groups",
        "_impressions",
        "_participation",
        "_projects",
        "_projects_by_group",
        "_proposals",
        "_proposals_by_project",
        "_replies",
        "_revisions",
        "_revisions_by_project",
        "_revisions_by_proposal",
        "_rows",
        "_source",
        "_versions_by_article",
        "_vote_counts",
        "_votes",
        "_votes_by_actant",
        "_votes_by_pair",
        "_votes_by_project",
        "_votes_by_revision",
    )

    _actants: Listing[Actant]
    _amendments_by_project: dict[str, Listing[Amendment]]
    _amendments_by_row: dict[str, Amendment]
    _amendments_by_target: dict[str, Listing[Amendment]]
    _arguments: Listing[Argument]
    _arguments_by_project: dict[str, Listing[Argument]]
    _arguments_by_author: dict[str, Listing[Argument]]
    _arguments_by_proposal: dict[str, Listing[Argument]]
    _article_versions: Listing[ArticleVersion]
    _articles: Listing[Article]
    _articles_by_project: dict[str, Listing[Article]]
    _as_of: str
    _children: dict[str, Listing[Group]]
    _current_revisions: dict[str, Revision]
    _current_versions: dict[str, ArticleVersion]
    _depths: dict[str, int]
    _exposure: Exposure
    _groups: Listing[Group]
    _impressions: frozenset[tuple[str, str]] | None
    _participation: dict[str, Participation]
    _projects: Listing[Project]
    _projects_by_group: dict[str, Listing[Project]]
    _proposals: Listing[Proposal]
    _proposals_by_project: dict[str, Listing[Proposal]]
    _replies: dict[str, Listing[Argument]]
    _revisions: Listing[Revision]
    _revisions_by_project: dict[str, Listing[Revision]]
    _revisions_by_proposal: dict[str, Listing[Revision]]
    _rows: _Row
    _source: str
    _versions_by_article: dict[str, Listing[ArticleVersion]]
    _vote_counts: dict[str, VoteCounts]
    _votes: Listing[Vote]
    _votes_by_actant: dict[str, Listing[Vote]]
    _votes_by_pair: dict[tuple[str, str], Vote]
    _votes_by_project: dict[str, Listing[Vote]]
    _votes_by_revision: dict[str, Listing[Vote]]

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
        self._build_articles(sections, projects)
        proposals = self._build_proposals(sections, projects)
        self._build_arguments(sections["arguments"], proposals)
        self._build_actants(
            sections, has_votes="votes" in data, has_impressions="impressions" in data
        )

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
        _check_tree(groups, "groups")
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

    def _build_articles(self, sections: Mapping[str, list[_Row]], projects: list[Project]) -> None:
        articles = [
            self._article(row, f"articles[{index}]")
            for index, row in enumerate(sections["articles"])
        ]
        _check_unique(articles, "articles", ("id",))
        known_projects = {project.id for project in projects}
        positions: dict[tuple[str, int], int] = {}
        for index, article in enumerate(articles):
            if article.project_id not in known_projects:
                raise ValidationError(
                    f"The row articles[{index}] (id {article.id!r}) has the project_id "
                    f"{article.project_id!r}, and no project has this id: project_id names a "
                    f"project of the dataset."
                )
            key = (article.project_id, article.position)
            if key in positions:
                raise ValidationError(
                    f"The rows articles[{positions[key]}] and articles[{index}] are both at the "
                    f"position {article.position} of the project {article.project_id!r}: the "
                    f"articles of a project have different positions."
                )
            positions[key] = index
        rank = {article.id: index for index, article in enumerate(articles)}
        versions = [
            self._article_version(row, f"article_versions[{index}]")
            for index, row in enumerate(sections["article_versions"])
        ]
        numbers: dict[tuple[str, int], int] = {}
        for index, version in enumerate(versions):
            if version.article_id not in rank:
                raise ValidationError(
                    f"The row article_versions[{index}] has the article_id "
                    f"{version.article_id!r}, and no article has this id: article_id names an "
                    f"article of the dataset."
                )
            key = (version.article_id, version.number)
            if key in numbers:
                raise ValidationError(
                    f"The rows article_versions[{numbers[key]}] and article_versions[{index}] "
                    f"are both the version number {version.number} of the article "
                    f"{version.article_id!r}: the numbers of the versions of an article differ."
                )
            numbers[key] = index
        versions.sort(key=lambda version: (rank[version.article_id], version.number))
        by_article: dict[str, list[ArticleVersion]] = {}
        for version in versions:
            by_article.setdefault(version.article_id, []).append(version)
        current: dict[str, ArticleVersion] = {}
        for index, article in enumerate(articles):
            found = next(
                (
                    version
                    for version in by_article.get(article.id, [])
                    if version.number == article.current_version_number
                ),
                None,
            )
            if found is None:
                raise ValidationError(
                    f"The row articles[{index}] (id {article.id!r}) has the "
                    f"current_version_number {article.current_version_number}, and the article "
                    f"has no version with this number in the section 'article_versions'."
                )
            current[article.id] = found
        by_project: dict[str, list[Article]] = {}
        for article in sorted(articles, key=lambda article: article.position):
            by_project.setdefault(article.project_id, []).append(article)
        _set = object.__setattr__
        _set(self, "_articles", Listing(articles))
        _set(self, "_article_versions", Listing(versions))
        _set(self, "_articles_by_project", _freeze(by_project))
        _set(self, "_versions_by_article", _freeze(by_article))
        _set(self, "_current_versions", current)

    def _build_proposals(
        self, sections: Mapping[str, list[_Row]], projects: list[Project]
    ) -> list[Proposal]:
        links = _read_amendment_links(sections["amendments"])
        proposals = [
            self._proposal(row, f"proposals[{index}]", links)
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
        known_proposals = {proposal.id for proposal in proposals}
        for proposal_id, (index, _row) in links.items():
            if proposal_id not in known_proposals:
                raise ValidationError(
                    f"The row amendments[{index}] has the proposal_id {proposal_id!r}, and no "
                    f"proposal has this id: proposal_id names the proposal that is the "
                    f"amendment."
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
        amendments = [proposal for proposal in proposals if isinstance(proposal, Amendment)]
        project_of = {proposal.id: proposal.project_id for proposal in proposals}
        _check_amendments(amendments, links, by_proposal, project_of)
        by_row = {amendment.amendment_id: amendment for amendment in amendments}
        for revision in revisions:
            if revision.amendment_id is not None and revision.amendment_id not in by_row:
                raise ValidationError(
                    f"The revision {revision.id!r} has the amendment_id "
                    f"{revision.amendment_id!r}, and no row of the section 'amendments' has "
                    f"this id: amendment_id names the amendment whose adoption produced it."
                )
        by_target: dict[str, list[Amendment]] = {}
        amendments_by_project: dict[str, list[Amendment]] = {}
        for amendment in amendments:
            by_target.setdefault(amendment.target_id, []).append(amendment)
            amendments_by_project.setdefault(amendment.project_id, []).append(amendment)
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
        _set(self, "_amendments_by_row", by_row)
        _set(self, "_amendments_by_target", _freeze(by_target))
        _set(self, "_amendments_by_project", _freeze(amendments_by_project))
        return proposals

    def _build_arguments(self, rows: list[_Row], proposals: list[Proposal]) -> None:
        arguments = [self._argument(row, f"arguments[{index}]") for index, row in enumerate(rows)]
        _check_unique(arguments, "arguments", ("id",))
        known = {proposal.id: proposal for proposal in proposals}
        by_id = {argument.id: argument for argument in arguments}
        for index, argument in enumerate(arguments):
            where = f"The row arguments[{index}] (id {argument.id!r})"
            proposal = known.get(argument.proposal_id)
            if proposal is None:
                raise ValidationError(
                    f"{where} has the proposal_id {argument.proposal_id!r}, and no proposal "
                    f"has this id: proposal_id names a proposal of the dataset."
                )
            own = self._revisions_by_proposal[proposal.id]
            if argument.revision_id is not None and own.get(argument.revision_id) is None:
                raise ValidationError(
                    f"{where} has the revision_id {argument.revision_id!r}, which is not a "
                    f"revision of its proposal {proposal.id!r}."
                )
            if argument.parent_id is None:
                continue
            parent = by_id.get(argument.parent_id)
            if parent is None:
                raise ValidationError(
                    f"{where} has the parent_id {argument.parent_id!r}, and no argument has "
                    f"this id: parent_id names the argument it replies to."
                )
            if parent.proposal_id != argument.proposal_id:
                raise ValidationError(
                    f"{where} replies to the argument {parent.id!r}, which is about the "
                    f"proposal {parent.proposal_id!r}, not {argument.proposal_id!r}: an "
                    f"argument replies to an argument on the same proposal."
                )
        _check_tree(arguments, "arguments")
        replies: dict[str, list[Argument]] = {}
        roots: dict[str, list[Argument]] = {}
        for argument in arguments:
            if argument.parent_id is None:
                roots.setdefault(argument.proposal_id, []).append(argument)
            else:
                replies.setdefault(argument.parent_id, []).append(argument)
        depths: dict[str, int] = {}
        by_proposal: dict[str, list[Argument]] = {}
        by_project: dict[str, list[Argument]] = {}
        for proposal in proposals:
            ordered: list[Argument] = []
            stack = [(0, root) for root in reversed(roots.get(proposal.id, []))]
            while stack:
                depth, argument = stack.pop()
                depths[argument.id] = depth
                ordered.append(argument)
                children = replies.get(argument.id, [])
                stack.extend((depth + 1, child) for child in reversed(children))
            by_proposal[proposal.id] = ordered
            by_project.setdefault(proposal.project_id, []).extend(ordered)
        _set = object.__setattr__
        _set(self, "_arguments", Listing(arguments))
        _set(self, "_arguments_by_proposal", _freeze(by_proposal))
        _set(self, "_arguments_by_project", _freeze(by_project))
        _set(self, "_replies", _freeze(replies))
        _set(self, "_depths", depths)

    def _build_actants(
        self, sections: Mapping[str, list[_Row]], *, has_votes: bool, has_impressions: bool
    ) -> None:
        actants = [
            self._actant(row, f"actants[{index}]") for index, row in enumerate(sections["actants"])
        ]
        seen: dict[str, int] = {}
        for index, actant in enumerate(actants):
            if actant.id in seen:
                raise ValidationError(
                    f"The rows actants[{seen[actant.id]}] and actants[{index}] have the same "
                    f"pseudonym {actant.id!r}: a pseudonym appears once in the section 'actants'."
                )
            seen[actant.id] = index
        authored: list[Proposal | Argument] = [*self._proposals, *self._arguments]
        for item in authored:
            if item.author_id is not None and item.author_id not in seen:
                raise ValidationError(
                    f"The {item.noun} {item.id!r} has the author_id {item.author_id!r}, and no "
                    f"actant has this pseudonym: author_id names an actant of the dataset."
                )
        revisions = {revision.id for revision in self._revisions}
        votes: list[Vote] = []
        pairs: dict[tuple[str, str], int] = {}
        for index, row in enumerate(sections["votes"]):
            where = f"votes[{index}]"
            actant_id, revision_id = _pair(row, where, seen, revisions)
            where = f"{where} (vote {actant_id + '@' + revision_id!r})"
            if (actant_id, revision_id) in pairs:
                raise ValidationError(
                    f"The rows votes[{pairs[actant_id, revision_id]}] and votes[{index}] are "
                    f"both votes of {actant_id!r} on the revision {revision_id!r}: an actant has "
                    f"one vote per revision. Keep the latest."
                )
            pairs[actant_id, revision_id] = index
            votes.append(
                Vote(
                    id=f"{actant_id}@{revision_id}",
                    dataset=self,
                    actant_id=actant_id,
                    revision_id=revision_id,
                    score=_vote_score(row, where),
                    cast_at=_optional_text(row, "cast_at", where),
                )
            )
        impressions = frozenset(
            _pair(row, f"impressions[{index}]", seen, revisions)
            for index, row in enumerate(sections["impressions"])
        )
        by_revision: dict[str, list[Vote]] = {}
        by_actant: dict[str, list[Vote]] = {}
        for vote in votes:
            by_revision.setdefault(vote.revision_id, []).append(vote)
            by_actant.setdefault(vote.actant_id, []).append(vote)
        by_project = {
            project_id: [vote for r in own for vote in by_revision.get(r.id, [])]
            for project_id, own in self._revisions_by_project.items()
        }
        by_author: dict[str, list[Argument]] = {}
        for argument in self._arguments:
            if argument.author_id is not None:
                by_author.setdefault(argument.author_id, []).append(argument)
        _set = object.__setattr__
        if has_votes and self._exposure is Exposure.PSEUDONYMISED:
            _set(
                self, "_vote_counts", _count_votes(self._revisions, by_revision, self._vote_counts)
            )
        _set(self, "_actants", Listing(actants))
        _set(self, "_votes", Listing(votes))
        _set(self, "_votes_by_revision", _freeze(by_revision))
        _set(self, "_votes_by_actant", _freeze(by_actant))
        _set(self, "_votes_by_project", _freeze(by_project))
        _set(self, "_votes_by_pair", {(v.actant_id, v.revision_id): v for v in votes})
        _set(self, "_impressions", impressions if has_impressions else None)
        _set(self, "_arguments_by_author", _freeze(by_author))

    def _actant(self, row: _Row, where: str) -> Actant:
        pseudonym = _identifier(row, "pseudonym", where)
        where = f"{where} (pseudonym {pseudonym!r})"
        for key in _PERSONAL:
            if key in row:
                raise ValidationError(
                    f"The row {where} has the key {key!r}: the SDK refuses personal data and "
                    f"knows an actant by its pseudonym only. Leave {key!r} out."
                )
        kind = _kind(row, where)
        cls = {ActantKind.HUMAN: Member, ActantKind.AGENT: Agent}.get(kind, Actant)
        return cls(id=pseudonym, dataset=self, kind=kind, role=_role(row, where))

    def _article(self, row: _Row, where: str) -> Article:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        return Article(
            id=id,
            dataset=self,
            project_id=_identifier(row, "project_id", where),
            position=_positive(row, "position", where),
            title=_text(row, "title", where),
            description=_text(row, "description", where),
            current_version_number=_positive(row, "current_version_number", where),
            published_at=_optional_text(row, "published_at", where),
        )

    def _article_version(self, row: _Row, where: str) -> ArticleVersion:
        article_id = _identifier(row, "article_id", where)
        number = _positive(row, "version_number", where)
        return ArticleVersion(
            id=f"{article_id}.v{number}",
            dataset=self,
            article_id=article_id,
            number=number,
            title=_text(row, "title", where),
            body=_text(row, "body", where),
            published_at=_optional_text(row, "published_at", where),
        )

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

    def _author(self, row: _Row, where: str) -> str | None:
        author_id = _optional_identifier(row, "author_id", where)
        if author_id is not None and self._exposure is Exposure.AGGREGATED:
            raise ValidationError(
                f"The row {where} has an author_id, and an aggregated dataset holds no "
                f"pseudonym. Set exposure to 'pseudonymised', or leave author_id out."
            )
        return author_id

    def _proposal(self, row: _Row, where: str, links: Mapping[str, tuple[int, _Row]]) -> Proposal:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        common: dict[str, Any] = {
            "id": id,
            "dataset": self,
            "project_id": _identifier(row, "project_id", where),
            "article_id": _optional_identifier(row, "article_id", where),
            "author_id": self._author(row, where),
            "created_at": _optional_text(row, "created_at", where),
            "current_revision_id": _optional_identifier(row, "current_revision_id", where),
        }
        if id not in links:
            return Proposal(**common)
        index, link = links[id]
        at = f"amendments[{index}] (id {link['id']!r})"
        return Amendment(
            **common,
            amendment_id=link["id"],
            target_id=_identifier(link, "target_proposal_id", at),
            target_revision_id=_identifier(link, "target_revision_id", at),
            status=_status(link, at),
            adopted_revision_id=_optional_identifier(link, "adopted_revision_id", at),
            is_stale=_flag(link, "stale", at),
        )

    def _argument(self, row: _Row, where: str) -> Argument:
        id = _identifier(row, "id", where)
        where = f"{where} (id {id!r})"
        return Argument(
            id=id,
            dataset=self,
            proposal_id=_identifier(row, "proposal_id", where),
            revision_id=_optional_identifier(row, "revision_id", where),
            author_id=self._author(row, where),
            position=_position(row, where),
            text=_text(row, "text", where),
            score=_score(row, where),
            parent_id=_optional_identifier(row, "parent_id", where),
            n_supports=_non_negative(row, "n_supports", where),
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

    @classmethod
    def from_file(cls, path: str | Path) -> "Dataset":
        """Open a dataset that :meth:`save` wrote, without network and without token.

        The dataset that comes back has the same fingerprint as the one saved, and the
        source ``"file <name of the file>"``.

        Args:
            path: The path of the file.

        Raises:
            NotFoundError: No file is at this path.
            ValidationError: The file is not JSON, or not in the format :data:`FORMAT`.
        """
        target = Path(path)
        return cls(_read_file(target), source=f"file {target.name}")

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
    def articles(self) -> Listing[Article]:
        """Every article of the dataset, in the order of the rows."""
        return self._articles

    @property
    def article_versions(self) -> Listing[ArticleVersion]:
        """Every version of every article: by article, in the order of the rows, then by
        number."""
        return self._article_versions

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

    @property
    def arguments(self) -> Listing[Argument]:
        """Every Argument of the dataset, in the order of the rows."""
        return self._arguments

    @property
    def actants(self) -> Listing[Actant]:
        """Every Actant of the dataset, in the order of the rows; empty when aggregated."""
        return self._actants

    @property
    def votes(self) -> Listing[Vote]:
        """Every vote of the dataset, in the order of the rows; empty when aggregated."""
        return self._votes

    @property
    def has_impressions(self) -> bool:
        """Whether the rows say which Revisions were shown to which Actants.

        It is true when the rows hold the section ``impressions``, even empty.
        """
        return self._impressions is not None

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

    def save(self, path: str | Path) -> Path:
        """Write the rows of the dataset to a JSON file, which :meth:`from_file` reopens.

        The file holds exactly the rows, in UTF-8, with sorted keys: every section,
        including the articles and their versions as the source gave them. It holds
        neither a token nor the source. A pseudonymised file holds individual votes
        under pseudonyms: share it as the exposure policy of the Project allows, and
        never commit it to a public repository.

        Args:
            path: Where to write the file. An existing file is replaced.

        Returns:
            The path of the file.
        """
        target = Path(path)
        text = json.dumps(self._rows, indent=1, sort_keys=True)
        # The same bytes on every system: no line ending is translated.
        target.write_text(text, encoding="utf-8", newline="\n")
        return target

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

    def _articles_in(self, project_id: str) -> Listing[Article]:
        return self._articles_by_project.get(project_id, Listing())

    def _versions_of(self, article_id: str) -> Listing[ArticleVersion]:
        return self._versions_by_article.get(article_id, Listing())

    def _current_version_of(self, article_id: str) -> ArticleVersion:
        return self._current_versions[article_id]

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

    def _amendments_of(self, proposal_id: str) -> Listing[Amendment]:
        return self._amendments_by_target.get(proposal_id, Listing())

    def _amendments_in(self, project_id: str) -> Listing[Amendment]:
        return self._amendments_by_project.get(project_id, Listing())

    def _amendment_by_row(self, amendment_id: str) -> Amendment:
        return self._amendments_by_row[amendment_id]

    def _arguments_of(self, proposal_id: str) -> Listing[Argument]:
        return self._arguments_by_proposal[proposal_id]

    def _arguments_in(self, project_id: str) -> Listing[Argument]:
        return self._arguments_by_project.get(project_id, Listing())

    def _replies_to(self, argument_id: str) -> Listing[Argument]:
        return self._replies.get(argument_id, Listing())

    def _depth_of(self, argument_id: str) -> int:
        return self._depths[argument_id]

    def _votes_on(self, revision_id: str) -> Listing[Vote]:
        return self._votes_by_revision.get(revision_id, Listing())

    def _votes_of(self, actant_id: str) -> Listing[Vote]:
        return self._votes_by_actant.get(actant_id, Listing())

    def _votes_in(self, project_id: str) -> Listing[Vote]:
        return self._votes_by_project.get(project_id, Listing())

    def _vote_of(self, actant_id: str, revision_id: str) -> Vote | None:
        return self._votes_by_pair.get((actant_id, revision_id))

    def _was_shown(self, actant_id: str, revision_id: str) -> bool:
        return self._impressions is not None and (actant_id, revision_id) in self._impressions

    def _arguments_by(self, actant_id: str) -> Listing[Argument]:
        return self._arguments_by_author.get(actant_id, Listing())


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


def _read_file(path: Path) -> _Row:
    """Read the rows of a dataset file, without checking them against the model."""
    if not path.is_file():
        raise NotFoundError(
            f"There is no dataset file at {str(path)!r}.",
            hint="Check the path; Dataset.save writes such a file.",
        )
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValidationError(
            f"The file {path.name!r} is not a dataset file: it is not JSON ({error})."
        ) from None
    if not isinstance(rows, dict):
        raise ValidationError(
            f"The file {path.name!r} is not a dataset file: it holds a JSON "
            f"{type(rows).__name__}, not a dictionary of sections."
        )
    return rows


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


def _positive(row: _Row, key: str, where: str) -> int:
    value = row.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValidationError(
            f"The row {where} has no valid {key!r}: it is a positive integer; got {value!r}."
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


def _check_tree(items: Sequence[Group | Argument], section: str) -> None:
    parent_of = {item.id: item.parent_id for item in items}
    for index, item in enumerate(items):
        path = [item.id]
        parent = item.parent_id
        while parent is not None:
            path.append(parent)
            if parent == item.id:
                raise ValidationError(
                    f"The row {section}[{index}] (id {item.id!r}) is its own ancestor: "
                    f"{' -> '.join(path)}. The {section} form a tree, through parent_id."
                )
            if len(path) > len(items) + 1:
                break  # a cycle above this item, reported from an item inside it
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


def _read_amendment_links(rows: list[_Row]) -> dict[str, tuple[int, _Row]]:
    ids: dict[str, int] = {}
    links: dict[str, tuple[int, _Row]] = {}
    for index, row in enumerate(rows):
        id = _identifier(row, "id", f"amendments[{index}]")
        if id in ids:
            raise ValidationError(
                f"The rows amendments[{ids[id]}] and amendments[{index}] have the same id "
                f"{id!r}: an id appears once in the section 'amendments'."
            )
        ids[id] = index
        proposal_id = _identifier(row, "proposal_id", f"amendments[{index}] (id {id!r})")
        if proposal_id in links:
            raise ValidationError(
                f"The rows amendments[{links[proposal_id][0]}] and amendments[{index}] are both "
                f"for the proposal {proposal_id!r}: a proposal has one row of amendment at most."
            )
        links[proposal_id] = (index, row)
    return links


def _check_amendments(
    amendments: list[Amendment],
    links: Mapping[str, tuple[int, _Row]],
    revisions_by_proposal: Mapping[str, list[Revision]],
    project_of: Mapping[str, str],
) -> None:
    by_id = {amendment.id: amendment for amendment in amendments}
    for amendment in amendments:
        index = links[amendment.id][0]
        where = f"The row amendments[{index}] (id {amendment.amendment_id!r})"
        target = amendment.target_id
        if target not in revisions_by_proposal:
            raise ValidationError(
                f"{where} has the target_proposal_id {target!r}, and no proposal has this id: "
                f"target_proposal_id names the proposal that the amendment targets."
            )
        if target == amendment.id:
            raise ValidationError(
                f"{where} makes the proposal {amendment.id!r} target itself: an amendment "
                f"targets another proposal."
            )
        own = {revision.id for revision in revisions_by_proposal[target]}
        if amendment.target_revision_id not in own:
            raise ValidationError(
                f"{where} has the target_revision_id {amendment.target_revision_id!r}, which "
                f"is not a revision of its target {target!r}."
            )
        if amendment.adopted_revision_id is not None:
            if amendment.status is not AmendmentStatus.ADOPTED:
                raise ValidationError(
                    f"{where} has an adopted_revision_id and the status "
                    f"{amendment.status.value!r}: only an adopted amendment has one."
                )
            if amendment.adopted_revision_id not in own:
                raise ValidationError(
                    f"{where} has the adopted_revision_id {amendment.adopted_revision_id!r}, "
                    f"which is not a revision of its target {target!r}."
                )
        target_project = project_of[target]
        if target_project != amendment.project_id:
            raise ValidationError(
                f"{where} targets the proposal {target!r} of the project {target_project!r}, "
                f"and the amendment {amendment.id!r} is in the project "
                f"{amendment.project_id!r}: an amendment and its target share a project."
            )
    for amendment in amendments:
        path = [amendment.id]
        current: Amendment | None = amendment
        while current is not None:
            path.append(current.target_id)
            if current.target_id == amendment.id:
                index = links[amendment.id][0]
                raise ValidationError(
                    f"The amendment {amendment.id!r} (amendments[{index}]) targets itself "
                    f"through {' -> '.join(path)}: the amendments of a proposal form a tree."
                )
            if len(path) > len(amendments) + 1:
                break  # a cycle above this amendment, reported from an amendment inside it
            current = by_id.get(current.target_id)


def _status(row: _Row, where: str) -> AmendmentStatus:
    value = row.get("status")
    if value is None:
        return AmendmentStatus.OPEN
    if isinstance(value, str) and value.lower() in {status.value for status in AmendmentStatus}:
        return AmendmentStatus(value.lower())
    raise ValidationError(
        f"The row {where} has the status {value!r}: the status of an amendment is 'open', "
        f"'adopted' or 'rejected', in any case."
    )


def _flag(row: _Row, key: str, where: str) -> bool:
    value = row.get(key)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValidationError(
            f"The row {where} has a {key!r} that is not true or false: {value!r}."
        )
    return value


def _position(row: _Row, where: str) -> Position | None:
    value = row.get("position")
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in {position.value for position in Position}:
        return Position(value.lower())
    raise ValidationError(
        f"The row {where} has the position {value!r}: a position is 'pro', 'con' or "
        f"'neutral', in any case."
    )


def _score(row: _Row, where: str) -> int | None:
    value = row.get("score")
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value in SCORES:
        return value
    raise ValidationError(
        f"The row {where} has the score {value!r}: a score is an integer from -2 to +2."
    )


def _non_negative(row: _Row, key: str, where: str) -> int:
    value = row.get(key)
    if value is None:
        return 0
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValidationError(
        f"The row {where} has the {key} {value!r}: it is an integer, zero or more."
    )


def _pair(
    row: _Row, where: str, actants: Mapping[str, int], revisions: set[str]
) -> tuple[str, str]:
    actant_id = _identifier(row, "actant", where)
    revision_id = _identifier(row, "revision_id", where)
    if actant_id not in actants:
        raise ValidationError(
            f"The row {where} has the actant {actant_id!r}, and no actant has this pseudonym: "
            f"actant names an actant of the dataset."
        )
    if revision_id not in revisions:
        raise ValidationError(
            f"The row {where} has the revision_id {revision_id!r}, and no revision has this "
            f"id: revision_id names a revision of the dataset."
        )
    return actant_id, revision_id


def _vote_score(row: _Row, where: str) -> int:
    value = row.get("score")
    if isinstance(value, int) and not isinstance(value, bool) and value in SCORES:
        return value
    raise ValidationError(
        f"The row {where} has the score {value!r}: a score is an integer from -2 to +2. An "
        f"abstention is the absence of a vote, not a score."
    )


def _count_votes(
    revisions: Sequence[Revision],
    votes: Mapping[str, list[Vote]],
    given: Mapping[str, VoteCounts],
) -> dict[str, VoteCounts]:
    counts: dict[str, VoteCounts] = {}
    for revision in revisions:
        counted = VoteCounts.from_scores(vote.score for vote in votes.get(revision.id, []))
        row = given.get(revision.id)
        if row is not None and row != counted:
            raise ValidationError(
                f"The vote counts of the revision {revision.id!r} are {row!r} in the section "
                f"'vote_counts', and its votes give {counted!r}: the two must agree."
            )
        counts[revision.id] = counted
    return counts


def _kind(row: _Row, where: str) -> ActantKind:
    value = row.get("kind")
    if value is None:
        return ActantKind.HUMAN
    if isinstance(value, str) and value.lower() in {kind.value for kind in ActantKind}:
        return ActantKind(value.lower())
    raise ValidationError(
        f"The row {where} has the kind {value!r}: the kind of an actant is 'human', 'agent' "
        f"or 'other', in any case."
    )


def _role(row: _Row, where: str) -> Role | None:
    value = row.get("role")
    if value is None:
        return None
    if isinstance(value, str) and value.upper() in Role.__members__:
        return Role[value.upper()]
    names = ", ".join(repr(role.name.lower()) for role in Role)
    raise ValidationError(
        f"The row {where} has the role {value!r}: a role is one of {names}, in any case."
    )
