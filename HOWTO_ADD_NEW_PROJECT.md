# HOWTO — Ajouter un nouveau projet à l'écosystème Vidocq

Ce guide décrit la procédure complète pour intégrer un **nouveau sous-projet
producteur** dans l'écosystème Vidocq (ex. : `cyrano`, `knock`, futurs). Il
couvre les conventions de structure du repo, les fichiers méta obligatoires
(dont les fichiers Claude / agents / skills), la wiring Maven côté
`vidocq/vidocq-mps`, et l'enregistrement dans le graphe `GestionProjet`.

> **Public visé** : mainteneurs Vidocq, agents IA qui doivent bootstrap un nouveau
> module sans surprise. Référencé par l'agent `claude` et le skill `init`.

---

## 0. Pré-requis & nommage

- **GroupId** : `io.vidocq.<nom-court>` (ex. `io.vidocq.cyrano`). Le `groupId`
  doit matcher la regex `^io\.vidocq(\..+)?$` — c'est le filtre du graphe
  GestionProjet (cf. `data/schema.json`).
- **Nom du repo Forgejo** : `vidocq/<nom-court>` (ex. `vidocq/cyrano`). Whitelist
  stricte côté GestionProjet.
- **Nom de la property Maven** dans les consommateurs : `<nom-court>.version`
  (ex. `<cyrano.version>`). Cette property porte le même nom que le repo court
  — sans quoi le workflow `upstream-pr.yml` côté consommateur ne peut pas
  résoudre la version automatiquement (cf. `workflow-templates/upstream-pr-consumer.yml`).
- **Version initiale** : `0.1.0-SNAPSHOT` par défaut (Mansart est l'exception
  historique à `1.0.0-SNAPSHOT`).
- **Java / Maven** : Java 25 Temurin + Maven 4.0.0-rc-5, pinés via `.sdkmanrc`.

---

## 1. Structure du repo producteur

