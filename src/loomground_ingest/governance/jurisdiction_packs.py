# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Jurisdiction packs — CARRIED DATA, not engine (judgment-marker subset).

The genre engine is jurisdiction-NEUTRAL: it walks a registry. WHAT a court
judgment looks like is a fact about *particular* legal systems — carried here as
plain data with a registration seam, not authored by the engine.

This module carries only the judgment-structure markers the governance ingest
compiler needs to recognise a court decision (so a holding never reaches the
express compiler). Shipped packs are the jurisdictions the compiler has needed so
far — ``de`` / ``eu`` / ``en-uk`` — a starting library, not a claim of coverage.
Add a jurisdiction by REGISTERING a pack; no engine change:

    from loomground_ingest.governance import jurisdiction_packs as JP
    JP.register_judgment_markers("us", [r"\\bU\\.S\\.\\b", ...])

Pure data + a tiny registry. No imports from the engines (they import *this*).
"""
from __future__ import annotations

# ── Judgment-structure markers (genre fingerprints for "this is a court decision") ────────
_MARKER_PACKS: dict[str, list[str]] = {}


def register_judgment_markers(pack_id: str, patterns: list[str]) -> None:
    _MARKER_PACKS[pack_id] = list(patterns)


def judgment_marker_patterns() -> list[str]:
    return [p for pats in _MARKER_PACKS.values() for p in pats]


register_judgment_markers("de", [
    r"\bLeitsa(?:tz|tze|tzes)\b", r"\bTatbestand\b", r"\bEntscheidungsgr(?:ü|ue)nde\b",
    r"\b(?:Urteil|Beschluss)\b", r"\bRn\.?\s*\d+",
    r"\b[IVX]+\s*ZR\s*\d+/\d+|\bKVR\s*\d+/\d+|\bB\d\s*-\d+/\d+",
])
register_judgment_markers("eu", [
    r"\bECLI:", r"\bJudgment of the Court\b",
    r"\bOpinion of (?:the )?Advocate General\b",
])
register_judgment_markers("en-uk", [
    r"\bthe Court\s+(?:holds?|held|finds?|found|rules?|ruled)\b",
    r"\[\d{4}\]\s+(?:UKSC|EWCA|EWHC|UKHL|AC|QB|WLR|CSOH|IESC)\b",
])
