# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The errors of the SDK.

Every error the SDK raises derives from :class:`CiviqHubError`. Its message says what is
wrong; its :attr:`~CiviqHubError.hint` says what to do next, in the words of the product.

An error also derives from the standard exception that means the same thing, when there
is one, so that code which does not know the SDK still catches it: ``except LookupError``
catches a :class:`NotFoundError`.

Messages and hints are complete English sentences. None of them holds a token, even in
part.
"""

__all__ = [
    "AuthenticationError",
    "CiviqHubError",
    "ExposureError",
    "MissingExtraError",
    "NotFoundError",
    "RateLimitedError",
    "UnavailableError",
    "ValidationError",
]


class CiviqHubError(Exception):
    """The root of every error of the SDK.

    Catch it to handle any error of the SDK in one place. The message says what is
    wrong. :attr:`hint` says what to do next; it is also attached to the error as a
    note, so that a traceback shows it under the message.

    Every subclass declares its own non-empty :attr:`hint`: a subclass without one
    raises :class:`TypeError` when it is defined.

    Args:
        message: What is wrong.
        hint: What to do next. Without it, or when it is empty, the error takes the
            hint of its class.
    """

    #: What to do next. Each error class declares its own; an error raised with a hint
    #: of its own carries that one instead.
    hint: str = "The message of this error says what is wrong and what to change."

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        hint = cls.__dict__.get("hint")
        if not isinstance(hint, str) or not hint.strip():
            raise TypeError(
                f"{cls.__name__} must declare its own non-empty class attribute 'hint': "
                "a complete sentence that says what to do next."
            )

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint or type(self).hint
        self.add_note(self.hint)


class AuthenticationError(CiviqHubError):
    """Raised when the token is missing, malformed, expired or revoked."""

    #: What to do next.
    hint = (
        "Create a personal access token in the settings of your Project, then pass it to "
        "civiqhub.connect(token) or set CIVIQHUB_TOKEN."
    )


class NotFoundError(CiviqHubError, LookupError):
    """Raised when what is asked for is not covered by the token, or does not exist.

    An id that does not exist in the dataset raises it too.
    """

    #: What to do next.
    hint = "Check the id or slug; client.group().projects lists what the token covers."


class ExposureError(CiviqHubError):
    """Raised when data is asked for at a level of detail the dataset does not hold.

    An aggregated dataset holds neither individual votes nor actants, for instance.

    It does not derive from :class:`PermissionError`, which is an error of the operating
    system: an ``except OSError`` written for the network would catch it.
    """

    #: What to do next.
    hint = (
        "Ask an administrator of the Project to enable pseudonymised access, then connect "
        'with civiqhub.connect(exposure="pseudonymised").'
    )


class RateLimitedError(CiviqHubError):
    """Raised when the API asks to slow down.

    Args:
        message: What is wrong.
        retry_after: How many seconds to wait before the next call, when the API says
            it.
    """

    #: What to do next.
    hint = "Wait retry_after seconds, then call again."

    #: How many seconds to wait before the next call, or ``None`` when the API does not
    #: say.
    retry_after: float | None

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ValidationError(CiviqHubError, ValueError):
    """Raised when rows break an invariant of the model."""

    #: What to do next.
    hint = "The message names the row and the rule it breaks."


class MissingExtraError(CiviqHubError, ImportError):
    """Raised when an analysis is asked for and the engine is not installed."""

    #: What to do next.
    hint = 'Install it with: pip install "civiqhub[selene]".'


class UnavailableError(CiviqHubError, LookupError):
    """Raised when a value is read from an analysis that has none."""

    #: What to do next.
    hint = "Test analysis.is_available first; analysis.unavailable says why."
