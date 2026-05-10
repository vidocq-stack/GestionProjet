# `graph/` — graphe de dépendances inversé

Ce dossier contient le résultat agrégé du graphe de dépendances Vidocq.

## `inverted.json`

Reconstruit automatiquement à chaque push touchant `data/**` (workflow
`.forgejo/workflows/build-graph.yml`). Ne pas éditer à la main.

Format :

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-10T12:35:00Z",
  "artifacts": {
    "io.vidocq.vauban:vauban-core": {
      "produced_by": "vidocq/vauban",
      "consumed_by": [
        {"repo": "vidocq/cassini",  "scope": "compile"},
        {"repo": "vidocq/foy",      "scope": "compile"},
        {"repo": "vidocq/mansart",  "scope": "test"}
      ]
    }
  }
}
```

- Clé : `groupId:artifactId` (sans version).
- `produced_by` : repo Forgejo qui publie l'artefact.
- `consumed_by` : liste des repos consommateurs avec le `scope` Maven (`compile`,
  `runtime`, `provided`, `test`, `import`, `build` pour les plugins).
- Les listes sont triées par `(repo, scope)` pour produire des diffs stables.

## Règles

- Whitelist : seuls les fichiers `data/<repo>.json` dont le champ `repo` commence
  par `vidocq/` sont indexés (cf. `scripts/build_inverted_graph.py`).
- Si un même artefact est déclaré comme produit par deux repos, le premier rencontré
  gagne et un avertissement est imprimé sur stderr du builder (cas pathologique).
- Les cycles repo→repo sont détectés et signalés sur stderr, sans faire échouer
  la construction.

## Comment l'utiliser

Côté producteur, pour découvrir les consommateurs impactés par une PR :

```bash
python3 scripts/resolve_impact.py \
  --graph graph/inverted.json \
  --changed io.vidocq.vauban:vauban-core io.vidocq.vauban:vauban-api \
  --format matrix
```

Sortie :

```json
{"include": [{"repo": "vidocq/cassini"}, {"repo": "vidocq/foy"}, {"repo": "vidocq/mansart"}, {"repo": "vidocq/vidocq"}]}
```

Cette matrice se branche directement sur un job `strategy.matrix` Forgejo Actions
pour déclencher le build des consommateurs (cf. `workflow-templates/trigger-downstream.yml`).
