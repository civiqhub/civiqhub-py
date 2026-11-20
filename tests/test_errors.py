# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The errors of the SDK: one root, a hint on every error, the right standard exception."""

import pytest

import civiqhub
import civiqhub.errors
from civiqhub.errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    MissingExtraError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
    ValidationError,
)

# Each error below the root, with the standard exception it also derives from.
ERRORS: list[tuple[type[CiviqHubError], type[Exception]]] = [
    (AuthenticationError, Exception),
    (NotFoundError, LookupError),
    (ExposureError, Exception),
    (RateLimitedError, Exception),
    (ValidationError, ValueError),
    (MissingExtraError, ImportError),
    (UnavailableError, LookupError),
]
NAMES = ["CiviqHubError", *(error.__name__ for error, _ in ERRORS)]


def test_the_eight_errors_are_exported_by_the_package() -> None:
    assert sorted(civiqhub.errors.__all__) == sorted(NAMES)
    for name in NAMES:
        assert name in civiqhub.__all__
        assert getattr(civiqhub, name) is getattr(civiqhub.errors, name)


@pytest.mark.parametrize(("error", "standard"), ERRORS)
def test_an_error_derives_from_the_root_and_from_its_standard_exception(
    error: type[CiviqHubError], standard: type[Exception]
) -> None:
    assert issubclass(error, CiviqHubError)
    assert issubclass(error, standard)


def test_except_lookup_error_catches_a_not_found_error() -> None:
    with pytest.raises(LookupError) as caught:
        raise NotFoundError("No proposal p-99 in this dataset.")
    assert caught.type is NotFoundError


@pytest.mark.parametrize("error", [error for error, _ in ERRORS])
def test_an_error_carries_the_hint_of_its_class(error: type[CiviqHubError]) -> None:
    raised = error("What is wrong.")
    assert str(raised) == "What is wrong."
    assert raised.hint == error.hint
    assert raised.__notes__ == [error.hint]


def test_each_error_has_a_hint_of_its_own_written_as_a_sentence() -> None:
    hints = [CiviqHubError.hint, *(error.hint for error, _ in ERRORS)]
    assert len(set(hints)) == len(hints)
    for hint in hints:
        assert hint[0].isupper()
        assert hint.endswith(".")


def test_a_hint_given_with_the_error_replaces_the_one_of_its_class() -> None:
    raised = CiviqHubError("m", hint="h")
    assert raised.hint == "h"
    assert raised.__notes__ == ["h"]
    assert NotFoundError("m", hint="h").hint == "h"


def test_an_empty_hint_given_with_the_error_counts_as_none() -> None:
    assert CiviqHubError("m", hint="").hint == CiviqHubError.hint


def test_an_error_class_without_a_hint_of_its_own_is_refused() -> None:
    with pytest.raises(TypeError, match="must declare its own non-empty class attribute 'hint'"):

        class BadError(CiviqHubError):
            pass

    with pytest.raises(TypeError, match="NarrowerError must declare"):

        class NarrowerError(NotFoundError):
            pass

    with pytest.raises(TypeError, match="BlankError must declare"):

        class BlankError(CiviqHubError):
            hint = "  "


def test_an_error_class_with_a_hint_of_its_own_is_accepted() -> None:
    class NarrowerError(NotFoundError):
        hint = "Do this instead."

    assert NarrowerError("m").hint == "Do this instead."


def test_a_rate_limit_carries_the_time_to_wait() -> None:
    assert RateLimitedError("m", retry_after=12.0).retry_after == 12.0
    assert RateLimitedError("m").retry_after is None


def test_an_exposure_error_is_not_an_error_of_the_operating_system() -> None:
    assert not issubclass(ExposureError, OSError)
    assert not issubclass(ExposureError, PermissionError)