Arborescence minimale attendue (s'inspirer de `vauban/`, `chappe/`, `cyrano/`) :

```
<nom-court>/
├── .sdkmanrc                  ← java=25-tem, maven=4.0.0-rc-5
├── .gitignore                 ← target/, *.iml, .idea/, etc.
├── LICENSE                    ← Apache-2.0 (cohérence écosystème)
├── README.md                  ← vue produit : modules, prérequis, commandes
├── CLAUDE.md                  ← guide spécifique pour Claude Code dans ce repo
├── AGENTS.md (optionnel)      ← inventaire agents dispo dans .claude/agents/
├── ROADMAP.md (optionnel)     ← jalons M1/M2/Mx
├── TCK.md (optionnel)         ← procédure TCK officiel si applicable
├── BUG.md                     ← traçabilité bugs (cf. CLAUDE.md workspace)
├── BENCH.md                   ← traçabilité benchmarks (idem)
├── pom.xml                    ← root POM (Model 4.1.0, root="true", pas de <parent>)
├── <nom>-api/                 ← API publique
├── <nom>-core/                ← implémentation standalone
├── <nom>-cdi-vauban/          ← intégration CDI via Vauban (si applicable)
├── <nom>-tck/                 ← TCK officiel, HORS reactor (cf. §5)
├── .claude/                   ← config Claude Code locale
│   ├── agents/                ← agents spécialisés (jpms-guardian, etc.)
│   └── skills/                ← skills (/log-bug, /log-bench)
└── .forgejo/workflows/        ← CI/CD (cf. §4)
    ├── ci.yml                 ← build + deploy snapshots sur push main
    ├── pr.yml                 ← validation PR + publication pr-staging
    ├── update-dep-graph.yml   ← maintenance GestionProjet
    └── upstream-pr.yml        ← réception dispatch consommateurs (si consommateur)
```

### 1.1 Root POM (Model 4.1.0)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.1.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.1.0 http://maven.apache.org/xsd/maven-4.1.0.xsd"
         root="true">
    <modelVersion>4.1.0</modelVersion>

    <groupId>io.vidocq.<nom-court></groupId>
    <artifactId><nom-court>-parent</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <packaging>pom</packaging>
    <name><Nom-Court></name>
    <description>… description courte avec mention zéro-dep / JPMS / VT …</description>

    <subprojects>
        <subproject><nom-court>-api</subproject>
        <subproject><nom-court>-core</subproject>
        <subproject><nom-court>-cdi-vauban</subproject>
        <!-- PAS le tck : volontairement hors reactor -->
    </subprojects>

    <properties>
        <maven.compiler.release>25</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <!-- versions des deps Vidocq amont (Vauban, Chappe, etc.) si consommateur -->
    </properties>

    <distributionManagement>
        <repository>
            <id>vidocq-releases</id>
            <url>https://repo.vidocq.dev/releases</url>
        </repository>
        <snapshotRepository>
            <id>vidocq-snapshots</id>
            <url>https://repo.vidocq.dev/snapshots</url>
        </snapshotRepository>
    </distributionManagement>
</project>
```

⚠️ **Model 4.1.0** : les modules enfants déclarent juste `<parent>` sans
version explicite. Le module `<nom>-tck` reste en **Model 4.0.0** standalone et
**ne déclare pas de `<parent>`** (incompatibilité ShrinkWrap Resolver 3.3 vs
Model 4.1.0 — voir CLAUDE.md du workspace).

---

## 2. Fichiers méta obligatoires

### 2.1 `.sdkmanrc`

```
java=25-tem
maven=4.0.0-rc-5
```

### 2.2 `CLAUDE.md` (gabarit minimal)

```markdown
# CLAUDE.md — <Nom-Court>

Ce fichier complète le `CLAUDE.md` du workspace Vidocq. À lire en priorité
avant toute modification dans ce repo.

## Identité
- groupId : `io.vidocq.<nom-court>`
- spec implémentée : <ex. MicroProfile Rest Client 4.0>
- philosophie : zéro-dep, JPMS strict, Virtual Threads, codegen statique

## Modules
| Module | Rôle |
|---|---|
| `<nom>-api` | … |
| `<nom>-core` | … |
| `<nom>-cdi-vauban` | … |
| `<nom>-tck` | TCK officiel — hors reactor |

## Commandes
- `./mvnw -ntp install -DskipTests` : build complet
- `./mvnw test` : tests unitaires
- `./run-official-tck-<spec>.sh` : TCK officiel (si applicable)

## Contraintes spécifiques
- … (limitations connues, exceptions à la philosophie zéro-dep, etc.)

## Traçabilité
- Bugs : voir `BUG.md`
- Benchmarks : voir `BENCH.md`
```

### 2.3 `BUG.md` et `BENCH.md`

Initialiser dès la création du repo, même vides (skills `/log-bug`
et `/log-bench` les créent à la volée sinon). Format documenté dans le
`CLAUDE.md` du workspace.

### 2.4 `.claude/` (config Claude Code locale)

```
.claude/
├── agents/      ← copier les agents pertinents du workspace
│                  (jpms-guardian, classfile-codegen, virtual-threads-reviewer,
│                   dependency-gatekeeper, tck-runner)
├── skills/      ← copier les skills /log-bug, /log-bench
└── settings.local.json (optionnel, non commité par défaut)
```

Référencer les agents pertinents pour ce sous-projet — pas la peine d'inclure
ce qui ne sert pas (un projet sans TCK n'a pas besoin de `tck-runner`).

---

## 3. Wiring côté `vidocq/vidocq-mps`

L'orchestrateur `vidocq-mps` consomme le sous-projet via un wrapper
d'extension. Quatre points à modifier dans `vidocq/vidocq-mps/` :

### 3.1 Property dans le parent POM (`vidocq/pom.xml`)

```xml
<properties>
    …
    <<nom-court>.version>0.1.0-SNAPSHOT</<nom-court>.version>
    …
</properties>
```

### 3.2 Entrées dans le `<dependencyManagement>`

Pour **chaque artefact consommé** (pattern Vauban : api + core + cdi-vauban +
indexer + classloader-spi sont tous explicités) :

```xml
<dependency>
    <groupId>io.vidocq.<nom-court></groupId>
    <artifactId><nom-court>-api</artifactId>
    <version>${<nom-court>.version}</version>
</dependency>
<dependency>
    <groupId>io.vidocq.<nom-court></groupId>
    <artifactId><nom-court>-core</artifactId>
    <version>${<nom-court>.version}</version>
</dependency>
<!-- etc. -->

<!-- PUIS l'extension wrapper Vidocq elle-même : -->
<dependency>
    <groupId>io.vidocq.mpserver</groupId>
    <artifactId>vidocq-mps-<nom-court>-extension</artifactId>
    <version>${project.version}</version>
</dependency>
```

> ⚠️ **Anti-pattern repéré sur la PR `add-cyrano`** : seul
> `vidocq-mps-cyrano-extension` est dans le dependencyManagement, les artefacts
> cyrano-api/core/cdi-vauban sont consommés directement via `${cyrano.version}`
> dans le pom de l'extension. Ça marche, mais c'est incohérent avec le pattern
> Vauban (qui liste *tous* ses artefacts). Pour rester homogène, ajouter
> systématiquement chaque artefact upstream dans le dependencyManagement.

### 3.3 Création du module wrapper `vidocq-mps-<nom-court>-extension`

Sous `vidocq-mps-core-extensions/vidocq-mps-<nom-court>-extension/`, un POM
Model 4.1.0 :

```xml
<project xmlns="http://maven.apache.org/POM/4.1.0" …>
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>io.vidocq.mpserver</groupId>
        <artifactId>vidocq-mps-core-extensions</artifactId>
    </parent>
    <artifactId>vidocq-mps-<nom-court>-extension</artifactId>
    <name>Vidocq :: Core Extensions :: <Description>></name>
    <description>Wrapper Maven/JPMS qui active <Nom-Court> dans un déploiement vidocq-mps.</description>

    <dependencies>
        <dependency>
            <groupId>io.vidocq.<nom-court></groupId>
            <artifactId><nom-court>-api</artifactId>
        </dependency>
        <!-- core, cdi-vauban, etc. : versions gérées par <dependencyManagement> du parent -->
    </dependencies>
</project>
```

Ajouter au moins une classe wrapper + un `module-info.java` qui ré-exporte
ou déclare `provides ServiceLoader …` selon la SPI vidocq-mps.

### 3.4 Enregistrement dans `vidocq-mps-core-extensions/pom.xml`

```xml
<subprojects>
    …
    <subproject>vidocq-mps-<nom-court>-extension</subproject>
    …
</subprojects>
```

---

## 4. Workflows Forgejo CI/CD

C'est l'étape **la plus importante côté nouveau producteur** — sans elle, son
artefact `0.1.0-SNAPSHOT` n'existe pas dans `repo.vidocq.dev/snapshots` et
**toutes les PR consommatrices vont planter** avec
`Could not resolve dependencies for io.vidocq.<nom-court>:…`.

> 💡 C'est précisément la cause du fail de la PR `add-cyrano` dans
> `vidocq/vidocq-mps` en mai 2026 : `cyrano/.forgejo/workflows/` n'existe pas
> encore au moment où on ouvre la PR consommatrice. Bootstrap les workflows
> producteur AVANT d'ouvrir la PR vidocq-mps.

### 4.1 `.forgejo/workflows/ci.yml`

Build + deploy snapshots sur push `main`. S'inspirer d'un repo existant
(cassini/vauban). Doit utiliser :
- `setup-java@v4` (Java 25 Temurin)
- Téléchargement manuel de Maven 4.0.0-rc-5 (pas d'image officielle)
- Authentification snapshots via secret organisation `MAVEN_DEPLOY_TOKEN`
- `mvn -B -ntp deploy` à la fin

### 4.2 `.forgejo/workflows/pr.yml`

Fusion des 4 jobs du template
[`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml) :
`build-pr`, `discover-impact`, `trigger-downstream`, `verify-downstream`.

