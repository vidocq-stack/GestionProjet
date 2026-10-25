# HOWTO — Add a new repository to the Vidocq ecosystem

This guide is the procedure to bring a **new producer repository** (a brick such as `cyrano` or
`knock`) into the Vidocq ecosystem: the layout of the repository, its build, its workflows, its
registration in the dependency graph, and its wiring into `Vidocq/vidocq`. The CI it plugs into is
described in [`README.md`](README.md).

> **Audience**: Vidocq maintainers, and AI agents bootstrapping a new module. When in doubt, copy
> from a recent brick: `knock` is a small, complete reference.

---

## 0. Prerequisites and naming

- **Repository**: `Vidocq/<short-name>` on Codefloe (for example `Vidocq/cyrano`). The graph only
  indexes repositories of the `Vidocq` organisation.
- **groupId**: `io.vidocq.<short-name>` (for example `io.vidocq.cyrano`). Only artifacts whose
  groupId matches `^io\.vidocq(\..+)?$` enter the graph.
- **Version property in consumers**: `<short-name>.version` (for example `<cyrano.version>`),
  named exactly like the repository. The downstream check pins the version of the producer under
  pull request through this property; a consumer without it is built against the published
  SNAPSHOT, and the job warns that it checks nothing.
- **Version**: the current version of the ecosystem (`0.4.0-SNAPSHOT` at the time of writing,
  aligned with `vidocq-parent`).
- **Java / Maven**: Java 25 Temurin and Maven 3.9.16, pinned in `.sdkmanrc`; every POM is
  `modelVersion 4.0.0`.

---

## 1. Repository layout

```
<short-name>/
├── .sdkmanrc                 java=25-tem, maven=3.9.16
├── .gitignore
├── .mvn/, mvnw, mvnw.cmd     Maven wrapper
├── LICENSE, NOTICE, licenses/   EPL-2.0 OR EUPL-1.2 OR GPL-2.0-or-later
├── CONTRIBUTING.md           CLA, GPG signature, DCO (copy from a brick)
├── README.md                 product view: modules, prerequisites, commands
├── CLAUDE.md, AGENTS.md      guide for AI agents working in this repository
├── BUG.md, BENCH.md          bug and benchmark records (workspace rule)
├── pom.xml                   root POM, parent io.vidocq:vidocq-parent
├── <name>-api/  <name>-core/  <name>-cdi-vauban/ ...
├── <name>-tck/               official TCK runner, in the reactor behind the `tck` profile
├── run-official-tck-<spec>.sh
├── docs/en/                  Antora component (English only)
└── .forgejo/workflows/       see §4
```

### 1.1 Root POM

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.vidocq</groupId>
        <artifactId>vidocq-parent</artifactId>
        <version>0.4.0-SNAPSHOT</version>
        <relativePath/>
    </parent>

    <groupId>io.vidocq.<short-name></groupId>
    <artifactId><short-name>-parent</artifactId>
    <version>0.4.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <modules>
        <module><short-name>-api</module>
        <module><short-name>-core</module>
    </modules>

    <properties>
        <!-- Upstream Vidocq bricks, one property per repository: <vauban.version>, ... -->
        <!-- The TCK the pull requests are gated on (see §5). -->
        <ci.tck.command>mvn -B -ntp -P tck,tck-official -pl <short-name>-tck test</ci.tck.command>
    </properties>

    <profiles>
        <profile>
            <id>tck</id>
            <modules>
                <module><short-name>-tck</module>
            </modules>
        </profile>
    </profiles>
</project>
```

`vidocq-parent` brings the publication settings (the `central-snapshots` repository, the
`release` profile with GPG and `central-publishing`, `deployAtEnd=true`) and the plugin versions:
do not repeat them. Copy the `<licenses>`, `<url>` and `<scm>` blocks from a brick.

---

## 2. Meta files

- **`.sdkmanrc`**: `java=25-tem` and `maven=3.9.16`.
- **`CLAUDE.md` / `AGENTS.md`**: identity (groupId, implemented specification), the module table,
  the commands (`./mvnw -ntp install -DskipTests`, `./mvnw test`, `./run-official-tck-<spec>.sh`),
  the repository's specific constraints, and pointers to `BUG.md` and `BENCH.md`. They complement
  the workspace `CLAUDE.md`.
- **`BUG.md` and `BENCH.md`**: create them with the repository, even empty (the `/log-bug` and
  `/log-bench` skills create them otherwise).
- **`.claude/`** (optional): the agents and skills of the workspace that matter for this
  repository.
- **Every Markdown and AsciiDoc file is in English.**

---

## 3. Wiring in `Vidocq/vidocq`

The runtime consumes the brick through an extension module. The layout of the runtime's reactor
is described in vidocq's `CLAUDE.md` ("Architecture & reactor layout"); the usual changes are:

1. the property `<short-name>.version` in vidocq's root `pom.xml`;
2. every consumed artifact of the brick in the root `<dependencyManagement>`;
3. the extension module `vidocq-runtime-<short-name>-<role>-extension`, under the aggregator of its
   domain in `vidocq-runtime-extensions/` (`*-essentials`, `*-jakartaee-core`, `*-jakartaee-web`,
   `*-microprofile`), with its `module-info.java` (`provides VidocqExtension with ...`);
4. its entries in `vidocq-runtime-bom` and in the extension catalog of `vidocq-runtime-tooling`.

Open this pull request **after** the brick's first SNAPSHOT is on `central-snapshots` (§4.1):
vidocq's build resolves the brick from there.

---

## 4. Workflows

Every workflow uses the composite actions of [`Vidocq/ci`](https://codefloe.com/Vidocq/ci), by
absolute URL (`https://codefloe.com/Vidocq/ci/<action>@main`), on the `vidocq-runner` label.

