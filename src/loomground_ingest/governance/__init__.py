# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Governance ingest — the policy compiler and its consumed ingester.

The compiler lowers governance policy text to a validated digital twin (the
express/policy/host classification, a v0.5 ``.lg`` patch, its projection and
netlist), consuming ``loomground-solver`` for validation/projection. The
:class:`GovernanceIngester` adapts that twin into a dimensioned ``Subgraph`` for
the ingest plane, keeping ``id = "policy"``.
"""
from . import compiler, genre_router, legal_norm_splitter, policy_normalise
from .compiler import ingest, set_default_proposer
from .ingester import GovernanceIngester

__all__ = [
    "GovernanceIngester",
    "ingest",
    "set_default_proposer",
    "compiler",
    "genre_router",
    "legal_norm_splitter",
    "policy_normalise",
]