- Publie en **pr-staging** (`https://repo.vidocq.dev/pr-staging`) avec une
  version dérivée `<base>-PR<num>.<run>-SNAPSHOT`.
- Découvre via GestionProjet quels repos consommateurs doivent être
  revalidés.
- Dispatch des `workflow_dispatch` vers leur `upstream-pr.yml`.

### 4.3 `.forgejo/workflows/update-dep-graph.yml`

Copier tel quel
[`workflow-templates/update-dep-graph.yml`](workflow-templates/update-dep-graph.yml).
Doit avoir accès au secret `VIDOCQ_BOT_TOKEN`. Lancer une fois manuellement en
`workflow_dispatch` pour amorcer `data/vidocq_<nom-court>.json` dans
GestionProjet.

### 4.4 `.forgejo/workflows/upstream-pr.yml` (si consommateur)

Si le nouveau projet **consomme** d'autres modules Vidocq (Vauban, Chappe…),
copier
[`workflow-templates/upstream-pr-consumer.yml`](workflow-templates/upstream-pr-consumer.yml)
dans `.forgejo/workflows/upstream-pr.yml`. Pré-requis : chaque dép amont est
référencée via une property `<nom-amont>.version` dans le pom.

---

## 5. TCK officiel (si applicable)

Si la spec implémentée a un TCK officiel (Jakarta, MicroProfile) :

- **Module `<nom>-tck` HORS reactor** : Model 4.0.0 standalone, pas de
  `<parent>`. Raison : ShrinkWrap Maven Resolver 3.3 (transitive du TCK
  officiel) ne sait pas parser Model 4.1.0.
- **Script `run-official-tck-<spec>.sh`** à la racine du repo, qui :
  1. installe les artefacts non publics dans le M2 local
  2. lance `mvn -f <nom>-tck/pom.xml test [-Dtest=…]`
