# Medical Literature Summarization & Verification: Architectural Approach

## 1. Problem Overview & Success Criteria
The **TCS Technology Day Challenge** requires building an autonomous AI agent capable of ingesting medical literature abstracts and producing concise, rigorously accurate summaries emphasizing key insights and clinical conclusions.

The core technical mandates and success criteria are:
1. **85%+ Quality Rating**: Measured through programmatic factual consistency and hallucination prevention.
2. **Multi-Abstract Processing**: Robust batch processing across diverse therapeutic domains.
3. **Domain-Specific Prompt Tuning**: Abstractive summarization tailored for clinical research.
4. **Data Privacy Compliance**: Strict usage of publicly available PubMed abstracts or synthetic clinical trial data (zero patient-identifiable or protected health information).
5. **Interactive UI & CLI**: Dual interfaces for development, batch evaluation, and demonstration.

---

## 2. Multi-Agent System Architecture
The application is architected as an autonomous two-stage pipeline using Google's **Agent Development Kit (ADK)** and the **Gemini 2.0 / 2.5** foundational model family.

```
                     ┌────────────────────────────────┐
                     │     User Query / Batch Data    │
                     └───────────────┬────────────────┘
                                     │
                 ┌───────────────────▼───────────────────┐
                 │          PubMed Tool (NCBI)           │
                 │    esearch.fcgi  +  efetch.fcgi       │
                 └───────────────────┬───────────────────┘
                                     │ Raw XML -> Parsed Abstract
                 ┌───────────────────▼───────────────────┐
                 │       Summarizer Agent (ADK)          │
                 │   • Domain-tuned prompt instruction   │
                 │   • 2 gold-standard clinical few-shots│
                 │   • Strict 5-section Pydantic schema  │
                 └───────────────────┬───────────────────┘
                                     │ Candidate JSON Summary
                 ┌───────────────────▼───────────────────┐
                 │        Verifier Agent (ADK)           │
                 │   • Adversarial medical auditor       │
                 │   • Atomic claim & metric check       │
                 │   • Confidence Score (0-100)          │
                 └───────────────────┬───────────────────┘
                                     │
                       ┌─────────────┴─────────────┐
                       │ Quality Gate: Score >= 85 │
                       ├─────────────┬─────────────┤
                       │             │             │
                    [PASSED]      [FAILED]         │
                       │             │             │
                Structured UI/CLI  Flagged Claims  │
                    Report         for Review      │
```

### Component Breakdown
1. **Data Ingestion & NCBI E-utilities (`tools/pubmed_tool.py`)**:
   - Communicates with NCBI Entrez E-utilities (`esearch.fcgi` for query-to-PMID resolution and `efetch.fcgi` for XML abstract retrieval).
   - Custom XML parser traverses `<AbstractText Label="...">` tags preserving structured headings (OBJECTIVE, METHODS, RESULTS, CONCLUSIONS) and author metadata.
   - Built-in rate limiting (0.35s request spacing) protects against NCBI unauthenticated quota throttling (max 3 req/sec).
   - Wrapped as an ADK `FunctionTool`.

2. **Domain-Tuned Summarizer Agent (`agents/summarizer_agent.py`)**:
   - Configured with `google.adk.agents.Agent`.
   - Enforces a fixed five-part schema:
     - `objective`: Research purpose or clinical hypothesis.
     - `methodology`: Trial design, cohort size, intervention arms, and duration.
     - `key_findings`: Primary quantitative outcomes (hazard ratios, confidence intervals, p-values, response rates).
     - `relevance`: Practice-changing clinical implications and translational value.
     - `limitations`: Explicit study caveats, adverse event profiles, or unaddressed endpoints.
     - `source_pmid`: Originating identifier.
   - Pydantic schema enforcement ensures deterministic JSON parsing.

3. **Adversarial Verifier Agent (`agents/verifier_agent.py`)**:
   - Operates as an independent peer reviewer with zero tool dependencies.
   - Deconstructs the summary into atomic claims and verifies each against the source abstract.
   - Output schema: `confidence_score` (0-100), `flagged_claims` (list of unsupported claims), `passed` (boolean), and `verification_notes`.

4. **Pipeline Orchestrator (`pipeline.py`)**:
   - Orchestrates execution via ADK's `Runner` with `InMemorySessionService`.
   - Contains a resilient fallback engine ensuring deterministic, zero-crash execution during offline demonstrations, unit tests, and CI/CD pipelines.

---

## 3. Prompt Design & Few-Shot Rationale

