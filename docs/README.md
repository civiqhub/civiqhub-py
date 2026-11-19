# Documentation

This folder holds the pages of the documentation site of `civiqhub-py`. The site is built with [Sphinx](https://www.sphinx-doc.org) from two sources: the Markdown pages of this folder, and the docstrings of the code.

This file explains how the site is organised and how to change it. It is read on GitHub and is not a page of the site.

## Build the site

The build needs Python 3.13 or later.

```bash
python -m pip install --upgrade pip
python -m pip install -e . --group docs
python -m sphinx -W -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`. The option `-W` turns every warning into an error: this is how the CI builds the site, in the `documentation` job.

## What is where

| Path | Content |
| --- | --- |
| `conf.py` | The configuration of Sphinx |
| `_ext/civiqhub_docs.py` | A local Sphinx extension; its docstring says what it does |
| `index.md` | The home page and the table of contents of the site |
| `reference/` | The reference: one page per public module, generated from the docstrings |
| `_build/` | The output of the build. Not committed |

The guide (getting started, a map of the library, the architecture) is planned and not written yet.

## Five rules

1. **Pages are Markdown.** They are read by [MyST](https://myst-parser.readthedocs.io), and they must stay readable on GitHub.
2. **The reference is never written by hand.** To change what the reference says, change the docstring.
3. **Every public module has a page in the reference.** `tests/test_docs_reference.py` checks it.
4. **Every Python block runs.** `tests/test_docs_examples.py` runs the Python blocks of `README.md` and of every page of this folder, and compares what they print with the output the page shows.
5. **Every reference to a name of the SDK resolves.** The build fails on a name that does not exist.

## Add a page to the guide

1. Create `docs/my-page.md`. It starts with one title of level 1.
2. Add `my-page` to a `toctree` of `index.md`. A page that is in no table of contents fails the build.
3. Build the site.

Link to another page with a relative Markdown link: `[Reference](reference/index.md)`. Link to a heading with the anchor GitHub gives it: `[the state of the package](index.md#state-of-the-package)`.

## Refer to a name of the SDK

Use a role, so that the name becomes a link to the reference and the build checks that it exists:

````markdown
{py:class}`~civiqhub.Project` holds the proposals of a project.
Call {py:func}`~civiqhub.connect` to get a client.
````

| Role | For |
| --- | --- |
| `{py:class}` | A class or an error |
| `{py:func}` | A function |
| `{py:meth}` | A method |
| `{py:attr}` | An attribute or a property |
| `{py:data}` | A constant |
| `{py:mod}` | A module |
| `{py:obj}` | Any of them |

The leading `~` shows the last part of the name only. Both import paths work: the package that exports the name (`civiqhub.Project`) and the module that defines it (`civiqhub.entities.Project`).

On GitHub a role shows as plain text. This is accepted.

## Write a Python block

````markdown
```python
import civiqhub

print(civiqhub.__version__.count("."))
```

```text
2
```
````

- A block fenced with `python` is run by the tests. The blocks of a page share one namespace and run in the order of the page.
- A `text` block that directly follows a Python block is its output: the test compares it with what the block prints, character for character. Show an output only when it does not depend on the machine or on the version of a dependency.
- To show code that cannot run, such as a skeleton, write the comment `<!-- not run: the reason -->` on the line before the block, followed by an empty line.
- A page whose blocks use `civiqhub_selene` or `civiqhub.analysis` gets the `engine` marker and is skipped where the engine is not installed. Nothing has to be declared.
- A page whose blocks another test runs is named in `RUN_ELSEWHERE`, in `tests/test_docs_examples.py`.
- Examples use synthetic data only and never a real token. They make no network call.
- `ruff format` also formats the Python blocks of the Markdown files.

## Write formulas and diagrams

A formula is written between dollar signs, inline (`$a + b$`) or on its own lines between `$$`. A diagram is a block fenced with `mermaid`; GitHub draws it as well.

The site loads MathJax and Mermaid from the jsDelivr network, on the pages that hold a formula or a diagram only.

## The reference

Each public module has one page, `reference/<dotted name of the module>.md`. The page of a module is three lines:

````markdown
# `civiqhub.errors`

```{eval-rst}
.. automodule:: civiqhub.errors
```
````

It shows the docstring of the module, then every name of its `__all__` with its docstring. The page of a package shows the docstring of the package, the names the package exports (the directive `public-names` reads its `__all__`) and the list of its modules.

When you add a public module:

1. Declare its `__all__`.
2. Create its page: copy the page of a sibling module, or the example above, and change the name on both lines.
3. Add the dotted name of the module to the `toctree` of the page of its package, for example `reference/civiqhub.md`. The first module of a package also adds a section "Modules" with that `toctree` to the page of the package:

   ````markdown
   ## Modules

   ```{toctree}
   :maxdepth: 1

   civiqhub.errors
   ```
   ````

When you add a name to an existing module, add it to `__all__`: the page follows. When you remove or rename a module, remove or rename its page.

A module whose name starts with an underscore is internal and has no page. An underscore method appears in the reference when it carries its own docstring: this is how a hook is documented. An override without a docstring does not appear.

## When the build fails

| Message | Cause | What to do |
| --- | --- | --- |
| `py:class reference target not found: civiqhub...` | A docstring or a page names something that does not exist, or that is not public | Fix the name. A name is public when it is in the `__all__` of a public module |
| `py:class reference target not found: decimal.Decimal` (a name of another package) | A signature uses a type of a package that `conf.py` does not know yet | Add the top-level package to the first pattern of `nitpick_ignore_regex` in `conf.py` |
| `py:class reference target not found: Some words` | A `Returns:` section starts with `some words: more words`; the words before the colon are read as a type | Reword the first line of the section without a colon |
| `document isn't included in any toctree` | A page is in no table of contents | Add it to a `toctree` |
| `cross-reference target not found` (`myst.xref_missing`) | A Markdown link points to a page or a heading that does not exist | Fix the link |
| `Unexpected indentation`, `Block quote ends without a blank line` | A docstring is not valid reStructuredText | Put an empty line before and after a list or an indented block; write `::` before a literal block |

The site is built without network access, and it does not link to the documentation of Python.
