# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Sphinx configuration of the documentation site.

How the site is organised and how to build it: see ``docs/README.md``.
"""

import os
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
    "sphinxext.opengraph",
    "civiqhub_docs",
]

# docs/README.md is read on GitHub; it explains the site and is not a page of it.
exclude_patterns = ["_build", "_ext", "_templates", "README.md"]

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
    ("py:.*", r"(abc|collections|enum|pathlib)\..*"),
    # Private modules, private module-level names and type variables are not documented.
    ("py:.*", r"civiqhub(\.[a-z]\w*)*\._\w+(\..*)?"),
    ("py:.*", r"civiqhub\..+\.\w*T(_co|_contra)?"),
]

# -- HTML -----------------------------------------------------------------------------

# The published site holds one folder per version, built by
# .github/scripts/build-docs-site.py, which sets CIVIQHUB_DOCS_CHANNEL to "dev" for the
# development branch and to "release" for a release.
is_development = os.environ.get("CIVIQHUB_DOCS_CHANNEL", "") == "dev" or "dev" in release

html_theme = "furo"
html_title = "CiviqHub"
html_favicon = "_static/favicon.ico"
templates_path = ["_templates"]
html_static_path = ["_static"]
html_css_files = ["version-switcher.css", "civiqhub.css"]
# force-light.js is also loaded in the head from _templates/page.html, so that
# Furo reads localStorage before it sets body[data-theme].
html_js_files = [
    ("force-light.js", {"priority": 200}),
    "search-shortcut.js",
    "version-switcher.js",
]
# The sidebar of the theme, with the version selector under the name of the site.
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "sidebar/version-switcher.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
        "sidebar/variant-selector.html",
    ]
}
html_theme_options = {
    "source_repository": "https://github.com/civiqhub/civiqhub-py/",
    "source_branch": "develop" if is_development else "main",
    "source_directory": "docs/",
    "light_logo": "logo.svg",
    "sidebar_hide_name": True,
    "light_css_variables": {
        "color-brand-primary": "#2C448B",
        "color-brand-content": "#2C448B",
        "color-background-primary": "#ffffff",
        "color-background-secondary": "#FAFAFA",
        "color-foreground-primary": "#020617",
        "color-foreground-secondary": "#64748b",
        "color-background-border": "#e2e8f0",
        "color-code-background": "#f1f5f9",
        "color-sidebar-background": "#FAFAFA",
        "color-sidebar-background-border": "#e2e8f0",
        "color-sidebar-brand-text": "#020617",
        "color-sidebar-caption-text": "#020617",
        "color-sidebar-link-text": "#64748b",
        "color-sidebar-link-text--top-level": "#64748b",
        "color-sidebar-item-background--current": "#f1f5f9",
        "color-sidebar-item-background--hover": "#f1f5f9",
        "color-sidebar-search-background": "#ffffff",
        "color-sidebar-search-border": "#e2e8f0",
        "color-sidebar-search-text": "#020617",
        "color-sidebar-search-foreground": "#64748b",
        "font-stack": (
            '"Bricolage Grotesque", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
        ),
        "font-stack--headings": (
            '"Bricolage Grotesque", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
        ),
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/civiqhub/civiqhub-py",
            "html": Path(__file__)
            .with_name("_static")
            .joinpath("github.svg")
            .read_text(encoding="utf-8"),
            "class": "",
        },
    ],
}
if is_development:
    html_theme_options["announcement"] = (
        f"This is the documentation of the development branch ({release}). "
        "It describes work that is not released yet."
    )

# Open Graph. The publication script may override html_baseurl with -D.
# Social cards stay off: the build has no network and must not pull matplotlib.
ogp_site_url = "https://civiqhub.github.io/civiqhub-py/"
ogp_site_name = "CiviqHub"
ogp_social_cards = {"enable": False}


def setup(app):
    """Bind ogp_site_url to html_baseurl once Sphinx has applied -D overrides."""

    def _bind_opengraph(app, config):
        if config.html_baseurl:
            config.ogp_site_url = config.html_baseurl

    app.connect("config-inited", _bind_opengraph)