### Anti-Hallucination Constraints
Medical summarization cannot tolerate probabilistic inaccuracies. Fabricating a hazard ratio or inflating an efficacy metric can lead to misinformed clinical assessments. The Summarizer Agent prompt incorporates strict negative constraints:
- *"ONLY state facts and numbers explicitly present in the source abstract."*
- *"DO NOT infer statistics, patient outcomes, or claims not written in the text."*
- *"If limitations are not explicitly stated, note 'Not explicitly stated in source abstract'."*

### Gold-Standard Few-Shot Anchoring
The prompt incorporates two handwritten clinical gold-standard pairs directly in the system instruction:
1. **Empagliflozin in Heart Failure (EMPEROR-Preserved, NEJM)**: Exemplifies extraction of composite endpoints, hazard ratios (`0.79; 95% CI 0.69-0.90; P<0.001`), adverse event balances, and subgroups.
2. **Pembrolizumab in Colorectal Cancer (KEYNOTE-177, NEJM)**: Exemplifies phase 3 oncology trial reporting, progression-free survival doubling (`16.5 vs 8.2 months`), grade 3+ toxicities, and study caveats.

These few-shot examples anchor the model's vocabulary, statistical precision, and conciseness, drastically suppressing hallucinations before verification.

---

## 4. Verification Methodology & 85%+ Quality Gating

The TCS brief requires an **85%+ quality rating**. Rather than relying on subjective human assessment or generic ROUGE/BLEU scores (which penalize abstractive rephrasing and fail to detect critical numerical errors), our architecture deploys a **programmatic Verification Gate**:

$$\text{Quality Gate} = \begin{cases} \text{PASS}, & \text{Confidence Score} \ge 85 \land |\text{Flagged Claims}| = 0 \\ \text{FAIL}, & \text{Confidence Score} < 85 \lor |\text{Flagged Claims}| > 0 \end{cases}$$

### Scoring Rubric
- **95–100**: Flawless factual alignment. Every reported metric, sample size, and conclusion is directly substantiated by the text.
- **85–94**: All clinical facts and statistics are 100% accurate; minor benign wording variations that preserve exact medical meaning.
- **70–84**: Minor unverified assertion or ambiguous extrapolation.
- **< 70**: Numerical mismatch, fabricated endpoint, or contradictory claim.

Any summary scoring below 85% is flagged with specific offending statements for clinician review or automated regeneration.

---

## 5. User Interface & Evaluation Framework

### CLI Interface (`cli.py`)
- `--query "<term>"`: Queries live NCBI PubMed, retrieves abstracts, and streams structured summaries with verification audit logs.
- `--file <path>`: Ingests an ad-hoc local abstract file.
- `--batch-file <path>`: Executes batch processing over local datasets (e.g. `data/synthetic_abstracts.json`) with aggregate metrics (total processed, pass rate %, average confidence).

### Web Demonstration Interface
- **ADK Web UI (`adk web .`)**: Native Google ADK developer UI connecting directly to the root agent (`medlit_agent`) for conversational debugging and inspection.
- **Streamlit Demo UI (`app.py`)**: Interactive web application featuring:
  - Batch execution on 6 preloaded synthetic medical abstracts across diverse specialties.
  - Live PubMed querying with interactive result cards.
  - Custom abstract text sandbox.
  - Downloadable JSON audit reports.

---

## 6. Theoretical Scaling Roadmap (Future Horizons)
While designed as a lightweight, modular system for TCS Technology Day, the architecture is decoupled to allow seamless production expansion without refactoring core logic:

1. **Throughput & Concurrency**:
   - Replace sequential loops with `asyncio.gather` worker pools or distributed message queues (Celery / Redis / Google Cloud Pub/Sub) to process thousands of abstracts concurrently.
2. **E-Utilities Rate Limits**:
   - Configure NCBI API key authentication (increasing limits from 3 to 10 req/sec) paired with exponential backoff and Redis-backed response caching.
3. **Persistence & Deduplication**:
   - Attach a persistent database (PostgreSQL with pgvector or Google Cloud Spanner) to index abstracts by PMID and cache verified summaries, preventing recomputation.
4. **Batch Inference API**:
   - Migrate large-scale offline runs to Gemini's Batch API for cost optimization and throughput efficiency.
5. **Multi-Tenancy & Authorization**:
   - Integrate OAuth2 / Google Workspace SSO with organization-level access controls and audit logging for institutional deployments.
6. **Active Regenerative Feedback Loop**:
   - Transform the Verifier into an active refinement gate: if `confidence_score < 85`, automatically feed `flagged_claims` back into the Summarizer agent with an error-correction prompt for iterative self-healing.
