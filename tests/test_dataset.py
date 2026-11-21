# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Dataset, Group and Project, built from hand-written rows."""

import copy
import hashlib
import json
from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import FORMAT, Dataset
from civiqhub.entities import Group, Project
from civiqhub.errors import ExposureError, NotFoundError, ValidationError
from civiqhub.listing import Listing
from civiqhub.values import Exposure, Participation
from support import (
    AS_OF,
    PARTICIPATION,
    TURNOUT,
    minimal_rows,
    pseudonymised_rows,
    reference_rows,
)

# The sections that this version keeps without building objects from them.
RESERVED = ("citations",)


def with_second_project(rows: dict[str, Any]) -> dict[str, Any]:
    """Add a second Project, with its participation, to the rows."""
    rows["projects"].append({"id": "parks", "slug": "parks-2027", "name": "Parks"})
    rows["participation"].append({**PARTICIPATION, "project_id": "parks"})
    return rows


def test_the_new_names_are_exported_by_the_package() -> None:
    assert civiqhub.Dataset is Dataset
    assert civiqhub.Group is Group
    assert civiqhub.Project is Project
    assert {"Dataset", "Group", "Project"} <= set(civiqhub.__all__)
    assert FORMAT == "civiqhub.dataset/0"


def test_minimal_rows_give_one_project_found_with_or_without_its_slug() -> None:
    dataset = Dataset(minimal_rows())
    project = dataset.project()
    assert dataset.project("budget-2027") is project
    assert project.group is not None
    assert project.group.projects[0] is project
    assert dataset.group() is project.group


def test_from_dict_builds_the_same_dataset() -> None:
    dataset = Dataset.from_dict(minimal_rows(), source="file")
    assert dataset.source == "file"
    assert dataset.fingerprint() == Dataset(minimal_rows()).fingerprint()


@pytest.mark.parametrize("value", [None, "civiqhub.snapshot/0", 0])
def test_rows_in_another_format_are_refused(value: object) -> None:
    rows = minimal_rows()
    if value is None:
        del rows["format"]
    else:
        rows["format"] = value
    with pytest.raises(ValidationError, match=r"civiqhub\.dataset/0") as caught:
        Dataset(rows)
    assert repr(value) in str(caught.value)


def test_two_projects_need_a_reference() -> None:
    dataset = Dataset(with_second_project(minimal_rows()))
    with pytest.raises(NotFoundError, match="budget-2027, parks-2027"):
        dataset.project()
    assert dataset.project("parks-2027") is dataset.project("parks")


def test_an_unknown_reference_lists_up_to_eight_slugs() -> None:
    rows = minimal_rows()
    for number in range(10):
        rows["projects"].append({"id": f"x-{number}", "slug": f"slug-{number}"})
        rows["participation"].append({**PARTICIPATION, "project_id": f"x-{number}"})
    dataset = Dataset(rows)
    with pytest.raises(NotFoundError) as caught:
        dataset.project("zzz")
    message = str(caught.value)
    assert "'zzz'" in message
    assert "budget-2027, slug-0, slug-1, slug-2, slug-3, slug-4, slug-5, slug-6, and 3 more" in (
        message
    )
    assert isinstance(caught.value, LookupError)


def test_a_dataset_without_project_says_so() -> None:
    rows = minimal_rows()
    rows["projects"] = []
    rows["participation"] = []
    with pytest.raises(NotFoundError, match="holds no project"):
        Dataset(rows).project()


def test_groups_form_a_tree_that_can_be_walked_both_ways() -> None:
    dataset = Dataset(reference_rows())
    top, circle = dataset.groups
    project = dataset.project()
    assert top.parent is None
    assert circle.parent is top
    assert top.groups == Listing([circle])
    assert circle.groups == Listing()
    assert circle.projects == Listing([project])
    assert top.projects == Listing()
    assert project.group is circle
    assert dataset.group("budget-circle") is circle
    with pytest.raises(NotFoundError, match="demo-collective, budget-circle"):
        dataset.group()


def test_a_project_reads_the_instant_and_the_exposure_of_its_dataset() -> None:
    project = Dataset(reference_rows()).project()
    assert project.as_of == AS_OF
    assert project.exposure is Exposure.AGGREGATED
    assert project.description == "Proposals for the budget of 2027."


def test_an_unknown_group_id_is_refused() -> None:
    rows = minimal_rows()
    rows["projects"][0]["group_id"] = "g-9"
    with pytest.raises(ValidationError, match=r"projects\[0\].*'g-9'"):
        Dataset(rows)


def test_an_unknown_parent_id_is_refused() -> None:
    rows = reference_rows()
    rows["groups"][1]["parent_id"] = "g-9"
    with pytest.raises(ValidationError, match=r"groups\[1\].*'g-9'"):
        Dataset(rows)