- **Ne PAS** ajouter le module tck au `<subprojects>` du parent.
- **Ne PAS** le builder via `mvn -pl`.

---

## 6. Enregistrement dans `GestionProjet`

### 6.1 Amorçage du fichier `data/vidocq_<nom-court>.json`

Sur la machine locale (ou via le workflow `update-dep-graph.yml` une fois
configuré) :

```bash
cd /chemin/vers/GestionProjet
bash scripts/extract_deps.sh /chemin/vers/<nom-court> "vidocq/<nom-court>" \
  > data/vidocq_<nom-court>.json
make validate     # vérifie conformité au schéma
make graph        # rebuild graph/inverted.json
git add data/vidocq_<nom-court>.json graph/inverted.json
git commit -m "feat(graph): register vidocq/<nom-court>"
```

### 6.2 Validation du schéma

Le fichier doit valider contre `data/schema.json` :
- `schema_version: 1`
- `repo` matche `^vidocq/<nom>$`
- chaque artefact dans `produces[]` a un `groupId` matchant
  `^io\.vidocq(\.[A-Za-z0-9_-]+)*$`
- `consumes[].scope` est dans
  `[compile, runtime, provided, test, system, import, build]`

---

## 7. Convention sur les commits

- **Pas de `Co-Authored-By: Claude`** ni de mention de l'IA (règle workspace).
- Format conventional commits : `feat(<scope>): …`, `fix(<scope>): …`,
  `ci(<scope>): …`, `M<jalon> — …` pour les jalons roadmap.

---

## 8. Checklist d'intégration (TL;DR)

À cocher avant d'ouvrir la PR consommatrice dans `vidocq/vidocq-mps` :

### Côté nouveau repo producteur
- [ ] `pom.xml` root Model 4.1.0, `root="true"`, groupId `io.vidocq.<nom>`
- [ ] `.sdkmanrc`, `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`
- [ ] `BUG.md` et `BENCH.md` (au moins en stub)
- [ ] `.claude/agents/` et `.claude/skills/` peuplés avec ce qui sert
- [ ] `<nom>-tck/` en Model 4.0.0 standalone (si TCK) + script `run-official-tck-*.sh`
- [ ] `.forgejo/workflows/ci.yml` qui deploy snapshots
- [ ] `.forgejo/workflows/pr.yml` (4 jobs du template producteur)
- [ ] `.forgejo/workflows/update-dep-graph.yml` activé une fois
- [ ] `.forgejo/workflows/upstream-pr.yml` (si consommateur amont)
- [ ] **`0.1.0-SNAPSHOT` publié dans `repo.vidocq.dev/snapshots`** (sinon les
      PR aval planteront)

### Côté `vidocq/vidocq-mps`
- [ ] Property `<<nom>.version>` ajoutée au parent POM
- [ ] Artefacts upstream listés dans `<dependencyManagement>` du parent
- [ ] Wrapper `vidocq-mps-<nom>-extension` créé sous `vidocq-mps-core-extensions/`
- [ ] Wrapper listé dans `<subprojects>` de `vidocq-mps-core-extensions/pom.xml`
- [ ] Wrapper référencé dans `<dependencyManagement>` du parent
- [ ] Test de non-régression `M5` (ServiceLoader + JPMS provides)

### Côté `GestionProjet`
- [ ] `data/vidocq_<nom>.json` validé et commité
- [ ] `graph/inverted.json` régénéré
- [ ] Secret organisation `VIDOCQ_BOT_TOKEN` accessible au nouveau repo

---

## 9. Mémo agents/skills associés

À utiliser proactivement pendant l'intégration :

- `jpms-guardian` : audit du `module-info.java` de chaque module nouveau
- `classfile-codegen` : revue de la génération de bytecode (proxies, indexers)
- `virtual-threads-reviewer` : revue de la concurrence (pas de pool plateforme
  sans raison)
- `dependency-gatekeeper` : revue du `pom.xml` (zéro-dep / specs Jakarta+MP only)
- `tck-runner` : exécution TCK + diagnostic (Model 4.0.0 standalone)
- skill `/log-bug` : ajoute une entrée à `<repo>/BUG.md`
- skill `/log-bench` : ajoute une entrée à `<repo>/BENCH.md`

---

## 10. Références

- Workspace : `vidocq/CLAUDE.md` (philosophie transverse, conventions BUG/BENCH)
- Graphe : `GestionProjet/README.md` (mécanisme producteur/consommateur,
  schéma data/, workflow templates)
- Schéma data : `GestionProjet/data/schema.json`
- Templates : `GestionProjet/workflow-templates/*.yml`
