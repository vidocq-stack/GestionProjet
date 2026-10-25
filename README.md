# GestionProjet — Vidocq CI architecture and repository templates

This repository describes how the Vidocq repositories are validated and published, and holds
the workflow templates every Maven repository of the organisation copies. It is also the issue
tracker for cross-repository project work (for example `Vidocq/GestionProjet#9`, the TCK gate).

| Path | Status | What it is |
|---|---|---|
| [`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml) | **current** | The source of truth for `.forgejo/workflows/pr.yml` in every producer repository. Edit it here, then propagate. |
| [`workflow-templates/update-dep-graph.yml`](workflow-templates/update-dep-graph.yml) | **current** | `.forgejo/workflows/update-dep-graph.yml`, identical in every repository. |
| [`HOWTO_ADD_NEW_PROJECT.md`](HOWTO_ADD_NEW_PROJECT.md) | **current** | How to add a new repository to the ecosystem. |
| `.forgejo/workflows/pr.yml`, `merge-bot.yml` | **current** | This repository's own checks (the governance gate, below) and its `/merge` command. |

The dependency graph is not here: it lives in [`Vidocq/dep-graph`](https://codefloe.com/Vidocq/dep-graph).
The copy this repository used to hold (`data/`, `graph/`, `scripts/`, `Makefile`, `build-graph.yml`),
frozen since the graph moved there on 2026-06-12 and read by nothing, was removed.

## Where things live

| Repository | Role in the CI |
|---|---|
| [`Vidocq/ci`](https://codefloe.com/Vidocq/ci) | The shared composite actions (`setup-maven`, `resolve-impacted`, `build-one-consumer`, `build-impacted`, `targeted-producer-tests`, `select-tck`, `deploy-maven`, `update-dep-graph`, the merge-bot...). Its [README](https://codefloe.com/Vidocq/ci/src/branch/main/README.md) documents every input. Workflows reference them by absolute URL, `https://codefloe.com/Vidocq/ci/<action>@main`. |
| [`Vidocq/dep-graph`](https://codefloe.com/Vidocq/dep-graph) | The dependency graph between the repositories (`data/*.json`, `graph/inverted.json`) and its scripts. Public, so that pull requests from forks can read it without a token. |
| [`Vidocq/vidocq-parent`](https://codefloe.com/Vidocq/vidocq-parent) | The parent POM of every brick. It sets `deployAtEnd=true` on `maven-deploy-plugin`, which the one-pass publication of `main` relies on. |
| `Vidocq/GestionProjet` (this repository) | The templates and this description. It holds no copy of the graph. |
| Each repository, `.forgejo/workflows/` | `pr.yml`, `ci.yml`, `update-dep-graph.yml`, `merge-bot.yml`, `release.yml`, `sonar.yml`, and so on. |

## Pull-request validation: `pr.yml`

Every producer repository runs the same workflow, copied from
[`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml). Nothing is published
and there is no staging registry: each job builds what it needs at a release-style pull-request
version, `<base>-PR<n>.<sha8>` (no `-SNAPSHOT`), and installs it into its own local Maven
repository.

```
                      ┌──> producer ───┐
governance-checks ────┤                ├──> downstream (matrix: one job per consumer) ──┐
                      └──> impacted ───┘                                                ├──> pr-validate
governance-checks, producer, impacted ──────────────────────────────────────────────────┘
```

| Job | What it does |
|---|---|
| `governance-checks` | The CLA, the GPG signature and the `Signed-off-by:` trailer of every commit (`ci/governance-checks`). Every other job waits for it: a pull request that fails it builds nothing. |
| `producer` | Detects the kind of change set (below), checks whether the same code tree was already validated (below), sets the PR version across the reactor (`versions:set`, plus the `plugin.xml` of `maven-plugin` modules), runs `mvn install` with the unit and integration tests, then the TCK the repository declares in its root pom (`ci.tck.modules`, `ci.tck.command`; none declared means no TCK on pull requests), plus the repository's own checks. |
| `impacted` | `ci/resolve-impacted`, in parallel with `producer`: reads the graph from `Vidocq/dep-graph`, checks that it is not older than the producer's data file (a stale graph fails the job, since it may miss consumers), keeps the consumers that exist on the forge, and outputs them as a job matrix with, for each consumer, the impacted upstreams it depends on. No checkout, no Java, no Maven. |
| `downstream` | One job per consumer, `ci/build-one-consumer`, `fail-fast: false`, `max-parallel: 6`. See [The downstream check](#the-downstream-check-flat-mode). |
| `pr-validate` | The aggregator, and the required check. It always runs and fails unless `governance-checks`, `producer` and `impacted` succeeded and `downstream` succeeded, or was skipped for a reason the aggregator accepts. |

### What a change set skips

The `producer` job reads the pull request's changed files from the forge API. Detection is done
with step-level `if`s, never with a `paths:` trigger filter: a filtered workflow would leave the
required check unreported and block `/merge` forever.

| Change set | Producer build, tests, TCK | Downstream rebuild |
|---|---|---|
| **docs-only**: every file is `*.md`, `*.adoc`, under `docs/`, `LICENSE*` or `NOTICE*`, and none is under a `src/` directory | skipped | skipped |
| **test-only**: every file is under a `src/test/` directory, or is a docs file | run | skipped |
| **CI-only**: every file is under `.forgejo/` (alone or with docs or test files) | run (it also exercises the changed workflow) | skipped |
| anything else | run | run |

Test code and CI configuration are not part of the produced artifacts, so the consumers cannot
observe them. One guard: when test files changed and a `pom.xml` of the repository declares
`<goal>test-jar</goal>`, the change set is not test-only, because a published test jar makes
test changes visible downstream.

### Reusing the validation of an unchanged code tree

`ci/validated-tree` (Vidocq/ci#57) keys a validation on the **code-tree id** of HEAD: a SHA-256 of
its tree without the documentation files (`*.md`, `*.adoc`, `docs/`, `LICENSE*`, `NOTICE*`, never
under a `src/`), instead of the commit.

- In `producer`, `mode: check` (scope `pr-validate`) asks whether a green run of this repository
  already validated that id. If so (`reused: true`), the build, the tests, the TCK and the
  `downstream` jobs are not run again. This covers a docs-only commit on top of validated code, a
  rebase on a `main` that moved by documentation only, and the merge-bot's re-signing of an
  unchanged rebase.
- In `pr-validate`, at the end of a green run that built something, `mode: record` stores the id as
  a ref of the repository, `refs/validated/pr-validate/<id>`, pushed with the bot token. A ref is
  seen by every runner, unlike the per-runner actions cache.
- Never reused: an event other than `pull_request`, a re-run (attempt > 1: re-running a run is how
  to ask for a real build), and a companion branch (another repository of the organisation has a
  branch named like the head branch; a forge error counts as one).

### The aggregator and the required checks

On Forgejo a skipped job counts as a success for branch protection, so `pr-validate` decides
alone. A skipped `downstream` passes only for a docs-only, test-only or CI-only change set, for a
code tree already validated (`reused`), or when no consumer is impacted. Forgejo creates no job for an empty matrix, so `resolve-impacted`
then outputs one placeholder entry (`{"repo":"none"}`) and `count: 0`, and `downstream` skips on
`count == 0`. In every other case a skipped, failed or cancelled `downstream` fails
`pr-validate`: it never passes when work was expected.

The branch protection of `main` requires `pr-validate / governance-checks (pull_request)` and
`pr-validate / pr-validate (pull_request)` (the per-repository list is in
[`Vidocq/governance` MAINTAINERS.md](https://codefloe.com/Vidocq/governance/src/branch/main/MAINTAINERS.md#branch-protection)).

### The downstream check (flat mode)

Each `downstream` job rebuilds the producer under pull request at its PR version, without its
tests, then builds **one** consumer against it, with its tests. Only the producer's version is
pinned in the consumer, through its `<producer>.version` property (for example
`<vauban.version>`); every other `io.vidocq` upstream comes from `central-snapshots` as
published, which is what Central holds right after the producer is merged. A consumer whose poms
declare no `<producer>.version` gets a warning: its build does not check the change.

- A failing consumer test is rerun once; a test that then passes does not fail the pull request,
  and the job summary lists it as a flake to record in that repository's `BUG.md`.
- **Companion branches**, for a change that spans several repositories: when a consumer has a
  branch named like the pull request's head branch, it is built on that branch, and each
  intermediate upstream that also has it is rebuilt first, in the same job, without its tests
  (a mini-chain). Only for a pull request from a branch of the producer repository, never from a
  fork. The workflow is in
  [`vidocq-workspace/docs/changes-across-repositories.md`](https://codefloe.com/Vidocq/vidocq-workspace/src/branch/main/docs/changes-across-repositories.md).
- What the flat check does not cover is the eventual state, where every intermediate consumer is
  rebuilt in order against the new producer. The nightly chain checks it (below).

### Targeted consumer tests (opt-in)

With `tests: targeted` on its `build-one-consumer` step, a producer asks its consumers to run
only the tests that can see a change. Every consumer module still compiles, test-compiles, runs
its codegen, packages and installs in the same single `install`; test execution is turned off
(`skipTests`, `skipITs`, `invoker.skip` written into the module's pom, never `-DskipTests` on the
command line) only in the modules whose build cannot see any artifact of the producer. The
analysis reads the consumer's effective POM: dependencies of every scope, plugins and their
dependencies, annotation processor paths, parents, BOM imports, nested builds, and producer
artifactIds named in `src/`. Any doubt makes a module affected, and the job falls back to the full
run, with the reason in the job summary, on a companion branch, a mini-chain, a Maven or analysis
error, or anything it cannot establish.

- **Live on** knock, grimm, cervantes, humboldt, heisenberg, champollion, ravel, dirac, cyrano,
  cassini, chappe and foy. The other producers run every consumer test (`tests: full`, the
  default).
- **To opt in**, add `tests: targeted` to the `build-one-consumer` step of the producer's
  `pr.yml` (see knock's `pr.yml`).
- `graph-pruning` stays `false` (the default). `true` skips, using the graph, the external
  artifacts of repositories that do not consume the producer: about 60 s less on vidocq, but the
  graph is then trusted without any freshness or version check.
- A **consumer** can declare, in the root-pom property `ci.targeted.mention-local`
  (comma-separated repository-relative paths or globs), files whose mentions of an artifact keep
  the tests of their own module only, not of its dependents. vidocq lists its generated
  `extension-catalog.properties`. The property asserts that nothing resolves the listed names at
  run time; a test that does makes the file unsafe, and it must leave the property.

### vidocq's own pull requests

vidocq adds two steps to its `producer` job:

- `targeted-producer-tests`: `mode: targeted` right before the `install` keeps the tests of the
  modules a changed path reaches (its owner module, the reactor modules depending on it, the
  modules naming it) and skips the others; `mode: restore` right after puts every edited pom back
  byte for byte; a guard fails any later Maven step, such as the TCK, while edits are in place.
  Any doubt (root pom, `.forgejo/`, scripts, an error) runs every test. The policy: only a
  repository whose `main` publishes after a full test run may use it.
- `select-tck`: replays only the declared TCK runners (`ci.tck.modules`) a change reaches; any
  doubt replays all of them, and the nightly `tck-nightly.yml` still replays every runner.

## Nightly downstream chain

The producers with at least five transitive consumers (vauban, chappe, champollion, ravel,
cassini) run `downstream-nightly.yml` every night on `main`: the sequential chain of
`ci/build-impacted`, with the producer at `<base>-NIGHTLY.<sha8>`, then every transitive consumer
in topological order, pinned to the producer and to every consumer rebuilt before it. It is
non-blocking and publishes nothing; a red run posts to Slack. erasmus still runs this sequential
chain on its pull requests.

## `main`: `ci.yml`

One job, one pass: `ci/deploy-maven` with `skip-tests: "false"` builds, tests and deploys the
reactor in the same Maven run. It is safe because vidocq-parent sets `deployAtEnd=true`: nothing
is uploaded unless the whole reactor built and passed its tests. A SNAPSHOT version goes to
`central-snapshots`, a release version through `central-publishing`.

```yaml
concurrency:
  group: publish-${{ github.repository }}
  cancel-in-progress: false      # queued, never cancelled: a newer merge must not cut a deploy
```

vauban is the exception: `mvn install`, then the CDI TCK (`ci/run-tck`), then the deploy. TCK
runners are never published: they stay out of the default reactor behind the `tck` profile, or
skip deployment in their own pom.

## Merging: the merge-bot and PR trains

`main` accepts fast-forward merges only and requires signed commits; `/merge` on a pull request
rebases it, re-signs it with the CI bot key and fast-forwards `main` once the required checks are
green (see [`Vidocq/governance` MAINTAINERS.md](https://codefloe.com/Vidocq/governance/src/branch/main/MAINTAINERS.md#the-merge-bot)).

When two or more pull requests of one repository are ready, merge them as a **train** instead of
one by one, since every merge moves `main` and restarts the downstream check of the others:

1. In a fresh worktree from `origin/main`, cherry-pick the commits of each pull request, in
   dependency order, signed (`git cherry-pick -S`). Do not rebase the branches onto each other:
   that duplicates commits.
2. Force-push each pull request's branch to its point of the chain: pull request *n* is a prefix
   of the chain, the last one, the top, holds everything. Cancel the runs started on the other
   pull requests.
3. Validate the top once: its `pr-validate` and its SonarQube comment cover the whole chain.
4. Merge the top with the forge's **Fast-forward only** merge (its commits are already signed by
   the cherry-picks): `main` moves over every pull request of the chain, in order. The forge's
   automatic merge detection then marks the other pull requests merged; mark any it misses as
   manually merged, with its head commit.

If the top fails, find the faulty pull request, take it out of the chain and rebuild the chain.

## Adding a repository

See [`HOWTO_ADD_NEW_PROJECT.md`](HOWTO_ADD_NEW_PROJECT.md).

## Secrets

| Secret (organisation level) | Used for |
|---|---|
| `VIDOCQ_BOT_TOKEN` | write access to `Vidocq/dep-graph` (`update-dep-graph`) and to the repository itself (the `refs/validated/...` refs of `validated-tree`), cloning consumers, the forge API (changed files, companion branches). Optional for reading the graph, which is public: fork pull requests run without it. |
| `SLACK_WEBHOOK_URL` | notifications |
| `CENTRAL_USERNAME`, `CENTRAL_PASSWORD`, `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE` | publication on `main` and releases |
| `CI_BOT_GPG_PRIVATE_KEY`, `CI_BOT_GPG_PASSPHRASE`, `CI_BOT_GPG_KEY_ID` | the merge-bot's signatures |
| `SONAR_TOKEN` (and the variable `SONAR_HOST_URL`) | the SonarQube analysis |

A composite action does not inherit `secrets.*`: each workflow passes them through `with:`.

## This repository's own checks

GestionProjet has no Maven build. Its `pr.yml` runs only the governance gate, the
`governance-checks` job of `Vidocq/ci/governance-checks`: the CLA of the pull request's author, and
the GPG signature and the `Signed-off-by:` trailer of every commit (see
[`CONTRIBUTING.md`](CONTRIBUTING.md)). It reports the context
`pr-validate / governance-checks (pull_request)`, the check to require on `main`. A change to the
templates is checked where it is propagated, by the `pr-validate` of each repository.
