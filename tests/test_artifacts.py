# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Required-artifact catalogue — branch-level tests.

The scan resolves a canonical named artifact + category from trigger phrases
(EN + DE), scores an obligation cue near the trigger, dedupes by key keeping the
highest-confidence hit, and invents nothing when the artifact is absent.
"""
from __future__ import annotations

from loomground_ingest import (
    ARTIFACT_CATALOGUE,
    CATEGORIES,
    RequiredArtifact,
    extract_required_artifacts,
)


def _by_key(hits: list[RequiredArtifact]) -> dict[str, RequiredArtifact]:
    return {h.key: h for h in hits}


def test_obligation_cue_near_trigger_scores_higher():
    hits = _by_key(extract_required_artifacts(
        "The controller shall maintain a record of processing activities."))
    assert "ropa" in hits
    ropa = hits["ropa"]
    assert ropa.canonical == "Records of Processing Activities (Art. 30 GDPR)"
    assert ropa.category == "register"
    assert ropa.obligated is True
    assert ropa.confidence == 0.9        # base 0.6 + obligation 0.3


def test_bare_mention_without_obligation_scores_lower():
    hits = _by_key(extract_required_artifacts(
        "A record of processing activities is one artefact among many."))
    assert hits["ropa"].obligated is False
    assert hits["ropa"].confidence == 0.6


def test_german_trigger_matches():
    hits = _by_key(extract_required_artifacts(
        "Der Verantwortliche muss ein Verzeichnis von Verarbeitungstätigkeiten führen."))
    assert "ropa" in hits
    assert hits["ropa"].obligated is True   # 'muss' is a German obligation cue


def test_multiple_distinct_artifacts_surface_together():
    hits = _by_key(extract_required_artifacts(
        "The provider must establish a risk management system and carry out a "
        "data protection impact assessment before deployment."))
    assert {"risk-management-system", "dpia"} <= set(hits)
    assert hits["risk-management-system"].category == "technical"
    assert hits["dpia"].category == "assessment"


def test_dedup_by_key_keeps_highest_confidence():
    # Same artifact appears twice — once bare, once under an obligation. One hit,
    # the obligated (higher-confidence) one wins.
    hits = extract_required_artifacts(
        "A data processing agreement was mentioned. Separately, processing shall "
        "be governed by a contract or other legal act between the parties.")
    dpas = [h for h in hits if h.key == "dpa"]
    assert len(dpas) == 1
    assert dpas[0].obligated is True and dpas[0].confidence == 0.9


def test_absent_artifact_is_never_invented():
    hits = extract_required_artifacts(
        "The weather today is fine and the meeting went well.")
    assert hits == []


def test_results_are_deterministic_catalogue_order():
    text = ("draw up the technical documentation; designate a data protection "
            "officer; standard contractual clauses apply.")
    keys_a = [h.key for h in extract_required_artifacts(text)]
    keys_b = [h.key for h in extract_required_artifacts(text)]
    assert keys_a == keys_b
    # order follows the catalogue, not the text
    cat_order = [s.key for s in ARTIFACT_CATALOGUE]
    assert keys_a == [k for k in cat_order if k in set(keys_a)]


def test_every_catalogue_category_is_declared():
    assert {s.category for s in ARTIFACT_CATALOGUE} <= CATEGORIES


def test_to_dict_round_trips_fields():
    hit = extract_required_artifacts(
        "The controller shall appoint a data protection officer.")[0]
    d = hit.to_dict()
    assert d["key"] == "dpo" and d["category"] == "appointment"
    assert set(d) == {"key", "canonical", "category", "trigger_phrase",
                      "obligated", "snippet", "confidence"}
