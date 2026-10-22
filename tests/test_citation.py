# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import pathlib
import re

import civiqhub

CITATION = pathlib.Path(__file__).resolve().parents[1] / "CITATION.cff"


def test_citation_version_matches_package():
    text = CITATION.read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"?([^"\s]+)"?\s*$', text, re.MULTILINE)
    assert match is not None
    assert match.group(1) == civiqhub.__version__
