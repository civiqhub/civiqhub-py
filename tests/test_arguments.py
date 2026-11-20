# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Argument: a reasoned stance on a Proposal, in threads, built from hand-written rows."""

from typing import Any

import pytest

import civiqhub
from civiqhub.dataset import Dataset
from civiqhub.entities import Argument
from civiqhub.errors import ValidationError
from civiqhub.values import Position
from support import reference_rows


def reference() -> Dataset:
    """Return a new dataset built from the reference rows."""
    return Dataset(reference_rows())


def argument_row(rows: dict[str, Any], id: str) -> dict[str, Any]:
    """Return the row of the argument with this id."""
    row: dict[str, Any] = next(row for row in rows["arguments"] if row["id"] == id)
    return row


def test_argument_is_exported_by_the_package() -> None:
    assert civiqhub.Argument is Argument
    assert "Argument" in civiqhub.__all__


def test_the_arguments_of_a_proposal_come_depth_first() -> None:
    dataset = reference()
    arguments = dataset.proposals["p-01"].arguments
    assert arguments.ids == ("arg-1", "arg-2", "arg-3", "arg-4", "arg-5", "arg-6")
    assert [argument.depth for argument in arguments] == [0, 1, 2, 0, 1, 1]
    assert dataset.arguments.ids == ("arg-1", "arg-4", "arg-2", "arg-5", "arg-6", "arg-3")
    assert dataset.project().arguments == arguments
    assert dataset.proposals["p-02"].arguments.ids == ()


def test_replies_and_parent_agree() -> None:
    dataset = reference()
    for argument in dataset.arguments:
        for reply in argument.replies:
            assert reply.parent is argument
        if argument.parent is None:
            assert argument.depth == 0
        else:
            assert argument in argument.parent.replies
            assert argument.depth == argument.parent.depth + 1
    assert dataset.arguments["arg-4"].replies.ids == ("arg-5", "arg-6")
    assert dataset.arguments["arg-3"].replies.ids == ()


@pytest.mark.parametrize(("value", "expected"), [("PRO", "pro"), ("pro", "pro"), ("Con", "con")])
def test_a_position_is_read_in_any_case(value: str, expected: str) -> None:
    rows = reference_rows()
    argument_row(rows, "arg-1")["position"] = value
    assert Dataset(rows).arguments["arg-1"].position is Position(expected)


def test_the_fields_of_an_argument_are_read() -> None:
    dataset = reference()
    first, other = dataset.arguments["arg-1"], dataset.arguments["arg-4"]
    assert first.proposal is dataset.proposals["p-01"]
    assert first.revision is dataset.revisions["p-01.r1"]
    assert first.position is Position.PRO
    assert first.score == 2
    assert first.n_supports == 3
    assert first.author_id is None
    assert other.revision is None
    assert other.score is None
    assert other.n_supports == 0
    assert dataset.arguments["arg-6"].position is Position.NEUTRAL


def test_repr_of_an_argument() -> None:
    assert repr(reference().arguments["arg-1"]) == "Argument('arg-1', 'More shade in the summer.')"


# One test per invariant; each message names the faulty id.


def test_an_argument_on_an_unknown_proposal_is_refused() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-5")["proposal_id"] = "p-99"
    with pytest.raises(ValidationError, match=r"\(id 'arg-5'\) has the proposal_id 'p-99'"):
        Dataset(rows)


def test_an_argument_is_on_a_revision_of_its_proposal() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-1")["revision_id"] = "p-02.r1"
    with pytest.raises(ValidationError, match=r"\(id 'arg-1'\) has the revision_id 'p-02.r1'"):
        Dataset(rows)


def test_a_reply_to_an_unknown_argument_is_refused() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-3")["parent_id"] = "arg-99"
    with pytest.raises(ValidationError, match=r"\(id 'arg-3'\) has the parent_id 'arg-99'"):
        Dataset(rows)


def test_a_reply_is_on_the_same_proposal() -> None:
    rows = reference_rows()
    rows["arguments"].append(
        {"id": "arg-7", "proposal_id": "p-02", "text": "Elsewhere.", "parent_id": "arg-1"}
    )
    with pytest.raises(ValidationError, match=r"\(id 'arg-7'\) replies to the argument 'arg-1'"):
        Dataset(rows)


def test_a_cycle_of_arguments_is_refused() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-1")["parent_id"] = "arg-3"
    expected = r"\(id 'arg-1'\) is its own ancestor: arg-1 -> arg-3 -> arg-2 -> arg-1"
    with pytest.raises(ValidationError, match=expected):
        Dataset(rows)


@pytest.mark.parametrize("position", ["maybe", 1])
def test_an_unknown_position_is_refused(position: object) -> None:
    rows = reference_rows()
    argument_row(rows, "arg-2")["position"] = position
    with pytest.raises(ValidationError, match=r"\(id 'arg-2'\) has the position"):
        Dataset(rows)


@pytest.mark.parametrize("score", [3, -3, True, 1.5, "2"])
def test_a_score_is_an_integer_from_minus_two_to_two(score: object) -> None:
    rows = reference_rows()
    argument_row(rows, "arg-1")["score"] = score
    with pytest.raises(ValidationError, match=r"\(id 'arg-1'\) has the score"):
        Dataset(rows)


@pytest.mark.parametrize("supports", [-1, 1.5, False])
def test_the_supports_are_counted_from_zero(supports: object) -> None:
    rows = reference_rows()
    argument_row(rows, "arg-1")["n_supports"] = supports
    with pytest.raises(ValidationError, match=r"\(id 'arg-1'\) has the n_supports"):
        Dataset(rows)


def test_an_aggregated_dataset_holds_no_author_of_an_argument() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-2")["author_id"] = "ps-ana"
    with pytest.raises(ValidationError, match=r"\(id 'arg-2'\) has an author_id"):
        Dataset(rows)
    rows["exposure"] = "pseudonymised"
    assert Dataset(rows).arguments["arg-2"].author_id == "ps-ana"


def test_an_argument_has_its_own_id() -> None:
    rows = reference_rows()
    argument_row(rows, "arg-4")["id"] = "arg-1"
    with pytest.raises(
        ValidationError, match=r"arguments\[0\] and arguments\[1\] have the same id"
    ):
        Dataset(rows)
