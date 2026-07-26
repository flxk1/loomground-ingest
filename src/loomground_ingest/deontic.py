# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Built-in reference ingester for the deontic language.

Lowers normative text into an nD ``Subgraph`` by consuming the deontic language
pack: its published ``extraction.json`` supplies the surface cues (modal phrase →
class, condition/exception leads), and the ``deontic`` package supplies the
classification (the O/P/F taxonomy, the Hohfeld incident, candidate conflicts) and
the acceptance check. The language defines *what*; this ingester does the *how* —
the surface read from text — exactly as solver's reference adapter consumes
governance. A host may still register its own domain-specific ingester instead.

Implements :class:`loomground_ingest.Ingester`.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

import deontic

from .types import Ctx, Predicate, Subgraph

# Consume the pack's published extraction cues (data, not code).
_EX = deontic.load_json("extraction.json")
_MODAL_CUES = [(re.compile(c["pattern"], re.I), c["modal"]) for c in _EX["modal_cues"]]
_NORMATIVE = re.compile("|".join(c["pattern"] for c in _EX["modal_cues"]), re.I)
_COND = re.compile(_EX["slot_cues"]["condition_lead"], re.I)
_EXC = re.compile(_EX["slot_cues"]["exception_lead"], re.I)


def _sentences(text: str) -> list[str]:
    return [
        s.strip().rstrip(".;").strip()
        for s in re.split(r"(?<=[.;])\s+|\n+", text or "")
        if s.strip().rstrip(".;").strip()
    ]


def _looks_normative(text: str) -> bool:
    return bool(_NORMATIVE.search(text or ""))


def _extract_slots(sentence: str) -> Optional[dict[str, str]]:
    condition, exception, body = "", "", sentence
    m = _COND.match(body)
    if m:
        condition = m.group("cond").strip(" ,")
        body = body[m.end():].strip()
    m = _EXC.search(body)
    if m:
        exception = m.group("exc").strip(" .")
        body = body[:m.start()].strip()
    for pat, modal in _MODAL_CUES:
        m = pat.search(body)
        if not m:
            continue
        subject = body[:m.start()].strip(" ,")
        action = body[m.end():].strip(" .")
        if not subject or not action:
            return None
        return {"modal": modal, "subject": subject, "action": action,
                "condition": condition, "exception": exception, "raw": sentence}
    return None


class DeonticIngester:
    """Consume the deontic language to lower normative text to an nD subgraph."""

    id = "deontic"

    def grammar(self) -> Optional[Predicate]:
        return _looks_normative

    def ingest(self, text: str, ctx: Ctx) -> Subgraph:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        rejections: list[dict[str, Any]] = []
        formulae = []
        recognised = 0
        context = ctx or {}
        source_identity = next(
            (str(context[key]) for key in ("source_id", "path", "source")
             if context.get(key)),
            text,
        )
        source_hash = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:16]
        for sentence_index, sentence in enumerate(_sentences(text), start=1):
            if not _looks_normative(sentence):
                continue
            recognised += 1
            slots = _extract_slots(sentence)
            if slots is None:
                rejections.append({
                    "sentence_index": sentence_index,
                    "text": sentence,
                    "reason": "missing_required_slot",
                })
                continue
            incident = deontic.classify_incident(
                slots["modal"], slots["action"], slots["raw"])
            f = deontic.formula_from_fields(
                slots["modal"], slots["subject"], slots["action"],
                condition=slots["condition"], exception=slots["exception"],
                incident=incident, raw_sentence=slots["raw"])
            if not deontic.validate(f)["ok"]:
                rejections.append({
                    "sentence_index": sentence_index,
                    "text": sentence,
                    "reason": "deontic_validation_failed",
                })
                continue
            formulae.append(f)
            formula_hash = hashlib.sha256(f.render().encode("utf-8")).hexdigest()[:16]
            nid = f"deontic:{source_hash}:{sentence_index}:{formula_hash}"
            nodes.append({
                "id": nid, "kind": "norm", "statement": f.render(),
                "operator": f.operator, "bearer": f.bearer, "action": f.action,
                "incident": f.incident, "correlative": deontic.correlative(f.incident),
                "condition": f.condition, "exception": f.exception,
                "provenance": {"source_sentence": slots["raw"]},
            })
            edges.append({"subject": f.bearer, "predicate": f.operator,
                          "object": f.action, "dimension": deontic.dimension_affinity(f.operator),
                          "norm": nid})

        conflicts = deontic.detect_conflicts(formulae)
        return Subgraph(
            dimension=_EX["dimension"], nodes=nodes, edges=edges,
            rejections=rejections,
            provenance={"ingester": self.id, "language_version": deontic.language_version(),
                        "recognised": recognised, "lowered": len(formulae),
                        "rejected": len(rejections), "conflicts": conflicts,
                        "actor": context.get("actor", "")},
        )
