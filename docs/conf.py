# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Sphinx configuration of the documentation site.

How the site is organised and how to build it: see ``docs/README.md``.
"""

import sys
from pathlib import Path

import civiqhub

# The local extension lives next to this file.
sys.path.insert(0, str(Path(__file__).parent / "_ext"))

project = "civiqhub"
author = "CiviqHub SAS"
project_copyright = "2026 CiviqHub SAS"
# The site documents the package that is installed in the environment of the build.
release = civiqhub.__version__
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
    "civiqhub_docs",
]

# docs/README.md is read on GitHub; it explains the site and is not a page of it.
exclude_patterns = ["_build", "_ext", "README.md"]

# -- Pages (Markdown, read by MyST) ---------------------------------------------------

source_suffix = {".md": "markdown"}
myst_enable_extensions = ["amsmath", "colon_fence", "deflist", "dollarmath"]
# Headings get the anchors GitHub gives them, so that "page.md#a-heading" works in both.
myst_heading_anchors = 3
# A ```mermaid fence is a diagram, on the site as on GitHub.
myst_fence_as_directive = ["mermaid"]

# -- Reference (generated from the docstrings) ----------------------------------------

autodoc_default_options = {"members": True, "show-inheritance": True}
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True
python_use_unqualified_type_names = True
napoleon_use_rtype = False

# -- Checks ---------------------------------------------------------------------------

# Every reference to a name of the SDK must resolve; the build runs with warnings as
# errors. The site is built without network access, so it does not link to the
# documentation of other packages: their names are declared here, by top-level package.
nitpicky = True
nitpick_ignore_regex = [
    ("py:.*", r"(abc|collections|enum)\..*"),
    # Private modules, private module-level names and type variables are not documented.
    ("py:.*", r"civiqhub(\.[a-z]\w*)*\._\w+(\..*)?"),
    ("py:.*", r"civiqhub\..+\.\w*T(_co|_contra)?"),
]

# -- HTML -----------------------------------------------------------------------------

html_theme = "furo"
html_title = f"civiqhub {release}"
html_theme_options = {
    "source_repository": "https://github.com/civiqhub/civiqhub-py/",
    "source_branch": "develop",
    "source_directory": "docs/",
}
if "dev" in release:
    html_theme_options["announcement"] = (
        f"This is the documentation of the development version {release}. "
        "It describes work that is not released yet."
    )
