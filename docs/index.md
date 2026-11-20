# civiqhub

`civiqhub` is the Python SDK of [CiviqHub](https://civiqhub.com). With a project token and three lines of code, it gives the objects of the product as they appear on screen: Group, Project, Proposal, Amendment, Revision, Argument, Vote and Actant. The SDK holds no formula: analyses live in the engine `civiqhub-selene`.

## Where to go

| I want to | Page |
| --- | --- |
| Install the SDK and read a first Project, without a token | [Getting started](getting-started.md) |
| Find the name to use for a need, and the module that holds it | [Finding your way](library-map.md) |
| Understand how the SDK is built, and why a dataset is frozen | [Architecture](architecture.md) |
| Copy the code of one use | [Snippets](snippets.md) |
| Read the documentation of a name | [Reference](reference/index.md) |

## State of the package

Pre-alpha. The objects of the product, their loading from the API, a file or memory, and a synthetic Project are written. The CiviqHub API is not published yet, so reading it is provisional. The bridge to the engine is planned. The version on PyPI, 0.0.1, only reserves the name.

```{toctree}
:hidden:
:caption: Guide

getting-started
library-map
architecture
snippets
```

```{toctree}
:hidden:
:caption: Reference

reference/index
```

```{toctree}
:hidden:
:caption: Project

Source code <https://github.com/civiqhub/civiqhub-py>
Contributing <https://github.com/civiqhub/civiqhub-py/blob/develop/CONTRIBUTING.md>
License <https://github.com/civiqhub/civiqhub-py/blob/develop/LICENSE>
```
