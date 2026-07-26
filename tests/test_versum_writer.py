# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
from __future__ import annotations

from copy import deepcopy

import pytest

from loomground_ingest import (
    VERSUM_RECEIPT_CONTRACT,
    VERSUM_SINK_CONTRACT,
    Subgraph,
    ingest_text,
    versum_writer,
)
from loomground_ingest.registry import IngesterRegistry

_DIGEST = "sha256:" + ("a" * 64)


class _Sink:
    def __init__(self) -> None:
        self.envelopes = []

    def upsert(self, envelope):
        self.envelopes.append(deepcopy(envelope))
        return {
            "schema": VERSUM_RECEIPT_CONTRACT,
            "idempotency_key": envelope["idempotency_key"],
            "content_digest": "sha256:" + ("b" * 64),
            "transaction_id": "subgraph:one",
            "status": "inserted",
        }


class _Ingester:
    id = "test"

    def grammar(self):
        return lambda text: True

    def ingest(self, text, ctx):
        return Subgraph(
            dimension="5D",
            nodes=[
                {
                    "id": "node:a",
                    "kind": "claim",
                    "dimensions": {"relational": "subject"},
                    "text": text,
                },
                {
                    "id": "node:b",
                    "kind": "concept",
                    "dimensions": {"relational": "object"},
                },
            ],
            edges=[{
                "id": "relation:1",
                "predicate": "supports",
                "source": "node:a",
                "target": "node:b",
                "dimension": "relational",
                "evidence_ids": ["evidence:1"],
            }],
            provenance={"source": "local-artifact"},
        )


def _writer(sink):
    return versum_writer(
        sink,
        idempotency_key="capture-001",
        source={"source_id": "source:1", "content_digest": _DIGEST},
        evidence=[{
            "evidence_id": "evidence:1",
            "source_id": "source:1",
            "locator": "artifact:1",
            "content_digest": _DIGEST,
        }],
        nd={
            "facet": "5D",
            "system_id": "system:federation-5d",
            "dimension_count": 1,
            "axes": ["relational"],
        },
    )


def test_pipeline_hands_exact_versioned_envelope_to_injected_sink():
    sink = _Sink()
    registry = IngesterRegistry()
    registry.register(_Ingester())

    result = ingest_text("verified claim", registry=registry, writer=_writer(sink))

    assert result["ok"] is True
    assert result["write"]["status"] == "inserted"
    assert sink.envelopes == [{
        "schema": VERSUM_SINK_CONTRACT,
        "idempotency_key": "capture-001",
        "source": {"source_id": "source:1", "content_digest": _DIGEST},
        "evidence": [{
            "evidence_id": "evidence:1",
            "source_id": "source:1",
            "locator": "artifact:1",
            "content_digest": _DIGEST,
        }],
        "nd": {
            "facet": "5D",
            "system_id": "system:federation-5d",
            "dimension_count": 1,
            "axes": ["relational"],
        },
        "nodes": [
            {
                "node_id": "node:a",
                "node_type": "claim",
                "dimensions": {"relational": "subject"},
                "properties": {"text": "verified claim"},
            },
            {
                "node_id": "node:b",
                "node_type": "concept",
                "dimensions": {"relational": "object"},
                "properties": {},
            },
        ],
        "relations": [{
            "relation_id": "relation:1",
            "relation_type": "supports",
            "source": {"kind": "node", "value": "node:a"},
            "target": {"kind": "node", "value": "node:b"},
            "dimension": "relational",
            "evidence_ids": ["evidence:1"],
            "properties": {},
        }],
    }]


def test_writer_revalidates_and_never_calls_sink_for_bad_or_quarantined_graph():
    sink = _Sink()
    writer = _writer(sink)

    invalid = writer.write(Subgraph(dimension="5D"))
    quarantined = writer.write(Subgraph(
        dimension="nD",
        provenance={"source": "local-artifact"},
        quarantined=True,
    ))

    assert invalid["reason"] == "invalid_subgraph"
    assert quarantined["reason"] == "quarantined"
    assert sink.envelopes == []


