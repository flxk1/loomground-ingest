# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The ingestion pipeline: (extract) → dispatch → ingest → write.

Host-agnostic. The registry's ingesters and the extractor are supplied by the
host — a host registers its ingesters (e.g. a policy → governance mapper) and,
for artifact input, passes the callable that turns a file into text (audio and
image are future formats the input role is defined to admit).
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .registry import IngesterRegistry
from .types import Ctx, validate_subgraph
from .writer import Writer

#: Default upper bound (characters) on a single ingest input. The plane
#: receives host-forwarded artifact text — potentially attacker-authored — and
#: processes it whole (the deontic ingester materialises the full sentence
#: split and loops per sentence), so an unbounded input drives unbounded CPU
#: and memory. Callers may override per call via ``max_input_chars``; ``None``
#: disables the guard for trusted, already-bounded input.
DEFAULT_MAX_INPUT_CHARS = 1_000_000


def ingest_text(text: str, *, registry: IngesterRegistry, writer: Writer,
                ctx: Optional[Ctx] = None,
                max_input_chars: Optional[int] = DEFAULT_MAX_INPUT_CHARS,
                ) -> dict[str, Any]:
    """Route one text through the plane and write its subgraph.

    Returns which ingester ran, the dimension it wrote, and the writer's
    result. Text no ingester claims returns ``ok=False`` with reason
    ``no_ingester`` rather than a guessed write.

    Input longer than ``max_input_chars`` is refused fail-closed before
    dispatch with reason ``input_too_large`` (nothing is processed or written);
    pass ``max_input_chars=None`` to disable the bound.
    """
    if max_input_chars is not None and len(text) > max_input_chars:
        return {"ok": False, "reason": "input_too_large",
                "limit": max_input_chars, "length": len(text)}
    ing = registry.dispatch(text)
    if ing is None:
        return {"ok": False, "reason": "no_ingester"}
    subgraph = ing.ingest(text, ctx or {})
    if subgraph.quarantined:
        return {
            "ok": False, "processed": True, "reason": "quarantined",
            "ingester": ing.id, "dimension": subgraph.dimension,
            "status": subgraph.status, "quarantined": True,
            "rejections": len(subgraph.rejections),
            "nodes": len(subgraph.nodes), "edges": len(subgraph.edges),
            "write": {"written": False, "reason": "quarantined",
                      "dimension": subgraph.dimension},
        }
    errors = validate_subgraph(subgraph)
    if errors:
        return {
            "ok": False, "processed": True, "reason": "invalid_subgraph",
            "errors": errors, "ingester": ing.id,
            "dimension": subgraph.dimension, "status": subgraph.status,
            "quarantined": False, "rejections": len(subgraph.rejections),
            "nodes": len(subgraph.nodes), "edges": len(subgraph.edges),
            "write": {"written": False, "reason": "invalid_subgraph",
                      "dimension": subgraph.dimension},
        }
    result = writer.write(subgraph)
    return {
        "ok": result.get("written") is True,
        "processed": True,
        "ingester": ing.id,
        "dimension": subgraph.dimension,
        "status": subgraph.status,
        "quarantined": subgraph.quarantined,
        "rejections": len(subgraph.rejections),
        "nodes": len(subgraph.nodes),
        "edges": len(subgraph.edges),
        "write": result,
    }


def ingest_artifact(artifact: Any, *, extract: Callable[[Any], str],
                    registry: IngesterRegistry, writer: Writer,
                    ctx: Optional[Ctx] = None,
                    max_input_chars: Optional[int] = DEFAULT_MAX_INPUT_CHARS,
                    ) -> dict[str, Any]:
    """Extract text from a multimodal artifact via the host-supplied ``extract``
    callable, then ingest it. ``extract`` returning empty text yields
    ``ok=False`` with reason ``no_text_extracted``. The extracted text is
    subject to the same ``max_input_chars`` bound as ``ingest_text``."""
    text = extract(artifact) or ""
    if not text.strip():
        return {"ok": False, "reason": "no_text_extracted"}
    return ingest_text(text, registry=registry, writer=writer, ctx=ctx,
                       max_input_chars=max_input_chars)
