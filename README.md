# GestionProjet — graphe de dépendances Vidocq

Ce dépôt centralise le **graphe de dépendances** entre les repos Maven de la
suite Vidocq. Il sert deux objectifs :

1. **Découverte automatique** des consommateurs (directs *et transitifs*) d'un
   artefact donné, pour qu'une PR sur Vauban (par exemple) puisse revalider
   automatiquement Cassini, Foy, Mansart, Vidocq, etc.
2. **Source unique** pour le job `pr-validate` des CI Forgejo (action
   `ci/build-impacted`) — plus de liste statique en dur, plus de désynchronisation.

La validation de PR se fait dans un **seul job** : le producteur est buildé puis
`install`é en version PR (release-style, sans `-SNAPSHOT`) dans le `~/.m2` du
runner, et chaque consommateur impacté est recloné et rebuildé contre ces
artefacts locaux, en ordre topologique. Aucun registry de staging n'est requis.

## Périmètre

- Whitelist stricte : seuls les repos `vidocq/*` peuvent s'enregistrer.
- Filtre groupId : seuls les artefacts dont le `groupId` matche
  `^io\.vidocq(\..+)?$` sont indexés.
- Le périmètre peut être assoupli plus tard (organisations externes), mais pour
  l'instant on reste fermé.

## Arborescence

