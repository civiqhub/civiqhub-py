# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Where data comes from: the port through which rows enter the SDK.

A :class:`Source` has one duty: give rows in the format :data:`~civiqhub.dataset.FORMAT`,
at the level of exposure asked for. A :class:`~civiqhub.dataset.Dataset` is then built
from them. :class:`MemorySource` serves rows held in memory, and :class:`FileSource` a
file written by :meth:`~civiqhub.dataset.Dataset.save`.

To write your own source:

1. Derive a class from :class:`Source` and give it a short ``name``.
2. Write its ``fetch(container=None, *, exposure)``. It returns rows in the format
   :data:`~civiqhub.dataset.FORMAT`, whose key ``exposure`` is the level asked for.
   :func:`at_exposure` serves rows held at one level at the level asked for.
3. Write its ``describe()``: one line that says where the rows come from, never a secret.

Then ``Dataset(source.fetch(exposure=Exposure.AGGREGATED), source=source.describe())``
builds a dataset from it, and nothing in the package changes.
"""

import copy
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

from .dataset import _read_file
from .errors import ExposureError, ValidationError
from .values import SCORES, Exposure

__all__ = ["FileSource", "MemorySource", "Source", "at_exposure"]

# The sections that describe individuals, left out at the aggregated level.
_INDIVIDUAL = ("actants", "votes", "impressions")

# The sections whose rows name an author, a pseudonym that the aggregated level hides.
_AUTHORED = ("proposals", "arguments")

_Row = dict[str, Any]


class Source(ABC):
    """Anything that gives rows in the format of a dataset: the API, a file, memory.

    A source is the first point of extension of the SDK: a class derived from it works
    with :class:`~civiqhub.dataset.Dataset` as the sources of the package do. The
    docstring of :mod:`civiqhub.sources` says how to write one.
    """

    #: A short word for the kind of source, such as ``"memory"``.
    name: ClassVar[str] = "source"

    @abstractmethod
    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Return the rows of what the source covers, at the level of exposure asked for.

        Args:
            container: The id or the slug of one Project, when the source covers several.
                Without it, the rows cover everything the source covers.
            exposure: The level of detail of the rows. Their key ``exposure`` equals it.

        Returns:
            Rows in the format :data:`~civiqhub.dataset.FORMAT`.
        """

    def describe(self) -> str:
        """Return one line that says where the rows come from, never with a secret.

        A :class:`~civiqhub.dataset.Dataset` shows it as its source. By default, it is
        :attr:`name`.
        """
        return self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.describe()!r})"


def at_exposure(rows: Mapping[str, Any], exposure: Exposure) -> dict[str, Any]:
    """Serve rows held at one level of exposure at the level asked for.

    Rows never gain detail. Rows held at the level asked for come back as a copy.
    Pseudonymised rows asked for at the aggregated level come back reduced: without the
    sections ``actants``, ``votes`` and ``impressions``, without the key ``author_id`` in
    ``proposals`` and ``arguments``, and with a row of ``vote_counts``, counted from the
    votes, for each revision that has votes and no such row.

    Args:
        rows: The rows, in the format :data:`~civiqhub.dataset.FORMAT`. They are not
            changed.
        exposure: The level asked for.

    Returns:
        New rows, at the level asked for.

    Raises:
        ExposureError: The rows are aggregated and the pseudonymised level is asked for.
        ValidationError: The rows or the level are not valid, or a vote cannot be
            counted.
    """
    asked = _level(exposure, "The level asked for")
    if not isinstance(rows, Mapping):
        raise ValidationError(
            f"The rows of a dataset are a dictionary of sections; got {type(rows).__name__}."
        )
    held = _level(rows.get("exposure"), "The level of the rows ('exposure')")
    if held is asked:
        return copy.deepcopy(dict(rows))
    if held is Exposure.AGGREGATED:
        raise ExposureError(
            "These rows are aggregated: they hold the vote counts of each revision and no "
            "individual vote, so they cannot be served at the pseudonymised level.",
            hint="Ask for the aggregated level, or get pseudonymised rows from the source "
            "that made these.",
        )
    return _aggregate(rows)


