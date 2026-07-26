# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The ingest-plane framework, standalone: dispatch, the writer seam, and the
pipeline. A fake ingester stands in for a host's real one.

Run: python -m pytest -q
"""
from __future__ import annotations

import pytest

from loomground_ingest import (
    CollectingWriter,
    DeonticIngester,
    IngesterRegistry,
    Subgraph,
    ingest_artifact,
    ingest_text,
    validate_subgraph,
    versum_writer,
)
from loomground_ingest.types import Ingester


class _KnowledgeIngester:
    """Fake 5D ingester: any text, one node per line, grammar on a prefix."""

    id = "knowledge"

    def grammar(self):
        return lambda t: t.strip().lower().startswith("claim:")

    def ingest(self, text, ctx):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return Subgraph(dimension="5D",
                        nodes=[{"id": i, "text": ln} for i, ln in enumerate(lines)],
                        provenance={"ingester": self.id})


class _FallbackIngester:
    id = "fallback"

    def grammar(self):
        return None

    def ingest(self, text, ctx):
        return Subgraph(dimension="nD", nodes=[{"id": "fallback:1", "text": text}],
                        provenance={"ingester": self.id})


class _QuarantiningIngester:
    id = "quarantine"

    def grammar(self):
        return None

    def ingest(self, text, ctx):
        return Subgraph(dimension="nD", quarantined=True,
                        provenance={"ingester": self.id})


def test_ingesters_satisfy_protocol():
    assert isinstance(_KnowledgeIngester(), Ingester)
    assert isinstance(_FallbackIngester(), Ingester)


def test_grammar_dispatch_precedes_fallback():
    reg = IngesterRegistry()
    reg.register(_KnowledgeIngester())
    reg.register(_FallbackIngester())
    assert reg.dispatch("claim: water boils").id == "knowledge"
    assert reg.dispatch("some prose").id == "fallback"


def test_second_fallback_is_refused():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())
    with pytest.raises(ValueError, match="fallback already registered"):
        reg.register(_QuarantiningIngester())


def test_pipeline_writes_dimensioned_subgraph():
    reg = IngesterRegistry()
    reg.register(_KnowledgeIngester())
    w = CollectingWriter()
    r = ingest_text("claim: a\nclaim: b", registry=reg, writer=w)
    assert r["ok"] and r["ingester"] == "knowledge" and r["dimension"] == "5D"
    assert r["nodes"] == 2 and r["write"]["written"] is True
    assert len(w.written) == 1


def test_quarantined_subgraph_is_refused_by_writer():
    reg = IngesterRegistry()
    reg.register(_QuarantiningIngester())
    w = CollectingWriter()
    r = ingest_text("anything", registry=reg, writer=w)
    assert r["ok"] is False and r["processed"] is True
    assert r["quarantined"] is True and r["write"]["written"] is False
    assert w.written == []


def test_pipeline_never_calls_writer_for_quarantined_subgraph():
    class SpyWriter:
        def __init__(self):
            self.calls = 0

        def write(self, subgraph):
            self.calls += 1
            raise AssertionError("writer must not be called")

    reg = IngesterRegistry()
    reg.register(_QuarantiningIngester())
    writer = SpyWriter()
    result = ingest_text("anything", registry=reg, writer=writer)
    assert result["reason"] == "quarantined"
    assert writer.calls == 0


@pytest.mark.parametrize(
    ("graph", "error"),
    [
        (Subgraph("6D", provenance={"source": "x"}), "invalid facet"),
        (Subgraph("nD"), "missing provenance"),
        (Subgraph("nD", nodes=[{"id": "n"}],
                  edges=[{"norm": "n", "dimension": "sixth"}],
                  provenance={"source": "x"}), "invalid edge dimension"),
        (Subgraph("nD", nodes=[{"id": "n"}],
                  edges=[{"norm": "missing", "dimension": "causal"}],
                  provenance={"source": "x"}), "dangling norm edge"),
        (Subgraph("nD", nodes=[{"id": "n"}], edges=[None],
                  provenance={"source": "x"}), "malformed edge"),
        (Subgraph("nD", nodes=[{"id": "n"}], quarantined=True,
                  provenance={"source": "x"}), "quarantine contains semantic content"),
        (Subgraph("nD", rejections=[{"sentence_index": 1, "text": "x",
                                     "reason": "bad"}],
                  provenance={"source": "x"}), "partial without accepted content"),
    ],
)
def test_product_subgraph_validation(graph, error):
    assert error in validate_subgraph(graph)


def test_pipeline_refuses_invalid_subgraph_before_writer():
    class InvalidIngester:
        id = "invalid"

        def grammar(self):
            return None

        def ingest(self, text, ctx):
            return Subgraph(dimension="6D", provenance={"source": "x"})

    class SpyWriter:
        calls = 0

        def write(self, subgraph):
            self.calls += 1
            return {"written": True}

    reg = IngesterRegistry()
    reg.register(InvalidIngester())
    writer = SpyWriter()
    result = ingest_text("x", registry=reg, writer=writer)
    assert result["reason"] == "invalid_subgraph"
    assert writer.calls == 0


def test_empty_registry_reports_no_ingester():
    r = ingest_text("x", registry=IngesterRegistry(), writer=CollectingWriter())
    assert r == {"ok": False, "reason": "no_ingester"}


def test_artifact_extraction_is_injected():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())
    r = ingest_artifact({"path": "doc.pdf"}, extract=lambda a: "extracted body",
                        registry=reg, writer=CollectingWriter())
    assert r["ok"] and r["nodes"] == 1
    empty = ingest_artifact({}, extract=lambda a: "", registry=reg,
                            writer=CollectingWriter())
    assert empty == {"ok": False, "reason": "no_text_extracted"}


def test_versum_writer_requires_complete_context():
    class Sink:
        def upsert(self, envelope):
            return {}

    with pytest.raises(ValueError, match="idempotency_key"):
        versum_writer(Sink(), idempotency_key="", source={"source_id": "one"},
                      evidence=[{"evidence_id": "one"}], nd={"system_id": "one"})
    with pytest.raises(ValueError, match="source"):
        versum_writer(Sink(), idempotency_key="one", source={},
                      evidence=[{"evidence_id": "one"}], nd={"system_id": "one"})
    with pytest.raises(ValueError, match="evidence"):
        versum_writer(Sink(), idempotency_key="one",
                      source={"source_id": "one"}, evidence=[],
                      nd={"system_id": "one"})
    with pytest.raises(ValueError, match="nd"):
        versum_writer(Sink(), idempotency_key="one",
                      source={"source_id": "one"},
                      evidence=[{"evidence_id": "one"}], nd={})


def test_deontic_mixed_valid_and_invalid_input_is_partial():
    reg = IngesterRegistry()
    reg.register(DeonticIngester())
    writer = CollectingWriter()

    result = ingest_text(
        "Controller must notify. The processor must.",
        registry=reg,
        writer=writer,
    )

    assert result["status"] == "partial"
    assert result["quarantined"] is False
    assert result["rejections"] == 1
    assert result["nodes"] == 1
    assert result["write"]["written"] is True
    assert len(writer.written) == 1
    assert writer.written[0].rejections == [{
        "sentence_index": 2,
        "text": "The processor must",
        "reason": "missing_required_slot",
    }]


def test_deontic_node_ids_are_stable_and_source_namespaced():
    ingester = DeonticIngester()
    text = "Controller must notify."

    first = ingester.ingest(text, {"source_id": "policy-a"})
    again = ingester.ingest(text, {"source_id": "policy-a"})
    other = ingester.ingest(text, {"source_id": "policy-b"})

    assert first.nodes[0]["id"] == again.nodes[0]["id"]
    assert first.nodes[0]["id"] != other.nodes[0]["id"]
    assert first.edges[0]["norm"] == first.nodes[0]["id"]


def test_deontic_semicolon_does_not_leak_into_action():
    graph = DeonticIngester().ingest(
        "Controller must notify; Processor may disclose.",
        {},
    )

    assert graph.quarantined is False
    assert [node["action"] for node in graph.nodes] == ["notify", "disclose"]
