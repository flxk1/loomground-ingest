"""Independent, bare release gate for loomground-ingest."""
from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys
import tomllib

from loomground_ingest import (
    CollectingWriter,
    DeonticIngester,
    IngesterRegistry,
    Subgraph,
    VERSUM_RECEIPT_CONTRACT,
    ingest_text,
    versum_writer,
)

ALLOWED_FACETS = {"5D", "nD"}
ALLOWED_EDGE_DIMENSIONS = {
    "structural", "causal", "intentional", "temporal", "relational",
}


def validate_subgraph(graph: Subgraph) -> list[str]:
    """Independent release authority over the neutral Subgraph contract."""
    errors: list[str] = []
    if graph.dimension not in ALLOWED_FACETS:
        errors.append("invalid facet")
    if not isinstance(graph.provenance, dict) or not graph.provenance:
        errors.append("missing provenance")
    raw_node_ids = [
        node.get("id") if isinstance(node, dict) else None
        for node in graph.nodes
    ]
    node_ids = set(raw_node_ids)
    if None in node_ids:
        errors.append("node missing id")
    if len(node_ids) != len(graph.nodes):
        errors.append("duplicate node id")
    for edge in graph.edges:
        if not isinstance(edge, dict):
            errors.append("malformed edge")
            continue
        if edge.get("dimension") not in ALLOWED_EDGE_DIMENSIONS:
            errors.append("invalid edge dimension")
        if edge.get("norm") not in node_ids:
            errors.append("dangling norm edge")
    if graph.quarantined:
        if graph.nodes or graph.edges:
            errors.append("quarantine contains semantic content")
        if graph.rejections:
            errors.append("quarantine contains unit rejections")
    elif graph.rejections and not graph.nodes:
        errors.append("partial without accepted content")
    for rejection in graph.rejections:
        if not isinstance(rejection, dict) or not all(
            rejection.get(key) not in (None, "")
            for key in ("sentence_index", "text", "reason")
        ):
            errors.append("malformed rejection")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bare", action="store_true",
        help="run gate assertions without recursively invoking pytest",
    )
    args = parser.parse_args()
    assertions = 0
    root = Path(__file__).resolve().parents[1]

    supply_chain_teeth = subprocess.run(
        [sys.executable, "tools/supply_chain_gate.py", "--self-test"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert supply_chain_teeth.returncode == 0, (
        supply_chain_teeth.stdout + supply_chain_teeth.stderr)
    assertions += 1
    supply_chain = subprocess.run(
        [sys.executable, "tools/supply_chain_gate.py"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert supply_chain.returncode == 0, supply_chain.stdout + supply_chain.stderr
    assertions += 1

    if not args.bare:
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        assert tests.returncode == 0, tests.stdout + tests.stderr
        assertions += 1

    diff_check = subprocess.run(
        ["git", "diff", "--check"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert diff_check.returncode == 0, diff_check.stdout + diff_check.stderr
    assertions += 1

    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    dependencies = metadata["project"]["dependencies"]
    assert any(dep.startswith("loomground-deontic") for dep in dependencies)
    assertions += 1

    forbidden = {
        ".venv", ".venv-meta", "__pycache__", ".pytest_cache",
        "build", "dist",
    }
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert not [
        path for path in tracked
        if forbidden.intersection(Path(path).parts)
        or path.endswith((".pyc", ".pyo"))
    ]
    assertions += 1

    registry = IngesterRegistry()
    registry.register(DeonticIngester())
    writer = CollectingWriter()
    result = ingest_text(
        "If risk is high, Controller must notify unless law forbids it. "
        "Processor may disclose. The recipient must.",
        registry=registry,
        writer=writer,
        ctx={"source_id": "release-vector"},
    )
    assert result["status"] == "partial"
    assertions += 1
    assert result["write"]["written"] is True and len(writer.written) == 1
    assertions += 1

    graph = writer.written[0]
    assert validate_subgraph(graph) == []
    assertions += 1
    assert len(graph.nodes) == len(graph.edges) == 2
    assertions += 1
    assert graph.provenance["recognised"] == (
        graph.provenance["lowered"] + graph.provenance["rejected"]
    )
    assertions += 1
    assert graph.nodes[0]["condition"] == "risk is high"
    assertions += 1
    assert graph.nodes[0]["exception"] == "law forbids it"
    assertions += 1
    assert graph.rejections == [{
        "sentence_index": 3,
        "text": "The recipient must",
        "reason": "missing_required_slot",
    }]
    assertions += 1

    again = DeonticIngester().ingest(
        "Controller must notify.", {"source_id": "same-source"})
    same = DeonticIngester().ingest(
        "Controller must notify.", {"source_id": "same-source"})
    other = DeonticIngester().ingest(
        "Controller must notify.", {"source_id": "other-source"})
    assert again.nodes[0]["id"] == same.nodes[0]["id"]
    assertions += 1
    assert again.nodes[0]["id"] != other.nodes[0]["id"]
    assertions += 1
    assert again == same
    assertions += 1

    # Teeth: the independent authority rejects corrupted artifacts.
    dangling = Subgraph(
        dimension="nD",
        nodes=[{"id": "norm:1"}],
        edges=[{"norm": "missing", "dimension": "causal"}],
        provenance={"source": "release-vector"},
    )
    assert "dangling norm edge" in validate_subgraph(dangling)
    assertions += 1
    corrupt_dimension = Subgraph(
        dimension="nD",
        nodes=[{"id": "norm:1"}],
        edges=[{"norm": "norm:1", "dimension": "sixth"}],
        provenance={"source": "release-vector"},
    )
    assert "invalid edge dimension" in validate_subgraph(corrupt_dimension)
    assertions += 1
    assert "missing provenance" in validate_subgraph(Subgraph(dimension="nD"))
    assertions += 1
    malformed_rejection = Subgraph(
        dimension="nD", nodes=[{"id": "norm:1"}],
        rejections=[{"sentence_index": 1, "text": ""}],
        provenance={"source": "release-vector"},
    )
    assert "malformed rejection" in validate_subgraph(malformed_rejection)
    assertions += 1
    duplicate_nodes = Subgraph(
        dimension="nD", nodes=[{"id": "norm:1"}, {"id": "norm:1"}],
        provenance={"source": "release-vector"},
    )
    assert "duplicate node id" in validate_subgraph(duplicate_nodes)
    assertions += 1
    malformed_edge = Subgraph(
        dimension="nD", nodes=[{"id": "norm:1"}], edges=[None],
        provenance={"source": "release-vector"},
    )
    assert "malformed edge" in validate_subgraph(malformed_edge)
    assertions += 1

    quarantined_writer = CollectingWriter()
    refused = quarantined_writer.write(
        Subgraph(dimension="nD", quarantined=True,
                 provenance={"source": "release-vector"}))
    assert refused["written"] is False and quarantined_writer.written == []
    assertions += 1

    quarantined_registry = IngesterRegistry()

    class _QuarantiningIngester:
        id = "release-quarantine"

        def grammar(self):
            return None

        def ingest(self, text, ctx):
            return Subgraph(
                dimension="nD", quarantined=True,
                provenance={"ingester": self.id},
            )

    quarantined_registry.register(_QuarantiningIngester())
    class _SpyWriter:
        calls = 0

        def write(self, graph):
            self.calls += 1
            raise AssertionError("pipeline called writer for quarantine")

    spy_writer = _SpyWriter()
    pipeline_refusal = ingest_text(
        "ambiguous document",
        registry=quarantined_registry,
        writer=spy_writer,
    )
    assert pipeline_refusal["ok"] is False
    assertions += 1
    assert pipeline_refusal["processed"] is True
    assertions += 1
    assert spy_writer.calls == 0
    assertions += 1

    class _VersumSink:
        def __init__(self):
            self.calls = []

        def upsert(self, envelope):
            self.calls.append(envelope)
            return {
                "schema": VERSUM_RECEIPT_CONTRACT,
                "idempotency_key": envelope["idempotency_key"],
                "content_digest": "sha256:" + ("b" * 64),
                "transaction_id": "subgraph:release-proof",
                "status": "inserted",
            }

    sink = _VersumSink()
    digest = "sha256:" + ("a" * 64)
    persistent_writer = versum_writer(
        sink,
        idempotency_key="release-proof-001",
        source={"source_id": "source:release-proof", "content_digest": digest},
        evidence=[{
            "evidence_id": "evidence:release-proof",
            "source_id": "source:release-proof",
            "locator": "release:proof",
            "content_digest": digest,
        }],
        nd={
            "facet": "5D",
            "system_id": "system:federation-5d",
            "dimension_count": 1,
            "axes": ["relational"],
        },
    )
    versum_graph = Subgraph(
        dimension="5D",
        nodes=[
            {"id": "node:a", "kind": "claim",
             "dimensions": {"relational": "subject"}},
            {"id": "node:b", "kind": "concept",
             "dimensions": {"relational": "object"}},
        ],
        edges=[{
            "id": "relation:1", "predicate": "supports",
            "source": "node:a", "target": "node:b",
            "dimension": "relational",
            "evidence_ids": ["evidence:release-proof"],
        }],
        provenance={"source": "release-proof"},
    )
    receipt = persistent_writer.write(versum_graph)
    assert receipt["written"] is True and receipt["status"] == "inserted"
    assertions += 1
    assert len(sink.calls) == 1
    assertions += 1
    assert sink.calls[0]["schema"].endswith("dimensioned-subgraph/v1")
    assertions += 1

    print(f"RELEASE GATE PASS ({assertions} assertions)")


if __name__ == "__main__":
    main()
