# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The objects of the product.

:class:`Entity` is what every object of the product shares: a frozen value, known by its
id, tied to the dataset it comes from. The objects themselves (Group, Project, Proposal
and the others) are not written yet.
"""

from dataclasses import dataclass, field
from typing import ClassVar

__all__ = ["Entity"]


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
    dataset: object = field(repr=False)

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
