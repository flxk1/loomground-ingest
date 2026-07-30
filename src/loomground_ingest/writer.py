# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The write role — upsert a dimensioned subgraph into the target store.

One verb writes any dimension; the subgraph names its facet. A quarantined
subgraph is refused (fail-safe) — the ingester recognised the input but declined
to lower it, so nothing lands in the graph.

``CollectingWriter`` is the in-memory writer used for deterministic tests and
dry runs. ``VersumWriter`` adapts this package's neutral ``Subgraph`` to the
versioned envelope accepted by a host-injected Versum sink. The sink owns
persistence; ingest neither imports Versum core nor opens a second write door.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping, Protocol, runtime_checkable

from .types import Subgraph, node_identity, validate_subgraph

VERSUM_SINK_CONTRACT = "loomground.versum.dimensioned-subgraph/v1"
VERSUM_RECEIPT_CONTRACT = "loomground.versum.dimensioned-subgraph-receipt/v1"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


@runtime_checkable
class Writer(Protocol):
    def write(self, subgraph: Subgraph) -> dict[str, Any]:
        ...


@runtime_checkable
class DimensionedSubgraphSink(Protocol):
    """Versum-owned persistence port supplied by the host."""

    def upsert(self, envelope: Mapping[str, Any]) -> Any:
        ...


class CollectingWriter:
    """Accumulates written subgraphs in memory; refuses quarantined ones."""

    def __init__(self) -> None:
        self.written: list[Subgraph] = []

    def write(self, subgraph: Subgraph) -> dict[str, Any]:
        if subgraph.quarantined:
            return {"written": False, "reason": "quarantined",
                    "dimension": subgraph.dimension}
        self.written.append(subgraph)
        return {"written": True, "dimension": subgraph.dimension,
                "status": subgraph.status,
                "nodes": len(subgraph.nodes), "edges": len(subgraph.edges),
                "rejections": len(subgraph.rejections)}


class VersumWriter:
    """Convert validated subgraphs to the Versum sink's v1 envelope."""

    def __init__(self, sink: DimensionedSubgraphSink, *,
                 idempotency_key: str, source: Mapping[str, Any],
                 evidence: list[Mapping[str, Any]],
                 nd: Mapping[str, Any]) -> None:
        if not callable(getattr(sink, "upsert", None)):
            raise TypeError("sink must provide upsert(envelope)")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if not isinstance(source, Mapping) or not source:
            raise ValueError("source is required")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, Mapping) for item in evidence
        ):
            raise ValueError("evidence is required")
        if not isinstance(nd, Mapping) or not nd:
            raise ValueError("nd is required")
        self._sink = sink
        self._idempotency_key = idempotency_key
        self._source = deepcopy(dict(source))
        self._evidence = deepcopy([dict(item) for item in evidence])
        self._nd = deepcopy(dict(nd))

    def write(self, subgraph: Subgraph) -> dict[str, Any]:
        if subgraph.quarantined:
            return {"written": False, "reason": "quarantined",
                    "dimension": subgraph.dimension}
        errors = validate_subgraph(subgraph)
        if errors:
            return {"written": False, "reason": "invalid_subgraph",
                    "dimension": subgraph.dimension, "errors": errors}
        if self._nd.get("facet") != subgraph.dimension:
            return {
                "written": False,
                "reason": "facet_mismatch",
                "dimension": subgraph.dimension,
            }

        node_ids = {node_identity(node) for node in subgraph.nodes}
        evidence_ids = [item.get("evidence_id") for item in self._evidence]
        relations = []
        for index, edge in enumerate(subgraph.edges):
            source_value = edge.get(
                "source_node_id",
                edge.get("source", edge.get("subject", edge.get("from"))),
            )
            target_value = edge.get(
                "target_node_id",
                edge.get("target", edge.get("object", edge.get("to"))),
            )
            relation_id = edge.get("relation_id", edge.get("id"))
            if relation_id is None:
                canonical = json.dumps(
                    edge, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
                relation_id = (
                    f"relation:{index + 1}:"
                    f"{hashlib.sha256(canonical).hexdigest()[:16]}"
                )
            consumed = {
                "relation_id", "id", "relation_type", "predicate",
                "source_node_id", "source", "subject", "from",
                "target_node_id", "target", "object", "to",
                "dimension", "evidence_ids",
            }
            relations.append({
                "relation_id": relation_id,
                "relation_type": edge.get(
                    "relation_type",
                    edge.get(
                        "predicate",
                        edge.get("type", edge.get("kind", edge.get("label", "cord"))),
                    ),
                ),
                "source": {
                    "kind": "node" if source_value in node_ids else "literal",
                    "value": source_value,
                },
                "target": {
                    "kind": "node" if target_value in node_ids else "literal",
                    "value": target_value,
                },
                "dimension": edge.get("dimension"),
                "evidence_ids": deepcopy(
                    edge.get("evidence_ids", evidence_ids)
                ),
                "properties": deepcopy({
                    key: value for key, value in edge.items()
                    if key not in consumed
                }),
            })

        envelope = {
            "schema": VERSUM_SINK_CONTRACT,
            "idempotency_key": self._idempotency_key,
            "source": deepcopy(self._source),
            "evidence": deepcopy(self._evidence),
            "nd": deepcopy(self._nd),
            "nodes": [
                {
                    "node_id": node_identity(node),
                    "node_type": node.get(
                        "node_type",
                        node.get("kind", node.get("class", node.get("type", "node"))),
                    ),
                    "dimensions": deepcopy(node.get("dimensions", {})),
                    "properties": deepcopy({
                        key: value for key, value in node.items()
                        if key not in {
                            "id", "node_id", "kind", "class", "type",
                            "node_type", "dimensions",
                        }
                    }),
                }
                for node in subgraph.nodes
            ],
            "relations": relations,
        }
        receipt = self._sink.upsert(envelope)
        if callable(getattr(receipt, "to_dict", None)):
            receipt = receipt.to_dict()
        if not isinstance(receipt, Mapping):
            raise TypeError("Versum sink receipt must be a mapping")
        result = dict(receipt)
        if set(result) != {
            "schema", "idempotency_key", "content_digest",
            "transaction_id", "status",
        }:
            raise ValueError("Versum sink receipt fields differ from contract")
        if result.get("schema") != VERSUM_RECEIPT_CONTRACT:
            raise ValueError("Versum sink receipt schema mismatch")
        if result.get("idempotency_key") != self._idempotency_key:
            raise ValueError("Versum sink receipt idempotency_key mismatch")
        if not isinstance(result.get("content_digest"), str) or not _SHA256.fullmatch(
            result["content_digest"]
        ):
            raise ValueError("Versum sink receipt content_digest is invalid")
        if not isinstance(result.get("transaction_id"), str) or not result[
            "transaction_id"
        ]:
            raise ValueError("Versum sink receipt transaction_id is invalid")
        if result.get("status") not in {"inserted", "unchanged"}:
            raise ValueError("Versum sink receipt status is invalid")
        return {
            **result,
            "written": result["status"] in {"inserted", "unchanged"},
        }


def versum_writer(sink: DimensionedSubgraphSink, *, idempotency_key: str,
                  source: Mapping[str, Any],
                  evidence: list[Mapping[str, Any]],
                  nd: Mapping[str, Any]) -> VersumWriter:
    """Build the ingest-side adapter to a host-supplied Versum write sink."""
    return VersumWriter(
        sink,
        idempotency_key=idempotency_key,
        source=source,
        evidence=evidence,
        nd=nd,
    )
