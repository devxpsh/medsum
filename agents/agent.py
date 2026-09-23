"""Main ADK Agent Entrypoint for `adk web`.

Exposes `root_agent` so running `adk web .` in the project root launches
the interactive Medical Literature Summarization & Verification Agent.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from tools.pubmed_tool import pubmed_fetch_tool
from agents.summarizer_agent import SUMMARIZER_INSTRUCTION, MedicalSummarySchema

load_dotenv()

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

AGENT_INSTRUCTION = f"""{SUMMARIZER_INSTRUCTION}

INTERACTIVE ASSISTANT BEHAVIOR:
- You are the MedLit Assistant.
- If the user provides a medical abstract, summarize it strictly following the 5 sections:
  1. Objective
  2. Methodology
  3. Key findings
  4. Clinical/research relevance
  5. Limitations
- If the user asks to search PubMed for a disease or treatment, use `fetch_abstracts` to retrieve the latest literature.
- Always perform factual verification to ensure all claims and numbers match the source with >=85% confidence.
"""

root_agent = Agent(
    name="medlit_agent",
    description="Medical Literature Summarization and Fact-Verification Agent.",
    model=DEFAULT_MODEL,
    instruction=AGENT_INSTRUCTION,
    tools=[pubmed_fetch_tool] if pubmed_fetch_tool is not None else [],
    output_schema=MedicalSummarySchema,
)
