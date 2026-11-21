# Finding your way

This page says which name to use for each need, which page of the reference documents it, and which file holds it. To understand why the SDK is built this way, read [Architecture](architecture.md).

Every name below is exported by the package: `import civiqhub` is enough, and {py:class}`civiqhub.Project` is the same class as {py:class}`civiqhub.entities.Project`.

## I want to...

### Read a Project

| I want to | Use | Module |
| --- | --- | --- |
| Load the Project that my token covers | {py:func}`civiqhub.connect`, then {py:meth}`Client.project <civiqhub.client.Client.project>` | [`client`](reference/civiqhub.client.md) |
| List the Projects of a Group | {py:meth}`Client.group <civiqhub.client.Client.group>`, {py:attr}`Group.projects <civiqhub.entities.Group.projects>` | [`client`](reference/civiqhub.client.md), [`entities`](reference/civiqhub.entities.md) |
| Read the articles of a Project and their versions | {py:attr}`Project.articles <civiqhub.entities.Project.articles>`, {py:class}`civiqhub.Article`, {py:attr}`Article.current_version <civiqhub.entities.Article.current_version>`, {py:class}`civiqhub.ArticleVersion` | [`entities`](reference/civiqhub.entities.md) |
| Read the Proposals and their Revisions | {py:attr}`Project.proposals <civiqhub.entities.Project.proposals>`, {py:attr}`Proposal.revisions <civiqhub.entities.Proposal.revisions>`, {py:attr}`Proposal.current_revision <civiqhub.entities.Proposal.current_revision>` | [`entities`](reference/civiqhub.entities.md) |
| Walk the tree of the Amendments | {py:class}`civiqhub.Amendment`, {py:meth}`Proposal.walk_amendments <civiqhub.entities.Proposal.walk_amendments>` | [`entities`](reference/civiqhub.entities.md) |
| Walk the tree of the Arguments | {py:attr}`Proposal.arguments <civiqhub.entities.Proposal.arguments>`, {py:attr}`Argument.depth <civiqhub.entities.Argument.depth>`, {py:class}`civiqhub.Position` | [`entities`](reference/civiqhub.entities.md), [`values`](reference/civiqhub.values.md) |
| Read the participation | {py:attr}`Project.participation <civiqhub.entities.Project.participation>`, {py:class}`civiqhub.Participation` | [`values`](reference/civiqhub.values.md) |
| Know when the data were read | {py:attr}`Project.as_of <civiqhub.entities.Project.as_of>` | [`entities`](reference/civiqhub.entities.md) |

### Read votes

| I want to | Use | Module |
| --- | --- | --- |
| Read the vote counts of a Revision | {py:attr}`Revision.vote_counts <civiqhub.entities.Revision.vote_counts>`, {py:class}`civiqhub.VoteCounts` | [`values`](reference/civiqhub.values.md) |
| Read each vote, at the pseudonymised level | {py:attr}`Project.votes <civiqhub.entities.Project.votes>`, {py:class}`civiqhub.Vote` | [`entities`](reference/civiqhub.entities.md) |
| Read the Actants and what each one did | {py:attr}`Project.actants <civiqhub.entities.Project.actants>`, {py:class}`civiqhub.Actant`, {py:class}`civiqhub.Member`, {py:class}`civiqhub.Agent` | [`entities`](reference/civiqhub.entities.md) |
| Know whether an Actant voted, abstained or never saw a Revision | {py:meth}`Actant.vote_state_on <civiqhub.entities.Actant.vote_state_on>`, {py:class}`civiqhub.VoteState` | [`entities`](reference/civiqhub.entities.md), [`values`](reference/civiqhub.values.md) |
| Choose the level of detail | {py:class}`civiqhub.Exposure`, the argument `exposure` of {py:func}`civiqhub.connect` | [`values`](reference/civiqhub.values.md) |

A vote is never inferred: an Actant who did not vote is "abstained" when the Revision was shown, "not shown" when it was not, and "unknown" when the data do not record what was shown.

### Load from a file or from memory

