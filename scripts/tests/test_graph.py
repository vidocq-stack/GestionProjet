"""Tests unitaires pour build_inverted_graph et resolve_impact."""
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

# Ajoute le répertoire parent (scripts/) au path pour importer les modules.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build_inverted_graph as builder  # noqa: E402
import resolve_impact as resolver  # noqa: E402


def make_payload(repo, produces=None, consumes=None):
    return {
        "schema_version": 1,
        "repo": repo,
        "branch": "main",
        "commit_sha": "abc",
        "updated_at": "2026-05-10T00:00:00Z",
        "produces": produces or [],
        "consumes": consumes or [],
    }


def art(g, a, version="1.0.0-SNAPSHOT", scope="compile"):
    return {"groupId": g, "artifactId": a, "version": version, "scope": scope}


def prod(g, a, version="1.0.0-SNAPSHOT"):
    return {"groupId": g, "artifactId": a, "version": version}


class BuildGraphTests(unittest.TestCase):
    def test_empty(self):
        graph = builder.build([])
        self.assertEqual(graph["artifacts"], {})
        self.assertEqual(graph["schema_version"], 1)

    def test_simple_chain(self):
        # A -> B -> C : vidocq/a produit io.vidocq.a:core, vidocq/b consomme et produit
        # io.vidocq.b:core, vidocq/c consomme io.vidocq.b:core.
        payloads = [
            make_payload("vidocq/a", produces=[prod("io.vidocq.a", "core")]),
            make_payload(
                "vidocq/b",
                produces=[prod("io.vidocq.b", "core")],
                consumes=[art("io.vidocq.a", "core")],
            ),
            make_payload("vidocq/c", consumes=[art("io.vidocq.b", "core")]),
        ]
        graph = builder.build(payloads)
        a_entry = graph["artifacts"]["io.vidocq.a:core"]
        self.assertEqual(a_entry["produced_by"], "vidocq/a")
        self.assertEqual(a_entry["consumed_by"], [{"repo": "vidocq/b", "scope": "compile"}])
        b_entry = graph["artifacts"]["io.vidocq.b:core"]
        self.assertEqual(b_entry["produced_by"], "vidocq/b")
        self.assertEqual(b_entry["consumed_by"], [{"repo": "vidocq/c", "scope": "compile"}])

    def test_diamond(self):
        # A -> B, A -> C, B -> D, C -> D
        payloads = [
            make_payload("vidocq/a", produces=[prod("io.vidocq.a", "core")]),
            make_payload(
                "vidocq/b",
                produces=[prod("io.vidocq.b", "core")],
                consumes=[art("io.vidocq.a", "core")],
            ),
            make_payload(
                "vidocq/c",
                produces=[prod("io.vidocq.c", "core")],
                consumes=[art("io.vidocq.a", "core")],
            ),
            make_payload(
                "vidocq/d",
                consumes=[art("io.vidocq.b", "core"), art("io.vidocq.c", "core")],
            ),
        ]
        graph = builder.build(payloads)
        impacted = resolver.resolve_impact(graph, ["io.vidocq.a:core"], max_depth=None)
        # Un changement dans A doit impacter B, C et D (transitif).
        self.assertEqual(impacted, ["vidocq/b", "vidocq/c", "vidocq/d"])

    def test_depth_limit(self):
        payloads = [
            make_payload("vidocq/a", produces=[prod("io.vidocq.a", "core")]),
            make_payload(
                "vidocq/b",
                produces=[prod("io.vidocq.b", "core")],
                consumes=[art("io.vidocq.a", "core")],
            ),
            make_payload("vidocq/c", consumes=[art("io.vidocq.b", "core")]),
        ]
        graph = builder.build(payloads)
        depth1 = resolver.resolve_impact(graph, ["io.vidocq.a:core"], max_depth=1)
        self.assertEqual(depth1, ["vidocq/b"])
        depth_all = resolver.resolve_impact(graph, ["io.vidocq.a:core"], max_depth=None)
        self.assertEqual(depth_all, ["vidocq/b", "vidocq/c"])

    def test_cycle_warning_no_crash(self):
        # B consomme A et A consomme B (cycle pathologique).
        payloads = [
            make_payload(
                "vidocq/a",
                produces=[prod("io.vidocq.a", "core")],
                consumes=[art("io.vidocq.b", "core")],
            ),
            make_payload(
                "vidocq/b",
                produces=[prod("io.vidocq.b", "core")],
                consumes=[art("io.vidocq.a", "core")],
            ),
        ]
        buf = io.StringIO()
        with redirect_stderr(buf):
            graph = builder.build(payloads)
        self.assertIn("cycle détecté", buf.getvalue())
        impacted = resolver.resolve_impact(graph, ["io.vidocq.a:core"], max_depth=None)
        self.assertEqual(impacted, ["vidocq/a", "vidocq/b"])

    def test_external_repo_filtered(self):
        # Un repo hors `vidocq/*` doit être ignoré par load_data_files.
        # On simule en appelant directement build (qui ne filtre pas) — la whitelist
        # est dans load_data_files.
        # Test fonctionnel : load_data_files sur un dossier avec un mauvais repo.
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            (data_dir / "vidocq_a.json").write_text(
                json.dumps(make_payload("vidocq/a", produces=[prod("io.vidocq.a", "core")]))
            )
            (data_dir / "external_b.json").write_text(
                json.dumps(make_payload("external/b", consumes=[art("io.vidocq.a", "core")]))
            )
            buf = io.StringIO()
            with redirect_stderr(buf):
                payloads = builder.load_data_files(data_dir)
            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0]["repo"], "vidocq/a")
            self.assertIn("hors whitelist", buf.getvalue())


class ResolveImpactCliTests(unittest.TestCase):
    def test_matrix_format(self):
        graph = builder.build(
            [
                make_payload("vidocq/a", produces=[prod("io.vidocq.a", "core")]),
                make_payload("vidocq/b", consumes=[art("io.vidocq.a", "core")]),
            ]
        )
        impacted = resolver.resolve_impact(graph, ["io.vidocq.a:core"], None)
        matrix = {"include": [{"repo": r} for r in impacted]}
        self.assertEqual(matrix, {"include": [{"repo": "vidocq/b"}]})


if __name__ == "__main__":
    unittest.main()