@pytest.mark.parametrize(
    ("parents", "expected"),
    [
        ({"g-1": "g-1"}, r"groups\[0\] \(id 'g-1'\) is its own ancestor: g-1 -> g-1"),
        ({"g-1": "g-2"}, r"groups\[0\] \(id 'g-1'\) is its own ancestor: g-1 -> g-2 -> g-1"),
    ],
)
def test_a_cycle_of_groups_is_refused(parents: dict[str, str], expected: str) -> None:
    rows = reference_rows()
    for group in rows["groups"]:
        if group["id"] in parents:
            group["parent_id"] = parents[group["id"]]
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


def test_a_cycle_above_a_group_is_refused() -> None:
    rows = reference_rows()
    rows["groups"][0]["parent_id"] = "g-2"
    rows["groups"].insert(0, {"id": "g-0", "slug": "below", "parent_id": "g-1"})
    with pytest.raises(ValidationError, match=r"groups\[1\] \(id 'g-1'\) is its own ancestor"):
        Dataset(rows)


@pytest.mark.parametrize(
    ("section", "key"),
    [("groups", "slug"), ("groups", "id"), ("projects", "slug"), ("projects", "id")],
)
def test_an_id_or_a_slug_appears_once(section: str, key: str) -> None:
    rows = reference_rows()
    if section == "groups":
        rows["groups"][1][key] = rows["groups"][0][key]
        rows["groups"][1].pop("parent_id")
    else:
        with_second_project(rows)
        rows["projects"][1][key] = rows["projects"][0][key]
        rows["participation"].pop()
    expected = rf"{section}\[0\] and {section}\[1\] have the same {key}"
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"slug": None}, r"projects\[0\] \(id 'budget-2027'\) has no valid 'slug'"),
        ({"id": ""}, r"projects\[0\] has no valid 'id'"),
        ({"name": 3}, r"projects\[0\] \(id 'budget-2027'\) has a 'name' that is not"),
        ({"group_id": 7}, r"'group_id': it is a non-empty string; got 7"),
    ],
)
def test_a_field_of_the_wrong_kind_is_refused(change: dict[str, Any], expected: str) -> None:
    rows = minimal_rows()
    rows["projects"][0].update(change)
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


def test_an_unknown_key_is_ignored() -> None:
    rows = reference_rows()
    rows["projects"][0]["colour"] = "green"
    rows["groups"][0]["kind"] = "collective"
    rows["amendments"][0].update({"type": "UPDATE", "itemType": "x", "kind": "y"})
    rows["unknown_section"] = {"anything": True}
    project = Dataset(rows).project()
    assert not hasattr(project, "colour")


def test_reserved_sections_are_kept_and_count_in_the_fingerprint() -> None:
    rows = minimal_rows()
    plain = Dataset(rows).fingerprint()
    for section in RESERVED:
        rows[section] = [{"id": f"{section}-1"}]
    dataset = Dataset(rows)
    assert dataset.fingerprint() != plain
    for section in RESERVED:
        changed = copy.deepcopy(rows)
        changed[section] = [{"id": f"{section}-2"}]
        assert Dataset(changed).fingerprint() != dataset.fingerprint()
    assert {section: dataset.to_dict()[section] for section in RESERVED} == {
        section: rows[section] for section in RESERVED
    }


def test_a_section_is_a_list_of_rows() -> None:
    rows = minimal_rows()
    rows["citations"] = {"id": "c-1"}
    with pytest.raises(ValidationError, match="'citations' is a list of rows"):
        Dataset(rows)
    rows["citations"] = ["c-1"]
    with pytest.raises(ValidationError, match=r"citations\[0\] is not a JSON object"):
        Dataset(rows)


def test_the_rows_are_copied_on_the_way_in_and_out() -> None:
    rows = minimal_rows()
    dataset = Dataset(rows)
    rows["projects"][0]["name"] = "Changed"
    rows["exposure"] = "pseudonymised"
    assert dataset.project().name == "Budget participatif"
    assert dataset.exposure is Exposure.AGGREGATED
    out = dataset.to_dict()
    assert out == minimal_rows()
    out["projects"].clear()
    assert dataset.to_dict() == minimal_rows()
    assert json.loads(json.dumps(out)) == out


def test_a_dataset_cannot_be_changed() -> None:
    dataset = Dataset(minimal_rows())
    with pytest.raises(AttributeError, match="cannot be changed"):
        dataset.source = "elsewhere"  # type: ignore[misc]
    with pytest.raises(AttributeError, match="cannot be changed"):
        dataset._rows = {}
    with pytest.raises(AttributeError, match="cannot be changed"):
        del dataset._rows


def test_the_same_rows_give_the_same_fingerprint_and_projects_that_differ() -> None:
    first, second = Dataset(minimal_rows()), Dataset(minimal_rows())
    assert first.fingerprint() == second.fingerprint()
    assert len(first.fingerprint()) == 16
    int(first.fingerprint(), 16)
    assert first.project() != second.project()
    assert first.project().id == second.project().id


