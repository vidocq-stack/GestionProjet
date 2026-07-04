# HOWTO — Ajouter un nouveau projet à l'écosystème Vidocq

Ce guide décrit la procédure complète pour intégrer un **nouveau sous-projet
producteur** dans l'écosystème Vidocq (ex. : `cyrano`, `knock`, futurs). Il
couvre les conventions de structure du repo, les fichiers méta obligatoires
(dont les fichiers Claude / agents / skills), la wiring Maven côté
`vidocq/vidocq`, et l'enregistrement dans le graphe `GestionProjet`.

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
  — sans quoi `ci/build-impacted` ne peut pas réécrire la version PR de la dép
  amont (`versions:set-property <nom-court>.version=<PR>`) lors d'une PR amont.
- **Version initiale** : `0.2.0` par défaut (Mansart est l'exception
  historique à `1.0.0-SNAPSHOT`).
- **Java / Maven** : Java 25 Temurin + Maven 3.9.16, pinés via `.sdkmanrc`.

---

## 1. Structure du repo producteur

Arborescence minimale attendue (s'inspirer de `vauban/`, `chappe/`, `cyrano/`) :

```
<nom-court>/
├── .sdkmanrc                  ← java=25-tem, maven=3.9.16
├── .gitignore                 ← target/, *.iml, .idea/, etc.
├── LICENSE                    ← EPL-2.0 OR EUPL-1.2 OR GPL-2.0-or-later (cohérence écosystème)
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
    ├── pr.yml                 ← validation PR en 1 job (build local + ci/build-impacted)
    └── update-dep-graph.yml   ← maintenance GestionProjet
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
    <version>0.2.0</version>
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
maven=3.9.16
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

## 3. Wiring côté `vidocq/vidocq`

L'orchestrateur `vidocq` consomme le sous-projet via un wrapper
d'extension. Quatre points à modifier dans `vidocq/vidocq/` :

### 3.1 Property dans le parent POM (`vidocq/pom.xml`)

```xml
<properties>
    …
    <<nom-court>.version>0.2.0</<nom-court>.version>
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
    <groupId>io.vidocq.runtime</groupId>
    <artifactId>vidocq-runtime-<nom-court>-extension</artifactId>
    <version>${project.version}</version>
</dependency>
```

> ⚠️ **Anti-pattern repéré sur la PR `add-cyrano`** : seul
> `vidocq-runtime-cyrano-rest-client-extension` est dans le dependencyManagement, les artefacts
> cyrano-api/core/cdi-vauban sont consommés directement via `${cyrano.version}`
> dans le pom de l'extension. Ça marche, mais c'est incohérent avec le pattern
> Vauban (qui liste *tous* ses artefacts). Pour rester homogène, ajouter
> systématiquement chaque artefact upstream dans le dependencyManagement.

### 3.3 Création du module wrapper `vidocq-runtime-<nom-court>-extension`

Sous `vidocq-runtime-extensions/vidocq-runtime-<nom-court>-extension/`, un POM
Model 4.1.0 :

```xml
<project xmlns="http://maven.apache.org/POM/4.1.0" …>
    <modelVersion>4.1.0</modelVersion>
    <parent>
        <groupId>io.vidocq.runtime</groupId>
        <artifactId>vidocq-runtime-extensions</artifactId>
    </parent>
    <artifactId>vidocq-runtime-<nom-court>-extension</artifactId>
    <name>Vidocq :: Core Extensions :: <Description>></name>
    <description>Wrapper Maven/JPMS qui active <Nom-Court> dans un déploiement vidocq.</description>

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
ou déclare `provides ServiceLoader …` selon la SPI vidocq.

### 3.4 Enregistrement dans `vidocq-runtime-extensions/pom.xml`

```xml
<subprojects>
    …
    <subproject>vidocq-runtime-<nom-court>-extension</subproject>
    …
</subprojects>
```

---

## 4. Workflows Forgejo CI/CD

C'est l'étape **la plus importante côté nouveau producteur** — sans elle, son
artefact `0.2.0` n'est pas publié sur `central-snapshots` et **toutes
les PR consommatrices vont planter** avec
`Could not resolve dependencies for io.vidocq.<nom-court>:…` (le job PR d'un
consommateur résout ses dépendances amont non modifiées depuis `central-snapshots`).

> 💡 C'est précisément la cause du fail de la PR `add-cyrano` dans
> `vidocq/vidocq` en mai 2026 : `cyrano/.forgejo/workflows/` n'existe pas
> encore au moment où on ouvre la PR consommatrice. Bootstrap les workflows
> producteur AVANT d'ouvrir la PR vidocq.

### 4.1 `.forgejo/workflows/ci.yml`

Build + TCK + deploy sur push `main`. S'inspirer d'un repo existant
(cassini/vauban) — tout passe par les composite actions du repo `Vidocq/ci` :
- `Vidocq/ci/setup-maven@v1` — Java 25 Temurin + Maven 3.9.16 + `settings.xml`
  (résolution des SNAPSHOT depuis `central-snapshots`)
- `Vidocq/ci/run-tck@v1` — TCK officiel (si applicable)
- `Vidocq/ci/deploy-maven@v1` — publie sur Maven Central (SNAPSHOT via
  `maven-deploy-plugin` → `central-snapshots` ; RELEASE via `central-publishing`).
  Secrets : `CENTRAL_USERNAME`, `CENTRAL_PASSWORD`, `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE`.
- `Vidocq/ci/notify-slack@v1` — notification

### 4.2 `.forgejo/workflows/pr.yml`

Copier tel quel le template
[`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml) : un
**seul** job `pr-validate`.

- Build le producteur en version PR release-style `<base>-PR<num>.<sha8>` (sans
  `-SNAPSHOT`) puis `mvn install` dans le `~/.m2` du runner — **rien n'est publié**.
- L'action `Vidocq/ci/build-impacted@v1` découvre via GestionProjet les
  consommateurs impactés (fermeture transitive, **ordre topologique**) et les
  reclone/rebuild un à un contre les artefacts PR locaux.
- Le succès de ce job unique est l'**unique required check** de la branch protection.

### 4.3 `.forgejo/workflows/update-dep-graph.yml`

Copier tel quel
[`workflow-templates/update-dep-graph.yml`](workflow-templates/update-dep-graph.yml).
Doit avoir accès au secret `VIDOCQ_BOT_TOKEN`. Lancer une fois manuellement en
`workflow_dispatch` pour amorcer `data/vidocq_<nom-court>.json` dans
GestionProjet.

### 4.4 Aucun workflow consommateur dédié

Le mécanisme `upstream-pr.yml` + dispatch est **supprimé** : `ci/build-impacted`
reclone et rebuild les consommateurs directement dans le job du producteur. Un
repo consommateur n'a donc **rien** à configurer côté réception — il suffit qu'il
expose ses dépendances amont via des properties `<nom-amont>.version` (cf. §0).

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

À cocher avant d'ouvrir la PR consommatrice dans `vidocq/vidocq` :

### Côté nouveau repo producteur
- [ ] `pom.xml` root Model 4.1.0, `root="true"`, groupId `io.vidocq.<nom>`
- [ ] `.sdkmanrc`, `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`
- [ ] `BUG.md` et `BENCH.md` (au moins en stub)
- [ ] `.claude/agents/` et `.claude/skills/` peuplés avec ce qui sert
- [ ] `<nom>-tck/` en Model 4.0.0 standalone (si TCK) + script `run-official-tck-*.sh`
- [ ] `.forgejo/workflows/ci.yml` (setup-maven + deploy-maven sur push main)
- [ ] `.forgejo/workflows/pr.yml` (job unique `pr-validate` du template producteur)
- [ ] `.forgejo/workflows/update-dep-graph.yml` activé une fois
- [ ] **`0.2.0` publié sur `central-snapshots`** (sinon les PR aval
      planteront à la résolution des dépendances amont)

### Côté `vidocq/vidocq`
- [ ] Property `<<nom>.version>` ajoutée au parent POM
- [ ] Artefacts upstream listés dans `<dependencyManagement>` du parent
- [ ] Wrapper `vidocq-runtime-<nom>-extension` créé sous `vidocq-runtime-extensions/`
- [ ] Wrapper listé dans `<subprojects>` de `vidocq-runtime-extensions/pom.xml`
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
