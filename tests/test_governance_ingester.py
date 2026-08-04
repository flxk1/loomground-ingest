# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The consumed GovernanceIngester: it lowers a policy twin to a valid nD Subgraph,
keeps id="policy", carries the language-chain provenance, and quarantines a judgment.
"""
from __future__ import annotations

from loomground_ingest import GovernanceIngester, validate_subgraph

from tests.test_policy_ingest import POLICY
from tests.test_policy_ingest_judgment_quarantine import JUDGMENT


def test_ingester_id_is_policy():
    assert GovernanceIngester().id == "policy"


def test_policy_lowers_to_valid_nd_subgraph():
    graph = GovernanceIngester().ingest(POLICY, {})
    assert validate_subgraph(graph) == []
    assert graph.dimension == "nD"
    assert graph.quarantined is False
    assert graph.status == "complete"
    assert graph.nodes and graph.edges
    # the actor and the express gates surface as nodes
    node_ids = {n["id"] for n in graph.nodes}
    assert "ai_system" in node_ids
    assert "automated_hiring_decision" in node_ids
    # provenance records both language packs in the chain
    chain = graph.provenance["language_chain"]
    assert chain["governance"]["package"] == "loomground-governance"
    assert chain["deontic"]["package"] == "loomground-deontic"
    assert graph.provenance["ingester"] == "policy"


def test_grammar_claims_governance_policy():
    recognises = GovernanceIngester().grammar()
    assert recognises(POLICY) is True
    assert recognises("The weather is pleasant today.") is False


def test_judgment_is_quarantined_and_writer_would_refuse():
    graph = GovernanceIngester().ingest(JUDGMENT, {})
    assert graph.quarantined is True
    assert graph.status == "quarantined"
    assert graph.nodes == [] and graph.edges == []
    # a quarantined subgraph carrying no semantic content is a valid contract shape
    assert validate_subgraph(graph) == []
