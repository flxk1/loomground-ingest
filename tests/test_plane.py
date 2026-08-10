# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""The ingest-plane framework, standalone: dispatch, the writer seam, and the
pipeline. A fake ingester stands in for a host's real one.

Run: python -m pytest -q
"""
from __future__ import annotations

import deontic
import pytest

from loomground_ingest import (
    DEFAULT_MAX_INPUT_CHARS,
    CollectingWriter,
    DeonticIngester,
    IngesterRegistry,
    Subgraph,
    ingest_artifact,
    ingest_text,
    node_identity,
    validate_subgraph,
    versum_writer,
)
from loomground_ingest.types import Ingester


class _KnowledgeIngester:
    """Fake 5D ingester: any text, one node per line, grammar on a prefix."""

    id = "knowledge"

    def grammar(self):
        return lambda t: t.strip().lower().startswith("claim:")

    def ingest(self, text, ctx):
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return Subgraph(dimension="5D",
                        nodes=[{"id": i, "text": ln} for i, ln in enumerate(lines)],
                        provenance={"ingester": self.id})


class _FallbackIngester:
    id = "fallback"

    def grammar(self):
        return None

    def ingest(self, text, ctx):
        return Subgraph(dimension="nD", nodes=[{"id": "fallback:1", "text": text}],
                        provenance={"ingester": self.id})


class _QuarantiningIngester:
    id = "quarantine"

    def grammar(self):
        return None

    def ingest(self, text, ctx):
        return Subgraph(dimension="nD", quarantined=True,
                        provenance={"ingester": self.id})


def test_ingesters_satisfy_protocol():
    assert isinstance(_KnowledgeIngester(), Ingester)
    assert isinstance(_FallbackIngester(), Ingester)


def test_grammar_dispatch_precedes_fallback():
    reg = IngesterRegistry()
    reg.register(_KnowledgeIngester())
    reg.register(_FallbackIngester())
    assert reg.dispatch("claim: water boils").id == "knowledge"
    assert reg.dispatch("some prose").id == "fallback"


def test_second_fallback_is_refused():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())
    with pytest.raises(ValueError, match="fallback already registered"):
        reg.register(_QuarantiningIngester())


def test_pipeline_writes_dimensioned_subgraph():
    reg = IngesterRegistry()
    reg.register(_KnowledgeIngester())
    w = CollectingWriter()
    r = ingest_text("claim: a\nclaim: b", registry=reg, writer=w)
    assert r["ok"] and r["ingester"] == "knowledge" and r["dimension"] == "5D"
    assert r["nodes"] == 2 and r["write"]["written"] is True
    assert len(w.written) == 1


def test_quarantined_subgraph_is_refused_by_writer():
    reg = IngesterRegistry()
    reg.register(_QuarantiningIngester())
    w = CollectingWriter()
    r = ingest_text("anything", registry=reg, writer=w)
    assert r["ok"] is False and r["processed"] is True
    assert r["quarantined"] is True and r["write"]["written"] is False
    assert w.written == []


def test_pipeline_never_calls_writer_for_quarantined_subgraph():
    class SpyWriter:
        def __init__(self):
            self.calls = 0

        def write(self, subgraph):
            self.calls += 1
            raise AssertionError("writer must not be called")

    reg = IngesterRegistry()
    reg.register(_QuarantiningIngester())
    writer = SpyWriter()
    result = ingest_text("anything", registry=reg, writer=writer)
    assert result["reason"] == "quarantined"
    assert writer.calls == 0


@pytest.mark.parametrize(
    ("graph", "error"),
    [
        (Subgraph("6D", provenance={"source": "x"}), "invalid facet"),
        (Subgraph("nD"), "missing provenance"),
        (Subgraph("nD", nodes=[{"id": "n"}],
                  edges=[{"norm": "n", "dimension": "sixth"}],
                  provenance={"source": "x"}), "invalid edge dimension"),
        (Subgraph("nD", nodes=[{"id": "n"}],
                  edges=[{"norm": "missing", "dimension": "causal"}],
                  provenance={"source": "x"}), "dangling norm edge"),
        (Subgraph("nD", nodes=[{"id": "n"}], edges=[None],
                  provenance={"source": "x"}), "malformed edge"),
        (Subgraph("nD", nodes=[{"id": "n"}], quarantined=True,
                  provenance={"source": "x"}), "quarantine contains semantic content"),
        (Subgraph("nD", rejections=[{"sentence_index": 1, "text": "x",
                                     "reason": "bad"}],
                  provenance={"source": "x"}), "partial without accepted content"),
    ],
)
def test_product_subgraph_validation(graph, error):
    assert error in validate_subgraph(graph)


def test_pipeline_refuses_invalid_subgraph_before_writer():
    class InvalidIngester:
        id = "invalid"

        def grammar(self):
            return None

        def ingest(self, text, ctx):
            return Subgraph(dimension="6D", provenance={"source": "x"})

    class SpyWriter:
        calls = 0

        def write(self, subgraph):
            self.calls += 1
            return {"written": True}

    reg = IngesterRegistry()
    reg.register(InvalidIngester())
    writer = SpyWriter()
    result = ingest_text("x", registry=reg, writer=writer)
    assert result["reason"] == "invalid_subgraph"
    assert writer.calls == 0


def test_empty_registry_reports_no_ingester():
    r = ingest_text("x", registry=IngesterRegistry(), writer=CollectingWriter())
    assert r == {"ok": False, "reason": "no_ingester"}


def test_artifact_extraction_is_injected():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())
    r = ingest_artifact({"path": "doc.pdf"}, extract=lambda a: "extracted body",
                        registry=reg, writer=CollectingWriter())
    assert r["ok"] and r["nodes"] == 1
    empty = ingest_artifact({}, extract=lambda a: "", registry=reg,
                            writer=CollectingWriter())
    assert empty == {"ok": False, "reason": "no_text_extracted"}


def test_versum_writer_requires_complete_context():
    class Sink:
        def upsert(self, envelope):
            return {}

    with pytest.raises(ValueError, match="idempotency_key"):
        versum_writer(Sink(), idempotency_key="", source={"source_id": "one"},
                      evidence=[{"evidence_id": "one"}], nd={"system_id": "one"})
    with pytest.raises(ValueError, match="source"):
        versum_writer(Sink(), idempotency_key="one", source={},
                      evidence=[{"evidence_id": "one"}], nd={"system_id": "one"})
    with pytest.raises(ValueError, match="evidence"):
        versum_writer(Sink(), idempotency_key="one",
                      source={"source_id": "one"}, evidence=[],
                      nd={"system_id": "one"})
    with pytest.raises(ValueError, match="nd"):
        versum_writer(Sink(), idempotency_key="one",
                      source={"source_id": "one"},
                      evidence=[{"evidence_id": "one"}], nd={})


def test_deontic_mixed_valid_and_invalid_input_is_partial():
    reg = IngesterRegistry()
    reg.register(DeonticIngester())
    writer = CollectingWriter()

    result = ingest_text(
        "Controller must notify. The processor must.",
        registry=reg,
        writer=writer,
    )

    assert result["status"] == "partial"
    assert result["quarantined"] is False
    assert result["rejections"] == 1
    assert result["nodes"] == 1
    assert result["write"]["written"] is True
    assert len(writer.written) == 1
    assert writer.written[0].rejections == [{
        "sentence_index": 2,
        "text": "The processor must",
        "reason": "missing_required_slot",
    }]


def test_deontic_node_ids_are_stable_and_source_namespaced():
    ingester = DeonticIngester()
    text = "Controller must notify."

    first = ingester.ingest(text, {"source_id": "policy-a"})
    again = ingester.ingest(text, {"source_id": "policy-a"})
    other = ingester.ingest(text, {"source_id": "policy-b"})

    assert first.nodes[0]["id"] == again.nodes[0]["id"]
    assert first.nodes[0]["id"] != other.nodes[0]["id"]
    assert first.edges[0]["norm"] == first.nodes[0]["id"]


def test_oversized_input_is_refused_before_any_processing():
    class ExplodingIngester:
        id = "exploding"

        def grammar(self):
            return None

        def ingest(self, text, ctx):
            raise AssertionError("oversized input must not reach an ingester")

    class SpyWriter:
        calls = 0

        def write(self, subgraph):
            self.calls += 1
            raise AssertionError("oversized input must not reach the writer")

    reg = IngesterRegistry()
    reg.register(ExplodingIngester())
    writer = SpyWriter()
    result = ingest_text("x" * (DEFAULT_MAX_INPUT_CHARS + 1),
                         registry=reg, writer=writer)
    assert result["ok"] is False and result["reason"] == "input_too_large"
    assert result["limit"] == DEFAULT_MAX_INPUT_CHARS
    assert result["length"] == DEFAULT_MAX_INPUT_CHARS + 1
    assert writer.calls == 0


def test_input_bound_is_configurable_and_disablable():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())

    tight = ingest_text("abcdef", registry=reg, writer=CollectingWriter(),
                        max_input_chars=3)
    assert tight == {"ok": False, "reason": "input_too_large",
                     "limit": 3, "length": 6}

    # At the limit is accepted; None disables the guard entirely.
    ok = ingest_text("abc", registry=reg, writer=CollectingWriter(),
                     max_input_chars=3)
    assert ok["ok"] is True
    huge = ingest_text("x" * (DEFAULT_MAX_INPUT_CHARS + 1), registry=reg,
                       writer=CollectingWriter(), max_input_chars=None)
    assert huge["ok"] is True


def test_artifact_ingest_enforces_input_bound():
    reg = IngesterRegistry()
    reg.register(_FallbackIngester())
    result = ingest_artifact({"path": "big.pdf"},
                             extract=lambda a: "y" * 20,
                             registry=reg, writer=CollectingWriter(),
                             max_input_chars=5)
    assert result["ok"] is False and result["reason"] == "input_too_large"


def test_node_identity_prefers_node_id_and_is_shared_across_plane():
    assert node_identity({"id": "a"}) == "a"
    assert node_identity({"node_id": "b"}) == "b"
    # A node carrying both is keyed on node_id — the value the writer emits.
    assert node_identity({"id": "a", "node_id": "b"}) == "b"
    assert node_identity("not-a-dict") is None


def test_validation_dedup_key_matches_writer_emit_key():
    # Two nodes whose ``id`` differs but ``node_id`` collides: validation must
    # catch the same duplicate the writer would emit, because both resolve
    # identity through node_identity.
    graph = Subgraph(
        dimension="nD",
        nodes=[{"id": "a1", "node_id": "shared"},
               {"id": "a2", "node_id": "shared"}],
        provenance={"source": "x"},
    )
    assert "duplicate node id" in validate_subgraph(graph)


def test_deontic_semicolon_does_not_leak_into_action():
    graph = DeonticIngester().ingest(
        "Controller must notify; Processor may disclose.",
        {},
    )

    assert graph.quarantined is False
    assert [node["action"] for node in graph.nodes] == ["notify", "disclose"]


def test_deontic_captures_defined_terms_as_structural_nodes():
    graph = DeonticIngester().ingest(
        "For the purposes of this Regulation, 'personal data' means any "
        "information relating to an identified natural person. "
        "'Controller' shall mean the body which determines the purposes. "
        "The Agency shall mean the European supervisory body.",
        {"source_id": "gdpr"},
    )

    assert validate_subgraph(graph) == []
    definitions = [n for n in graph.nodes if n["kind"] == "definition"]
    assert [d["term"] for d in definitions] == [
        "personal data", "Controller", "The Agency",
    ]
    assert definitions[0]["definition"] == (
        "any information relating to an identified natural person"
    )
    assert graph.provenance["definitions"] == 3
    # Every definition emits exactly one structural edge attributed to its node.
    def_edges = [e for e in graph.edges if e["predicate"] == "defines"]
    assert len(def_edges) == 3
    assert all(e["dimension"] == "structural" for e in def_edges)
    assert {e["norm"] for e in def_edges} == {d["id"] for d in definitions}
    assert {e["object"] for e in def_edges} == {d["term"] for d in definitions}


def test_deontic_definition_takes_precedence_over_shall_modal():
    # "shall mean" must be read as a definition, not lowered as an obligation.
    graph = DeonticIngester().ingest(
        "'Controller' shall mean the responsible body.", {},
    )

    assert [n["kind"] for n in graph.nodes] == ["definition"]
    assert graph.provenance["lowered"] == 0
    assert graph.provenance["recognised"] == 0


def test_deontic_definition_node_ids_are_stable_and_source_namespaced():
    text = "'controller' means the body which determines the purposes."
    first = DeonticIngester().ingest(text, {"source_id": "policy-a"})
    again = DeonticIngester().ingest(text, {"source_id": "policy-a"})
    other = DeonticIngester().ingest(text, {"source_id": "policy-b"})

    assert first.nodes[0]["id"].startswith("definition:")
    assert first.nodes[0]["id"] == again.nodes[0]["id"]
    assert first.nodes[0]["id"] != other.nodes[0]["id"]


def test_deontic_cross_references_link_norm_to_cited_provisions():
    graph = DeonticIngester().ingest(
        "The controller must notify the authority under Article 33(1) and "
        "Annex II pursuant to Regulation (EU) 2016/679 and Directive 95/46/EC.",
        {},
    )

    assert validate_subgraph(graph) == []
    refs = [e for e in graph.edges
            if e["predicate"] == "refers-to" and e["dimension"] == "relational"]
    cited = {e["object"] for e in refs}
    assert cited == {
        "Article 33(1)", "Annex II",
        "Regulation (EU) 2016/679", "Directive 95/46/EC",
    }
    norm_id = next(n["id"] for n in graph.nodes if n["kind"] == "norm")
    assert all(e["norm"] == norm_id for e in refs)


def test_deontic_cross_reference_ignores_bare_prose():
    graph = DeonticIngester().ingest(
        "The processor must consider the point of view of the data subject.",
        {},
    )

    assert not [e for e in graph.edges if e["predicate"] == "refers-to"]


def test_deontic_required_artifacts_are_structural_edges():
    # AI Act Article 16 (c)/(d)/(e)/(g)/(h) style provider deliverables.
    graph = DeonticIngester().ingest(
        "The provider shall draw up an EU declaration of conformity and affix "
        "the CE marking. The provider must keep the logs referred to in "
        "Article 19 and maintain a quality management system.",
        {"source_id": "ai-act-16"},
    )

    assert validate_subgraph(graph) == []
    artifacts = [e for e in graph.edges
                 if e["predicate"] == "requires-artifact"]
    assert all(e["dimension"] == "structural" for e in artifacts)
    assert {e["object"] for e in artifacts} == {
        "EU declaration of conformity", "CE marking",
        "logs", "quality management system",
    }
    # Every artifact edge is attributed to a real norm node.
    norm_ids = {n["id"] for n in graph.nodes if n["kind"] == "norm"}
    assert all(e["norm"] in norm_ids and e["subject"] in norm_ids
               for e in artifacts)


def test_deontic_authorisation_points_are_causal_edges():
    graph = DeonticIngester().ingest(
        "Placing the system on the market shall be subject to prior "
        "authorisation. The competent authority shall decide within 30 days.",
        {"source_id": "auth"},
    )

    assert validate_subgraph(graph) == []
    gates = [e for e in graph.edges if e["predicate"] == "authorised-by"]
    assert all(e["dimension"] == "causal" for e in gates)
    assert {e["object"] for e in gates} == {
        "subject to prior authorisation", "shall decide",
    }
    norm_ids = {n["id"] for n in graph.nodes if n["kind"] == "norm"}
    assert all(e["norm"] in norm_ids for e in gates)


def test_deontic_artifact_and_authorisation_ignore_bare_prose():
    graph = DeonticIngester().ingest(
        "The processor must consider the point of view of the data subject "
        "and keep the customer informed of the outcome.",
        {},
    )

    assert not [e for e in graph.edges
                if e["predicate"] in ("requires-artifact", "authorised-by")]


def _only_norm(graph):
    return next(n for n in graph.nodes if n["kind"] == "norm")


def test_deontic_deadline_populates_typed_field_on_node_and_formula():
    # The deadline is read via the language's PUBLISHED deadline cues.
    graph = DeonticIngester().ingest(
        "The provider shall notify the authority within 30 days.", {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    assert norm["deadline"] == "30 days"
    assert norm["cross_references"] == []
    assert norm["sanction"] == ""
    # The same value round-trips onto the deontic formula the language builds.
    formula = deontic.formula_from_fields(
        norm["operator"], norm["bearer"], norm["action"],
        deadline=norm["deadline"])
    assert formula.deadline == "30 days"


def test_deontic_deadline_surface_records_action_anchored_span():
    # The deadline's SURFACE — the full published-cue match — is recorded
    # with exact offsets into the node's action, so a consumer can remove it
    # span-exact instead of re-searching (which can over/under-remove).
    graph = DeonticIngester().ingest(
        "The provider shall notify the authority within 30 days.", {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    surface = norm["deadline_surface"]
    assert surface["text"] == "within 30 days"
    assert norm["action"][surface["start"]:surface["end"]] == surface["text"]
    # The typed VALUE field is unchanged by the surface recording.
    assert norm["deadline"] == "30 days"


def test_deontic_deadline_surface_is_cue_wide_not_clause_wide():
    # The recorded surface is exactly as wide as the language's published
    # cue — the language owns the vocabulary, the ingester never widens it.
    # Here that means the feasibility qualifier and the reference-point tail
    # around the cue stay in the action. When the deontic pack publishes a
    # clause-level cue, THIS assertion is updated deliberately.
    graph = DeonticIngester().ingest(
        "The controller shall notify the supervisory authority without undue "
        "delay and, where feasible, not later than 72 hours after having "
        "become aware of it.", {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    surface = norm["deadline_surface"]
    assert surface["text"] == "not later than 72 hours"
    assert norm["action"][surface["start"]:surface["end"]] == surface["text"]
    assert "where feasible" in norm["action"]
    assert "after having become aware" in norm["action"]


def test_deontic_deadline_surface_records_german_cue():
    graph = DeonticIngester().ingest(
        "Der Anbieter muss die Behörde innerhalb von 30 Tagen "
        "benachrichtigen.", {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    surface = norm["deadline_surface"]
    assert surface["text"] == "innerhalb von 30 Tagen"
    assert norm["action"][surface["start"]:surface["end"]] == surface["text"]
    assert norm["deadline"] == "30 Tagen"


def test_deontic_deadline_surface_empty_when_no_deadline():
    graph = DeonticIngester().ingest(
        "The controller must delete the data in accordance with Article 17.",
        {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    assert norm["deadline_surface"] == {}
    assert norm["deadline"] == ""


def test_deontic_cross_references_populate_typed_list_on_node_and_formula():
    graph = DeonticIngester().ingest(
        "The controller must delete the data in accordance with Article 17.",
        {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    assert norm["cross_references"] == ["Article 17"]
    assert norm["deadline"] == ""
    assert norm["sanction"] == ""
    formula = deontic.formula_from_fields(
        norm["operator"], norm["bearer"], norm["action"],
        cross_references=norm["cross_references"])
    assert formula.cross_references == ["Article 17"]


def test_deontic_sanction_populates_typed_field_on_node_and_formula():
    graph = DeonticIngester().ingest(
        "A person who processes the data shall be liable to a fine of EUR 10000.",
        {},
    )

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    assert norm["sanction"]
    assert "fine" in norm["sanction"].lower()
    assert norm["deadline"] == ""
    assert norm["cross_references"] == []
    formula = deontic.formula_from_fields(
        norm["operator"], norm["bearer"], norm["action"],
        sanction=norm["sanction"])
    assert formula.sanction == norm["sanction"]


def test_deontic_plain_norm_carries_empty_typed_defaults():
    # A norm with none of the three cues is unchanged: empty defaults.
    graph = DeonticIngester().ingest("Controller must notify.", {})

    assert validate_subgraph(graph) == []
    norm = _only_norm(graph)
    assert norm["deadline"] == ""
    assert norm["cross_references"] == []
    assert norm["sanction"] == ""
