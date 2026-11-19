# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Local Sphinx extension of the documentation site.

Each object of the SDK is documented once, on the page of the module that defines it
(``civiqhub.entities.Project``). Users import many of them from a package
(``civiqhub.Project``). This extension lets the pages use either name:

1. A reference to a public import path resolves to the place where the object is
   documented.
2. The directive ``public-names`` lists the names a package exports, each linked to its
   documentation. The list is read from ``__all__``, so it cannot go stale.
3. The first line of the docstring of a property or of a constant is never read as a
   type. Napoleon reads ``text: more text`` on that line as ``type: description``.

It also shows the hooks of the SDK: an underscore method appears in the reference
when the SDK writes it with a docstring of its own. An override without a docstring
stays out.

Last, it loads the Mermaid script on the pages that hold a diagram only. The Mermaid
extension also loads it, from a third-party network, on every page Sphinx generates
without a source (search, index, source code).
"""

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Any

from docutils import nodes
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.pycode import ModuleAnalyzer
from sphinx.util.docutils import SphinxDirective
from sphinxcontrib import mermaid

ROOT = "civiqhub"


def _split(dotted: str) -> tuple[ModuleType, list[str]] | None:
    """Split a dotted name into its longest importable module and the attributes left."""
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            return importlib.import_module(".".join(parts[:cut])), parts[cut:]
        except ImportError:
            continue
    return None


def _home(module: ModuleType, name: str, obj: Any) -> str:
    """Return the documented name of an object found as ``module.name``."""
    defined_in = getattr(obj, "__module__", None)
    qualified = getattr(obj, "__qualname__", None)
    if isinstance(defined_in, str) and defined_in.startswith(ROOT) and qualified:
        return f"{defined_in}.{qualified}"
    # A constant does not know where it is defined: look for the public module of the
    # package that exports this very object.
    for info in pkgutil.iter_modules(getattr(module, "__path__", ()), module.__name__ + "."):
        if info.ispkg or info.name.rpartition(".")[2].startswith("_"):
            continue
        candidate = importlib.import_module(info.name)
        if name in getattr(candidate, "__all__", ()) and getattr(candidate, name) is obj:
            return f"{candidate.__name__}.{name}"
    return f"{module.__name__}.{name}"


def canonical_name(dotted: str) -> str | None:
    """Return the name under which the object of a dotted path is documented."""
    if not dotted.startswith(ROOT + "."):
        return None
    found = _split(dotted)
    if found is None or not found[1]:
        return None
    module, (name, *rest) = found
    if not hasattr(module, name):
        return None
    obj = getattr(module, name)
    if rest and inspect.isclass(obj):
        # A member is documented with the class that defines it, not with its subclasses.
        obj = next((base for base in obj.__mro__ if rest[0] in vars(base)), obj)
    return ".".join([_home(module, name, obj), *rest])


def resolve_public_path(
    app: Sphinx, env: BuildEnvironment, node: pending_xref, contnode: nodes.Element
) -> nodes.reference | None:
    """Resolve a reference written with a public import path."""
    if node.get("refdomain") != "py":
        return None
    target = node.get("reftarget", "")
    # A short name is first read from where it is written: its class, then its module.
    candidates = [target]
    if module := node.get("py:module"):
        if owner := node.get("py:class"):
            candidates.append(f"{module}.{owner}.{target}")
        candidates.append(f"{module}.{target}")
    for candidate in candidates:
        canonical = canonical_name(candidate)
        if canonical is None or canonical == target:
            continue
        resolved = env.domains.python_domain.resolve_xref(
            env, node["refdoc"], app.builder, node["reftype"], canonical, node, contnode
        )
        if resolved is not None:
            return resolved
    return None


def _summary(module: ModuleType, name: str, obj: Any) -> str:
    """Return the first paragraph of the documentation of an exported name, on one line."""
    if inspect.isclass(obj) or inspect.isroutine(obj):
        lines = (inspect.getdoc(obj) or "").splitlines()
    else:
        # The documentation of a constant is the "#:" comment above it.
        home = _home(module, name, obj).rpartition(".")[0]
        lines = ModuleAnalyzer.for_module(home).find_attr_docs().get(("", name), [])
    paragraph: list[str] = []
    for line in lines:
        if not line.strip():
            break
        paragraph.append(line.strip())
    return " ".join(paragraph)


class PublicNames(SphinxDirective):
    """List the names a package exports, each linked to its documentation.

    Usage, in reStructuredText (inside an ``eval-rst`` block on a Markdown page)::

        .. public-names:: civiqhub
    """

    required_arguments = 1

    def run(self) -> list[nodes.Node]:
        package = importlib.import_module(self.arguments[0])
        self.env.note_dependency(str(package.__file__))
        rows = [
            ".. list-table::",
            "   :header-rows: 1",
            "   :widths: 30 70",
            "",
            "   * - Name",
            "     - What it is",
        ]
        for name in sorted(package.__all__, key=str.lower):
            obj = getattr(package, name)
            target = _home(package, name, obj)
            rows.append(f"   * - :py:obj:`{name} <{target}>`")
            rows.append(f"     - {_summary(package, name, obj)}")
        return self.parse_text_to_nodes("\n".join(rows))


def keep_first_line_as_text(
    app: Sphinx, what: str, name: str, obj: Any, options: Any, lines: list[str]
) -> None:
    """Stop Napoleon from reading the first line of a docstring as ``type: description``.

    Napoleon splits the first line of such a docstring on its first colon. An empty
    reStructuredText comment placed first takes that role and renders as nothing.
    """
    if what in {"attribute", "data", "property"} and lines and lines[0].strip():
        lines[:0] = ["..", ""]


def show_documented_hooks(
    app: Sphinx, what: str, name: str, obj: Any, skip: bool, options: Any
) -> bool | None:
    """Keep an underscore method that the SDK writes with a docstring of its own."""
    if what not in {"class", "exception"} or not name.startswith("_") or name.startswith("__"):
        return None
    function = next(
        (inner for key in ("__func__", "fget", "func") if (inner := getattr(obj, key, None))), obj
    )
    written_here = str(getattr(function, "__module__", "")).startswith(ROOT)
    return False if written_here and getattr(function, "__doc__", None) else None


def load_mermaid_where_a_diagram_is(
    app: Sphinx, pagename: str, templatename: str, context: dict[str, Any], doctree: Any
) -> None:
    """Call the Mermaid extension for the pages that have a source, and only them."""
    if doctree is not None:
        mermaid.install_js(app, pagename, templatename, context, doctree)


def setup(app: Sphinx) -> dict[str, bool]:
    # This extension is listed after "sphinxcontrib.mermaid": it replaces its listener.
    app.setup_extension("sphinxcontrib.mermaid")
    for listener in list(app.events.listeners["html-page-context"]):
        if listener.handler is mermaid.install_js:
            app.disconnect(listener.id)
    app.connect("html-page-context", load_mermaid_where_a_diagram_is)

    app.add_directive("public-names", PublicNames)
    app.connect("missing-reference", resolve_public_path)
    app.connect("autodoc-skip-member", show_documented_hooks)
    # Napoleon listens with the default priority (500); this must run before it.
    app.connect("autodoc-process-docstring", keep_first_line_as_text, priority=400)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
