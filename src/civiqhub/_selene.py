# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The one place where the analysis layer is imported, and only when it is needed."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from .errors import MissingExtraError


def _family(name: str) -> tuple[ModuleType, ModuleType]:
    try:
        return import_module("civiqhub_selene"), import_module(f"civiqhub_selene.{name}")
    except ImportError as error:
        raise MissingExtraError(f"the analysis layer is not installed ({error})") from error


def require() -> tuple[ModuleType, ModuleType]:
    """The engine and its co-clustering family (which needs NumPy), or an error that
    gives the command."""
    return _family("blocks")


def require_ordinal() -> tuple[ModuleType, ModuleType]:
    """The engine and its ordinal family: five counters in, standard library only."""
    return _family("ordinal")
