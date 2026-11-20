# civiqhub

Python package by [CiviqHub](https://civiqhub.com).

`civiqhub` is the Python SDK of CiviqHub. With a personal access token and three lines of code, it gives the objects of a Project as they appear on screen: Group, Project, Proposal, Amendment, Revision, Argument, Vote and Actant. It reads them through the CiviqHub API, a saved file or rows held in memory, and gives one frozen graph of objects that navigates without the network.

**Status: pre-alpha.** The objects of the product, their loading and the synthetic Project are written. The CiviqHub API is not published yet, so reading it is provisional.

## Install

```bash
pip install civiqhub
```

The version on PyPI, 0.0.1, only reserves the name. Until the next release, install the development branch:

```bash
pip install "civiqhub @ git+https://github.com/civiqhub/civiqhub-py@develop"
```

## Use

Create a personal access token in the settings of your Project, and set it in the environment variable `CIVIQHUB_TOKEN`, or pass it as `civiqhub.connect("civ_pat_...")`.

Load the Project that the token covers:

```python
import civiqhub

project = civiqhub.connect().project()
for proposal in project.proposals:
    print(proposal.id, proposal.text)
```

Read the Revisions and their vote counts:

```python
import civiqhub

project = civiqhub.connect().project()
print("Data as of", project.as_of)
for proposal in project.proposals:
    for revision in proposal.revisions:
        print(revision.number, revision.vote_counts, revision is proposal.current_revision)
```

Save, then reopen without network:

```python
import civiqhub

project = civiqhub.connect().project()
path = project.dataset.save("consultation.json")
dataset = civiqhub.load(path)
print(dataset.fingerprint() == project.dataset.fingerprint())
```

To try the SDK without a token, `civiqhub.make_project()` gives a synthetic Project, which describes nobody. [`docs/snippets.md`](docs/snippets.md) holds these snippets and six more.

## Levels of exposure

The level of exposure is the level of detail of the data.

- `aggregated`, the default: the vote counts of each Revision and the participation of the Project. Nothing says who voted.
- `pseudonymised`: one row per vote, each Actant known by a pseudonym only. An administrator of the Project must enable it; then connect with `civiqhub.connect(exposure="pseudonymised")`.

No name, e-mail address or user id of a person ever enters an object. The token appears in no file and no error message, and a `repr` shows its last four characters at most.

## No formula

This package reads and navigates data; it computes no statistic. Analyses live in the engine `civiqhub-selene`.

## Documentation

The documentation is published at <https://civiqhub.github.io/civiqhub-py/>, with one version per release and one for the development branch. [`docs/README.md`](docs/README.md) says how to build it.

## Citing

Citation metadata lives in [`CITATION.cff`](CITATION.cff); on GitHub, the "Cite this repository" button exports it as BibTeX or APA.

## Contributing

Contributions are welcome under the [Developer Certificate of Origin](https://developercertificate.org): sign off each commit with `git commit -s`. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full procedure.

## License

[Mozilla Public License 2.0](LICENSE). You can use `civiqhub` in any project, open or closed. If you distribute modified files of this package, publish those modifications under the MPL-2.0.
