# Snippets

Each snippet is the exact code for one use of the SDK, in eight lines at most. It reads on its own: it starts with `import civiqhub` and needs nothing from the snippets before it. The tests run every snippet of this page and of the README, against a fake API that opens no connection.

The snippets S1 to S7 read the CiviqHub API with a personal access token. `civiqhub.connect()` reads the token in the environment variable `CIVIQHUB_TOKEN`; `civiqhub.connect("civ_pat_...")` takes it as an argument. The snippets S8 and S9 need neither a token nor a network.

Under each snippet, "Reads alone" says whether every name of the snippet is clear without a comment, or lists the names that still need one.

## S1. Load the Project that the token covers

```python
import civiqhub

project = civiqhub.connect().project()
for proposal in project.proposals:
    print(proposal.id, proposal.text)
```

Reads alone: yes.

## S2. Read the Revisions and their vote counts

```python
import civiqhub

project = civiqhub.connect().project()
print("Data as of", project.as_of)
for proposal in project.proposals:
    for revision in proposal.revisions:
        print(revision.number, revision.vote_counts, revision is proposal.current_revision)
```

Reads alone: yes.

## S3. Walk the tree of the Amendments and the tree of the Arguments

```python
import civiqhub

proposal = civiqhub.connect().project().proposals[0]
for depth, amendment in proposal.walk_amendments():
    print("  " * depth, amendment.id, amendment.text)
for argument in proposal.arguments:
    print("  " * argument.depth, argument.position, argument.text)
```

Reads alone: no. `walk_amendments()` gives the Proposal itself first, at depth 0, before its Amendments; the name does not say it.

## S4. Read the participation

```python
import civiqhub

participation = civiqhub.connect().project().participation
print(participation.n_voters, "of", participation.n_actants, "actants voted")
print("Turnout:", participation.turnout)
```

Reads alone: yes.

## S5. List the Projects of a Group

```python
import civiqhub

group = civiqhub.connect().group()
for project in group.projects:
    print(project.slug, project.name)
```

Reads alone: yes.

## S6. Read the hint of an error

```python
import civiqhub

try:
    civiqhub.connect("a token copied badly")
except civiqhub.AuthenticationError as error:
    print(error)
    print(error.hint)
```

Reads alone: yes.

## S7. Save, then reopen without network

```python
import civiqhub

project = civiqhub.connect().project()
path = project.dataset.save("consultation.json")
dataset = civiqhub.load(path)
print(dataset.fingerprint() == project.dataset.fingerprint())
```

Reads alone: no. `dataset`: why the Project is saved through its dataset, and what a dataset is (all that the source gave at one instant), needs one sentence.

## S8. Read rows held in memory

Rows from any system, in the format `civiqhub.dataset/0`, go through a `MemorySource`. Here, the rows are synthetic.

```python
import civiqhub

rows = civiqhub.make_rows(seed=1)
source = civiqhub.MemorySource(rows)
project = civiqhub.connect(source=source, exposure="pseudonymised").project()
print(len(project.actants), "actants,", len(project.votes), "votes")
```

```text
48 actants, 415 votes
```

Reads alone: no. `exposure="pseudonymised"`: the word "exposure" for the level of detail needs a comment.

## S9. Try the SDK on a synthetic Project

The synthetic Project is made up from a seed: it describes nobody.

```python
import civiqhub

project = civiqhub.make_project()
proposal = project.proposals[0]
print(project.name)
print(proposal.text, proposal.current_revision.vote_counts)
```

```text
Demo project (synthetic)
Synthetic proposal 01. VoteCounts(-2: 8, -1: 4, 0: 6, +1: 4, +2: 8)
```

Reads alone: yes.
