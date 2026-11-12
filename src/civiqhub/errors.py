# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""One root error and a short hierarchy.

The message says what is wrong; the note attached to every error says what to do next.
An error also inherits from the standard exception that means the same thing, when
there is one, so ``except LookupError`` catches a missing Project without knowing this
library.
"""

from __future__ import annotations

from typing import ClassVar


class CiviqHubError(Exception):
    """Root of every error raised by the library."""

    hint: ClassVar[str] = "Read the message above; it names what to change."

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("hint"):
            raise TypeError(
                f"{cls.__name__} must declare a class attribute `hint`: what to do next"
            )

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.add_note(hint or self.hint)


class AuthenticationError(CiviqHubError):
    """The token is missing, malformed, expired or revoked."""

    hint: ClassVar[str] = (
        "Create a personal access token in the Project settings and pass it to "
        "civiqhub.connect(token) or set CIVIQHUB_TOKEN."
    )


class NotFoundError(CiviqHubError, LookupError):
    """The token does not give access to what was asked for."""

    hint: ClassVar[str] = "List what the token covers with client.group().projects."


class ExposureError(CiviqHubError):
    """The data was asked at a level of detail the snapshot does not hold.

    It does not inherit from ``PermissionError``: that one is an ``OSError``, and an
    ``except OSError`` written for the network would swallow it.
    """

    hint: ClassVar[str] = (
        'Reconnect with civiqhub.connect(exposure="pseudonymised"); the Project must allow it.'
    )


class RateLimitedError(CiviqHubError):
    """The API asked to slow down."""

    hint: ClassVar[str] = "Wait `retry_after` seconds, then call again."

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(CiviqHubError, ValueError):
    """A payload or an argument breaks an invariant of the CiviqHub grammar."""

    hint: ClassVar[str] = "The message names the object and the rule it breaks."


class MissingExtraError(CiviqHubError, ImportError):
    """The analysis layer is not installed."""

    hint: ClassVar[str] = 'Install it with: pip install "civiqhub[selene]"'


class UnavailableError(CiviqHubError, LookupError):
    """A value was read from an analysis that has none on this Project."""

    hint: ClassVar[str] = "Test analysis.is_available() first; analysis.unavailable says why."
