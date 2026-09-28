# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""A deontic operator edge is ought, not is: it carries no 5D dimension.

The deontic plane's dimension_affinity() returns None for O, P and F. The
subgraph validator must accept exactly those edges without a dimension and
still reject any other edge that lacks one.
"""
from __future__ import annotations

from loomground_ingest import DeonticIngester
from loomground_ingest.types import OPERATOR_PREDICATES, Subgraph, validate_subgraph


def test_ingested_norm_is_valid_with_a_dimensionless_operator_edge():
    sg = DeonticIngester().ingest(
        "The controller shall notify the supervisory authority without undue delay.", {})
    operator_edges = [e for e in sg.edges if e.get("predicate") in OPERATOR_PREDICATES]
    assert operator_edges, "the norm must carry its operator edge"
    assert all(e.get("dimension") is None for e in operator_edges)
    assert validate_subgraph(sg) == []


def _one_edge(edge):
    return Subgraph(dimension="nD", nodes=[{"id": "n1"}], edges=[edge])


def test_operator_edge_without_dimension_is_valid():
    edge = {"subject": "controller", "predicate": "O", "object": "notify", "dimension": None, "norm": "n1"}
    assert "invalid edge dimension" not in validate_subgraph(_one_edge(edge))


def test_other_edge_without_dimension_is_rejected():
    edge = {"subject": "n1", "predicate": "concerns", "object": "notify", "dimension": None, "norm": "n1"}
    assert "invalid edge dimension" in validate_subgraph(_one_edge(edge))
