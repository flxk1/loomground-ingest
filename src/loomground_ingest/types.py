# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Ingestion-plane currency and the ingester contract.

A ``Subgraph`` is the neutral hand-off between an ingester and the writer:
nodes, edges and provenance, tagged with the Versum dimension they occupy
(``"5D"`` for knowledge and claims, ``"nD"`` for governance). One writer
upserts any dimension; the ingester chooses the facet, not a separate sink.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

ALLOWED_FACETS = frozenset({"5D", "nD"})
FEDERATION_EDGE_DIMENSIONS = frozenset({
    "structural", "causal", "intentional", "temporal", "relational",
})

#: A grammar predicate: does this text belong to an ingester? ``None`` from an
#: ingester's ``grammar()`` marks it best-guess-only (matched by fallback).
Predicate = Callable[[str], bool]

#: Per-call context (folder, actor, options); opaque to the plane.
Ctx = dict[str, Any]


@dataclass
class Subgraph:
    """A dimensioned graph fragment destined for Versum.

    ``quarantined`` marks input the ingester recognised but refused to lower
    into the graph (e.g. a court judgment, which interprets norms rather than
    enacting them); the writer fail-safes such a subgraph rather than writing it.
    """

    dimension: str
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    quarantined: bool = False
    rejections: list[dict[str, Any]] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Outcome at the subgraph boundary.

        Partial means validated content may be written while explicitly
        rejected units remain available for audit. Quarantine is reserved for
        input whose semantic boundary is not safe to write at all.
        """
        if self.quarantined:
            return "quarantined"
        if self.rejections:
            return "partial"
        return "complete"


def node_identity(node: Any) -> Any:
    """The single identity a node is keyed by across the plane.

    ``validate_subgraph`` (dedup, dangling-edge resolution) and the writer
    (emitted ``node_id``, edge-endpoint matching) both resolve identity through
    this one helper, so a node's dedup key and its emit/endpoint key can never
    diverge. ``node_id`` takes precedence over ``id`` to match the envelope the
    writer emits. Non-dict nodes have no identity (``None``).
    """
    if not isinstance(node, dict):
        return None
    return node.get("node_id", node.get("id"))


def validate_subgraph(subgraph: Subgraph) -> list[str]:
    """Return contract violations without mutating ``subgraph``.

    Deontic edges refer to their emitted norm through ``norm``. Their
    ``subject`` and ``object`` fields are semantic values, not node IDs, so
    referential integrity intentionally applies only to ``norm`` here.
    """
    errors: list[str] = []
    if subgraph.dimension not in ALLOWED_FACETS:
        errors.append("invalid facet")
    if not isinstance(subgraph.provenance, dict) or not subgraph.provenance:
        errors.append("missing provenance")

    node_ids: list[Any] = [node_identity(node) for node in subgraph.nodes]
    # The presence check stays keyed on ``id`` so node_id-only nodes remain
    # rejected; dedup and edge resolution below use the shared identity.
    if any(
        not isinstance(node, dict)
        or not isinstance(node.get("id"), (str, int))
        for node in subgraph.nodes
    ):
        errors.append("node missing id")
    if len(node_ids) != len(set(node_ids)):
        errors.append("duplicate node id")
    known_ids = set(node_ids)

    for edge in subgraph.edges:
        if not isinstance(edge, dict):
            errors.append("malformed edge")
            continue
        if edge.get("dimension") not in FEDERATION_EDGE_DIMENSIONS:
            errors.append("invalid edge dimension")
        if "norm" in edge and edge["norm"] not in known_ids:
            errors.append("dangling norm edge")

    if subgraph.quarantined:
        if subgraph.nodes or subgraph.edges:
            errors.append("quarantine contains semantic content")
        if subgraph.rejections:
            errors.append("quarantine contains unit rejections")
    elif subgraph.rejections and not subgraph.nodes:
        errors.append("partial without accepted content")

    for rejection in subgraph.rejections:
        if not isinstance(rejection, dict) or not all(
            rejection.get(key) not in (None, "")
            for key in ("sentence_index", "text", "reason")
        ):
            errors.append("malformed rejection")
    return errors


@runtime_checkable
class Ingester(Protocol):
    """Turns text into one dimensioned ``Subgraph``.

    The deterministic core runs with the local-LLM cascade off, so the same
    text yields the same subgraph; LLM enrichment is opt-in and never the
    source of truth.
    """

    id: str

    def grammar(self) -> Optional[Predicate]:
        """A predicate matched before best-guess dispatch, or ``None`` to be
        reached only as the fallback."""
        ...

    def ingest(self, text: str, ctx: Ctx) -> Subgraph:
        ...
