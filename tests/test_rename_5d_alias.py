# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The federation -> 5D rename: the new name works, the old name is a deprecated alias.

``FEDERATION_EDGE_DIMENSIONS`` is retired in favor of ``EDGE_DIMENSIONS_5D``; the old
name stays importable from both ``loomground_ingest`` and ``loomground_ingest.types``,
warns ``DeprecationWarning`` on access, and is the identical object (``is``) as the
new name — never a copy that could drift.
"""
from __future__ import annotations

import pytest

import loomground_ingest
import loomground_ingest.types as types_module
from loomground_ingest import EDGE_DIMENSIONS_5D
from loomground_ingest.types import EDGE_DIMENSIONS_5D as types_edge_dimensions_5d


def test_edge_dimensions_5d_is_the_new_name():
    assert EDGE_DIMENSIONS_5D == {
        "structural", "causal", "intentional", "temporal", "relational",
    }
    assert types_edge_dimensions_5d is EDGE_DIMENSIONS_5D


def test_federation_edge_dimensions_alias_from_package_warns_and_is_identical():
    with pytest.warns(DeprecationWarning):
        old = loomground_ingest.FEDERATION_EDGE_DIMENSIONS
    assert old is EDGE_DIMENSIONS_5D


def test_federation_edge_dimensions_alias_from_types_module_warns_and_is_identical():
    with pytest.warns(DeprecationWarning):
        old = types_module.FEDERATION_EDGE_DIMENSIONS
    assert old is EDGE_DIMENSIONS_5D


def test_unknown_attribute_still_raises_attribute_error():
    with pytest.raises(AttributeError):
        loomground_ingest.NOT_A_REAL_ATTRIBUTE
    with pytest.raises(AttributeError):
        types_module.NOT_A_REAL_ATTRIBUTE


def test_import_from_package_path_warns_and_is_identical():
    # The literal ``from loomground_ingest import FEDERATION_EDGE_DIMENSIONS`` form.
    with pytest.warns(DeprecationWarning):
        from loomground_ingest import FEDERATION_EDGE_DIMENSIONS
    assert FEDERATION_EDGE_DIMENSIONS is EDGE_DIMENSIONS_5D


def test_import_from_types_module_path_warns_and_is_identical():
    # The literal ``from loomground_ingest.types import FEDERATION_EDGE_DIMENSIONS`` form.
    with pytest.warns(DeprecationWarning):
        from loomground_ingest.types import FEDERATION_EDGE_DIMENSIONS
    assert FEDERATION_EDGE_DIMENSIONS is EDGE_DIMENSIONS_5D
