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

Then open `docs/_build/html/index.html`. The option `-W` turns every warning into an error, as in the CI.

This builds the documentation of the code you have, as one site without versions. The published site holds several versions: see [How the site is published](#how-the-site-is-published).

## What is where

| Path | Content |
| --- | --- |
| `conf.py` | The configuration of Sphinx |
| `_ext/civiqhub_docs.py` | A local Sphinx extension; its docstring says what it does |
| `_templates/sidebar/version-switcher.html`, `_static/version-switcher.js`, `_static/version-switcher.css` | The version selector of the sidebar |
| `_templates/sidebar/brand.html`, `_templates/sidebar/search.html`, `_templates/page.html` | The mark of the site, the search field, and the forced light theme |
| `_static/civiqhub.css`, `_static/force-light.js`, `_static/search-shortcut.js` | The CiviqHub theme, the light-only lock, and the Ctrl K shortcut |
| `_static/fonts/` | Bricolage Grotesque (OFL 1.1) and `OFL.txt` |
| `_static/logo.svg`, `_static/favicon.ico` | The CiviqHub glyph and the favicon |
| `index.md` | The home page and the table of contents of the site |
| `getting-started.md`, `library-map.md`, `architecture.md` | The guide: a first Project, the name to use for each need, how the SDK is built |
| `snippets.md` | The code of each use, in eight lines; `tests/test_snippets.py` runs it against a fake API |
| `reference/` | The reference: one page per public module, generated from the docstrings |
| `_build/` | The output of the build. Not committed |

The pages of the bridge to the engine are planned and not written yet.

## Thème du site

Le site publié est en mode clair seulement. Il reprend le style de la documentation produit CiviqHub sur GitBook : marque en tête de barre latérale, recherche en pilule, légendes de section en capitales, colonne de lecture, cartes d'accueil.

### Police Bricolage Grotesque

Trois graisses statiques, sous-ensemble latin (accents français, guillemets, ponctuation de code), licence SIL OFL 1.1.

| Fichier | Graisse | sha256 |
| --- | --- | --- |
| `docs/_static/fonts/BricolageGrotesque-Regular.woff2` | 400 | `e621e8a37e58558ca0e1dab28e2989854a79d89926879377788c400329a68bde` |
| `docs/_static/fonts/BricolageGrotesque-SemiBold.woff2` | 600 | `31302f47b289491baa9154e8ba49107173ca3461db2e62382e5d9b785fadaefd` |
| `docs/_static/fonts/BricolageGrotesque-Bold.woff2` | 700 | `522c92d99315b6c4b4fc9efb11857c318cc0e64f955d5a28707601cbbf5b4344` |

`docs/_static/fonts/OFL.txt` est la licence OFL 1.1 livrée à côté.

Provenance : le dépôt [`google/fonts`](https://github.com/google/fonts), dossier `ofl/bricolagegrotesque`, commit `06bfe0d62a98375cb09c942fa18e68bd32cff057`. Source variable : `BricolageGrotesque[opsz,wdth,wght].ttf`. Reconstruction (instances `opsz=14`, `wdth=100`, `wght` 400 / 600 / 700, puis sous-ensemble latin Google Fonts compressé en `woff2`) :

```bash
git clone --filter=blob:none --sparse https://github.com/google/fonts.git
cd fonts
git sparse-checkout set ofl/bricolagegrotesque
git checkout 06bfe0d62a98375cb09c942fa18e68bd32cff057

LATIN="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
SRC="ofl/bricolagegrotesque/BricolageGrotesque[opsz,wdth,wght].ttf"

for spec in Regular:400 SemiBold:600 Bold:700; do
  name="${spec%:*}"
  weight="${spec#*:}"
  fonttools varLib.instancer "$SRC" opsz=14 wdth=100 "wght=${weight}" \
    --output "BricolageGrotesque-${name}.ttf"
  pyftsubset "BricolageGrotesque-${name}.ttf" \
    --unicodes="$LATIN" \
    --layout-features="*" \
    --flavor=woff2 \
    --output-file="BricolageGrotesque-${name}.woff2"
done
cp ofl/bricolagegrotesque/OFL.txt OFL.txt
```

`civiqhub.css` déclare trois `@font-face` (`font-display: swap`). Texte courant en 400, titres H2 à H4 et légendes de barre latérale en 600, H1 et le mot « CiviqHub » en 700. La police de code reste celle de Furo.

### Fichiers du thème

| Fichier | Rôle |
| --- | --- |
| `_static/civiqhub.css` | Tokens, `@font-face`, barre latérale, recherche, cartes, colonne de lecture |
| `_static/force-light.js` | Écrit `localStorage.theme = "light"` avant que Furo lise la clé |
| `_static/search-shortcut.js` | Ctrl K / Cmd K focusent le champ de recherche |
| `_static/logo.svg` | Glyphe CiviqHub (carré noir à coins arrondis en CSS) |
| `_static/favicon.ico` | Favicon ICO du site |
| `_static/home.svg` | Glyphe de maison du H1 d'accueil |
| `_static/github.svg` | Icône GitHub du pied de page |
| `_static/fonts/` | Les trois `woff2` et `OFL.txt` |
| `_static/version-switcher.js`, `_static/version-switcher.css` | Sélecteur de version de la publication |
| `_templates/page.html` | Charge `force-light.js` dans le `<head>` ; fil d'Ariane ; enveloppe d'accueil |
| `_templates/sidebar/brand.html` | Marque : icône puis « CiviqHub » en Bold |
| `_templates/sidebar/search.html` | Pilule : une loupe, « Rechercher... », badge Ctrl K |
| `_templates/sidebar/version-switcher.html` | Emplacement du sélecteur de version |

### Tokens

Les couleurs et arrondis viennent de `civiqhub-web` au SHA `22756d33636bb8b341e7c41ec8846c421867dc10`, fichier `packages/civiqhub-ui/src/tokens/generated.css`. Ce sont des valeurs de bootstrap : aucun contrat du design system n'est `ready`. Liens en `primary` `#2C448B` : provisoire jusqu'à l'arbitrage du ds:gap [#648](https://github.com/civiqhub/civiqhub-web/issues/648). Info, avertissement, police mono et favicon SVG gardent Furo, en attendant [#649](https://github.com/civiqhub/civiqhub-web/issues/649), [#650](https://github.com/civiqhub/civiqhub-web/issues/650) et [#543](https://github.com/civiqhub/civiqhub-web/issues/543).

| Variable CSS | Valeur | Rôle |
| --- | --- | --- |
| `--civiqhub-primary` | `#2C448B` | Marque, liens, dégradé des cartes |
| `--civiqhub-primary-foreground` | `#ffffff` | Texte sur la marque |
| `--civiqhub-background` | `#ffffff` | Fond de page |
| `--civiqhub-shell-surface` | `#FAFAFA` | Barre latérale |
| `--civiqhub-muted` | `#f1f5f9` | Entrée active, fonds discrets |
| `--civiqhub-border` | `#e2e8f0` | Bordures |
| `--civiqhub-foreground` | `#020617` | Texte principal |
| `--civiqhub-muted-foreground` | `#64748b` | Texte secondaire |
| `--civiqhub-success` | `#047857` | Avertissements tip / hint |
| `--civiqhub-destructive` | `#dc2626` | Avertissements danger / error |
| `--civiqhub-radius-sm` / `md` / `lg` / `xl` | 4 / 8 / 12 / 16 px | Arrondis |
| `--civiqhub-card-banner-from` / `to` | `color-mix` de primary 18 % puis 6 % avec le fond | Bandeaux des cartes |

`logo.svg` est `public/images/logo.svg` de `civiqhub-web` au même SHA. `favicon.ico` est dérivé de l'icône d'application CiviqHub.

### Thème clair forcé

Furo 2025.12.19 lit `localStorage.getItem("theme")` dans `base.html` et pose `body[data-theme]`. `force-light.js` s'exécute dans le `<head>` (`_templates/page.html`) **et** via `html_js_files`, pour que la clé soit `light` avant ce script. `civiqhub.css` masque `.theme-toggle-container`. `dark_css_variables` n'est pas défini.

### Extensions et dépendances

Groupe `docs` de `pyproject.toml` : `sphinx==9.2.0` (BSD-2-Clause), `myst-parser==5.2.0` (MIT), `furo==2025.12.19` (MIT), `sphinxcontrib-mermaid==2.1.1` (BSD-2-Clause), `sphinxext-opengraph==0.13.0` (BSD-3-Clause). `sphinxext-opengraph` pose `ogp_site_url` d'après `html_baseurl` ; les cartes sociales PNG sont désactivées (`ogp_social_cards.enable = False`) parce que le build n'a pas de réseau et ne doit pas tirer matplotlib. Extension locale : `docs/_ext/civiqhub_docs.py`.

### Build local

```bash
python -m pip install -e . --group docs
python -m sphinx -W -b html docs docs/_build/html
python .github/scripts/build-docs-site.py --output _site --development HEAD
```

La première commande construit un site sans versions. La seconde reproduit la publication (`dev/` pour HEAD). Python 3.13 ou plus récent.

### Reporter le thème sur civiqhub-selene

Le CSS du site Selene doit rester identique à `docs/_static/civiqhub.css`, à l'en-tête de licence près.

1. Copier `_static/civiqhub.css`, `_static/force-light.js`, `_static/search-shortcut.js`, `_static/logo.svg`, `_static/favicon.ico`, `_static/home.svg`, `_static/github.svg` et `_static/fonts/` (les trois `woff2` et `OFL.txt`).
2. Copier `_templates/page.html`, `_templates/sidebar/brand.html` et `_templates/sidebar/search.html`. Laisser le sélecteur de version propre à chaque dépôt.
3. Dans `docs/conf.py` : `html_title`, `html_favicon`, `html_css_files` (`civiqhub.css` après le CSS local), `html_js_files` (`force-light.js` puis `search-shortcut.js`), `html_sidebars` avec `brand.html` et `search.html`, `light_logo`, `sidebar_hide_name`, les mêmes `light_css_variables`, `footer_icons`, et `sphinxext-opengraph` comme ci-dessus.
4. Vérifier `python -m sphinx -W -b html docs docs/_build/html`. Ne pas inventer de token hors du tableau. Ne pas ajouter de règles sombres.

## How the site is published

The workflow `.github/workflows/docs.yml` publishes the site to GitHub Pages, at <https://civiqhub.github.io/civiqhub-py/>. It runs when `develop` or `main` moves, and it can be started by hand: Actions, workflow `docs`, "Run workflow". It never runs on a pull request.

The published site holds one folder per version:

| Folder | Built from | Shown in the selector as |
| --- | --- | --- |
| `X.Y.Z/` | `main`, for the version `main` holds | `X.Y.Z (latest release)` |
| `X.Y.Z/` | The tag `vX.Y.Z`, for each earlier release | `X.Y.Z` |
| `dev/` | `develop` | `dev (development branch)` |

A commit without `docs/conf.py` holds no documentation and is left out: this is the case of `main` and of the tag `v0.0.1` today. The address of the site redirects to the latest release, or to `dev` as long as `main` holds no documentation.

Every publication rebuilds every version, each from its own commit and with the tools this commit pins: GitHub Pages replaces the whole site each time. The script is `.github/scripts/build-docs-site.py`. It reads the version of each commit in `src/civiqhub/__init__.py`. Run it to build the site as it is published, from the references of your clone:

```bash
git fetch origin develop main --tags
python .github/scripts/build-docs-site.py --output _site
python -m http.server --directory _site
```

The version selector of the sidebar reads `versions.json`, a file the script writes next to the folders. It only appears on the published site, or behind a web server as above: a page opened from the disk has no selector. The `documentation` job of the CI runs the same script on the commit of the pull request alone, and keeps the result as the artifact `docs-html`.

A release needs nothing more for its documentation: when `main` receives the release, the site gains its folder. To change the address of the site, change `SITE_URL` in the workflow and the `Documentation` address in `pyproject.toml`.

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

Sphinx reads no other site during a build, and the site does not link to the documentation of Python.