```
GestionProjet/
├── data/
│   ├── schema.json              JSON Schema des fichiers de données.
│   └── vidocq_<repo>.json       Une entrée par repo consommateur/producteur.
├── graph/
│   ├── inverted.json            Graphe inversé (généré, ne pas éditer à la main).
│   └── README.md                Format détaillé.
├── scripts/
│   ├── extract_deps.sh          Côté consommateur : produit le JSON `data/...`.
│   ├── update_data_file.sh      Push idempotent du JSON dans GestionProjet.
│   ├── build_inverted_graph.py  Reconstruit `graph/inverted.json`.
│   ├── resolve_impact.py        Fermeture transitive des consommateurs impactés.
│   ├── validate_data.py         Validation `data/*.json` (stdlib only).
│   └── tests/                   Tests unittest.
├── .forgejo/workflows/
│   └── build-graph.yml          Reconstruit `graph/inverted.json` sur push `data/**`.
├── workflow-templates/
│   ├── update-dep-graph.yml     À copier dans chaque repo (maintien du graphe).
│   └── pr-producer.yml          À copier dans .forgejo/workflows/pr.yml (job pr-validate).
├── Makefile                     Cibles locales (graph, impact, test, validate).
└── README.md                    Ce fichier.
```

## Format `data/<owner>_<repo>.json`

Chaque consommateur publie son inventaire dans un fichier dont le nom est
`<owner>_<repo>.json` (les `/` du slug remplacés par `_`). Format conforme à
`data/schema.json` :

```json
{
  "schema_version": 1,
  "repo": "vidocq/cassini",
  "branch": "main",
  "commit_sha": "abc123...",
  "updated_at": "2026-05-10T12:34:56Z",
  "produces": [
    {"groupId": "io.vidocq.cassini", "artifactId": "cassini-core",  "version": "0.1.0-SNAPSHOT"}
  ],
  "consumes": [
    {"groupId": "io.vidocq.vauban", "artifactId": "vauban-core",    "version": "0.1.0-SNAPSHOT", "scope": "compile"},
    {"groupId": "io.vidocq.vauban", "artifactId": "vauban-indexer", "version": "0.1.0-SNAPSHOT", "scope": "build", "type": "maven-plugin"}
  ]
}
```

## Format `graph/inverted.json`

Voir [`graph/README.md`](graph/README.md).

## Ajouter un nouveau consommateur

1. Le repo doit être hébergé sous `vidocq/*` sur la forge.
2. Copier [`workflow-templates/update-dep-graph.yml`](workflow-templates/update-dep-graph.yml)
   dans `.forgejo/workflows/update-dep-graph.yml` du repo cible.
3. Vérifier qu'il a accès au secret organisation **`VIDOCQ_BOT_TOKEN`** (write
   sur `vidocq/GestionProjet`, read sur le repo courant, dispatch sur les
   consommateurs).
4. Lancer une fois manuellement (`workflow_dispatch`) pour amorcer le fichier
   `data/<owner>_<repo>.json`.

Si le repo est *aussi* producteur, copier en plus
[`workflow-templates/pr-producer.yml`](workflow-templates/pr-producer.yml)
dans `.forgejo/workflows/pr.yml` (job unique `pr-validate` : build du producteur
puis `ci/build-impacted` qui rebuild les consommateurs en local).

## Debugger localement

Toutes les opérations passent par `make` :

```bash
make graph                                                # rebuild graph/inverted.json
make impact ARTIFACT=io.vidocq.vauban:vauban-core         # fermeture transitive
make impact ARTIFACT=io.vidocq.chappe:chappe-core DEPTH=1 # consommateurs directs uniquement
make validate                                             # vérifie tous les data/*.json
make test                                                 # tests Python
make clean                                                # supprime graph/inverted.json
```

Pour bootstrapper manuellement un repo local :

```bash
bash scripts/extract_deps.sh /chemin/vers/cassini "vidocq/cassini" > data/vidocq_cassini.json
make graph
```

## Flux complet : PR producteur → revalidation des consommateurs

Tout se déroule dans le **seul** job `pr-validate` du repo producteur. Chaque
niveau `install`é en local devient disponible pour le suivant : un consommateur
transitif (ex. `vidocq`) résout ses dépendances amont rebuildées (`cassini`,
`chappe`, …) depuis le `~/.m2` du runner, jamais depuis le réseau.

```
                                           ┌──────────────────────────┐
                                           │ Vidocq/GestionProjet     │
                                           │  graph/inverted.json     │
                                           │  scripts/resolve_impact  │
                                           └─────────┬────────────────┘
                                                     │ curl (--ordered)
                                                     ▼
┌─────────────────┐  PR ouverte  ┌──────────────────────────────────────────────┐
│ Vidocq/vauban   │─────────────▶│ vauban CI · job pr-validate (1 seul runner)    │
│ pom.xml         │              │  1. versions:set <base>-PR<n>.<sha8> (release) │
└─────────────────┘              │  2. mvn install            → ~/.m2 local       │
                                 │  3. ci/build-impacted :                        │
                                 │     resolve_impact --ordered                   │
                                 │       → [cassini, foy, …, vidocq] (topo)        │
                                 │     pour chaque consommateur, dans l'ordre :    │
                                 │       git clone (branche par défaut)            │
                                 │       versions:set-property <up>.version=<PR>   │
                                 │       versions:set <base>-PR<n>.<sha8>          │
                                 │       mvn install          → ~/.m2 local       │
                                 └──────────────────┬─────────────────────────────┘
                                                    │ tout vert ?
                                                    ▼
                              Required check `pr-validate` OK sur la PR vauban
```

## Mise à jour du graphe : flux côté consommateur

```
push dans vidocq/<repo>
        │
        ▼
.forgejo/workflows/update-dep-graph.yml
        │ extract_deps.sh PWD owner/repo  → /tmp/deps.json
        │ update_data_file.sh             → push data/<owner>_<repo>.json
        ▼
vidocq/GestionProjet (commit `[skip ci]` sur data/)
        │
        ▼ trigger : push paths data/**
.forgejo/workflows/build-graph.yml
        │ build_inverted_graph.py
        ▼
graph/inverted.json (commit `[skip ci]`)
```

Le `[skip ci]` empêche les boucles : le commit qui *met à jour* le graphe ne
re-déclenche pas le workflow. Le workflow `build-graph` filtre lui aussi pour
ignorer les commits qui ne touchent que `graph/inverted.json`.

## Secrets requis

Un seul PAT, **`VIDOCQ_BOT_TOKEN`** au niveau organisation Forgejo, avec :

- **Write** sur `vidocq/GestionProjet` (pour `update_data_file.sh` et
  `build-graph.yml`).
- **Read** sur tous les autres repos `vidocq/*` (pour récupérer scripts/graph
  via `curl` **et cloner les consommateurs** dans `ci/build-impacted`).

Le token est partagé entre tous les jobs (graph, clone) volontairement — pas de
séparation des rôles dans cette première version.
