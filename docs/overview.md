<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# Place in the workflow

Text moved verbatim from the README (2026-09-09); the README keeps the interface, this file keeps the workflow narrative.

The ingest plane of the Loomground designer workflow: **multimodal input → the
versum mental model.**

Ingest begins only after a host has acquired the artifact. URL acquisition and
SSRF defenses remain host-owned. This package is
network-free: it accepts text or a host-supplied extractor and does not fetch
URLs.

```
multimodal input  →  [loomground-ingest]  →  versum (5D + nD)  ⟷  solver
                                                     │
                                          [loomground-builder]  →  the tool/UI
```

Ingest performs the *translation of functions*: it reads any input a tool
declares itself through — a manual, a function list, docs, a live
machine-readable surface (image and audio extraction are host-supplied and
still forthcoming) — and writes the tool's mental model into **versum** as
Federation-5D relations (structural · causal · intentional · temporal ·
relational) plus typed nD context, provenance-stamped. It invents nothing;
missing context is recorded as incomplete, never as false.

Downstream, **solver** reasons over that model (genre, layout, tiers) and
**loomground-builder** renders the fitting working UI. Ingest never renders and
never reasons — it only builds the knowledge the other planes consume.

The framework — the plane's currency and stages — is built and
tested (`v0.1.1`); see [docs/contract.md](contract.md). This package ships one
built-in deontic ingester (normative text → nD) and a policy-text → nD
governance ingester. Hosts may contribute additional ingesters. The Versum
consumer adapter is an injected, versioned sink boundary; Versum remains the
owner of persistence.
