# Architecture diagrams

Mermaid sources of the class architecture of the `civiqhub` core, taken from the design tickets UML-1.3 and UML-1.10.

**Status: draft, not adopted.** The tickets are under review and the architecture decision record is still a proposal. The decisions live in that record; only the diagram sources live here.

| File | Diagram | How to read it |
| --- | --- | --- |
| [`packages.mmd`](packages.mmd) | Packages and their dependencies | The package map recommended by UML-1.3. It is not the layout of `src/civiqhub/` on the exploratory branch. |
| [`domain-classes.mmd`](domain-classes.mmd) | Domain classes | Draws the recommendations of UML-1.4. The exploratory code differs: there `Amendment` derives from `Proposal`, and `Member` and `Agent` derive from `Actant`. |
| [`sequence-load-project.mmd`](sequence-load-project.mmd) | Load a Project from a token | As the prototype does it. It has run against a fake API only. The endpoint that tells what a token covers, and reads at a given instant, are assumptions. |
| [`sequence-dissensus-index.mmd`](sequence-dissensus-index.mmd) | Ordinal dissensus index on a revision | As the prototypes do it. No method returns an uncertainty yet: the field is `None`. |
| [`sequence-simulation.mmd`](sequence-simulation.mmd) | A small deliberation held in memory | As the prototype allows it. It is not a simulation: no step lets an Actant act. |
