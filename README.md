<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# loomground-ingest

Deterministic normalization and evidence packaging: lowers a host-acquired artifact to a dimensioned subgraph envelope for loomground-versum.

## Problem

Unstructured input needs deterministic lowering with provenance, explicit rejections and quarantine.

## Install

```bash
pip install -r requirements-dev.txt
pip install .
```

## Usage

```python
from loomground_ingest import (CollectingWriter, DeonticIngester,
                               IngesterRegistry, ingest_text)

registry = IngesterRegistry()
registry.register(DeonticIngester())
report = ingest_text(text, registry=registry, writer=CollectingWriter())
```

For persistent writes, the host injects `sink` into `versum_writer(…)`.

## Example

```
in : text = "The operator must delete personal data within 30 days after the contract ends. The operator must not transfer personal data outside the EU. The operator may retain invoices."
     ingest_text(text, registry=registry, writer=CollectingWriter())
out: {'ok': True, 'processed': True, 'ingester': 'deontic', 'dimension': 'nD', 'status': 'complete', 'quarantined': False, 'rejections': 0, 'nodes': 3, 'edges': 10, 'write': {'written': True, 'dimension': 'nD', 'status': 'complete', 'nodes': 3, 'edges': 10, 'rejections': 0}}
```

## Interface

| Element | Definition |
| --- | --- |
| Input | `ingest_text(…)` · `ingest_artifact(…)` with a host-supplied extractor |
| Ingester | `grammar() -> Predicate \| None` (None = best-guess fallback) · `ingest(text, ctx) -> Subgraph` |
| `Subgraph` | nodes, edges, provenance, dimension, rejections, quarantine and status |
| 5D edge dimensions | structural · causal · intentional · temporal · relational |
| Writer | `CollectingWriter` (dry run) · `VersumWriter` emits versioned envelopes to an injected sink and checks receipts |
| Refusals | missing ingester/text · oversized input · quarantine · validation errors; all fail before write |
| Built-ins | `deontic`: normative text → nD norms · `policy`: validated `.lg` twin → nD governance |
| Extras | `compose`: `enrich_subgraph` / `EnrichingWriter` union factual + epistemic facets onto the deontic subgraph (opt-in, needs loomground-epistemic) |
| Network | none; acquisition and URL fetching are host-side |

Full contract: [docs/contract.md](docs/contract.md).

## Family

Deterministic normalization and evidence packaging; inputs and Versum-ready outputs defined.

- consumes: [loomground-deontic](https://github.com/flxk1/loomground-deontic) `>=0.2,<0.3` (extraction cues, O/P/F classification) · [loomground-solver](https://github.com/flxk1/loomground-solver) `>=0.2,<0.7` (validate / parse / project / to_netlist) · [loomground-governance](https://github.com/flxk1/loomground-governance) `>=0.8,<0.12` (policy grammar and vocabulary) · [loomground-factual](https://github.com/flxk1/loomground-factual) `>=0.1,<0.2` (`clean_entity` bearer NP-head)
- consumed by: [loomground-versum](https://github.com/flxk1/loomground-versum) (`versum.ingestion.DimensionedSubgraphSink`) and host applications through the public compiler API
- pipeline: `source → loomground-ingest → loomground-versum → loomground-solver → applied or diagnostic planes`

Place in the workflow: [docs/overview.md](docs/overview.md).

## Status

- version 0.2.0 · sink contract `dimensioned-subgraph/v1`
- 118 tests passed, 1 skipped (`python -m pytest -q`)
- python >=3.10 · 1 skill (`skills/loomground-ingest`)

## License

Apache-2.0 — `LICENSES/Apache-2.0.txt`, `NOTICE`.
