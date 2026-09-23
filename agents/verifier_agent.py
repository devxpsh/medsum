"""Verifier Agent for Medical Literature using Google ADK.

This agent acts as an adversarial medical peer reviewer and factual validator.
It evaluates a generated medical summary against the original abstract,
checks every atomic claim and statistic, flags unsupported assertions, and
assigns a factual confidence score (0-100).

Threshold:
- confidence_score >= 85: PASSED (meets TCS Technology Day 85%+ quality standard)
- confidence_score < 85: FAILED / Flagged for review or regeneration
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from google.adk.agents import Agent

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class VerificationResultSchema(BaseModel):
    """Schema for factual verification of generated medical summaries."""

    confidence_score: int = Field(
        ge=0,
        le=100,
        description="Factual consistency confidence score (0-100). Must be >= 85 to pass quality threshold.",
    )
    flagged_claims: list[str] = Field(
        default_factory=list,
        description="List of specific claims, numbers, or conclusions in the summary not strictly supported by the source abstract. Empty list if fully verified.",
    )
    passed: bool = Field(
        default=True,
        description="True if confidence_score >= 85 and no critical factual errors exist; False otherwise.",
    )
    verification_notes: str = Field(
        description="Concise rationale explaining the score and breakdown of factual alignment.",
    )


VERIFIER_INSTRUCTION = """You are a rigorous, adversarial Medical Literature Verifier AI agent.
Your sole responsibility is to evaluate a generated medical summary against its original source abstract.

VERIFICATION PROTOCOL:
1. Deconstruct the generated summary into atomic factual statements across:
   - Objective
   - Methodology (sample size, trial phase, design, arms)
   - Key findings (percentages, hazard ratios, p-values, endpoints)
   - Relevance (clinical conclusions)
   - Limitations
2. Compare each atomic claim strictly against the source abstract text.
3. Apply zero tolerance for hallucinations:
   - Any invented number, statistical metric, or sample size must be flagged.
   - Any claim not explicitly stated or logically necessitated by the abstract is unsupported.
   - Do NOT assume external medical knowledge beyond what is explicitly written in the provided source abstract.
4. Scoring Rubric (0-100):
   - 95-100: Flawlessly faithful. Every single metric, cohort description, and outcome matches the source.
   - 85-94: All clinical facts and numbers are 100% accurate; minor benign wording differences that do not distort medical meaning.
   - 70-84: One minor unverified claim or ambiguous extrapolation.
   - 50-69: Factual discrepancy in numbers, wrong endpoint, or invented finding.
   - 0-49: Severe hallucinations, fabricated trial results, or contradictory claims.
5. Quality Gate:
   - If confidence_score >= 85: passed = true.
   - If confidence_score < 85: passed = false.
   - List each unverified statement in `flagged_claims`. If no issues exist, `flagged_claims` MUST be an empty list [].

INPUT FORMAT EXPECTED:
--- SOURCE ABSTRACT ---
<original abstract text>

--- GENERATED SUMMARY ---
<summary text or JSON>
"""


def create_verifier_agent(model_name: str | None = None) -> Agent:
    """Creates and returns the ADK Verifier Agent."""
    return Agent(
        name="medical_verifier",
        description="Rigorously checks generated medical summaries against source abstracts for factual accuracy and flags hallucinations.",
        model=model_name or DEFAULT_MODEL,
        instruction=VERIFIER_INSTRUCTION,
        tools=[],  # Pure verification, no tools needed
        output_schema=VerificationResultSchema,
    )


# Default agent instance
verifier_agent = create_verifier_agent()
root_agent = verifier_agent