def test_writer_refuses_facet_mismatch_before_sink():
    sink = _Sink()
    result = _writer(sink).write(Subgraph(
        dimension="nD",
        nodes=[{"id": "node:a"}],
        provenance={"source": "local-artifact"},
    ))

    assert result["reason"] == "facet_mismatch"
    assert sink.envelopes == []


def test_literal_endpoints_and_residual_edge_properties_are_preserved():
    sink = _Sink()
    graph = Subgraph(
        dimension="5D",
        nodes=[{"id": "norm:1", "kind": "norm"}],
        edges=[{
            "subject": "Operator",
            "predicate": "must",
            "object": "retain",
            "dimension": "relational",
            "norm": "norm:1",
        }],
        provenance={"source": "local-artifact"},
    )

    _writer(sink).write(graph)
    relation = sink.envelopes[0]["relations"][0]

    assert relation["source"] == {"kind": "literal", "value": "Operator"}
    assert relation["target"] == {"kind": "literal", "value": "retain"}
    assert relation["evidence_ids"] == ["evidence:1"]
    assert relation["properties"] == {"norm": "norm:1"}
    assert relation["relation_id"].startswith("relation:1:")


def test_rvnd_policy_projection_shape_maps_without_semantic_rewrite():
    sink = _Sink()
    graph = Subgraph(
        dimension="5D",
        nodes=[
            {"id": "actor:1", "class": "actor", "role": "operator"},
            {"id": "gate:1", "class": "gate", "risk_floor": "high"},
        ],
        edges=[{
            "from": "actor:1",
            "to": "gate:1",
            "type": "authority",
            "dimension": "relational",
        }],
        provenance={"source": "policy-ingester"},
    )

    _writer(sink).write(graph)
    envelope = sink.envelopes[0]

    assert envelope["nodes"][0] == {
        "node_id": "actor:1",
        "node_type": "actor",
        "dimensions": {},
        "properties": {"role": "operator"},
    }
    assert envelope["relations"][0]["relation_type"] == "authority"
    assert envelope["relations"][0]["source"] == {
        "kind": "node", "value": "actor:1",
    }
    assert envelope["relations"][0]["target"] == {
        "kind": "node", "value": "gate:1",
    }


@pytest.mark.parametrize(
    "receipt,error",
    [
        (None, TypeError),
        ({"schema": "v0", "idempotency_key": "capture-001",
          "status": "inserted"}, ValueError),
        ({"schema": VERSUM_RECEIPT_CONTRACT, "idempotency_key": "other",
          "status": "inserted"}, ValueError),
        ({"schema": VERSUM_RECEIPT_CONTRACT, "idempotency_key": "capture-001",
          "status": "unknown"}, ValueError),
    ],
)
def test_writer_rejects_unverifiable_receipts(receipt, error):
    class BadSink:
        def upsert(self, envelope):
            return receipt

    with pytest.raises(error):
        _writer(BadSink()).write(_Ingester().ingest("claim", {}))


def test_envelope_is_detached_from_caller_owned_values():
    sink = _Sink()
    evidence = [{
        "evidence_id": "evidence:1",
        "source_id": "source:1",
        "locator": "artifact:1",
        "content_digest": _DIGEST,
    }]
    graph = _Ingester().ingest("before", {})
    writer = versum_writer(
        sink,
        idempotency_key="capture-001",
        source={"source_id": "source:1", "content_digest": _DIGEST},
        evidence=evidence,
        nd={
            "facet": "5D",
            "system_id": "system:federation-5d",
            "dimension_count": 1,
            "axes": ["relational"],
        },
    )

    writer.write(graph)
    evidence[0]["locator"] = "changed"
    graph.nodes[0]["text"] = "after"

    assert sink.envelopes[0]["evidence"][0]["locator"] == "artifact:1"
    assert sink.envelopes[0]["nodes"][0]["properties"]["text"] == "before"
