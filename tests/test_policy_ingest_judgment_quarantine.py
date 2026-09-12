# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Genre routing in front of the governance compiler: court judgments are quarantined
(routed to the interpreter, no governance patch), while genuine policies compile normally.

Host integration tests may read real decisions and frameworks from a local
corpus through format-aware extractors. Here the judgment is a synthetic fixture
carrying the co-occurring decision-structure markers the neutral engine
fingerprints, so the quarantine path is proven without a host dependency.
"""
from __future__ import annotations

from loomground_ingest.governance import compiler as policy_ingest
from loomground_ingest.governance import genre_router

from tests.test_policy_ingest import POLICY   # the golden fixture — shared, not copied

# A court decision fingerprint: several German judgment-structure markers co-occur
# (Urteil, Leitsatz, Tatbestand, Entscheidungsgründe, Rn.) — well over the >=3 threshold.
JUDGMENT = (
    "BGH, Urteil vom 12. Mai 2021 - I ZR 123/20\n\n"
    "Leitsatz\n"
    "Der Betreiber haftet fuer Rechtsverletzungen, sobald er Kenntnis erlangt.\n\n"
    "Tatbestand\n"
    "Die Klaegerin nimmt die Beklagte auf Unterlassung in Anspruch. Rn. 1\n\n"
    "Entscheidungsgruende\n"
    "Die Revision ist unbegruendet. Der Anspruch folgt aus dem Gesetz. Rn. 15\n"
)


def test_judgment_is_quarantined_no_patch():
    assert genre_router.detect_genre(JUDGMENT) == "case-law"
    t = policy_ingest.ingest(JUDGMENT)
    assert t["ok"] is True                       # a judgment is valid input, just not a policy
    assert t.get("quarantined") is True
    assert t.get("genre") == "case-law"
    assert t.get("routed_to") == "interpreter"
    assert t.get("patch") is None                # no governance patch from a court's reasoning
    assert "netlist" not in t
    assert t["classification"]["express"] == []


def test_golden_policy_not_falsely_quarantined():
    assert genre_router.detect_genre(POLICY) != "case-law"
    t = policy_ingest.ingest(POLICY)
    assert t["ok"] is True
    assert not t.get("quarantined")
    assert t.get("patch") is not None
    assert "reserve automated_hiring_decision by compliance_officer" in t["classification"]["express"]
