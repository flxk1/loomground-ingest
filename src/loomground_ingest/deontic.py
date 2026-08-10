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

# Surface cues for the two axes a bare operator edge can't carry: a TEMPORAL
# deadline and a RELATIONAL cross-reference to another provision. These read the
# norm's own text — the same "how" role as the modal/slot cues — so each norm
# lands on more than the single operator-affinity dimension.
_DEADLINE = re.compile(
    r"\b(?:within|no later than|not later than|at the latest(?: within)?)\s+\d+\s+"
    r"(?:hour|day|week|month|year)s?\b"
    r"|\bat least\s+\d+\s+(?:day|week|month|year)s?\b"
    r"|\bby\s+\d{1,2}\s+\w+\s+\d{4}\b",
    re.I,
)
_XREF = re.compile(
    # A named instrument: Regulation/Directive with the (EU)/(EC)/(EEC) marker
    # and its running number, with or without a "No" (e.g. "Regulation (EU)
    # 2016/679", "Directive 95/46/EC", "Regulation (EC) No 45/2001").
    r"\b(?:Regulation|Directive)s?\s*(?:\((?:EU|EC|EEC)(?:,\s*Euratom)?\))?\s*"
    r"(?:No\.?\s*)?\d+/\d+(?:/\w+)?\b"
    # An article, with any nested paragraph/point sub-references
    # (e.g. "Article 6", "Article 6a", "Article 6(1)", "Article 6(1)(a)").
    r"|\bArticle\s+\d+[a-z]?(?:\(\d+[a-z]?\))?(?:\([a-z]+\))?(?:\(\d+\))?(?!\w)"
    r"|\bAnnex(?:es)?\s+[IVXLC]+\b"
    # Other numbered structural units, each requiring a real locator (a number,
    # a roman numeral, or a parenthesised token) so bare prose does not match.
    r"|\b(?:Section|Chapter|Title|Paragraph|Point|Recital|Subparagraph)\s+"
    r"(?:\d+[a-z]?|\([0-9a-z]+\)|[IVXLC]+)(?!\w)",
    re.I,
)

# Surface cues for a STRUCTURAL definition: a defined term and its definition
# body. A definition is part-of the instrument's own vocabulary — captured here
# so a consumer can retire a separate definitions extractor. Two forms: a quoted
# term followed by "means"/"shall mean" (with an optional "for the purposes of …"
# lead), and the unquoted "X shall mean …" form.
_Q_OPEN = "'\"‘“"
_Q_CLOSE = "'\"’”"
_DEFINITION = re.compile(
    r"(?:^|[\s(,])"
    r"[" + _Q_OPEN + r"]"
    r"(?P<term>[^" + _Q_OPEN + _Q_CLOSE + r"]+?)"
    r"[" + _Q_CLOSE + r"]"
    r"\s+(?:shall\s+)?means?\b\s*"
    r"(?P<definition>.+)$",
    re.I | re.S,
)
_DEFINITION_SHALL = re.compile(
    r"^(?:for the purposes of[^,]*,\s*)?"
    r"(?P<term>.+?)\s+shall\s+means?\b\s*(?P<definition>.+)$",
    re.I | re.S,
)


# Surface cues for a STRUCTURAL required artifact / deliverable: a norm that
# requires producing or keeping a document, record, assessment, marking, or
# register. These are dense in regulation (e.g. AI Act Article 16 (a)-(l)). Two
# forms, each capturing the artifact name in the ``artifact`` group: a
# producing/keeping verb followed by a document-type object, and a set of
# self-naming regulatory artifacts that are the artifact whatever the governing
# verb ("affix the CE marking", "have a quality management system in place").
_ARTIFACT_NOUN = (
    r"(?:EU\s+)?declaration of conformity"
    r"|quality management system"
    r"|(?:[A-Za-z-]+\s+){0,3}impact assessment"
    r"|(?:technical\s+)?documentation"
    r"|records?"
    r"|logs?"
    r"|registers?"
)
_ARTIFACT_VERB = re.compile(
    r"\b(?:draw(?:ing|n)?\s+up|drew\s+up|keep(?:ing|s)?|kept|maintain(?:ing|s|ed)?"
    r"|establish(?:ing|es|ed)?|set(?:ting)?\s+up|put(?:ting)?\s+in\s+place"
    r"|retain(?:ing|s|ed)?|prepar(?:e|ing|es|ed)|compil(?:e|ing|es|ed))\s+"
    r"(?:the\s+|a\s+|an\s+|its\s+|their\s+|any\s+)?"
    r"(?P<artifact>" + _ARTIFACT_NOUN + r")\b",
    re.I,
)
_ARTIFACT_NAMED = re.compile(
    r"(?P<artifact>"
    r"(?:EU\s+)?declaration of conformity"
    r"|CE marking"
    r"|quality management system"
    r"|(?:[A-Za-z-]+\s+){0,3}impact assessment"
    r")",
    re.I,
)

