# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""What every analysis of a Project carries, whatever family of the engine computed it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ._selene import require_ordinal
from .errors import UnavailableError
from .model import Project

if TYPE_CHECKING:
    from collections.abc import Mapping

    import civiqhub_selene as selene
else:
    selene, _ = require_ordinal()  # the contract itself needs the standard library only


@dataclass(frozen=True)
class Citation:
    """What it takes to quote an analysis and to compute it again."""

    project: str
    as_of: str
    snapshot: str  # fingerprint of the data
    source: str
    method: str  # slug of the method
    version: str  # version of the method
    reference: str
    engine_version: str
    parameters: Mapping[str, object]
    seed: int | None  # None for a method that draws nothing
    dependencies: Mapping[str, str]
    computation: str  # fingerprint of the computation: same value, same request
    impressions_recorded: bool

    def __str__(self) -> str:
        seed = "" if self.seed is None else f", seed {self.seed}"
        return (
            f"{self.method} {self.version} ({self.reference}), engine {self.engine_version}{seed}, "
            f"on project {self.project} as of {self.as_of} (snapshot {self.snapshot})"
        )


class Analysis:
    """What every analysis of a Project carries: the Project, the engine's result as
    it came, and a citation. An analysis the Project cannot carry is still an answer:
    ``is_available()`` is false and ``unavailable`` says why."""

    project: Project
    engine: selene.Result[Any]

    def is_available(self) -> bool:
        return self.engine.is_available()

    @property
    def unavailable(self) -> selene.Unavailable | None:
        """Why there is no answer, or ``None`` when there is one."""
        value = self.engine.value
        return value if isinstance(value, selene.Unavailable) else None

    def _require(self, what: str) -> None:
        absent = self.unavailable
        if absent is not None:
            raise UnavailableError(
                f"{what} cannot be read: this analysis of project {self.project.slug!r} is {absent}"
            )

    @property
    def citation(self) -> Citation:
        seal = self.engine.provenance
        snapshot = self.project.snapshot
        return Citation(
            project=self.project.slug,
            as_of=snapshot.as_of,
            snapshot=snapshot.fingerprint(),
            source=snapshot.source,
            method=seal.method.name,
            version=seal.method.version,
            reference=seal.method.reference,
            engine_version=seal.engine_version,
            parameters=seal.to_payload()["parameters"],
            seed=seal.seed,
            dependencies=dict(seal.dependencies),
            computation=seal.fingerprint(),
            impressions_recorded=snapshot.records_impressions,
        )
