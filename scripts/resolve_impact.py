#!/usr/bin/env python3
"""Calcule la fermeture transitive des consommateurs impactés par un set d'artefacts changés.

Usage :
  resolve_impact.py --graph graph/inverted.json --changed g:a [g:a ...] [--depth N|all]
                    [--format json|matrix]

Algo : BFS sur le graphe inversé. Niveau 1 = consommateurs directs. Pour chaque consommateur
on regarde les artefacts qu'il *produit* lui-même, et on enchaîne sur leurs consommateurs.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--graph", required=True, help="Chemin vers graph/inverted.json")
    p.add_argument(
        "--changed",
        nargs="+",
        required=True,
        help="Artefacts modifiés au format groupId:artifactId",
    )
    p.add_argument(
        "--depth",
        default="all",
        help="Profondeur maximale (entier) ou 'all' pour fermeture complète",
    )
    p.add_argument(
        "--format",
        choices=["json", "matrix"],
        default="json",
        help="Format de sortie : json (par défaut) ou matrix (Forgejo Actions)",
    )
    return p.parse_args()


def load_graph(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def repo_to_artifacts(graph: dict) -> dict[str, list[str]]:
    """Inverse partiel : repo producteur -> [g:a, ...]."""
    out: dict[str, list[str]] = {}
    for key, entry in graph.get("artifacts", {}).items():
        prod = entry.get("produced_by")
        if prod:
            out.setdefault(prod, []).append(key)
    return out


def resolve_impact(graph: dict, changed: list[str], max_depth: int | None) -> list[str]:
    """Retourne la liste triée des repos consommateurs impactés.

    `max_depth=None` = pas de limite (fermeture complète).
    Profondeur 1 = consommateurs directs des artefacts changés.
    """
    artifacts_index = graph.get("artifacts", {})
    by_repo = repo_to_artifacts(graph)

    impacted: set[str] = set()
    # File : (artefact_g_a, depth)
    queue: deque[tuple[str, int]] = deque()
    seen_artifacts: set[str] = set()

    for art in changed:
        if art in artifacts_index:
            queue.append((art, 0))
            seen_artifacts.add(art)
        else:
            print(
                f"resolve_impact: artefact inconnu dans le graphe : {art}",
                file=sys.stderr,
            )

    while queue:
        art, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        consumers = artifacts_index.get(art, {}).get("consumed_by", [])
        for c in consumers:
            repo = c["repo"]
            if repo in impacted:
                continue
            impacted.add(repo)
            # Niveau suivant : on enchaîne sur les artefacts produits par ce repo.
            for a2 in by_repo.get(repo, []):
                if a2 not in seen_artifacts:
                    seen_artifacts.add(a2)
                    queue.append((a2, depth + 1))

    return sorted(impacted)


def main() -> int:
    args = parse_args()
    graph_path = Path(args.graph)
    if not graph_path.is_file():
        print(f"resolve_impact: graphe introuvable : {graph_path}", file=sys.stderr)
        return 1
    graph = load_graph(graph_path)

    if args.depth == "all":
        max_depth: int | None = None
    else:
        try:
            max_depth = int(args.depth)
            if max_depth < 0:
                raise ValueError
        except ValueError:
            print(
                f"resolve_impact: --depth doit être un entier >=0 ou 'all', reçu : {args.depth}",
                file=sys.stderr,
            )
            return 2

    impacted = resolve_impact(graph, args.changed, max_depth)

    if args.format == "matrix":
        out = {"include": [{"repo": r} for r in impacted]}
    else:
        out = {"impacted": [{"repo": r} for r in impacted]}

    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