# Surface cues for a CAUSAL decision / authorisation gate: a norm whose action
# is made subject to a decision or a prior authorisation. The norm is marked
# gated (predicate "authorised-by").
_AUTHORISATION = re.compile(
    r"\b(?:"
    r"prior\s+(?:authoris\w+|authoriz\w+)"
    r"|subject to\s+(?:a\s+|an\s+|the\s+)?(?:prior\s+)?(?:authoris\w+|authoriz\w+)"
    r"|shall\s+(?:not\s+)?be\s+(?:authoris\w+|authoriz\w+)"
    r"|shall\s+decide"
    r"|(?:authoris\w+|authoriz\w+)\s+(?:granted|given|issued|conferred)\s+by"
    r"|subject to\s+(?:a\s+|an\s+|the\s+)?(?:prior\s+)?decision"
    r")",
    re.I,
)
_LEAD_DETERMINER = re.compile(r"^(?:a|an|the|its|their|any|this|of|in)\s+", re.I)

# The language OWNS the deadline / cross-reference / sanction vocabulary: it
# publishes these cues in extraction.json so the FORMULA-FIELD population below
# consumes them rather than a private second cue set. (The private _DEADLINE /
# _XREF regexes above stay in force purely for the 5D EDGE emission.) Each cue
# set may be a mapping ``{label: pattern}`` or a list of ``{"pattern": ...}``;
# compile whichever shape the pack ships.
def _compile_cue_set(cue_set: Any) -> list[re.Pattern[str]]:
    entries = cue_set.values() if isinstance(cue_set, dict) else (cue_set or [])
    patterns: list[re.Pattern[str]] = []
    for entry in entries:
        pattern = entry["pattern"] if isinstance(entry, dict) else entry
        patterns.append(re.compile(pattern, re.I))
    return patterns


_DEADLINE_CUES = _compile_cue_set(_EX.get("deadline_cues"))
_XREF_CUES = _compile_cue_set(_EX.get("cross_reference_cues"))
_SANCTION_CUES = _compile_cue_set(_EX.get("sanction_cues"))


def _cue_spans(patterns: list[re.Pattern[str]], text: str,
               prefer: tuple[str, ...]) -> list[str]:
    """Spans matched by the published cues (ordered, deduped).

    Prefer a named capture group from ``prefer`` when the pack labels one;
    fall back to the whole match otherwise.
    """
    out: list[str] = []
    for pattern in patterns:
        for m in pattern.finditer(text or ""):
            value = ""
            groups = m.groupdict()
            for name in prefer:
                if groups.get(name):
                    value = m.group(name).strip(" .,;")
                    break
            if not value:
                value = m.group(0).strip(" .,;")
            if value:
                out.append(value)
    return list(dict.fromkeys(out))


def _extract_deadline(text: str) -> str:
    """The norm's stated deadline via the pack's published deadline cues (or "")."""
    spans = _cue_spans(_DEADLINE_CUES, text, ("deadline",))
    return spans[0] if spans else ""


def _deadline_surface(text: str) -> dict[str, Any]:
    """The deadline's recorded surface in ``text``: the FULL published-cue
    match with exact offsets (or ``{}`` when no cue matches).

    ``deadline`` keeps the typed VALUE (the named group); this records WHERE
    the surface sits, so a consumer that needs the deadline text removed can
    anchor on the recorded span instead of re-searching persisted values —
    a re-search can over/under-remove. The surface is exactly as wide as the
    language's published cue, no wider: the language owns the vocabulary.
    """
    for pattern in _DEADLINE_CUES:
        m = pattern.search(text or "")
        if m:
            return {"text": m.group(0), "start": m.start(0), "end": m.end(0)}
    return {}


def _extract_cross_references(text: str) -> list[str]:
    """Cross-references the norm cites via the pack's published cross-ref cues."""
    return _cue_spans(_XREF_CUES, text, ("ref",))


def _extract_sanction(text: str) -> str:
    """The norm's stated sanction via the pack's published sanction cues (or "")."""
    spans = _cue_spans(_SANCTION_CUES, text, ("sanction", "amount"))
    return spans[0] if spans else ""


def _clean_span(span: str) -> str:
    """Drop a leading determiner and surrounding punctuation from a cue span."""
    return _LEAD_DETERMINER.sub("", span.strip()).strip(" .,;")


def _extract_artifacts(text: str) -> list[str]:
    """Named required artifacts / deliverables in the norm's text (ordered, deduped)."""
    spans = [m.group("artifact") for m in _ARTIFACT_VERB.finditer(text)]
    spans += [m.group("artifact") for m in _ARTIFACT_NAMED.finditer(text)]
    cleaned = [c for c in (_clean_span(s) for s in spans) if c]
    return list(dict.fromkeys(cleaned))


def _extract_authorisations(text: str) -> list[str]:
    """Decision / authorisation gate cues in the norm's text (ordered, deduped)."""
    spans = (_clean_span(m.group(0)) for m in _AUTHORISATION.finditer(text))
    return list(dict.fromkeys(s for s in spans if s))


