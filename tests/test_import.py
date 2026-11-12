# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from support import small_payload

import civiqhub


def _python(code: str) -> str:
    """Run code in a fresh interpreter: what it imports is not what the tests imported."""
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def test_version_is_exposed() -> None:
    assert civiqhub.__version__ == version("civiqhub")


def test_importing_the_package_loads_neither_the_engine_nor_numpy() -> None:
    out = _python(
        "import sys, civiqhub\n"
        "heavy = ('civiqhub_selene', 'numpy')\n"
        "bridge = ('_selene', 'analysis', 'citation', 'regimes', 'synthetic')\n"
        "print(sorted(name for name in sys.modules if name.split('.')[0] in heavy))\n"
        "print(sorted(name for name in bridge if f'civiqhub.{name}' in sys.modules))\n"
    )
    assert out.splitlines() == ["[]", "[]"]


def test_the_core_works_where_the_engine_and_numpy_cannot_be_imported(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(small_payload()), encoding="utf-8")
    out = _python(
        "import sys\n"
        "sys.modules['civiqhub_selene'] = None\n"  # from here on, importing either one fails
        "sys.modules['numpy'] = None\n"
        "import civiqhub\n"
        f"project = civiqhub.load({str(path)!r}).project()\n"
        "amended = project.proposals['p-1']\n"
        "print(len(project.proposals), amended.tally.total, len(project.votes))\n"
        "print(project.participation.n_votes, amended.amendments[0].is_adopted)\n"
    )
    assert out.splitlines() == ["5 3 10", "8 True"]
