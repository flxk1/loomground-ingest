# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Required-artifact detection — the curated compliance-artifact catalogue.

A normative provision often *implies a deliverable*: an Art. 28 GDPR processing
contract, a Records of Processing register, a DPIA, a Risk Management System.
This module owns the catalogue that maps trigger phrases (EN + DE) to a canonical
artifact name and a category, and the deterministic scan that surfaces the
required artifacts in a piece of text — scoring higher when an obligation cue
(*shall / must / ist verpflichtet*) sits near the trigger, so a genuine
requirement outranks a bare mention.

This is the single home for that vocabulary in the ingest plane, so a consumer
(a governance orchestrator, a compliance dispatcher) *consumes* it rather than
carrying its own parallel catalogue. It is distinct from — and complementary to —
the deontic ingester's surface artifact-noun tagging (which projects bare artifact
nouns onto a norm's STRUCTURAL edges): this module resolves the *canonical* named
artifact and its category for compliance analysis. Deterministic, stdlib only.

Categories: ``contract`` · ``register`` · ``assessment`` · ``policy`` ·
``appointment`` · ``technical``.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

__all__ = [
    "ArtifactSpec", "RequiredArtifact", "CATEGORIES",
    "ARTIFACT_CATALOGUE", "extract_required_artifacts",
]

CATEGORIES: frozenset[str] = frozenset(
    {"contract", "register", "assessment", "policy", "appointment", "technical"})


@dataclass(frozen=True)
class ArtifactSpec:
    """One catalogue entry: a canonical artifact, its category, and the lowercase
    trigger phrases (EN + DE) that name it. Triggers are matched case-insensitively
    as substrings, kept specific enough not to fire on prose that merely mentions
    the noun."""

    key: str
    canonical: str
    category: str
    triggers: tuple[str, ...]


# The curated catalogue, scoped to the target domains (GDPR / AI Act / NIS2 /
# DORA / contracts). Extend this tuple to add an artifact — this is the one place
# the vocabulary lives.
ARTIFACT_CATALOGUE: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        "dpa", "Data Processing Agreement (Art. 28 GDPR)", "contract",
        ("processing shall be governed by a contract", "data processing agreement",
         "processor shall be bound by a contract", "auftragsverarbeitungsvertrag",
         "governed by a contract or other legal act")),
    ArtifactSpec(
        "sccs", "Standard Contractual Clauses", "contract",
        ("standard contractual clauses", "standardvertragsklauseln",
         "appropriate safeguards for the transfer")),
    ArtifactSpec(
        "ropa", "Records of Processing Activities (Art. 30 GDPR)", "register",
        ("record of processing activities", "records of processing",
         "verzeichnis von verarbeitungstätigkeiten", "maintain a record of")),
    ArtifactSpec(
        "dpia", "Data Protection Impact Assessment (Art. 35 GDPR)", "assessment",
        ("data protection impact assessment", "impact assessment",
         "datenschutz-folgenabschätzung", "carry out an assessment of the impact")),
    ArtifactSpec(
        "fria", "Fundamental Rights Impact Assessment (Art. 27 AI Act)", "assessment",
        ("fundamental rights impact assessment",
         "impact assessment on fundamental rights")),
    ArtifactSpec(
        "conformity-assessment", "Conformity Assessment (AI Act)", "assessment",
        ("conformity assessment", "konformitätsbewertung",
         "undergo the relevant conformity assessment")),
    ArtifactSpec(
        "privacy-policy", "Privacy Policy / Information Notice (Arts. 13–14 GDPR)",
        "policy",
        ("privacy policy", "privacy notice", "information to be provided",
         "datenschutzerklärung", "transparency information")),
    ArtifactSpec(
        "dpo", "Data Protection Officer designation (Art. 37 GDPR)", "appointment",
        ("designate a data protection officer", "data protection officer",
         "datenschutzbeauftragten benennen", "appoint a data protection officer")),
    ArtifactSpec(
        "eu-representative", "EU Representative designation", "appointment",
        ("designate a representative in the union", "eu representative",
         "appoint a representative", "vertreter in der union")),
    ArtifactSpec(
        "toms", "Technical and Organisational Measures", "technical",
        ("technical and organisational measures",
         "technische und organisatorische maßnahmen",
         "appropriate technical and organisational")),
    ArtifactSpec(
        "incident-register", "Incident / Breach Register", "register",
        ("document any personal data breach", "record of incidents",
         "log of incidents", "register of incidents", "breach notification")),
    ArtifactSpec(
        "risk-management-system", "Risk Management System (Art. 9 AI Act)", "technical",
        ("risk management system", "risikomanagementsystem",
         "establish, implement, document and maintain a risk management")),
    ArtifactSpec(
        "technical-documentation", "Technical Documentation (Annex IV AI Act)",
        "register",
        ("technical documentation", "technische dokumentation",
         "draw up the technical documentation")),
    ArtifactSpec(
        "logs", "Automatic Logging / Record-keeping (Art. 12 AI Act)", "technical",
        ("automatic recording of events", "logging capabilities",
         "keep the logs", "record-keeping")),
)

# Every catalogue category is a declared one (a typo in a new row fails fast).
assert all(spec.category in CATEGORIES for spec in ARTIFACT_CATALOGUE)

# An obligation cue near a trigger raises confidence: the artifact is *required*,
# not merely mentioned.
_OBLIGATION_CUE = re.compile(
    r"\b(shall|must|is\s+required\s+to|are\s+required\s+to|obliged\s+to|"
    r"muss|müssen|ist\s+verpflichtet|sind\s+verpflichtet|hat\s+zu|haben\s+zu)\b",
    re.IGNORECASE)
_OBLIGATION_WINDOW = 160   # chars around the trigger to look for an obligation cue

_BASE_CONFIDENCE = 0.6
_OBLIGATION_BONUS = 0.3


@dataclass(frozen=True)
class RequiredArtifact:
    """A required artifact surfaced in text: the canonical name and category, the
    trigger phrase that matched, whether an obligation cue sits nearby, a snippet
    of the surrounding text, and a confidence in ``[0, 1]``."""

    key: str
    canonical: str
    category: str
    trigger_phrase: str
    obligated: bool
    snippet: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_required_artifacts(content: str) -> list[RequiredArtifact]:
    """Scan ``content`` for obligations that imply a required artifact.

    Deduplicates by artifact key — the highest-confidence hit per artifact wins,
    so an artifact named with a nearby obligation cue ("shall maintain a *record
    of processing*") outranks a bare mention. Results are returned in catalogue
    order (deterministic). Invents nothing: an artifact absent from the text is
    simply not returned.
    """
    low = (content or "").lower()
    found: dict[str, RequiredArtifact] = {}
    for spec in ARTIFACT_CATALOGUE:
        for trig in spec.triggers:
            idx = low.find(trig)
            if idx == -1:
                continue
            start = max(0, idx - _OBLIGATION_WINDOW)
            end = min(len(content), idx + len(trig) + _OBLIGATION_WINDOW)
            window = content[start:end]
            obligated = bool(_OBLIGATION_CUE.search(window))
            conf = _BASE_CONFIDENCE + (_OBLIGATION_BONUS if obligated else 0.0)
            conf = round(min(1.0, conf), 3)
            existing = found.get(spec.key)
            if existing is None or conf > existing.confidence:
                found[spec.key] = RequiredArtifact(
                    key=spec.key, canonical=spec.canonical, category=spec.category,
                    trigger_phrase=trig, obligated=obligated,
                    snippet=window.strip()[:240], confidence=conf)
    return list(found.values())
