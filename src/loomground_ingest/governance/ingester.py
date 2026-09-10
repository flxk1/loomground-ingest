# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The governance ingester — consumes the ported policy compiler.

Wraps the deterministic ``compiler.ingest`` mapper and lowers its digital twin
into an nD ``Subgraph``: the twin's ``projection`` already carries the Loomground
nodes and cords (the nD structure), so this ingester adapts, it does not re-map.
A court judgment interprets norms rather than enacting them; the compiler
quarantines it, and the resulting subgraph is marked quarantined so the writer
refuses it.

Keeps ``id = "policy"`` so host dispatch and existing test semantics are
preserved. Implements :class:`loomground_ingest.Ingester`.
"""
from __future__ import annotations

from typing import Optional

import deontic
import loomground_governance

from ..deontic import DeonticIngester
from ..types import Ctx, Predicate, Subgraph
from . import compiler as policy_ingest


class GovernanceIngester:
    id = "policy"

    def grammar(self) -> Optional[Predicate]:
        """Claim text that the governance pack can lower deterministically.

        General normative prose remains available to the Deontic ingester. A
        governance policy wins only when the compiler identifies an express
        declaration or a policy/host hand-off; this prevents the Deontic grammar
        from swallowing governance-specific reservations and prohibitions.
        """
        def recognises(text: str) -> bool:
            twin = policy_ingest.ingest(text, use_llm=False)
            classification = twin.get("classification") or {}
            # Express governance primitives belong in the policy graph. Host
            # hand-offs do not: general normative content must still reach the
            # Deontic grammar. Case law is claimed solely so this ingester can
            # preserve its mandatory quarantine decision.
            return bool(twin.get("quarantined") or classification.get("express"))

        return recognises

    def ingest(self, text: str, ctx: Ctx) -> Subgraph:
        twin = policy_ingest.ingest(text, use_llm=bool((ctx or {}).get("use_llm")))
        # Policy projection's grammar/vocabulary authority is loomground-governance.
        # Consume both language packs here: Governance identifies the exact language
        # contract used for the projection; Deontic classifies the source's normative
        # sentences without becoming a second writer.
        deontic_analysis = DeonticIngester().ingest(text, ctx or {})
        proj = twin.get("projection") or {}
        edges = [
            {**cord, "dimension": cord.get("dimension", "relational")}
            for cord in (proj.get("cords") or [])
        ]
        return Subgraph(
            dimension="nD",
            nodes=list(proj.get("nodes") or []),
            edges=edges,
            provenance={
                "ingester": self.id,
                "source": "governance.compiler",
                "applied": twin.get("applied", False),
                "classification": twin.get("classification"),
                "reservations": proj.get("reservations"),
                "redress": proj.get("redress"),
                "note": twin.get("note"),
                "language_chain": {
                    "governance": {
                        "package": "loomground-governance",
                        "version": loomground_governance.language_version(),
                        "status": loomground_governance.language_status(),
                        "role": "authoritative policy grammar and vocabulary",
                    },
                    "deontic": {
                        "package": "loomground-deontic",
                        "version": deontic.language_version(),
                        "status": deontic.language_status(),
                        "role": "normative classification",
                        "recognised": deontic_analysis.provenance.get(
                            "recognised", 0
                        ),
                        "lowered": deontic_analysis.provenance.get("lowered", 0),
                        "rejected": deontic_analysis.provenance.get(
                            "rejected", 0
                        ),
                    },
                },
            },
            quarantined=bool(twin.get("quarantined")),
        )
