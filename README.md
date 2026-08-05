<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->

# loomground-ingest

The ingest plane of the Loomground designer workflow: **multimodal input → the
versum mental model.**

In the current execution path, ingest begins only after a host has acquired the
artifact. URL acquisition and SSRF defenses remain RVND-owned. This package is
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
tested (`v0.1.1`); see [docs/contract.md](docs/contract.md). This package ships two
built-in reference ingesters: `deontic` (normative text → nD) and `governance`
(policy text → nD governance subgraphs, `GovernanceIngester`), both self-contained
on solver + governance; hosts contribute the rest and register the ingester set
they want. The Versum consumer adapter is an injected, versioned sink
boundary; Versum remains the owner of persistence.
## License

Apache License 2.0. See `LICENSE`, `LICENSES/Apache-2.0.txt`, and `NOTICE`.
