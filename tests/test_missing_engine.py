# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""What the bridge does when the analysis engine cannot be imported.

These tests run with or without the engine installed: they hide it first.
"""

from __future__ import annotations

import sys

import pytest

from civiqhub import _selene
from civiqhub.errors import MissingExtraError


@pytest.mark.parametrize("door", [_selene.require, _selene.require_ordinal])
def test_the_engine_is_asked_for_by_name_when_it_is_missing(
    door: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "civiqhub_selene", None)  # importing it now fails
    assert callable(door)
    with pytest.raises(MissingExtraError, match="analysis layer is not installed") as missing:
        door()
    assert isinstance(missing.value, ImportError)  # an `except ImportError` catches it
    assert missing.value.__notes__ == ['Install it with: pip install "civiqhub[selene]"']
