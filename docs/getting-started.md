# Getting started

This page installs the SDK and reads a synthetic Project, without a token and without the network. The tests of the repository run every Python block of this page and compare what it prints with the output shown.

## Install

```bash
pip install civiqhub
```

The version on PyPI, 0.0.1, only reserves the name. To run what this page shows, install the development branch:

```bash
pip install "civiqhub @ git+https://github.com/civiqhub/civiqhub-py@develop"
```

Python 3.11 or later is required. The SDK depends on nothing but the standard library.

## Open a synthetic project

{py:func}`civiqhub.make_project` gives a Project made up from a seed. It describes nobody, and it has a known structure: three opinion groups of Actants and two blocks of Proposals, which the votes follow.

```python
import civiqhub

project = civiqhub.make_project()
print(project)
print(len(project.proposals), "proposals,", len(project.amendments), "amendments")
```

```text
Project('pr-demo', 'Demo project (synthetic)')
15 proposals, 2 amendments
```

The Project is read through a {py:class}`civiqhub.MemorySource`, at the pseudonymised level: it holds every vote, each Actant known by a pseudonym.

## Read proposals and vote counts

A Proposal has one or more Revisions; the current one is {py:attr}`~civiqhub.entities.Proposal.current_revision`. The votes of a Revision are counted from score -2 to score +2 in {py:class}`civiqhub.VoteCounts`. Everything was read at one instant, {py:attr}`~civiqhub.entities.Project.as_of`.

```python
print("Data as of", project.as_of)
for proposal in project.proposals[:3]:
    revision = proposal.current_revision
    print(proposal.id, revision.number, revision.vote_counts)
```

```text
Data as of 2026-01-01T00:00:00Z
p-01 1 VoteCounts(-2: 8, -1: 4, 0: 6, +1: 4, +2: 8)
p-02 1 VoteCounts(-2: 4, -1: 8, 0: 2, +1: 5, +2: 11)
p-03 1 VoteCounts(-2: 10, -1: 1, 0: 5, +1: 10, +2: 9)
```

The counts are raw: the SDK computes no mean and no label of consensus. The Proposal `p-15` has two Revisions; the second one comes from an Amendment that was adopted.

```python
amended = project.proposals[14]
print([revision.number for revision in amended.revisions])
print(amended.current_revision.amendment)
```

```text
[1, 2]
Amendment('p-16', 'Synthetic amendment 16.')
```

## Read the participation

{py:attr}`~civiqhub.entities.Project.participation` gives the counts of the Project. {py:attr}`~civiqhub.values.Participation.turnout` is the share of the Actants who voted.

```python
participation = project.participation
print(participation.n_voters, "of", participation.n_actants, "actants voted")
print(participation.turnout)
```

```text
48 of 48 actants voted
1.0
```

## Save and reopen

What a source gave is a {py:class}`civiqhub.Dataset`: the Project, and everything around it, at one instant. {py:meth}`~civiqhub.dataset.Dataset.save` writes it to a file, and {py:func}`civiqhub.load` reopens it without the network.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as folder:
    path = project.dataset.save(Path(folder) / "demo.json")
    reopened = civiqhub.load(path)
print(reopened.fingerprint() == project.dataset.fingerprint())
print(reopened.source)
```

```text
True
file demo.json
```

The fingerprint identifies the rows: the same rows give the same fingerprint, on every system.

## Connect with a token

To read your own Project, create a personal access token in the settings of the Project and set it in the environment variable `CIVIQHUB_TOKEN`. {py:func}`civiqhub.connect` reads it, and gives a {py:class}`civiqhub.Client`:

<!-- not run: needs a token and the network -->

```python
import civiqhub

project = civiqhub.connect().project()
group = civiqhub.connect("civ_pat_...").group()
```

The second line passes the token as an argument instead. A token covers one Project or one Group, and never more than what its owner sees. The SDK only reads: it sends no change.

## Exposure levels

The level of exposure is the level of detail of the data, a value of {py:class}`civiqhub.Exposure`. {py:func}`~civiqhub.connect` asks for the aggregated level by default: the vote counts and the participation, and nothing about who voted. Asking an aggregated Project for its Actants or its votes raises {py:class}`civiqhub.ExposureError`, whose {py:attr}`~civiqhub.errors.CiviqHubError.hint` says what to do.

```python
aggregated = civiqhub.make_project(exposure="aggregated")
print(aggregated.dataset.exposure)
try:
    aggregated.actants
except civiqhub.ExposureError as error:
    print(error.hint)
```

```text
aggregated
Ask an administrator of the Project to enable pseudonymised access, then connect with civiqhub.connect(exposure="pseudonymised").
```

The pseudonymised level gives one row per vote. An administrator of the Project must enable it.

## Next

- [Finding your way](library-map.md) says which name to use for what, and where it lives.
- [Architecture](architecture.md) explains how the SDK is built and why a dataset is frozen.
- [Snippets](snippets.md) holds the code of each use in eight lines.
- The [reference](reference/index.md) documents every public name.
