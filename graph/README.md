# `graph/` — obsolete copy

**Do not read or edit this directory.** `inverted.json` here is an old copy of the Vidocq
dependency graph, frozen since the graph moved to
[`Vidocq/dep-graph`](https://codefloe.com/Vidocq/dep-graph) on 2026-06-12. No workflow and no
`Vidocq/ci` action reads it, and nothing updates it any more.

- The live graph: [`Vidocq/dep-graph`, `graph/inverted.json`](https://codefloe.com/Vidocq/dep-graph/src/branch/main/graph/inverted.json).
- Its format, its rules and how to query it: [`Vidocq/dep-graph`, `graph/README.md`](https://codefloe.com/Vidocq/dep-graph/src/branch/main/graph/README.md).
- How the CI uses it: [`README.md`](../README.md) of this repository.

The same holds for `data/`, `scripts/`, the `Makefile` and `.forgejo/workflows/build-graph.yml` of
this repository. They are kept until a maintainer removes them.
