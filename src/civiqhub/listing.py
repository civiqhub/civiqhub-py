# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The collection that every navigation returns.

``project.proposals`` and ``proposal.revisions`` are each a :class:`Listing`: an ordered,
immutable sequence that is also searched by id.
"""

from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Protocol, TypeVar, overload

from .errors import NotFoundError, ValidationError

__all__ = ["Listing"]


class _Identified(Protocol):
    @property
    def id(self) -> str: ...


ItemT = TypeVar("ItemT", bound=_Identified)

# How many ids a NotFoundError cites, and how many ids repr shows.
_CITED = 8
_SHOWN = 3


class Listing(Sequence[ItemT]):
    """An ordered, immutable sequence of objects, also searched by id.

    It is built from objects that each have an ``id``, and keeps their order. Read an
    object by position (``listing[0]``, ``listing[-1]``) or by id (``listing["p-01"]``);
    a slice (``listing[1:3]``) is a :class:`Listing` too. The search by id takes constant
    time.

    ``x in listing`` accepts an object or an id. mypy in strict mode refuses an id there,
    because the listing holds objects: ``listing.get(id) is not None`` tests an id as
    well. Two listings are equal when they hold the same objects in the same order.

    An unknown id raises :class:`~civiqhub.errors.NotFoundError`, which is also a
    :class:`LookupError`. Two objects with the same id raise
    :class:`~civiqhub.errors.ValidationError` when the listing is built.

    Args:
        items: The objects, in order.
    """

    __slots__ = ("_by_id", "_items")

    def __init__(self, items: Iterable[ItemT] = ()) -> None:
        self._items: tuple[ItemT, ...] = tuple(items)
        self._by_id: dict[str, ItemT] = {}
        for item in self._items:
            if item.id in self._by_id:
                raise ValidationError(
                    f"Two objects of this listing have the id {item.id!r}; "
                    "an id appears once in a listing."
                )
            self._by_id[item.id] = item

    @overload
    def __getitem__(self, key: int) -> ItemT: ...

    @overload
    def __getitem__(self, key: str) -> ItemT: ...

    @overload
    def __getitem__(self, key: slice) -> "Listing[ItemT]": ...

    def __getitem__(self, key: int | str | slice) -> "ItemT | Listing[ItemT]":
        if isinstance(key, str):
            try:
                return self._by_id[key]
            except KeyError:
                raise NotFoundError(self._describe_unknown(key)) from None
        if isinstance(key, slice):
            return Listing(self._items[key])
        return self._items[key]

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[ItemT]:
        return iter(self._items)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return item in self._by_id
        key = getattr(item, "id", None)
        if not isinstance(key, str):
            return False
        found = self._by_id.get(key)
        return found is not None and found == item

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Listing):
            return NotImplemented
        return self._items == other._items

    def __hash__(self) -> int:
        return hash(self._items)

    def __repr__(self) -> str:
        if not self._items:
            return f"{type(self).__name__}(0)"
        shown = ", ".join(self.ids[:_SHOWN])
        more = ", ..." if len(self) > _SHOWN else ""
        return f"{type(self).__name__}({len(self)}: {shown}{more})"

    @property
    def ids(self) -> tuple[str, ...]:
        """The ids of the objects, in order."""
        return tuple(self._by_id)

    def get(self, id: str) -> ItemT | None:
        """Return the object with this id, or ``None`` when there is none.

        Args:
            id: The id of the object.
        """
        return self._by_id.get(id)

    def where(
        self, test: Callable[[ItemT], bool] | None = None, /, **equals: object
    ) -> "Listing[ItemT]":
        """Keep the objects that pass a test and whose attributes equal the values given.

        ``proposals.where(author_id="m-003")`` keeps the proposals of one author, and
        ``revisions.where(lambda revision: revision.number > 1)`` the revisions after the
        first. Without an argument, it returns an equal listing.

        Args:
            test: A function that tells whether to keep an object.
            **equals: Names of attributes, each with the value that the attribute must
                equal.
        """
        return Listing(
            item
            for item in self._items
            if (test is None or test(item))
            and all(getattr(item, name) == value for name, value in equals.items())
        )

    def _describe_unknown(self, key: str) -> str:
        if not self._items:
            return f"No object has the id {key!r}: this listing is empty."
        cited = ", ".join(self.ids[:_CITED])
        if len(self) > _CITED:
            return (
                f"No object has the id {key!r} in this listing. Its first ids are: {cited}, "
                f"and {len(self) - _CITED} more."
            )
        return f"No object has the id {key!r} in this listing. Its ids are: {cited}."
