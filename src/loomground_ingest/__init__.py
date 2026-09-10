# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""loomground-ingest — the ingest plane framework.

Multimodal input → a dimensioned subgraph in Versum: extract → dispatch
(grammar, else best guess) → ingest → write. This package owns the plane's
currency and stages; a host registers ingesters (each lowering its input to a
``Subgraph`` tagged with its Versum dimension — 5D knowledge, nD governance)
and supplies the writer and, for artifact input, the extractor.
"""
from .pipeline import DEFAULT_MAX_INPUT_CHARS, ingest_artifact, ingest_text
from .registry import IngesterRegistry
from .types import (
    ALLOWED_FACETS,
    FEDERATION_EDGE_DIMENSIONS,
    Ctx,
    Ingester,
    Predicate,
    Subgraph,
    node_identity,
    validate_subgraph,
)
from .writer import (
    VERSUM_RECEIPT_CONTRACT,
    VERSUM_SINK_CONTRACT,
    CollectingWriter,
    DimensionedSubgraphSink,
    VersumWriter,
    Writer,
    versum_writer,
)
from .deontic import DeonticIngester
from .governance import GovernanceIngester
from .compose import enrich_subgraph, EnrichingWriter
from .artifacts import (
    ARTIFACT_CATALOGUE,
    CATEGORIES,
    ArtifactSpec,
    RequiredArtifact,
    extract_required_artifacts,
)

__all__ = [
    "ingest_text", "ingest_artifact", "DEFAULT_MAX_INPUT_CHARS",
    "IngesterRegistry",
    "Ingester", "Subgraph", "Predicate", "Ctx",
    "Writer", "CollectingWriter", "DimensionedSubgraphSink", "VersumWriter",
    "versum_writer", "VERSUM_SINK_CONTRACT", "VERSUM_RECEIPT_CONTRACT",
    "DeonticIngester", "GovernanceIngester", "validate_subgraph", "node_identity",
    "enrich_subgraph", "EnrichingWriter",
    "ALLOWED_FACETS", "FEDERATION_EDGE_DIMENSIONS",
    # required-artifact catalogue (the compliance-artifact detection capability)
    "extract_required_artifacts", "RequiredArtifact", "ArtifactSpec",
    "ARTIFACT_CATALOGUE", "CATEGORIES",
]
