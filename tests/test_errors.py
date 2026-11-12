# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The error hierarchy: one root, a next step on every error, a standard base."""

from __future__ import annotations

import pytest

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

HIERARCHY = (
    AuthenticationError,
    NotFoundError,
    ExposureError,
    RateLimitedError,
    ValidationError,
    MissingExtraError,
    UnavailableError,
)


@pytest.mark.parametrize("error", HIERARCHY)
def test_every_error_says_what_to_do_next(error: type[CiviqHubError]) -> None:
    raised = error("what is wrong")
    assert isinstance(raised, CiviqHubError)
    assert str(raised) == "what is wrong"
    assert raised.__notes__ == [error.hint]
    assert error.hint != CiviqHubError.hint  # each error has its own next step


def test_a_hint_given_with_the_error_replaces_the_one_of_its_class() -> None:
    raised = CiviqHubError("what is wrong", hint="do this instead")
    assert raised.__notes__ == ["do this instead"]


def test_errors_inherit_from_the_standard_exception_that_means_the_same() -> None:
    assert issubclass(NotFoundError, LookupError)
    assert issubclass(UnavailableError, LookupError)
    assert issubclass(ValidationError, ValueError)
    assert issubclass(MissingExtraError, ImportError)
    # PermissionError is an OSError: an `except OSError` written for the network
    # must not swallow a refusal of exposure.
    assert not issubclass(ExposureError, OSError)


def test_a_rate_limit_carries_the_time_to_wait() -> None:
    assert RateLimitedError("slow down", retry_after=7.0).retry_after == 7.0
    assert RateLimitedError("slow down").retry_after is None


def test_an_error_class_without_a_hint_is_refused() -> None:
    with pytest.raises(TypeError, match="must declare a class attribute `hint`"):
        type("Silent", (CiviqHubError,), {})
