# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The way in: a token or a source, then a Project or a Group.

:func:`connect` returns a :class:`Client`, which holds a source and a level of exposure,
and gives the Project or the Group that the source covers. :func:`load` reopens a file
written by :meth:`~civiqhub.dataset.Dataset.save`, without network and without token.

The default level is ``aggregated``: the most careful one.
"""

from pathlib import Path

from .dataset import Dataset
from .entities import Group, Project
from .errors import NotFoundError, ValidationError
from .sources import DEFAULT_URL, ApiSource, Source
from .values import Exposure

__all__ = ["Client", "connect", "load"]


class Client:
    """Reads one source at one level of exposure, and keeps what it read.

    A client loads a :class:`~civiqhub.dataset.Dataset` the first time it is asked for a
    container, and gives the same one afterwards without reading the source again.
    :meth:`refresh` forgets them, so that the next call reads the source again.

    Args:
        source: Where the rows come from: the API, a file, memory, or a source of your
            own.
        exposure: The level of detail asked for: ``"aggregated"`` (the default) or
            ``"pseudonymised"``.

    Raises:
        ValidationError: The source is not a :class:`~civiqhub.sources.Source`, or the
            level is unknown. The message lists the two levels.
    """

    #: Where the rows come from.
    source: Source
    #: The level of detail of every dataset the client loads.
    exposure: Exposure

    def __init__(self, source: Source, *, exposure: Exposure | str = Exposure.AGGREGATED) -> None:
        if not isinstance(source, Source):
            raise ValidationError(
                f"The source of a client derives from civiqhub.Source; got {type(source).__name__}."
            )
        self.source = source
        self.exposure = _read_level(exposure)
        self._datasets: dict[str | None, Dataset] = {}

    def load(self, container: str | None = None) -> Dataset:
        """Return the dataset of what the source covers, read once and then kept.

        Args:
            container: The id or the slug of one Project, when the source covers several.
                Each container is loaded and kept apart.

        Returns:
            The dataset, whose source is the description of the source.

        Raises:
            CiviqHubError: The source could not give the rows; the error says why.
            ValidationError: The rows break a rule of the model.
        """
        dataset = self._datasets.get(container)
        if dataset is None:
            rows = self.source.fetch(container, exposure=self.exposure)
            dataset = Dataset(rows, source=self.source.describe())
            self._datasets[container] = dataset
        return dataset

    def project(self, ref: str | None = None) -> Project:
        """Return the Project with this id or slug, or the one that the source covers.

        Args:
            ref: The id or the slug of the Project. Without it, the source must cover
                exactly one Project.

        Raises:
            NotFoundError: No Project has this id or slug, or ``ref`` is left out and the
                source covers several Projects.
        """
        return self.load(ref).project(ref)

    def group(self, ref: str | None = None) -> Group:
        """Return the Group with this id or slug, or the one that the source covers.

        Args:
            ref: The id or the slug of the Group. Without it, the source must cover
                exactly one Group.

        Raises:
            NotFoundError: The source covers no Group, as a token of a Project does; or no
                Group has this id or slug.
        """
        dataset = self.load()
        if not dataset.groups:
            raise NotFoundError(
                f"The token covers no Group: the source ({dataset.source}) gives a Project "
                f"and no Group.",
                hint="Ask for client.project(), or connect with a token of a Group.",
            )
        return dataset.group(ref)

    def refresh(self) -> None:
        """Forget the datasets loaded so far: the next call reads the source again.

        The objects already given stay valid and unchanged: they belong to their own
        dataset.
        """
        self._datasets.clear()

    def __repr__(self) -> str:
        return f"Client({self.source.describe()}, {self.exposure.value})"


def connect(
    token: str | None = None,
    *,
    exposure: Exposure | str = Exposure.AGGREGATED,
    source: Source | None = None,
    base_url: str = DEFAULT_URL,
) -> Client:
    """Open CiviqHub with a personal access token, or with a source of your own.

    Nothing is read until a Project or a Group is asked for.

    Args:
        token: The personal access token. Without it and without ``source``, the
            variable ``CIVIQHUB_TOKEN`` is read.
        exposure: ``"aggregated"`` (the default): the vote counts of each Revision.
            ``"pseudonymised"``: one row per vote, when the Project allows it.
        source: A source that replaces the API: a file, memory, or a source of your own.
        base_url: The base address of the API, when the source is the API.

    Returns:
        A client of the source.

    Raises:
        ValidationError: Both a token and a source are given, or a base address with a
            source, or the level is unknown.
        AuthenticationError: The source is the API and no valid token is found.
    """
    level = _read_level(exposure)
    if source is not None and token is not None:
        raise ValidationError("Pass a token or a source, not both.")
    if source is not None and base_url != DEFAULT_URL:
        raise ValidationError(
            "Pass a base address with a token only: a source of your own has no address."
        )
    chosen = source if source is not None else ApiSource(token, base_url=base_url)
    return Client(chosen, exposure=level)


def load(path: str | Path) -> Dataset:
    """Reopen a dataset written by :meth:`~civiqhub.dataset.Dataset.save`.

    No network and no token are needed. It is the same as
    :meth:`Dataset.from_file <civiqhub.dataset.Dataset.from_file>`.

    Args:
        path: The path of the file.

    Raises:
        NotFoundError: No file is at this path.
        ValidationError: The file is not JSON, or not in the format of a dataset.
    """
    return Dataset.from_file(path)


def _read_level(value: object) -> Exposure:
    if isinstance(value, str) and value in {level.value for level in Exposure}:
        return Exposure(value)
    levels = " or ".join(repr(level.value) for level in Exposure)
    raise ValidationError(f"The level of exposure is {levels}; got {value!r}.")
