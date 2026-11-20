# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Python package by CiviqHub: preview, not functional yet.

The SDK is being written. It exposes ``__version__`` and the errors of the SDK, defined
in :mod:`civiqhub.errors`.
"""

from .errors import (
    AuthenticationError,
    CiviqHubError,
    ExposureError,
    MissingExtraError,
    NotFoundError,
    RateLimitedError,
    UnavailableError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "CiviqHubError",
    "ExposureError",
    "MissingExtraError",
    "NotFoundError",
    "RateLimitedError",
    "UnavailableError",
    "ValidationError",
    "__version__",
]

#: Version of the package, in PEP 440 notation.
__version__ = "0.0.1"