def test_the_fingerprint_is_the_digest_of_the_sorted_compact_json() -> None:
    rows = minimal_rows()
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    assert Dataset(rows).fingerprint() == hashlib.sha256(text.encode()).hexdigest()[:16]
    assert Dataset(rows, source="file").fingerprint() == Dataset(rows).fingerprint()


def test_an_aggregated_dataset_has_no_individual_votes() -> None:
    dataset = Dataset(minimal_rows())
    assert dataset.has_individual_votes is False
    with pytest.raises(ExposureError, match=r"^The vote matrix needs individual votes") as caught:
        dataset.require_individual_votes("the vote matrix")
    assert "pseudonymised" in caught.value.hint


def test_a_pseudonymised_dataset_has_individual_votes() -> None:
    rows = minimal_rows()
    rows["exposure"] = "pseudonymised"
    dataset = Dataset(rows)
    assert dataset.has_individual_votes is True
    dataset.require_individual_votes("the vote matrix")


@pytest.mark.parametrize("section", ["actants", "votes", "impressions"])
def test_an_aggregated_dataset_refuses_individual_rows(section: str) -> None:
    rows = minimal_rows()
    rows[section] = [{"id": "ps-1"}]
    with pytest.raises(ValidationError, match=f"section '{section}' has 1"):
        Dataset(rows)
    rows[section] = []
    Dataset(rows)
    assert len(Dataset(pseudonymised_rows()).to_dict()[section]) > 0


@pytest.mark.parametrize(
    "value", [None, "2026-11-16", "2026-11-16T09:00:00", "2026-11-16T10:00:00+01:00", "soon", 3]
)
def test_as_of_is_an_instant_in_utc(value: object) -> None:
    rows = minimal_rows()
    rows["as_of"] = value
    with pytest.raises(ValidationError, match="'as_of'"):
        Dataset(rows)


def test_as_of_is_kept_as_written() -> None:
    rows = minimal_rows()
    rows["as_of"] = "2026-11-16T09:00:00+00:00"
    assert Dataset(rows).as_of == "2026-11-16T09:00:00+00:00"


@pytest.mark.parametrize("value", [None, "public", "AGGREGATED"])
def test_exposure_is_aggregated_or_pseudonymised(value: object) -> None:
    rows = minimal_rows()
    rows["exposure"] = value
    with pytest.raises(ValidationError, match="'aggregated' or 'pseudonymised'"):
        Dataset(rows)


def test_the_participation_of_a_project_is_read_from_its_row() -> None:
    participation = Dataset(minimal_rows()).project().participation
    assert participation == Participation(
        n_proposals=3, n_amendments=3, n_arguments=6, n_votes=12, n_actants=4, n_voters=3
    )
    assert participation.turnout == TURNOUT


def test_a_participation_without_actants_has_no_turnout() -> None:
    rows = minimal_rows()
    del rows["participation"][0]["n_actants"]
    assert Dataset(rows).project().participation.turnout is None


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"project_id": "nowhere"}, r"participation\[0\] has the project_id 'nowhere'"),
        ({"n_votes": -1}, r"participation\[0\] \(project 'budget-2027'\) breaks a rule"),
        ({"n_votes": None}, "got n_votes=None"),
    ],
)
def test_a_wrong_participation_is_refused(change: dict[str, Any], expected: str) -> None:
    rows = minimal_rows()
    rows["participation"][0].update(change)
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


def test_a_project_has_one_row_of_participation() -> None:
    rows = minimal_rows()
    rows["participation"].append(dict(PARTICIPATION))
    with pytest.raises(ValidationError, match=r"participation\[0\] and participation\[1\]"):
        Dataset(rows)
    rows["participation"] = []
    with pytest.raises(ValidationError, match=r"'budget-2027' .* has no row"):
        Dataset(rows)


@pytest.mark.parametrize("rows", [[], "rows", {"format": FORMAT, "as_of": {1, 2}}])
def test_rows_are_a_dictionary_of_json_data(rows: Any) -> None:
    with pytest.raises(ValidationError, match="The rows of a dataset are"):
        Dataset(rows)


def test_the_source_is_a_string() -> None:
    with pytest.raises(ValidationError, match="source"):
        Dataset(minimal_rows(), source=None)  # type: ignore[arg-type]


def test_repr_counts_the_projects_and_the_proposals() -> None:
    rows = minimal_rows()
    assert repr(Dataset(rows)) == (
        f"Dataset(1 project, 0 proposals, aggregated, as of {AS_OF}, from memory)"
    )
    rows = with_second_project(reference_rows())
    assert repr(Dataset(rows, source="file")) == (
        f"Dataset(2 projects, 6 proposals, aggregated, as of {AS_OF}, from file)"
    )


def test_repr_of_a_group_and_a_project() -> None:
    dataset = Dataset(reference_rows())
    assert repr(dataset.project()) == "Project('budget-2027', 'Budget participatif')"
    assert repr(dataset.group("g-1")) == "Group('g-1', 'Demo collective')"
    assert "Dataset(" not in repr(dataset.project())
