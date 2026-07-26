<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Release definition of done

A release is done only when the bare command below prints `RELEASE GATE PASS`.
Passing unit tests alone is necessary but insufficient.

```sh
python -m tests.release_gate
```

## R1 — Public contract

- The package imports through its public API on every supported Python version.
- Dispatch is deterministic: grammar matches precede the single fallback.
- Every produced subgraph declares `5D` or `nD`, provenance, nodes, and edges.
- Every edge uses a Federation dimension; deontic `norm` references resolve to
  a unique emitted node.
- Outcomes are exactly `complete`, `partial`, or `quarantined`.
- `partial` carries structured rejections; it is never silently incomplete.
- `quarantined` is reserved for document-level uncertainty and writes nothing.

## R2 — Deontic fidelity

- O, P, and F cues lower through the published deontic language pack.
- Conditions, exceptions, incidents, correlatives, and edge dimensions survive.
- Every written edge points to an emitted norm node.
- IDs are deterministic for the same source and input, and source-namespaced.
- Sentence punctuation does not alter the extracted proposition.
- Candidate conflicts are reported but never resolved by ingest.

## R3 — Partial-input honesty

- A valid sentence beside a malformed sentence writes only the validated norm.
- The malformed sentence is retained verbatim with position and reason.
- Rejected text creates neither a node nor an edge.
- Counts reconcile: recognized = lowered + rejected.

## R4 — Fail-closed write boundary

- A quarantined subgraph never enters the writer's persisted collection.
- The pipeline refuses quarantine and malformed subgraphs before calling any
  writer; writer-side refusal is an additional defense.
- `versum_writer()` requires an injected sink plus idempotency, source,
  evidence, and nD context; the sink owns its authorized target and no default
  or hidden persistence path exists.
- The Versum adapter revalidates the subgraph and rejects unverifiable,
  wrong-version, or wrong-idempotency receipts.
- Pipeline success does not claim that a refused write was persisted.

## R5 — Out-of-band verification and teeth

The release gate inspects the writer's stored subgraph, not the pipeline's own
summary. It also proves the checks have teeth by constructing bad artifacts:

- an edge whose norm target is absent must be rejected by the gate;
- a dimension outside the allowed vocabulary must be rejected;
- missing provenance, duplicate node IDs, and malformed rejection records must
  each be rejected independently;
- a malformed normative sentence must not appear as written graph content;
- a quarantined subgraph must leave writer state unchanged.

## R6 — Distribution and hygiene

- The complete test suite passes.
- CI runs the complete suite and the bare, non-recursive release gate.
- `git diff --check` is clean.
- Package metadata declares the runtime dependency range.
- Documentation states the injected, versioned Versum write boundary accurately.
- The release contains no caches, virtual environments, or build artifacts.

Any failed criterion blocks release. A gate must never be weakened to turn a
real failure green; fix the product or explicitly revise this contract first.