| I want to | Use | Module |
| --- | --- | --- |
| Save what I loaded, and reopen it later | {py:meth}`Dataset.save <civiqhub.dataset.Dataset.save>`, {py:func}`civiqhub.load` | [`dataset`](reference/civiqhub.dataset.md), [`client`](reference/civiqhub.client.md) |
| Read rows held in memory | {py:class}`civiqhub.MemorySource` | [`sources`](reference/civiqhub.sources.md) |
| Read a saved file through a client | {py:class}`civiqhub.FileSource` | [`sources`](reference/civiqhub.sources.md) |
| Build a dataset from rows directly | {py:class}`civiqhub.Dataset` | [`dataset`](reference/civiqhub.dataset.md) |
| Try the SDK on synthetic data | {py:func}`civiqhub.make_project`, {py:func}`civiqhub.make_rows`, {py:func}`civiqhub.make_truth` | [`synthetic`](reference/civiqhub.synthetic.md) |

### Understand an error

| I want to | Use | Module |
| --- | --- | --- |
| Catch any error of the SDK | {py:class}`civiqhub.CiviqHubError` | [`errors`](reference/civiqhub.errors.md) |
| Know what to do next | {py:attr}`CiviqHubError.hint <civiqhub.errors.CiviqHubError.hint>` | [`errors`](reference/civiqhub.errors.md) |
| Handle a token that is missing or refused | {py:class}`civiqhub.AuthenticationError` | [`errors`](reference/civiqhub.errors.md) |
| Handle a level of detail that the data do not hold | {py:class}`civiqhub.ExposureError` | [`errors`](reference/civiqhub.errors.md) |
| Handle rows that break a rule of the model | {py:class}`civiqhub.ValidationError` | [`errors`](reference/civiqhub.errors.md) |
| Wait when the API asks to slow down | {py:class}`civiqhub.RateLimitedError`, {py:attr}`RateLimitedError.retry_after <civiqhub.errors.RateLimitedError.retry_after>` | [`errors`](reference/civiqhub.errors.md) |

### Write a source

| I want to | Use | Module |
| --- | --- | --- |
| Give the SDK the data of another system | A subclass of {py:class}`civiqhub.Source` | [`sources`](reference/civiqhub.sources.md) |
| Serve stored rows at the level asked for | {py:func}`civiqhub.sources.at_exposure` | [`sources`](reference/civiqhub.sources.md) |
| Know the format of the rows | {py:data}`civiqhub.dataset.FORMAT` | [`dataset`](reference/civiqhub.dataset.md) |

The docstring of {py:mod}`civiqhub.sources` says how to write a source in three steps. [Architecture](architecture.md#sources) says where it fits.

## Two names for one object

Each object has two import paths: the module that defines it, and the package that exports it.

```python
from civiqhub import Project
from civiqhub.entities import Project as SameProject

print(Project is SameProject)
```

```text
True
```

Import from the package: it is the shorter path, and the one that stays stable. The reference documents each object once, on the page of the module that defines it; the [page of the package](reference/civiqhub.md) lists what the package exports.

## Where the files are

| Path | Content |
| --- | --- |
| [`src/civiqhub/`](https://github.com/civiqhub/civiqhub-py/tree/develop/src/civiqhub) | The SDK. One file per module of the reference: `civiqhub.sources` is `src/civiqhub/sources.py` |
| [`tests/`](https://github.com/civiqhub/civiqhub-py/tree/develop/tests) | The tests, one file per subject. `tests/support.py` holds the hand-written rows and the fake API that the tests share |
| [`docs/`](https://github.com/civiqhub/civiqhub-py/tree/develop/docs) | The pages of this site |
| [`docs/snippets.md`](https://github.com/civiqhub/civiqhub-py/tree/develop/docs/snippets.md) | The code of each use, run by the tests against a fake API |

In the reference, the **[source]** link next to a name opens the code that defines it.

## Not written yet

The bridge to the engine `civiqhub-selene` (the collective regimes, the vote matrix, co-clustering and consensus between opinion groups) is planned, and so are the paragraphs of an article, the placement of the Proposals in them, and the citations between Proposals.