def _extract_definition(sentence: str) -> Optional[dict[str, str]]:
    """Detect a defined term and its definition body, or ``None``.

    Tries the quoted form first (``'X' means …`` / ``'X' shall mean …``), then
    the unquoted ``X shall mean …`` form. Deterministic, regex-only.
    """
    match = _DEFINITION.search(sentence) or _DEFINITION_SHALL.match(sentence)
    if match is None:
        return None
    term = match.group("term").strip().strip(_Q_OPEN + _Q_CLOSE).strip(" ,")
    definition = match.group("definition").strip(" .;")
    if not term or not definition:
        return None
    return {"term": term, "definition": definition}


def _norm_edges(nid: str, f: Any, raw: str) -> list[dict[str, Any]]:
    """Project one norm across the fixed 5D, not just the operator's affinity.

    STRUCTURAL — the norm is built around its action (part-of).
    CAUSAL     — the operator (O/F) governs, the condition triggers, the
                 exception defeats.
    INTENTIONAL— the norm binds its bearer (the addressee it exists for; also
                 where a permission/right's affinity lands).
    TEMPORAL   — a deadline stated in the norm's text.
    RELATIONAL — cross-references to other provisions (and the always-true floor).
    """
    edges: list[dict[str, Any]] = [
        {"subject": nid, "predicate": "concerns", "object": f.action,
         "dimension": "structural", "norm": nid},
        {"subject": f.bearer, "predicate": f.operator, "object": f.action,
         "dimension": deontic.dimension_affinity(f.operator), "norm": nid},
        {"subject": nid, "predicate": "binds", "object": f.bearer,
         "dimension": "intentional", "norm": nid},
    ]
    if f.condition:
        edges.append({"subject": f.condition, "predicate": "triggers",
                      "object": nid, "dimension": "causal", "norm": nid})
    if f.exception:
        edges.append({"subject": f.exception, "predicate": "defeated-by",
                      "object": nid, "dimension": "causal", "norm": nid})
    haystack = " ".join((f.condition, f.action, f.exception, raw))
    for span in dict.fromkeys(m.group(0).strip() for m in _DEADLINE.finditer(haystack)):
        edges.append({"subject": nid, "predicate": "due-by", "object": span,
                      "dimension": "temporal", "norm": nid})
    for span in dict.fromkeys(m.group(0).strip() for m in _XREF.finditer(raw)):
        edges.append({"subject": nid, "predicate": "refers-to", "object": span,
                      "dimension": "relational", "norm": nid})
    # STRUCTURAL — a required artifact / deliverable the norm calls for.
    for artifact in _extract_artifacts(raw):
        edges.append({"subject": nid, "predicate": "requires-artifact",
                      "object": artifact, "dimension": "structural", "norm": nid})
    # CAUSAL — a decision / prior-authorisation gate on the norm's action.
    for gate in _extract_authorisations(raw):
        edges.append({"subject": nid, "predicate": "authorised-by",
                      "object": gate, "dimension": "causal", "norm": nid})
    return edges


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
        definitions = 0
        for sentence_index, sentence in enumerate(_sentences(text), start=1):
            definition = _extract_definition(sentence)
            if definition is not None:
                # A definition is not a norm — it takes precedence so a
                # "shall mean" phrasing is never mis-read as an obligation.
                term_hash = hashlib.sha256(
                    definition["term"].encode("utf-8")).hexdigest()[:16]
                did = f"definition:{source_hash}:{sentence_index}:{term_hash}"
                nodes.append({
                    "id": did, "kind": "definition",
                    "term": definition["term"],
                    "definition": definition["definition"],
                    "provenance": {"source_sentence": sentence},
                })
                edges.append({
                    "subject": did, "predicate": "defines",
                    "object": definition["term"], "dimension": "structural",
                    "norm": did,
                })
                definitions += 1
                continue
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
            # Populate the typed formula fields from the LANGUAGE's published
            # cues so the solver's norm_contract can consume typed
            # deadlines / cross-refs / sanctions. Read the norm's own text.
            deadline = _extract_deadline(slots["raw"])
            # The surface span is anchored on the ACTION slot (the field a
            # consumer would trim), not on raw: offsets index the persisted
            # action string, and node["action"][start:end] == text holds.
            deadline_surface = _deadline_surface(slots["action"])
            cross_references = _extract_cross_references(slots["raw"])
            sanction = _extract_sanction(slots["raw"])
            f = deontic.formula_from_fields(
                slots["modal"], slots["subject"], slots["action"],
                condition=slots["condition"], exception=slots["exception"],
                incident=incident, deadline=deadline,
                cross_references=cross_references, sanction=sanction,
                raw_sentence=slots["raw"])
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
                "deadline": deadline, "deadline_surface": deadline_surface,
                "cross_references": cross_references,
                "sanction": sanction,
                "provenance": {"source_sentence": slots["raw"]},
            })
            edges.extend(_norm_edges(nid, f, slots["raw"]))

        conflicts = deontic.detect_conflicts(formulae)
        return Subgraph(
            dimension=_EX["dimension"], nodes=nodes, edges=edges,
            rejections=rejections,
            provenance={"ingester": self.id, "language_version": deontic.language_version(),
                        "recognised": recognised, "lowered": len(formulae),
                        "rejected": len(rejections), "definitions": definitions,
                        "conflicts": conflicts,
                        "actor": context.get("actor", "")},
        )
