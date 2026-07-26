# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Ingester registry and dispatch.

Dispatch tries each registered grammar predicate in registration order and
returns the first match; text no grammar claims falls to the registered
fallback (an ingester whose ``grammar()`` is ``None``). With no match and no
fallback, dispatch returns ``None`` and the caller reports an un-ingestable
input rather than guessing.
"""
from __future__ import annotations

from typing import Optional

from .types import Ingester


class IngesterRegistry:
    def __init__(self) -> None:
        self._ingesters: list[Ingester] = []
        self._fallback: Optional[Ingester] = None

    def register(self, ingester: Ingester) -> None:
        """Register an ingester. One with ``grammar() is None`` becomes the
        fallback; registering a second fallback is refused so dispatch stays
        deterministic."""
        if ingester.grammar() is None:
            if self._fallback is not None:
                raise ValueError(
                    f"fallback already registered ({self._fallback.id!r}); "
                    f"{ingester.id!r} cannot also be best-guess-only")
            self._fallback = ingester
        else:
            self._ingesters.append(ingester)

    def dispatch(self, text: str) -> Optional[Ingester]:
        for ing in self._ingesters:
            pred = ing.grammar()
            if pred is not None and pred(text):
                return ing
        return self._fallback

    def ids(self) -> list[str]:
        out = [i.id for i in self._ingesters]
        if self._fallback is not None:
            out.append(self._fallback.id)
        return out
