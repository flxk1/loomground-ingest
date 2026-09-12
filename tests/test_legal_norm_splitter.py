# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 flxk1
"""Article-level segmentation: a law's own provisions are cut into individual
units, each anchored to its instrument with its article pinpoint.

The fixture is real GDPR operative text (a handful of articles) so the test
exercises actual legal drafting, not synthetic sentences. Per-article placement
belongs to a host registry; the splitter itself is dependency-free and is proven
here.
"""

from __future__ import annotations

from loomground_ingest.governance import legal_norm_splitter as splitter


# Real GDPR operative text (abridged to a few articles; wording verbatim).
GDPR = """REGULATION (EU) 2016/679 (General Data Protection Regulation)

Article 5
Principles relating to processing of personal data
1. Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.
2. The controller shall be responsible for, and be able to demonstrate compliance with, paragraph 1.

Article 6
Lawfulness of processing
1. Processing shall be lawful only if and to the extent that at least one of the following applies: (a) the data subject has given consent to the processing of his or her personal data for one or more specific purposes; (b) processing is necessary for the performance of a contract.

Article 17
Right to erasure
1. The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay.
3. Paragraphs 1 and 2 shall not apply to the extent that processing is necessary for compliance with a legal obligation which requires processing by Union or Member State law.

Article 33
Notification of a personal data breach to the supervisory authority
1. In the case of a personal data breach, the controller shall without undue delay and, where feasible, not later than 72 hours after having become aware of it, notify the personal data breach to the supervisory authority.
"""


def test_segments_articles_and_paragraphs_with_pinpoints():
    provs = splitter.segment_provisions(GDPR)
    pins = [p.pinpoint for p in provs]
    assert "Art. 5(1)" in pins and "Art. 6(1)" in pins
    assert "Art. 17(1)" in pins and "Art. 17(3)" in pins and "Art. 33(1)" in pins
    # Art. 17 yields two distinct paragraph-level provisions
    assert sum(1 for p in provs if p.article == "17") == 2


def test_german_paragraph_segmentation():
    text = "§ 286\n1. Der Schuldner kommt in Verzug.\n2. Dem Verzug steht es gleich."
    provs = splitter.segment_provisions(text)
    assert {p.pinpoint for p in provs} >= {"§ 286(1)", "§ 286(2)"}