class MemorySource(Source):
    """Rows held in memory: for tests, simulations and the data of another system.

    The source keeps a deep copy of the rows: changing them afterwards does not change
    what it gives. It covers what the rows cover, so ``container`` is ignored.

    Args:
        rows: The rows, in the format :data:`~civiqhub.dataset.FORMAT`.

    Raises:
        ValidationError: The rows are not a dictionary.
    """

    name = "memory"

    def __init__(self, rows: Mapping[str, Any]) -> None:
        if not isinstance(rows, Mapping):
            raise ValidationError(
                f"The rows of a dataset are a dictionary of sections; got {type(rows).__name__}."
            )
        self._rows = copy.deepcopy(dict(rows))

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Return a copy of the rows, at the level asked for (see :func:`at_exposure`).

        Args:
            container: Ignored: the source covers what its rows cover.
            exposure: The level asked for.

        Raises:
            ExposureError: The rows are aggregated and the pseudonymised level is asked
                for.
        """
        return at_exposure(self._rows, exposure)


class FileSource(Source):
    """A file written by :meth:`~civiqhub.dataset.Dataset.save`, read without network.

    The file is read at each :meth:`fetch`. It covers what its rows cover, so
    ``container`` is ignored.

    Args:
        path: The path of the file.
    """

    name = "file"

    #: The path of the file.
    path: Path

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def describe(self) -> str:
        """Return ``"file <name of the file>"``."""
        return f"file {self.path.name}"

    def fetch(self, container: str | None = None, *, exposure: Exposure) -> dict[str, Any]:
        """Read the file and return its rows, at the level asked for.

        Args:
            container: Ignored: the source covers what its file covers.
            exposure: The level asked for.

        Raises:
            NotFoundError: No file is at the path.
            ValidationError: The file is not JSON, or not a dictionary of sections.
            ExposureError: The file is aggregated and the pseudonymised level is asked
                for.
        """
        return at_exposure(_read_file(self.path), exposure)


def _level(value: object, what: str) -> Exposure:
    if isinstance(value, str) and value in {level.value for level in Exposure}:
        return Exposure(value)
    raise ValidationError(f"{what} is 'aggregated' or 'pseudonymised'; got {value!r}.")


def _aggregate(rows: Mapping[str, Any]) -> _Row:
    reduced = {key: copy.deepcopy(value) for key, value in rows.items() if key not in _INDIVIDUAL}
    reduced["exposure"] = Exposure.AGGREGATED.value
    for section in _AUTHORED:
        if isinstance(reduced.get(section), list):
            for row in reduced[section]:
                if isinstance(row, dict):
                    row.pop("author_id", None)
    counted = _count_votes(rows.get("votes", []))
    if counted:
        given = reduced.get("vote_counts", [])
        if not isinstance(given, list):
            raise ValidationError(
                f"The section 'vote_counts' is a list of rows; got {type(given).__name__}."
            )
        known = {row.get("revision_id") for row in given if isinstance(row, dict)}
        missing = [
            revision_id for revision_id in _ordered(rows, counted) if revision_id not in known
        ]
        reduced["vote_counts"] = given + [
            {"revision_id": revision_id, "counts": counted[revision_id]} for revision_id in missing
        ]
    return reduced


def _count_votes(votes: object) -> dict[str, list[int]]:
    if not isinstance(votes, list):
        raise ValidationError(f"The section 'votes' is a list of rows; got {type(votes).__name__}.")
    counted: dict[str, list[int]] = {}
    for index, row in enumerate(votes):
        revision_id = row.get("revision_id") if isinstance(row, dict) else None
        score = row.get("score") if isinstance(row, dict) else None
        if not isinstance(revision_id, str) or not revision_id:
            raise ValidationError(
                f"The row votes[{index}] has no valid 'revision_id', so it cannot be counted; "
                f"got {row!r}."
            )
        if not isinstance(score, int) or isinstance(score, bool) or score not in SCORES:
            raise ValidationError(
                f"The row votes[{index}] has the score {score!r}: a score is an integer from "
                f"-2 to +2, so it cannot be counted."
            )
        counts = counted.setdefault(revision_id, [0] * len(SCORES))
        counts[SCORES.index(score)] += 1
    return counted


def _ordered(rows: Mapping[str, Any], counted: Mapping[str, list[int]]) -> list[str]:
    """Return the counted revisions in the order of the section ``revisions``."""
    revisions = rows.get("revisions")
    if not isinstance(revisions, list):
        revisions = []
    listed = [row.get("id") for row in revisions if isinstance(row, dict)]
    first = [
        revision_id
        for revision_id in listed
        if isinstance(revision_id, str) and revision_id in counted
    ]
    seen = set(first)
    return first + [revision_id for revision_id in counted if revision_id not in seen]
