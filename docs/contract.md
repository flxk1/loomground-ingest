<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# The ingest-plane contract

The [README](../README.md) states the plane's place in the workflow; this states
its contract. The plane turns **already-acquired multimodal input into a
dimensioned subgraph in versum**: a host supplies an artifact or extracted text,
a dispatcher picks an ingester (by grammar when one matches, by best guess
otherwise), the ingester lowers it to a subgraph, and the writer upserts that
subgraph into versum. The plane invents nothing; missing context is recorded as
incomplete, never as false.

For the current execution path, URL acquisition and its SSRF controls are owned
by RVND. This package performs no network access and does not accept a URL as an
instruction to fetch; its boundary begins after acquisition.

## The pipeline

```
artifact ──► extract ──► dispatch ──► ingest ──► write
(pdf/docx/   (→ text +   (grammar    (instance   (upsert the
 pages/…)     metadata)   match, else  produces a  dimensioned
                          best guess)  dimensioned subgraph into
                                       subgraph)   versum)
```

## One store, many dimensions

Versum is the one graph store; a dimension selects the facet. **5D** carries the
tool's mental model as Federation relations — structural, causal, intentional,
temporal, relational. **nD** carries governance. An ingester tags its subgraph's
nodes and edges with the dimension they occupy; one writer upserts any
dimension, so the ingester chooses the facet rather than a separate sink.

## The contract (this package)

- `Subgraph` — the neutral currency: nodes, edges, provenance, a `dimension`
  tag, structured per-unit `rejections`, and a `quarantined` flag reserved for
  input whose document-level boundary is unsafe to lower. Its derived status is
  `complete`, `partial`, or `quarantined`.
- `Ingester` — `grammar() -> Predicate | None` (None ⇒ best-guess fallback) and
  `ingest(text, ctx) -> Subgraph`. Deterministic core, LLM enrichment opt-in and
  never the source of truth.
- `IngesterRegistry` — grammar predicates first, one best-guess fallback.
- `Writer` — `write(Subgraph)`; `CollectingWriter` for tests and dry runs. The
  writer refuses a quarantined subgraph. `VersumWriter` converts a validated
  subgraph to the versioned envelope accepted by an injected
  `DimensionedSubgraphSink`.
- `ingest_text` / `ingest_artifact` — the pipeline; the host supplies the
  ingesters, the writer, and (for artifacts) the extractor.
- Product-side validation rejects invalid facets, edge dimensions, provenance,
  outcome combinations, semantic content in quarantine, and dangling deontic
  `norm` references before a writer can be called.

The plugin manifest's legacy-named `humanConfirmation` field is a declarative
requirement on the host. The library does not prompt for or enforce
confirmation. RVND satisfies the requirement through its automated governance
authority before supplying a persistent writer. Quarantine and structural
validation are library-enforced independently of that host gate.

The framework owns no *domain-specific* ingester and no extractor itself: a host
registers those. It does ship one **built-in reference ingester** — `deontic` —
the way solver ships a reference adapter for governance; it consumes the deontic
language pack (its published `extraction.json` cues and the `deontic` package's
classification) and lowers normative text to an nD subgraph. A host may register
its own instead.

## Ingesters

- **Normative text → nD deontic** *(built; the reference ingester, this package).*
  Consumes the deontic language pack — its published `extraction.json` supplies the
  surface cues (modal phrase → class, condition/exception leads); the `deontic`
  package supplies the O/P/F taxonomy, the Hohfeld incident, and candidate-conflict
  flagging. One node per norm (statement, operator, bearer, action, incident and
  its correlative, condition, exception, provenance), edges on the operator's axis
  (causal for O/F, intentional for P). A norm-bearing sentence it cannot lower is
  retained as a structured rejection while independently validated sentences can
  land. Document-level ambiguity is quarantined; missing slots are never guessed.
- **Policy text → nD governance** *(built; the instance lives in rvnd).* Wraps
  rvnd's policy mapper: it lowers a policy's Loomground projection (nodes and
  cords) into an nD subgraph and quarantines a court judgment, which interprets
  norms rather than enacting them. rvnd contributes this ingester and wires its
  format-aware extractor as the input role, consuming this package.

## The Versum write boundary

`versum_writer(sink, idempotency_key=..., source=..., evidence=..., nd=...)` is
the consumer-side adapter. It requires all semantic context up front and emits
the `loomground.versum.dimensioned-subgraph/v1` envelope:

- idempotency, source identity/digest, evidence identity/digest/locator, and the
  nD system/axes are host supplied;
- nodes become typed Versum nodes with honest coordinates on the axes the
  ingester assigns (an empty mapping means unassigned); non-contract ingester
  fields survive under node `properties`;
- edges become typed relations with node or scalar-literal endpoints and
  evidence references bound to the envelope evidence; non-contract edge fields
  survive under relation `properties`;
- the injected sink owns persistence and returns a receipt with the matching
  receipt schema and idempotency key plus `inserted` or `unchanged` status;
- malformed or mismatched receipts fail closed.

The adapter is structural: this package does not import Versum core and cannot
write a Versum store directly. A host injects the live Versum implementation of
`DimensionedSubgraphSink.upsert(envelope)`. This preserves Versum's ownership of
its write door while making the Ingestor → Versum consumption path executable.
The target and authorized store root belong to that injected sink rather than
the envelope.
The path remains post-acquisition and performs no network access.

## Status

Framework built and tested standalone (`v0.1.1`). The policy ingester is built
and lives in rvnd, which depends on this package. The Ingestor → Versum
consumer adapter is built; the host supplies Versum's live sink implementation.
