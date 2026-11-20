# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Entity: a frozen value, known by its id, tied to the dataset it comes from."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Entity
from civiqhub.listing import Listing
from support import minimal_rows


def make_dataset() -> Dataset:
    """Return a new dataset, built from the minimal rows."""
    return Dataset(minimal_rows(), source="file")


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class Thing(Entity):
    """A small entity for the tests, labelled by its name."""

    name: str = ""
    noun: ClassVar[str] = "thing"

    def _label(self) -> str:
        return self.name


@dataclass(frozen=True, kw_only=True, eq=False, repr=False)
class SpecialThing(Thing):
    """A subclass of the test entity."""

    noun: ClassVar[str] = "special thing"


DATASET = make_dataset()


def test_entity_is_exported_by_the_package() -> None:
    assert civiqhub.Entity is Entity
    assert "Entity" in civiqhub.__all__


def test_two_entities_with_the_same_class_id_and_dataset_are_equal() -> None:
    first = Thing(id="t-1", dataset=DATASET, name="First")
    again = Thing(id="t-1", dataset=DATASET, name="First")
    assert first == again
    assert hash(first) == hash(again)
    assert len({first, again}) == 1


def test_an_entity_from_another_dataset_differs() -> None:
    assert Thing(id="t-1", dataset=DATASET) != Thing(id="t-1", dataset=make_dataset())


def test_an_entity_with_another_id_differs() -> None:
    assert Thing(id="t-1", dataset=DATASET) != Thing(id="t-2", dataset=DATASET)


def test_a_subclass_is_not_equal_to_its_parent_class() -> None:
    parent = Thing(id="t-1", dataset=DATASET)
    child = SpecialThing(id="t-1", dataset=DATASET)
    assert parent != child
    assert child != parent


def test_an_entity_is_not_equal_to_another_kind_of_object() -> None:
    thing = Thing(id="t-1", dataset=DATASET)
    assert thing != "t-1"
    assert thing != ("Thing", "t-1")


def test_the_hash_depends_on_the_class_name_and_the_id() -> None:
    assert hash(Thing(id="t-1", dataset=DATASET)) == hash(("Thing", "t-1"))


def test_an_entity_is_frozen() -> None:
    thing = Thing(id="t-1", dataset=DATASET)
    with pytest.raises(dataclasses.FrozenInstanceError):
        thing.id = "t-2"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        thing.dataset = make_dataset()  # type: ignore[misc]


def test_the_fields_are_given_by_keyword_only() -> None:
    with pytest.raises(TypeError):
        Entity("t-1", DATASET)  # type: ignore[call-arg]


def test_repr_shows_the_class_the_id_and_the_label() -> None:
    assert repr(Entity(id="e-1", dataset=DATASET)) == "Entity('e-1')"
    assert repr(Thing(id="t-1", dataset=DATASET)) == "Thing('t-1')"
    labelled = Thing(id="budget-2027", dataset=DATASET, name="Budget participatif")
    assert repr(labelled) == "Thing('budget-2027', 'Budget participatif')"


def test_repr_holds_on_one_line_and_hides_the_dataset() -> None:
    shown = repr(Thing(id="t-1", dataset=DATASET, name="Two\nlines"))
    assert "\n" not in shown
    assert "Dataset" not in shown
    assert "file" not in shown


def test_noun_names_the_entity_in_messages() -> None:
    assert Entity.noun == "entity"
    assert Thing.noun == "thing"
    assert "noun" not in {field.name for field in dataclasses.fields(Thing)}


def test_entities_go_in_a_listing() -> None:
    things = Listing([Thing(id="t-1", dataset=DATASET), Thing(id="t-2", dataset=DATASET)])
    assert Thing(id="t-1", dataset=DATASET) in things
    assert Thing(id="t-1", dataset=make_dataset()) not in things
    assert things["t-2"] == Thing(id="t-2", dataset=DATASET)
