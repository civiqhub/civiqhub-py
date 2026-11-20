# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Listing: an ordered, immutable sequence, also searched by id."""

from dataclasses import dataclass
from typing import assert_type

import pytest

import civiqhub
from civiqhub.errors import NotFoundError, ValidationError
from civiqhub.listing import Listing


@dataclass(frozen=True)
class Item:
    """A synthetic object with an id, standing for an entity."""

    id: str
    number: int = 0
    author_id: str = ""


ITEMS = [
    Item(f"p-{n:02d}", number=n, author_id="m-003" if n % 2 else "m-001") for n in range(1, 15)
]


@pytest.fixture
def listing() -> Listing[Item]:
    return Listing(ITEMS)


def test_listing_is_exported_by_the_package() -> None:
    assert civiqhub.Listing is Listing
    assert "Listing" in civiqhub.__all__


def test_an_object_is_read_by_position(listing: Listing[Item]) -> None:
    assert listing[0] is ITEMS[0]
    assert listing[-1] is ITEMS[-1]
    with pytest.raises(IndexError):
        listing[14]


def test_an_object_is_read_by_id(listing: Listing[Item]) -> None:
    assert listing["p-01"] is ITEMS[0]
    assert listing["p-14"] is ITEMS[13]


def test_an_unknown_id_cites_the_id_and_the_first_eight_ids(listing: Listing[Item]) -> None:
    with pytest.raises(NotFoundError) as caught:
        listing["zzz"]
    message = str(caught.value)
    assert "'zzz'" in message
    assert "p-01, p-02, p-03, p-04, p-05, p-06, p-07, p-08, and 6 more" in message
    assert "p-09" not in message


def test_an_unknown_id_is_a_lookup_error() -> None:
    with pytest.raises(LookupError, match=r"Its ids are: p-01, p-02\."):
        Listing(ITEMS[:2])["zzz"]
    with pytest.raises(LookupError, match="this listing is empty"):
        Listing[Item]()["zzz"]


def test_a_slice_is_a_listing(listing: Listing[Item]) -> None:
    part = listing[1:3]
    assert isinstance(part, Listing)
    assert list(part) == ITEMS[1:3]
    assert part["p-03"] is ITEMS[2]


def test_length_and_iteration_keep_the_order_of_construction() -> None:
    backwards = Listing(reversed(ITEMS))
    assert len(backwards) == 14
    assert list(backwards) == ITEMS[::-1]
    assert backwards.ids[0] == "p-14"


def test_in_accepts_an_object_or_an_id(listing: Listing[Item]) -> None:
    assert ITEMS[0] in listing
    # mypy --strict refuses an id here, because the listing holds objects; at run time,
    # an id is accepted.
    assert "p-01" in listing  # type: ignore[comparison-overlap]
    assert "zzz" not in listing  # type: ignore[comparison-overlap]
    assert Item("p-01", number=99) not in listing
    assert Item("zzz") not in listing
    assert 1 not in listing  # type: ignore[comparison-overlap]
    assert None not in listing


def test_an_id_is_tested_with_get_under_mypy_strict(listing: Listing[Item]) -> None:
    assert listing.get("p-01") is not None
    assert listing.get("zzz") is None


def test_ids_are_a_tuple_in_order(listing: Listing[Item]) -> None:
    assert listing.ids == tuple(f"p-{n:02d}" for n in range(1, 15))


def test_get_returns_none_for_an_unknown_id(listing: Listing[Item]) -> None:
    assert listing.get("p-02") is ITEMS[1]
    assert listing.get("zzz") is None


def test_where_combines_a_test_and_equalities(listing: Listing[Item]) -> None:
    by_author = listing.where(author_id="m-003")
    assert by_author.ids == ("p-01", "p-03", "p-05", "p-07", "p-09", "p-11", "p-13")
    after_ten = listing.where(lambda item: item.number > 10)
    assert after_ten.ids == ("p-11", "p-12", "p-13", "p-14")
    both = listing.where(lambda item: item.number > 10, author_id="m-003")
    assert both.ids == ("p-11", "p-13")
    assert isinstance(both, Listing)


def test_where_without_an_argument_returns_an_equal_listing(listing: Listing[Item]) -> None:
    assert listing.where() == listing
    assert listing.where() is not listing


def test_two_listings_are_equal_with_the_same_objects_in_the_same_order() -> None:
    assert Listing(ITEMS) == Listing(list(ITEMS))
    assert Listing(ITEMS) != Listing(reversed(ITEMS))
    assert Listing(ITEMS) != Listing(ITEMS[:-1])
    assert Listing(ITEMS) != ITEMS
    assert hash(Listing(ITEMS)) == hash(Listing(list(ITEMS)))


def test_repr_shows_the_number_then_three_ids_at_most(listing: Listing[Item]) -> None:
    assert repr(listing) == "Listing(14: p-01, p-02, p-03, ...)"
    assert repr(Listing(ITEMS[:2])) == "Listing(2: p-01, p-02)"
    assert repr(Listing[Item]()) == "Listing(0)"


def test_a_listing_cannot_be_changed(listing: Listing[Item]) -> None:
    with pytest.raises(TypeError):
        listing[0] = ITEMS[1]  # type: ignore[index]
    with pytest.raises(AttributeError):
        listing.extra = 1  # type: ignore[attr-defined]


def test_two_objects_with_the_same_id_are_refused() -> None:
    with pytest.raises(ValidationError, match="'p-01'"):
        Listing([ITEMS[0], Item("p-01", number=2)])


def test_mypy_types_an_object_and_a_slice(listing: Listing[Item]) -> None:
    # mypy --strict checks these at type-checking time; at run time they do nothing.
    assert_type(listing[0], Item)
    assert_type(listing["p-01"], Item)
    assert_type(listing[1:3], Listing[Item])
    assert_type(listing.get("p-01"), Item | None)
    assert_type(listing.where(), Listing[Item])
