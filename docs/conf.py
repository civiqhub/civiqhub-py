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
            '"Bricolage Grotesque", ui-sans-serif, system-ui, -apple-system, '
            '"Segoe UI", sans-serif'
        ),
        "font-stack--headings": (
            '"Bricolage Grotesque", ui-sans-serif, system-ui, -apple-system, '
            '"Segoe UI", sans-serif'
        ),
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/civiqhub/civiqhub-py",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
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
