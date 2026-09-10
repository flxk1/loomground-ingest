---
name: loomground-ingest
description: Drive the Loomground ingest plane - turn a multimodal artifact into a dimensioned subgraph headed for the Versum mental model. Dispatches to the host-registered ingester by grammar, reports the subgraph (nodes, edges, dimension, provenance, quarantine) as a dry run by default, and writes only through a real host-injected Versum sink after the host's governance gate admits it. Invents nothing - missing context is recorded as incomplete, never as false. Use when the user wants to lower a policy or other artifact into the Versum graph, preview what it would add, or run the ingest plane as a dry run. Triggers - "ingest this policy", "lower this policy into the graph", "run the ingest plane", "what would this artifact add to versum", "dry-run the ingest".
allowed-tools: ingest_text
---

# loomground-ingest — the ingest plane

Translation of functions: read what a tool or policy declares itself through and
lower it to a **dimensioned subgraph** — 5D (structural · causal · intentional ·
temporal · relational) for a tool's mental model, nD for governance. The plane
invents nothing; what the input does not state is recorded as incomplete, never
guessed. Downstream, solver reasons over the graph and loomground-builder renders
UIs — this skill neither reasons nor renders.

## Step 0 — Resolve the profile, not the skill body

Which ingesters are registered and where output goes is **host configuration**,
never hardcoded here (profile pattern: the skill body stays neutral; the host or
config names the ingester set, the target graph, and the workspace). The host
registers the ingester set it needs — including any of the built-in reference
ingesters (deontic, governance/policy) — in its own registry.

## Step 1 — Dry-run first: artifact → subgraph, nothing written

The current pipeline starts after acquisition and is
`extract → dispatch → ingest → write`. URL acquisition and SSRF protection are
host responsibilities; this network-free package must not fetch URLs.

Primary path: call `ingest_text` with
`{"text": "<the artifact text>", "ingesters": ["deontic", "policy"], "max_input_chars": 1000000}`
(`ingesters` optional — omitted routes through every built-in; nothing is
written) — it returns the nodes, edges, rejections, quarantined, and the
subgraphs; `unavailable` means no ingester claimed the text.

Shell fallback — run it with the `CollectingWriter` so the write stage collects
instead of persisting:

```python
from loomground_ingest import ingest_text  # or ingest_artifact with an extractor
from loomground_ingest.registry import IngesterRegistry
from loomground_ingest.writer import CollectingWriter

registry = IngesterRegistry()   # host registers its ingesters here
writer = CollectingWriter()
ingest_text(text, registry=registry, writer=writer)
```

Report to the host, from the collected subgraph(s):
- **Dimension** — which facet this occupies (5D mental model / nD governance).
- **Nodes and edges** — counts and a readable sample; every element carries
  provenance back to the artifact.
- **Incomplete** — what the artifact did not state. Present, never papered over.
- **Quarantined** — input the ingester recognised but refused to lower (e.g. a
  court judgment, which interprets norms rather than enacting them). A
  quarantined subgraph is a finding for the host, not an error to retry.

## Step 2 — Write only through a real writer after governance admission

The Versum write verb is an injected seam. The library supplies the adapter;
the host supplies the authorized Versum sink:

```python
from loomground_ingest.writer import versum_writer
writer = versum_writer(
    sink,
    idempotency_key=key,
    source=source,
    evidence=evidence,
    nd=nd,
)
```

- No writer → the dry-run report is the deliverable. Do not hand-write rows
  into Versum to compensate — Versum writes go
  through versum's own gated door (`knowledge.capture`), not around it.
- Writer available → the host evaluates the proposed upsert and supplies the writer
  only after its automated governance authority admits it. `humanConfirmation`
  is legacy-named declarative host metadata; this Python library never prompts
  for or enforces it. The pipeline refuses quarantined subgraphs before
  invoking any writer — do not strip the flag to force one through.

## Step 3 — Verify on the graph, not on the run's own output

After a real write, verify in versum the way the KG skills do: the subgraph's
nodes/edges appear in the target dimension's tables and answer a query with
provenance intact. A successful-looking run is not verification.

## Boundaries

- Landing is not promotion: lowering an artifact to a subgraph (even writing it)
  never bypasses Versum's canonical-knowledge gates.
- This skill does not fetch weekly feeds or build digests (editorial's ingest
  front door), does not file documents (`loomground-organise`), does not mint
  concepts (`loomground-curate`), and does not reason or render (solver,
  builder).
- Deterministic core; LLM enrichment is opt-in and never the source of truth.
