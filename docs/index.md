# CiviqHub

`civiqhub` is the Python SDK of [CiviqHub](https://civiqhub.com). With a project token and three lines of code, it gives the objects of the product as they appear on screen: Group, Project, Proposal, Amendment, Revision, Argument, Vote and Actant. The SDK holds no formula: analyses live in the engine `civiqhub-selene`.

## Démarrer

```{raw} html
<div class="civiqhub-cards">
  <a class="civiqhub-card" href="getting-started.html">
    <div class="civiqhub-card-banner">
      <img src="_static/logo.svg" alt="" width="50" height="53">
      <span>CiviqHub</span>
    </div>
    <div class="civiqhub-card-body">
      <span class="civiqhub-card-title">Getting started</span>
      <p>Install the SDK and read a first Project, without a token.</p>
    </div>
  </a>
  <a class="civiqhub-card" href="library-map.html">
    <div class="civiqhub-card-banner">
      <img src="_static/logo.svg" alt="" width="50" height="53">
      <span>CiviqHub</span>
    </div>
    <div class="civiqhub-card-body">
      <span class="civiqhub-card-title">Finding your way</span>
      <p>Find the name to use for a need, and the page that documents it.</p>
    </div>
  </a>
  <a class="civiqhub-card" href="architecture.html">
    <div class="civiqhub-card-banner">
      <img src="_static/logo.svg" alt="" width="50" height="53">
      <span>CiviqHub</span>
    </div>
    <div class="civiqhub-card-body">
      <span class="civiqhub-card-title">Architecture</span>
      <p>How the SDK is built, and why a dataset is frozen.</p>
    </div>
  </a>
  <a class="civiqhub-card" href="reference/index.html">
    <div class="civiqhub-card-banner">
      <img src="_static/logo.svg" alt="" width="50" height="53">
      <span>CiviqHub</span>
    </div>
    <div class="civiqhub-card-body">
      <span class="civiqhub-card-title">Reference</span>
      <p>Every public name, generated from the docstrings of the code.</p>
    </div>
  </a>
</div>
```

## State of the package

Pre-alpha. The objects of the product, their loading from the API, a file or memory, and a synthetic Project are written. The CiviqHub API is not published yet, so reading it is provisional. The bridge to the engine is planned. The version on PyPI, 0.0.1, only reserves the name.

```{toctree}
:hidden:
:caption: Démarrer

Accueil <self>
getting-started
library-map
architecture
snippets
```

```{toctree}
:hidden:
:caption: Référence

Référence <reference/index>
```

```{toctree}
:hidden:
:caption: Projet

Code source <https://github.com/civiqhub/civiqhub-py>
Contribuer <https://github.com/civiqhub/civiqhub-py/blob/develop/CONTRIBUTING.md>
Licence <https://github.com/civiqhub/civiqhub-py/blob/develop/LICENSE>
```
