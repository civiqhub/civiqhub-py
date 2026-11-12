# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""What the bridge does when the analysis engine cannot be imported.

These tests run with or without the engine installed: they hide it first.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from civiqhub import _selene
from civiqhub.errors import MissingExtraError

HINT = 'Install it with: pip install "civiqhub[selene]"'
LAZY_NAMES = ("Analysis", "Citation")


def _without_engine(code: str) -> list[str]:
    """Run code in a fresh interpreter where importing the engine fails."""
    hidden = "import sys\nsys.modules['civiqhub_selene'] = None\n"
    done = subprocess.run(
        [sys.executable, "-c", hidden + code], capture_output=True, text=True, check=True
    )
    return done.stdout.strip().splitlines()


@pytest.mark.parametrize("door", [_selene.require, _selene.require_ordinal])
def test_the_engine_is_asked_for_by_name_when_it_is_missing(
    door: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "civiqhub_selene", None)  # importing it now fails
    assert callable(door)
    with pytest.raises(MissingExtraError, match="analysis layer is not installed") as missing:
        door()
    assert isinstance(missing.value, ImportError)  # an `except ImportError` catches it
    assert missing.value.__notes__ == [HINT]


def test_a_name_of_the_analysis_layer_asks_for_the_engine_on_first_use() -> None:
    out = _without_engine(
        "import civiqhub\n"
        f"for name in {LAZY_NAMES!r}:\n"
        "    assert name in civiqhub.__all__\n"
        "    try:\n"
        "        getattr(civiqhub, name)\n"
        "    except ImportError as error:\n"
        "        print(name, type(error).__name__, '|', error.__notes__[0])\n"
    )
    assert out == [f"{name} MissingExtraError | {HINT}" for name in LAZY_NAMES]