| Workflow | Copy from | Notes |
|---|---|---|
| `pr.yml` | [`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml) | Pull-request validation (§4.2). |
| `update-dep-graph.yml` | [`workflow-templates/update-dep-graph.yml`](workflow-templates/update-dep-graph.yml) | Keeps the repository's entry in `Vidocq/dep-graph` (§6). |
| `ci.yml` | any brick (knock) | Build, test and publish on `main` (§4.1). |
| `merge-bot.yml` | any brick | The `/merge` and `/rebase` comment commands. |
| `notify-docs.yml` | any brick | Rebuilds the docs site after a `main` push touching `docs/**`. |
| `notify-slack.yml` | any brick | Pull-request opened / merged notifications. |
| `sonar.yml` | any brick | SonarQube analysis, report mode (see `vidocq-workspace/QUALITY.md`). |
| `release.yml`, `refresh-release-yml.yml` | any brick | Releases (see the `release-maven` README in `Vidocq/ci`). |
| `downstream-nightly.yml` | vauban | Only once the repository has at least five transitive consumers in the graph (§4.3). |

### 4.1 `ci.yml` (push on `main`)

One job, one pass: `deploy-maven` with `skip-tests: "false"` builds, tests and deploys the
reactor, and `deployAtEnd` (from vidocq-parent) uploads nothing unless the whole reactor passed.
Keep the `concurrency` block as it is:

```yaml
concurrency:
  group: publish-${{ github.repository }}
  cancel-in-progress: false
```

The first green run publishes the brick's SNAPSHOT on `central-snapshots`. **Do it before any
consumer depends on the brick**: the downstream jobs and the consumers' own pull requests resolve
every unchanged upstream from `central-snapshots`, and fail with
`Could not resolve dependencies for io.vidocq.<short-name>:...` until it is there.

### 4.2 `pr.yml` (pull requests)

Copy [`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml), then keep the
repository's own producer steps in the `producer` job (and its runner label on every job). Do
not add a `paths:` filter: the docs-only, test-only and CI-only detection is done inside the
jobs, so that the required check is always reported.

- The template reuses the validation of an unchanged code tree (`ci/validated-tree`, see
  [README.md](README.md#reusing-the-validation-of-an-unchanged-code-tree)): the organisation secret
  `VIDOCQ_BOT_TOKEN` must be able to push refs to the new repository, for the `record` step.
- The TCK the pull requests run is the one the root pom declares: `ci.tck.modules`
  (comma-separated modules, each run with `-Ptck`) and/or `ci.tck.command` (a shell command).
  Declare neither to run no TCK on pull requests.
- **Targeted consumer tests** (opt-in): add `tests: targeted` to the `build-one-consumer` step of
  the `downstream` job, as knock's `pr.yml` does. Leave `graph-pruning` at its default (`false`).
  See [README.md](README.md#targeted-consumer-tests-opt-in).
- As a **consumer**, the repository may list in the root-pom property `ci.targeted.mention-local`
  the files whose mentions of an artifact keep only their own module's tests (a generated
  catalog of names that nothing resolves at run time).

Set the branch protection of `main` (an `Owners` member does it, in the repository settings):
signed commits required, fast-forward merges only, required checks
`pr-validate / governance-checks (pull_request)` and `pr-validate / pr-validate (pull_request)`.
Also enable the manual merge and its automatic detection, which the PR trains rely on.

### 4.3 `downstream-nightly.yml`

The pull-request check is flat: each consumer is built against the producer under pull request
and the published SNAPSHOTs. A producer with at least five transitive consumers also runs, every
night on `main`, the sequential chain (`ci/build-impacted`) that rebuilds every consumer in order.
Copy vauban's file and stagger its cron by five minutes from the others.

### 4.4 Nothing to configure on the consumer side

A consumer has no workflow to receive anything: the producer's `downstream` jobs clone and build
it directly. It only has to expose each upstream through a `<upstream>.version` property (§0).

---

## 5. Official TCK

- The runner module `<name>-tck` is in the reactor, **inside the `tck` profile**: a plain
  `mvn install` neither downloads nor runs anything of the TCK.
- It is never published: `maven.deploy.skip` and `skipPublishing` for
  `central-publishing-maven-plugin` in its pom (copy knock's `knock-tck/pom.xml`).
- `run-official-tck-<spec>.sh` at the root runs it (`-Ptck`, plus `tck-official` when the suite
  needs it), and must exit non-zero when the suite fails.
- Declare it in `ci.tck.command` or `ci.tck.modules` (§4.2) so that pull requests are gated on it.

---

## 6. Registration in the dependency graph

The graph lives in [`Vidocq/dep-graph`](https://codefloe.com/Vidocq/dep-graph), not in this
repository.

1. Make sure the organisation secret `VIDOCQ_BOT_TOKEN` (write access to `Vidocq/dep-graph`) is
   available to the new repository.
2. Push `update-dep-graph.yml` to `main`, then run it once by hand (`workflow_dispatch`). It
   extracts the repository's `io.vidocq.*` artifacts and dependencies (dependencies of every scope,
   managed dependencies, plugins and their dependencies, annotation processor paths, profiles),
   writes `data/Vidocq_<short-name>.json` and rebuilds `graph/inverted.json` in the same commit.
   From then on it runs on every `main` push that touches a `pom.xml`.
3. Check the result in `Vidocq/dep-graph`: the data file exists, and `graph/inverted.json` lists
   the repository under the artifacts it consumes.

To preview the data file locally, from a clone of `Vidocq/dep-graph`:

```bash
bash scripts/extract_deps.sh /path/to/<short-name> Vidocq/<short-name>
```

---

## 7. Commits and pull requests

- Conventional Commits, in English, with the project ticket (`feat(core): ... (#12)`).
- Every commit is GPG-signed and signed off: `git commit -S -s` (CLA signed and key registered in
  `Vidocq/governance`).
- Author and committer: the human alone. When an AI tool helped, add a `Co-Authored-By:` trailer
  naming it (see `AI-POLICY.md`).
- Never write the CI-skip marker in a commit message, not even to explain it: Forgejo then starts
  no workflow, and the pull request never gets its required checks.

---

## 8. Checklist

### New repository
- [ ] `pom.xml` with parent `io.vidocq:vidocq-parent`, groupId `io.vidocq.<short-name>`, Model 4.0.0
- [ ] `.sdkmanrc`, `.gitignore`, Maven wrapper, `LICENSE`, `NOTICE`, `licenses/`, `CONTRIBUTING.md`
- [ ] `README.md`, `CLAUDE.md`, `AGENTS.md`, `BUG.md`, `BENCH.md`, in English
- [ ] TCK runner in the `tck` profile, never published, declared in `ci.tck.*` (if a TCK exists)
- [ ] `.forgejo/workflows/`: `pr.yml` (template), `update-dep-graph.yml` (template), `ci.yml`,
      `merge-bot.yml`, `notify-docs.yml`, `notify-slack.yml`, `sonar.yml`, `release.yml`,
      `refresh-release-yml.yml`
- [ ] Branch protection: signed commits, fast-forward only, the two required checks, manual merge
      with automatic detection
- [ ] First SNAPSHOT published on `central-snapshots`

### `Vidocq/dep-graph`
- [ ] `update-dep-graph` run once; `data/Vidocq_<short-name>.json` present
- [ ] `graph/inverted.json` lists the new repository

### `Vidocq/vidocq`
- [ ] Property `<short-name>.version` and the brick's artifacts in `<dependencyManagement>`
- [ ] Extension module under its domain aggregator, in the BOM and the extension catalog
- [ ] Tests of the extension (ServiceLoader discovery, named modules)

---

## 9. References

- Workspace rules: the workspace `CLAUDE.md` and `vidocq-workspace/AGENTS.md`
- CI architecture: [`README.md`](README.md)
- Shared actions: [`Vidocq/ci` README](https://codefloe.com/Vidocq/ci/src/branch/main/README.md)
- Dependency graph: [`Vidocq/dep-graph`](https://codefloe.com/Vidocq/dep-graph)
- Merging and branch protection: [`Vidocq/governance` MAINTAINERS.md](https://codefloe.com/Vidocq/governance/src/branch/main/MAINTAINERS.md)
- Changes spanning several repositories: [`vidocq-workspace/docs/changes-across-repositories.md`](https://codefloe.com/Vidocq/vidocq-workspace/src/branch/main/docs/changes-across-repositories.md)
