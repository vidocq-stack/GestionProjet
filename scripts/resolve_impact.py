#!/usr/bin/env python3
"""Calcule la fermeture transitive des consommateurs impactés par un set d'artefacts changés.

Usage :
  resolve_impact.py --graph graph/inverted.json --changed g:a [g:a ...] [--depth N|all]
                    [--format json|matrix] [--verbose]

Algo : BFS sur le graphe inversé. Niveau 1 = consommateurs directs. Pour chaque consommateur
on regarde les artefacts qu'il *produit* lui-même, et on enchaîne sur leurs consommateurs.

`--verbose` active les logs DEBUG montrant l'avancement de la BFS pas à pas.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import deque
from pathlib import Path

LOG_FORMAT = "[%(levelname)s] %(message)s"
logger = logging.getLogger("resolve_impact")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


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
    p.add_argument(
        "--verbose", action="store_true",
        help="Active les logs DEBUG (BFS pas à pas).",
    )
    return p.parse_args()


def load_graph(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def repo_to_artifacts(graph: dict) -> dict[str, list[str]]:
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
    queue: deque[tuple[str, int]] = deque()
    seen_artifacts: set[str] = set()

    for art in changed:
        if art in artifacts_index:
            queue.append((art, 0))
            seen_artifacts.add(art)
            logger.debug("Seed BFS : %s @ profondeur 0", art)
        else:
            logger.warning("Artefact inconnu dans le graphe : %s", art)

    while queue:
        art, depth = queue.popleft()
        logger.debug("Visite %s @ profondeur %d", art, depth)
        if max_depth is not None and depth >= max_depth:
            logger.debug("  profondeur max atteinte (%d), skip.", max_depth)
            continue
        consumers = artifacts_index.get(art, {}).get("consumed_by", [])
        for c in consumers:
            repo = c["repo"]
            if repo in impacted:
                logger.debug("  consommateur %s déjà connu, skip.", repo)
                continue
            impacted.add(repo)
            logger.debug("  + %s ajouté aux impactés (via %s, scope=%s).",
                         repo, art, c.get("scope"))
            for a2 in by_repo.get(repo, []):
                if a2 not in seen_artifacts:
                    seen_artifacts.add(a2)
                    queue.append((a2, depth + 1))
                    logger.debug("    enqueue %s @ profondeur %d", a2, depth + 1)

    logger.debug("BFS terminée : %d repo(s) impacté(s).", len(impacted))
    return sorted(impacted)


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    graph_path = Path(args.graph)
    if not graph_path.is_file():
        logger.error("Graphe introuvable : %s", graph_path)
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
            logger.error("--depth doit être un entier >=0 ou 'all', reçu : %s", args.depth)
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
