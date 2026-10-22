# Contributing to civiqhub

`civiqhub` is in preview and not functional yet. This guide explains how to contribute.

## Developer Certificate of Origin

Every commit carries a sign-off certifying that you have the right to submit it under the project's license, as defined by the [Developer Certificate of Origin 1.1](https://developercertificate.org).

Sign off with:

```bash
git commit -s -m "Fix typo in README"
```

This appends a line with your real name and email:

```
Signed-off-by: Jane Doe <jane.doe@example.org>
```

To sign off commits you already made on a branch: `git rebase --signoff main`. The `dco` check runs on every pull request and lists any commit without a sign-off.

## License of contributions

Contributions are accepted under the [Mozilla Public License 2.0](LICENSE), the project's license (inbound equals outbound). Start each new source file with the MPL-2.0 notice:

```python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
```

## Dependency policy

- **Core:** the core will depend on numpy, scipy and pandas only.
- **Interoperability:** exports to other tools will write their file formats directly, with no extra dependency. Conversions that require another library's objects will live in an optional extra.
- **Licenses:** every dependency, optional ones included, uses a permissive or weak copyleft license compatible with the MPL-2.0 (BSD, MIT, Apache-2.0, MPL-2.0). Discuss any new dependency in an issue before adding it.
- **Layering:** the object model and the analysis code will work without the platform client, so that any system can use them on its own data.

## Statistical and algorithmic contributions

Each estimator or algorithm ships with:

1. its mathematical definition in the docstring, with the reference it comes from;
2. its uncertainty (variance, interval or posterior) whenever one can be computed;
3. tests on known cases: unanimity, extreme splits, small samples and exact threshold values;
4. explicit, versioned parameters, so that a published result can be reproduced with the same settings.

Results will describe the group and decide nothing. Outputs computed on CiviqHub data will respect the project's exposure policy and show other members only as groups above a minimum size.

## Development workflow

```bash
git clone https://github.com/civiqhub/civiqhub-py
cd civiqhub-py
python -m venv .venv && source .venv/bin/activate
pip install -e . pytest
pytest
```

1. Open an issue describing the change, unless it is a small fix.
2. Work on a branch, with signed-off commits.
3. Open a pull request linked to the issue; tests and the `dco` check must pass.
4. A maintainer reviews and merges.

## Citation

If your contribution implements a published method, add its reference to the docstring. If you publish research using `civiqhub`, cite it with [`CITATION.cff`](CITATION.cff).
