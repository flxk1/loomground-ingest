# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Multi-language composition for a norm subgraph.

A policy item is not one facet. A norm carries a deontic obligation (built by
:class:`~loomground_ingest.deontic.DeonticIngester`), its *condition* is a
FACTUAL claim, and its trigger may be EPISTEMIC ("reasonable grounds to
believe"). This layer runs the applicable languages and MERGES their
contributions onto the same dimensioned subgraph — additively, never removing
deontic content. Because every language targets the one fixed 5D + node id, the
merge is a union, not an orchestration: factual -> 5D edges, epistemic -> an nD
facet on the norm, and a belief nests over the fact it is about
(``epistemic.proposition`` lowered by the factual substrate).

This is *composition* (apply every applicable language), distinct from the
registry's *dispatch* (pick one primary ingester). It is opt-in: the base
DeonticIngester stays pure-deontic so its contract is unchanged.
"""
from __future__ import annotations

from typing import Any

from .types import Subgraph

__all__ = ["enrich_subgraph", "EnrichingWriter"]


def enrich_subgraph(subgraph: Subgraph) -> Subgraph:
    """Compose factual + epistemic onto every norm node in ``subgraph`` (in place).

    The composed languages are OPTIONAL extras (``pip install loomground-ingest[compose]``);
    imported lazily so the base pipeline neither requires nor pins them. A clear
    error is raised only if composition is used without them installed."""
    try:
        from loomground_epistemic import extract as _epistemic
        from loomground_factual import lower as _factual
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "composition needs the 'compose' extra: pip install loomground-ingest[compose] "
            "(loomground-factual + loomground-epistemic)"
        ) from exc
    added: list[dict[str, Any]] = []
    for node in subgraph.nodes:
        if node.get("kind") != "norm":
            continue
        raw = (node.get("provenance") or {}).get("source_sentence", "") or ""
        condition = node.get("condition") or ""

        # EPISTEMIC — a modality over the proposition (belief/knowledge at a
        # threshold). Prefer the condition (where triggers live), fall back to raw.
        facet = _epistemic(condition) or _epistemic(raw)
        fact = None
        if facet:
            node["epistemic"] = facet                        # nD facet on the norm
            # the fact BELIEVED, lowered by the substrate (belief nests over fact)
            fact = _factual(facet.get("proposition", "") or "")

        # FACTUAL — the condition as a structured 5D claim (else opaque text).
        if fact is None and condition:
            fact = _factual(condition)
        if fact:
            node["condition_fact"] = fact                    # the 5D fact the norm tests
            added.append({
                "subject": node["id"], "predicate": "conditioned-by",
                "object": fact["object"], "dimension": "causal",  # condition = causal trigger
                "norm": node["id"], "origin": "factual",
                "fact_dimension": fact["dimension"], "negated": fact["negated"],
            })

    subgraph.edges.extend(added)
    return subgraph


class EnrichingWriter:
    """Writer wrapper that composes factual + epistemic onto each subgraph before
    delegating to the inner (versum) writer.

    This is the seam where ingest *builds the versum with multiple nDs*: the base
    pipeline and DeonticIngester stay pure-deontic, and a host opts in by wrapping
    its writer. ``write`` enriches in place, then hands the composed subgraph to
    the inner writer unchanged, so the persisted envelope carries the extra facets
    under ``properties`` automatically.
    """

    def __init__(self, inner: Any) -> None:
        if not hasattr(inner, "write"):
            raise TypeError("inner writer must provide write(subgraph)")
        self._inner = inner

    def write(self, subgraph: Subgraph) -> Any:
        return self._inner.write(enrich_subgraph(subgraph))
