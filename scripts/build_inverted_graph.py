#!/usr/bin/env python3
"""Reconstruit graph/inverted.json à partir des fichiers data/*.json.

Stdlib uniquement. Whitelist : seuls les repos `vidocq/*` sont acceptés.
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_OWNER_PREFIX = "vidocq/"
SCHEMA_VERSION = 1


def load_data_files(data_dir: Path) -> list[dict]:
    out: list[dict] = []
    for fp in sorted(glob.glob(str(data_dir / "*.json"))):
        path = Path(fp)
        if path.name == "schema.json":
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"build_inverted_graph: JSON invalide ({path.name}): {exc}", file=sys.stderr)
            continue
        repo = payload.get("repo")
        if not isinstance(repo, str) or not repo.startswith(ALLOWED_OWNER_PREFIX):
            print(
                f"build_inverted_graph: repo hors whitelist ignoré ({path.name}): {repo!r}",
                file=sys.stderr,
            )
            continue
        out.append(payload)
    return out


def build(payloads: list[dict]) -> dict:
    artifacts: dict[str, dict] = {}

    # Pass 1 : producteurs.
    for p in payloads:
        repo = p["repo"]
        for prod in p.get("produces", []):
            key = f"{prod['groupId']}:{prod['artifactId']}"
            entry = artifacts.setdefault(
                key, {"produced_by": None, "consumed_by": []}
            )
            if entry["produced_by"] and entry["produced_by"] != repo:
                print(
                    f"build_inverted_graph: artefact {key} déclaré par "
                    f"{entry['produced_by']} ET {repo} — conserve le premier",
                    file=sys.stderr,
                )
                continue
            entry["produced_by"] = repo

    # Pass 2 : consommateurs.
    for p in payloads:
        repo = p["repo"]
        for cons in p.get("consumes", []):
            key = f"{cons['groupId']}:{cons['artifactId']}"
            entry = artifacts.setdefault(
                key, {"produced_by": None, "consumed_by": []}
            )
            scope = cons.get("scope", "compile")
            entry["consumed_by"].append({"repo": repo, "scope": scope})

    # Tri stable des consumed_by + déduplication par (repo, scope).
    for entry in artifacts.values():
        seen = set()
        deduped = []
        for c in entry["consumed_by"]:
            t = (c["repo"], c["scope"])
            if t in seen:
                continue
            seen.add(t)
            deduped.append(c)
        deduped.sort(key=lambda c: (c["repo"], c["scope"]))
        entry["consumed_by"] = deduped

    # Avertissement de cycle (sans crash).
    detect_cycles(artifacts)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": artifacts,
    }


def detect_cycles(artifacts: dict[str, dict]) -> None:
    """Construit un graphe repo->repos consommateurs et détecte les cycles."""
    repo_consumers: dict[str, set[str]] = {}
    for key, entry in artifacts.items():
        producer = entry.get("produced_by")
        if not producer:
            continue
        for c in entry["consumed_by"]:
            repo_consumers.setdefault(producer, set()).add(c["repo"])

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {r: WHITE for r in repo_consumers}
    for r in list(repo_consumers):
        for c in repo_consumers[r]:
            color.setdefault(c, WHITE)

    def visit(node: str, path: list[str]) -> None:
        color[node] = GRAY
        for nxt in repo_consumers.get(node, ()):
            if color.get(nxt, WHITE) == GRAY:
                cycle_path = " -> ".join(path + [nxt])
                print(
                    f"build_inverted_graph: cycle détecté : {cycle_path}",
                    file=sys.stderr,
                )
            elif color.get(nxt, WHITE) == WHITE:
                visit(nxt, path + [nxt])
        color[node] = BLACK

    for n in list(color):
        if color[n] == WHITE:
            visit(n, [n])


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    data_dir = here / "data"
    out_path = here / "graph" / "inverted.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payloads = load_data_files(data_dir)
    graph = build(payloads)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(
        f"build_inverted_graph: {len(graph['artifacts'])} artefacts indexés "
        f"depuis {len(payloads)} repos.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
