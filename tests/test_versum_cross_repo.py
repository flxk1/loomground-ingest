# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Executable sibling-repository proof of Ingestor -> Versum consumption."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from loomground_ingest import (
    DeonticIngester,
    IngesterRegistry,
    ingest_text,
    versum_writer,
)


def test_deontic_ingester_persists_through_live_versum_sink(tmp_path):
    versum_src = Path(__file__).parents[2] / "loomground-versum" / "src"
    if not versum_src.is_dir():
        pytest.skip("sibling loomground-versum source is not available")
    sys.path.insert(0, str(versum_src))
    try:
        from versum.ingestion import (  # type: ignore[import-not-found]
            DimensionedSubgraphSink,
            load_dimensioned_subgraphs,
        )
    finally:
        sys.path.remove(str(versum_src))

    text = "Controller must notify the operator."
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_id = "source:deontic-proof"
    evidence_id = "evidence:deontic-proof"
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    sink = DimensionedSubgraphSink(
        authorized / "store",
        authorized_store_root=authorized,
    )
    writer = versum_writer(
        sink,
        idempotency_key="deontic:proof:1",
        source={"source_id": source_id, "content_digest": digest},
        evidence=[{
            "evidence_id": evidence_id,
            "source_id": source_id,
            "locator": "sentence:1",
            "content_digest": digest,
        }],
        nd={
            "facet": "nD",
            "system_id": "system:deontic",
            "dimension_count": 5,
            "axes": [
                "structural", "causal", "intentional", "temporal", "relational",
            ],
        },
    )
    registry = IngesterRegistry()
    registry.register(DeonticIngester())

    first = ingest_text(
        text,
        registry=registry,
        writer=writer,
        ctx={"source_id": source_id},
    )
    second = ingest_text(
        text,
        registry=registry,
        writer=writer,
        ctx={"source_id": source_id},
    )

    assert first["ok"] is True
    assert first["write"]["status"] == "inserted"
    assert second["write"]["status"] == "unchanged"
    persisted = load_dimensioned_subgraphs(authorized / "store")
    assert len(persisted) == 1
    relation = persisted[0].to_dict()["relations"][0]
    assert relation["source"]["kind"] == "literal"
    assert relation["properties"]["norm"].startswith("deontic:")
