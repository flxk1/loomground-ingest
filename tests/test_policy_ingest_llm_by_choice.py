# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""LLM is allowed BY CHOICE — the opt-in, fenced enrichment path, driven through the
INJECTION seam (``llm_proposer=`` / ``set_default_proposer``), never a real model.

The deterministic extractor (LLM off) mis-reads a passive prohibition
("Candidate photos must not be shared externally." -> kind 'be_shared_externally').
This is the residual the phrasing-reliability matrix leaves red on purpose.

When a caller OPTS IN (use_llm=True) and a proposer is wired, the proposer recovers the
correct primitive ('share_candidate_photo') — but only through two fail-closed gates:
  * GROUNDED  — the proposal's quote must occur verbatim in the policy (no hallucination);
  * WELL-FORMED + Loomground-validated like every other primitive.
So this proves: (1) LLM off is unchanged/deterministic; (2) LLM on recovers what cues miss;
(3) an ungrounded proposal is refused even with the LLM on. The built-in local-model route
stays a host concern (RVND); this package exposes only the injection seam.
"""
from __future__ import annotations

from loomground_ingest.governance import compiler as PI

PHOTO = "Candidate photos must not be shared externally."


def _prohibit_kinds(twin):
    return {p["kind"] for p in (twin.get("patch") or {}).get("prohibitions", [])}


def test_llm_off_is_deterministic_and_misses_the_passive_prohibition():
    twin = PI.ingest(PHOTO)                      # default: LLM off
    assert twin["ok"] and twin["llm_used"] is False
    assert "share_candidate_photo" not in _prohibit_kinds(twin)   # the documented gap


def test_llm_by_choice_recovers_the_correct_primitive_when_grounded():
    def proposer(text, ctx):
        # a local model would return this; the quote is copied verbatim from the policy
        return [{"declaration": "prohibit", "kind": "share candidate photo",
                 "quote": "Candidate photos must not be shared externally"}]

    twin = PI.ingest(PHOTO, use_llm=True, llm_proposer=proposer)
    assert twin["ok"] and twin["llm_used"] is True
    assert "share_candidate_photo" in _prohibit_kinds(twin)        # recovered by choice
    # SUPERSEDE: the grounded proposal REPLACES the same-sentence deterministic mis-read,
    # it does not sit beside it — so the wrong 'be_shared_externally' is gone.
    assert _prohibit_kinds(twin) == {"share_candidate_photo"}
    # provenance: the recovered primitive is tagged as LLM-origin, not silently merged
    llm_prohibitions = [p for p in twin["patch"]["prohibitions"] if p.get("origin") == "llm"]
    assert any(p["kind"] == "share_candidate_photo" for p in llm_prohibitions)
    # internal provenance is not leaked into the twin
    assert all("_src" not in p for p in twin["patch"]["prohibitions"])


def test_ungrounded_llm_proposal_is_refused_even_when_opted_in():
    def hallucinating_proposer(text, ctx):
        return [{"declaration": "prohibit", "kind": "appoint blockchain officer",
                 "quote": "the company shall appoint a blockchain officer"}]  # NOT in the policy

    twin = PI.ingest(PHOTO, use_llm=True, llm_proposer=hallucinating_proposer)
    assert twin["ok"] and twin["llm_used"] is True
    assert "appoint_blockchain_officer" not in _prohibit_kinds(twin)  # grounding fence held


def test_use_llm_without_proposer_degrades_to_deterministic():
    # No proposer wired (and no default registered): opting in must degrade to the exact
    # deterministic result and report llm_used=False — this package has no built-in route.
    PI.set_default_proposer(None)
    twin = PI.ingest(PHOTO, use_llm=True)
    assert twin["ok"] and twin["llm_used"] is False
    assert _prohibit_kinds(twin) == {"be_shared_externally"}         # deterministic, no crash
    assert twin["capability"] is None


def test_default_proposer_registration_is_opt_in():
    captured = {}

    def proposer(text, ctx):
        captured["called"] = True
        return []

    PI.set_default_proposer(proposer)
    try:
        PI.ingest(PHOTO)                          # use_llm=False -> proposer NOT consulted
        assert "called" not in captured
        PI.ingest(PHOTO, use_llm=True)            # opt-in -> default proposer consulted
        assert captured.get("called") is True
    finally:
        PI.set_default_proposer(None)


def test_ambiguous_short_quote_cannot_wipe_unrelated_rules():
    # a short grounded quote ("approved by") substring-matches MANY sentences; supersede is a
    # DELETION of genuine rules, so an ambiguous quote must evict NOTHING (fail-closed).
    policy = ("Offer letters must be approved by the hr manager. "
              "Terminations must be approved by legal counsel.")

    def proposer(text, ctx):
        return [{"declaration": "reserve", "kind": "coffee order", "by": "barista",
                 "quote": "approved by"}]           # verbatim, grounded — but ambiguous

    base = PI.ingest(policy)                        # deterministic rules to protect
    kinds0 = {r["kind"] for r in base["patch"]["reservations"]}
    assert len(kinds0) >= 2

    twin = PI.ingest(policy, use_llm=True, llm_proposer=proposer)
    kinds = {r["kind"] for r in twin["patch"]["reservations"]}
    assert kinds0 <= kinds                          # NO genuine rule was evicted


def test_unambiguous_supersede_still_works():
    # the legit case — a quote identifying exactly ONE provision still replaces that
    # provision's deterministic mis-read (pinned above in the recovery test too).
    def proposer(text, ctx):
        return [{"declaration": "prohibit", "kind": "share candidate photo",
                 "quote": "Candidate photos must not be shared externally"}]
    twin = PI.ingest(PHOTO, use_llm=True, llm_proposer=proposer)
    assert {p["kind"] for p in twin["patch"]["prohibitions"]} == {"share_candidate_photo"}
