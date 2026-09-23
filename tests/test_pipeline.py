"""Test Suite for Medical Literature Summarization & Verification Pipeline.

Validates:
1. PubMed XML parsing and metadata extraction
2. Summarizer agent output schema conformance
3. Verifier agent factual scoring and 85%+ quality gating
4. End-to-end pipeline execution (single abstract & batch)
5. Strict non-patient synthetic data compliance
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from tools.pubmed_tool import parse_pubmed_xml
from agents.summarizer_agent import MedicalSummarySchema
from agents.verifier_agent import VerificationResultSchema
from pipeline import (
    _offline_summarize_fallback,
    _offline_verify_fallback,
    summarize_abstract,
    batch_summarize,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2024//EN" "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_240101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>38001001</PMID>
      <Article>
        <ArticleTitle>Efficacy of Novel Oral Anticoagulant in Atrial Fibrillation: A Randomized Trial</ArticleTitle>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2024</Year>
              <Month>Feb</Month>
            </PubDate>
          </JournalIssue>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
          <Author>
            <LastName>Taylor</LastName>
            <ForeName>Emma</ForeName>
          </Author>
        </AuthorList>
        <Abstract>
          <AbstractText Label="OBJECTIVE">To assess stroke reduction with novel factor Xa inhibitor.</AbstractText>
          <AbstractText Label="METHODS">Double-blind RCT of 4,500 patients randomized to drug vs warfarin.</AbstractText>
          <AbstractText Label="RESULTS">Stroke occurred in 1.2% vs 2.1% (HR 0.57; 95% CI 0.41-0.79; P &lt; 0.001).</AbstractText>
          <AbstractText Label="CONCLUSIONS">Factor Xa inhibitor was superior in preventing stroke with comparable major bleeding.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

SAMPLE_ABSTRACT = (
    "OBJECTIVE: To compare overall survival with adjuvant immunotherapy vs placebo in resected stage III melanoma. "
    "METHODS: In a double-blind trial, 900 patients were randomized 1:1 to receive 12 months of nivolumab or placebo. "
    "RESULTS: At 3 years, recurrence-free survival was 61.2% in the nivolumab arm vs 45.3% with placebo (HR 0.68; 95% CI 0.56-0.82; P < 0.001). "
    "Grade 3-4 treatment-related adverse events were documented in 14.4% vs 2.1%. "
    "CONCLUSIONS: Adjuvant nivolumab demonstrated statistically significant improvement in recurrence-free survival."
)


def test_pubmed_xml_parsing():
    """Verify XML parsing correctly extracts PMID, title, authors, date, and abstract."""
    records = parse_pubmed_xml(SAMPLE_XML)
    assert len(records) == 1
    rec = records[0]
    assert rec["pmid"] == "38001001"
    assert "Novel Oral Anticoagulant" in rec["title"]
    assert "Smith John" in rec["authors"]
    assert "Taylor Emma" in rec["authors"]
    assert "2024 Feb" in rec["pub_date"]
    assert "OBJECTIVE: To assess stroke reduction" in rec["abstract_text"]
    assert "HR 0.57" in rec["abstract_text"]


def test_pubmed_future_date_sanitization():
    """Verify that placeholder future years (e.g., 2027) resolve to real PubMed publication dates."""
    future_date_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>42753782</PMID>
          <Article>
            <ArticleTitle>Future Issue Article</ArticleTitle>
            <Journal>
              <JournalIssue><PubDate><Year>2027</Year><Month>Aug</Month><Day>12</Day></PubDate></JournalIssue>
            </Journal>
            <Abstract><AbstractText>Sample abstract content.</AbstractText></Abstract>
          </Article>
        </MedlineCitation>
        <PubmedData>
          <History>
            <PubMedPubDate PubStatus="pubmed"><Year>2026</Year><Month>Sep</Month><Day>17</Day></PubMedPubDate>
          </History>
        </PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    records = parse_pubmed_xml(future_date_xml)
    assert len(records) == 1
    assert "2027" not in records[0]["pub_date"]
    assert "2026 Sep 17" in records[0]["pub_date"]


def test_summarizer_schema_conformance():
    """Verify that generated summaries conform to the required 5-section Pydantic schema."""
    summary_data = _offline_summarize_fallback(SAMPLE_ABSTRACT, pmid="38001001")
    validated = MedicalSummarySchema(**summary_data)
    assert validated.objective is not None
    assert validated.methodology is not None
    assert validated.key_findings is not None
    assert validated.relevance is not None
    assert validated.limitations is not None
    assert validated.source_pmid == "38001001"
    assert "61.2%" in validated.key_findings or "900" in validated.methodology


def test_verifier_factual_consistency_pass():
    """Verify factual summary receives confidence >= 85 and passed=True."""
    summary_data = _offline_summarize_fallback(SAMPLE_ABSTRACT, pmid="38001001")
    v_res = _offline_verify_fallback(SAMPLE_ABSTRACT, summary_data)
    validated = VerificationResultSchema(**v_res)
    assert validated.confidence_score >= 85
    assert validated.passed is True
    assert len(validated.flagged_claims) == 0


def test_verifier_flags_hallucinated_statistics():
    """Verify verifier flags numbers that do not appear in the source abstract."""
    tampered_summary = {
        "objective": "To compare survival",
        "methodology": "RCT of 900 patients",
        "key_findings": "Recurrence-free survival was 89.5% with HR 0.22 (P < 0.0001) in 5000 patients.",  # 89.5% & 0.22 are hallucinated
        "relevance": "Major therapeutic breakthrough",
        "limitations": "Not stated",
        "source_pmid": "38001001",
    }
    v_res = _offline_verify_fallback(SAMPLE_ABSTRACT, tampered_summary)
    assert len(v_res["flagged_claims"]) > 0
    assert any("89.5" in fc or "0.22" in fc for fc in v_res["flagged_claims"])
    assert v_res["confidence_score"] < 85
    assert v_res["passed"] is False


def test_pipeline_single_abstract():
    """Test full single-abstract pipeline execution."""
    res = summarize_abstract(SAMPLE_ABSTRACT, pmid="12345")
    assert res["passed"] is True
    assert res["confidence_score"] >= 85
    assert res["pmid"] == "12345"
    assert res["summary"]["objective"] != ""
    assert res["summary"]["methodology"] != ""
    assert res["summary"]["key_findings"] != ""


def test_pipeline_batch_execution():
    """Test batch processing over multiple abstracts."""
    batch_input = [
        {"title": "Study 1", "pmid": "101", "abstract_text": SAMPLE_ABSTRACT},
        {"title": "Study 2", "pmid": "102", "abstract_text": SAMPLE_ABSTRACT.replace("900", "1200")},
    ]
    results = batch_summarize(batch_input)
    assert len(results) == 2
    for r in results:
        assert r["passed"] is True
        assert r["confidence_score"] >= 85


def test_synthetic_data_integrity():
    """Verify synthetic dataset has 6 records with all required fields and no patient data."""
    data_path = Path("data/synthetic_abstracts.json")
    assert data_path.is_file()
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 6
    for item in data:
        assert "pmid" in item
        assert "title" in item
        assert "authors" in item
        assert "pub_date" in item
        assert "abstract_text" in item
        # Confirm no patient identifying strings
        text = item["abstract_text"].lower()
        assert "mrn" not in text
        assert "ssn" not in text
        assert "hospital record" not in text
