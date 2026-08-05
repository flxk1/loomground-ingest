# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Composition: one policy item -> deontic norm + factual condition + epistemic facet.

Proves ingest carries MULTIPLE nD contributions per norm, merged on the shared
5D+node-id. The base DeonticIngester stays pure; enrich_subgraph composes.
"""
from __future__ import annotations

import pytest

# Composition is an opt-in extra; skip cleanly when its languages aren't installed.
pytest.importorskip("loomground_factual")
pytest.importorskip("loomground_epistemic")

from loomground_ingest import DeonticIngester, enrich_subgraph  # noqa: E402


def _norms(sg):
    return [n for n in sg.nodes if n.get("kind") == "norm"]


def test_factual_condition_becomes_a_5d_edge():
    sg = DeonticIngester().ingest(
        "If the data is sensitive, the controller shall notify the authority.", {})
    enrich_subgraph(sg)
    n = _norms(sg)[0]
    assert n["operator"] == "O" and n["bearer"] == "controller"
    # condition lowered to a structured fact, not opaque text
    fact = n.get("condition_fact")
    assert fact and fact["subject"] == "data" and "sensitive" in fact["object"]
    # a causal "conditioned-by" edge now carries the fact into the graph
    assert any(e.get("origin") == "factual" and e.get("norm") == n["id"]
               for e in sg.edges)


def test_epistemic_trigger_becomes_an_nd_facet():
    sg = DeonticIngester().ingest(
        "If the controller has reasonable grounds to believe processing is unlawful, "
        "it shall cease the processing.", {})
    enrich_subgraph(sg)
    n = _norms(sg)[0]
    facet = n.get("epistemic")
    assert facet and facet["system_id"] == "system:epistemic"
    assert facet["operator"] == "B" and facet["certainty"] == "reasonable-grounds"
    assert facet["holder"] == "controller"


def test_base_ingester_stays_pure_without_compose():
    # no enrichment unless composed — the deontic contract is unchanged
    sg = DeonticIngester().ingest(
        "If the data is sensitive, the controller shall notify the authority.", {})
    n = _norms(sg)[0]
    assert "epistemic" not in n and "condition_fact" not in n
