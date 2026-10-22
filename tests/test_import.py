# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from importlib.metadata import version

import civiqhub


def test_version_is_exposed():
    assert civiqhub.__version__ == version("civiqhub")
