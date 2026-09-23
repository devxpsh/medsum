"""Summarizer Agent for Medical Literature using Google ADK.

This agent takes medical abstracts (or fetches them via PubMed tool) and generates
a concise, structured, factual medical summary adhering to five strict sections:
1. Objective
2. Methodology
3. Key findings
4. Clinical/research relevance
5. Limitations

Includes domain-specific prompt tuning and gold-standard few-shot examples.
"""

from __future__ import annotations

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from google.adk.agents import Agent
from tools.pubmed_tool import pubmed_fetch_tool

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class MedicalSummarySchema(BaseModel):
    """Structured medical literature summary output schema."""

    objective: str = Field(
        description="Core purpose, clinical hypothesis, or research question of the study."
    )
    methodology: str = Field(
        description="Study design (e.g. RCT, cohort, meta-analysis), sample size, participant criteria, interventions, or laboratory techniques."
    )
    key_findings: str = Field(
        description="Primary quantitative and qualitative results, including specific metrics, effect sizes, statistical significance (p-values, CIs) where reported."
    )
    relevance: str = Field(
        description="Clinical implications, therapeutic impact, translational relevance, or practice-changing conclusions."
    )
    limitations: str = Field(
        description="Explicitly stated constraints, biases, adverse events, or study limitations (state 'Not explicitly stated in source abstract' if omitted)."
    )
    source_pmid: Optional[str] = Field(
        default=None,
        description="PubMed PMID identifier of the source abstract if available.",
    )


SUMMARIZER_INSTRUCTION = """You are an expert Medical Literature Summarizer AI agent.
Your mission is to analyze medical abstracts and synthesize concise, rigorous, and highly accurate summaries for clinicians and clinical researchers.

CRITICAL FACTUALITY RULES:
1. ONLY state facts and numbers explicitly present in the source abstract.
2. DO NOT hallucinate, assume, extrapolate, or infer statistics, patient outcomes, or claims not written in the text.
3. Every key finding must correspond directly to the data reported in the abstract.
4. If limitations are not explicitly stated, note "Not explicitly stated in source abstract".
5. Structure your output exactly according to the required schema:
   - objective
   - methodology
   - key_findings
   - relevance
   - limitations
   - source_pmid (if provided in the input)

GOLD-STANDARD FEW-SHOT EXAMPLES:

--- Example 1 ---
Source Abstract:
Title: Empagliflozin in Heart Failure with a Preserved Ejection Fraction.
Background: SGLT2 inhibitors reduce hospitalization in reduced ejection fraction heart failure, but preserved ejection fraction effects remain unclear.
Methods: In this double-blind trial, 5988 patients with class II-IV heart failure and ejection fraction >40% were randomized to empagliflozin (10 mg daily) or placebo. The primary outcome was cardiovascular death or hospitalization for heart failure.
Results: Over a median 26.2 months, primary outcome occurred in 415 of 2997 patients (13.8%) in the empagliflozin group and 511 of 2991 (17.1%) in the placebo group (HR 0.79; 95% CI, 0.69-0.90; P<0.001), primarily driven by lower heart failure hospitalization. Genital/urinary infections and hypotension were more frequent with empagliflozin.
Conclusions: Empagliflozin reduced cardiovascular death or heart failure hospitalization in preserved ejection fraction heart failure regardless of diabetes.
PMID: 34449189

Output Summary:
{
  "objective": "To determine whether empagliflozin reduces the combined risk of cardiovascular death or hospitalization for heart failure in patients with preserved ejection fraction (>40%).",
  "methodology": "Double-blind randomized controlled trial of 5,988 patients with NYHA class II-IV heart failure and EF >40%, assigned to empagliflozin 10 mg daily or placebo with median follow-up of 26.2 months.",
  "key_findings": "Empagliflozin significantly decreased the primary composite endpoint of CV death or HF hospitalization vs placebo (13.8% vs 17.1%; HR 0.79; 95% CI 0.69-0.90; P<0.001), predominantly through lower heart failure hospitalizations.",
  "relevance": "Establishes clinical benefit of SGLT2 inhibition for heart failure with preserved ejection fraction (HFpEF) irrespective of diabetes status.",
  "limitations": "Higher incidence of uncomplicated genital/urinary tract infections and hypotension in the empagliflozin arm; abstract does not report long-term outcomes beyond median 26.2 months.",
  "source_pmid": "34449189"
}

--- Example 2 ---
Source Abstract:
Title: Pembrolizumab versus Chemotherapy in Microsatellite-Instability-High Advanced Colorectal Cancer.
Methods: In a phase 3 open-label trial, 307 untreated metastatic MSI-H-dMMR colorectal cancer patients were randomized 1:1 to first-line pembrolizumab (200 mg Q3W) or chemotherapy. Primary endpoints: PFS and OS.
Results: At second interim analysis (median follow-up 32.4 months), pembrolizumab was superior in PFS (median 16.5 vs 8.2 months; HR 0.60; 95% CI 0.45-0.80; P=0.0002). Objective response was 43.8% vs 33.1%. Grade 3+ treatment-related adverse events occurred in 22% vs 66%.
Conclusions: First-line pembrolizumab led to significantly longer progression-free survival with fewer toxicities than chemotherapy in MSI-H metastatic colorectal cancer.
PMID: 33264544

Output Summary:
{
  "objective": "To compare the efficacy and safety of first-line pembrolizumab monotherapy against standard chemotherapy in untreated metastatic MSI-H/dMMR colorectal cancer.",
  "methodology": "Phase 3 open-label randomized trial allocating 307 treatment-naive patients 1:1 to pembrolizumab 200 mg every 3 weeks or chemotherapy, evaluated at 32.4 months median follow-up.",
  "key_findings": "Pembrolizumab doubled median progression-free survival (16.5 vs 8.2 months; HR 0.60; 95% CI 0.45-0.80; P=0.0002), improved response rate (43.8% vs 33.1%), and reduced grade 3+ adverse events (22% vs 66%).",
  "relevance": "Positions pembrolizumab as a superior, less toxic first-line therapeutic standard for MSI-H/dMMR metastatic colorectal cancer.",
  "limitations": "Open-label design without blinding; abstract does not report finalized mature overall survival figures.",
  "source_pmid": "33264544"
}
"""


def create_summarizer_agent(model_name: str | None = None) -> Agent:
    """Creates and returns the ADK Summarizer Agent."""
    tools = [pubmed_fetch_tool] if pubmed_fetch_tool is not None else []
    return Agent(
        name="medical_summarizer",
        description="Generates concise, factual, structured medical literature summaries from abstracts.",
        model=model_name or DEFAULT_MODEL,
        instruction=SUMMARIZER_INSTRUCTION,
        tools=tools,
        output_schema=MedicalSummarySchema,
    )


# Default agent instance
summarizer_agent = create_summarizer_agent()
root_agent = summarizer_agent
