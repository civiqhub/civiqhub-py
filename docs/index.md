# civiqhub

`civiqhub` is the Python SDK of [CiviqHub](https://civiqhub.com). With a project token and three lines of code, it gives the objects of the product as they appear on screen: Group, Project, Proposal, Amendment, Revision, Argument, Vote and Actant. The SDK holds no formula: analyses live in the engine `civiqhub-selene`, reached through an optional extra.

## State of the package

The SDK is not functional yet. The published version only reserves the `civiqhub` name on PyPI and exposes nothing but `__version__`. The objects of the product, their loading and the bridge to the engine are being written; each module joins the [reference](reference/index.md) as it arrives.

```{toctree}
:hidden:
:caption: Reference

reference/index
snippets
```

```{toctree}
:hidden:
:caption: Project

Source code <https://github.com/civiqhub/civiqhub-py>
Contributing <https://github.com/civiqhub/civiqhub-py/blob/develop/CONTRIBUTING.md>
License <https://github.com/civiqhub/civiqhub-py/blob/develop/LICENSE>
```
