# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The front door: a token in, a Project out."""

from __future__ import annotations

from pathlib import Path

from .model import Exposure, Group, Project, Snapshot
from .sources import DEFAULT_URL, ApiSource, FileSource, Source


class Client:
    """Reads CiviqHub through one source and hands back navigable objects.

    A client holds no data: each ``project()`` or ``group()`` call takes one snapshot
    and returns objects bound to it. Call ``refresh()`` to take a new one.
    """

    source: Source
    exposure: Exposure  # the level of detail every snapshot is asked at

    def __init__(self, source: Source, *, exposure: Exposure | str = Exposure.AGGREGATED) -> None:
        self.source = source
        self.exposure = Exposure(exposure)
        self._snapshots: dict[str | None, Snapshot] = {}

    def snapshot(self, container: str | None = None) -> Snapshot:
        """Load everything the token covers, once; later calls reuse it."""
        if container not in self._snapshots:
            payload = self.source.fetch(container, exposure=self.exposure)
            self._snapshots[container] = Snapshot(payload, source=self.source.describe())
        return self._snapshots[container]

    def project(self, ref: str | None = None) -> Project:
        """The Project the token covers, or the one with this id or slug."""
        return self.snapshot(ref).project(ref)

    def group(self, ref: str | None = None) -> Group:
        """The Group the token covers, with its Groups and Projects."""
        return self.snapshot().group(ref)

    def refresh(self) -> None:
        """Forget the snapshots taken so far; the next call reads the source again."""
        self._snapshots.clear()

    def __repr__(self) -> str:
        return f"Client({self.source.describe()}, {self.exposure.value})"


def connect(
    token: str | None = None,
    *,
    exposure: Exposure | str = Exposure.AGGREGATED,
    source: Source | None = None,
    base_url: str = DEFAULT_URL,
) -> Client:
    """Open CiviqHub with a personal access token (or ``CIVIQHUB_TOKEN``).

    ``exposure="aggregated"`` (default) reads vote counts per revision.
    ``exposure="pseudonymised"`` reads one row per vote, when the Project allows it.
    ``source`` replaces the API by a file or by data in memory.
    """
    return Client(source or ApiSource(token, base_url=base_url), exposure=exposure)


def load(path: str | Path) -> Snapshot:
    """Reopen a snapshot saved with ``project.save(path)``. No network, no token."""
    source = FileSource(path)
    return Snapshot(source.read(), source=source.describe())
