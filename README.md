# Medical Literature Summarization & Verification Tool (MedLit AI)

> **TCS Technology Day Challenge Submission**  
> An autonomous AI agent system built with **Google ADK (Agent Development Kit)** and **Google Gemini** that ingests medical abstracts and generates concise, structured, and factual summaries with programmatic verification against an **85%+ quality rating threshold**.

---

## 🌟 Key Features

- **Multi-Agent ADK Architecture**:
  - **PubMed Retrieval Tool** (`tools/pubmed_tool.py`): Connects to NCBI E-utilities (`esearch` + `efetch`) with automated XML parsing and rate limiting.
  - **Domain-Tuned Summarizer Agent** (`agents/summarizer_agent.py`): Produces structured JSON across 5 required medical sections (Objective, Methodology, Key Findings, Relevance, Limitations) anchored with gold-standard few-shot clinical examples.
  - **Adversarial Verifier Agent** (`agents/verifier_agent.py`): Performs atomic claim-by-claim verification and enforces the **>= 85% quality gate**.
- **Batch Processing**: Summarizes multiple abstracts sequentially with aggregate metrics (total processed, pass rate %, average confidence).
- **Zero Patient Data**: Strictly uses publicly available NCBI PubMed abstracts and realistic synthetic clinical trial records (`data/synthetic_abstracts.json`).
- **Dual Interfaces**:
  - **Terminal CLI** (`cli.py`): Clean, color-coded structured reports for batch automation.
  - **Interactive Streamlit Web UI** (`app.py`): Visual demo cards, live PubMed querying, and pass/fail metric gauges.
  - **Native ADK Web UI** (`adk web .`): Direct inspection of ADK root agent and tool execution traces.
- **Full Test Suite** (`tests/test_pipeline.py`): Automated unit & integration tests covering XML parsing, schema compliance, verification gating, and pipeline execution.

---

## 📁 Repository Structure

```
medlit-summarizer/
├── agents/
│   ├── __init__.py
│   ├── agent.py                 # ADK root agent entrypoint for `adk web .`
│   ├── summarizer_agent.py      # ADK agent: generates 5-section structured summary
│   └── verifier_agent.py        # ADK agent: checks summary against source
├── tools/
│   ├── __init__.py
│   └── pubmed_tool.py           # ADK FunctionTool wrapping esearch/efetch
├── pipeline.py                  # Orchestrates Summarizer -> Verifier -> output
├── cli.py                       # CLI entrypoint for batch & single runs
├── app.py                       # Streamlit interactive demo Web UI
├── data/
│   ├── sample_abstract.txt      # Sample text abstract for quick CLI test
│   └── synthetic_abstracts.json # 6 synthetic clinical abstracts (no patient data)
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py         # Pytest suite
├── docs/
│   ├── approach.md              # In-depth architectural & prompt design report
│   └── progress-log.md          # Milestone-by-milestone build log
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.11 or higher (Python 3.12 recommended)
- `uv` (recommended) or standard `python3`

### 2. Create and Activate Virtual Environment

```bash
# Using uv (fastest)
uv venv .venv --python 3.12
source .venv/bin/activate

# Or using standard python
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
uv pip install -r requirements.txt
# or: pip install -r requirements.txt
```

### 4. Configure API Key (Optional for Live Gemini Calls)

Copy `.env.example` to `.env` and insert your Gemini API Key:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-2.0-flash"
```

*(Note: If no API key is provided, the pipeline automatically runs in resilient offline mode using its built-in medical extraction engine, ensuring zero crashes during offline evaluation or demo recordings).*

---

## 💻 Usage Guide

### Mode A: Command-Line Interface (`cli.py`)

#### 1. Batch Run on Synthetic Dataset (Offline Demo Safety Net)
```bash
python cli.py --batch-file data/synthetic_abstracts.json
```

#### 2. Live PubMed Query Search & Summarization
```bash
python cli.py --query "cancer immunotherapy" --max-results 3
```

#### 3. Single Abstract File
```bash
python cli.py --file data/sample_abstract.txt
```

#### 4. Save Output to JSON
```bash
python cli.py --batch-file data/synthetic_abstracts.json --output results.json
```

---

### Mode B: Streamlit Web UI (`app.py`)

Launch the visual interactive demo:

```bash
streamlit run app.py
```

The browser UI provides:
- **Tab 1: Synthetic Dataset (Batch Demo)** — 1-click batch summarization of 6 clinical trial abstracts with pass/fail badges, confidence gauges, and JSON export.
- **Tab 2: Live PubMed Search** — Real-time search query against NCBI Entrez E-utilities.
- **Tab 3: Custom Abstract Input** — Freeform text sandbox for pasting any abstract.

---

### Mode C: Native Google ADK Web UI (`adk web`)

Launch Google ADK's native developer server:

```bash
adk web .
```

Navigate to `http://127.0.0.1:8000` to interact with `medlit_agent` and inspect live agent event streams and tool calls.

---

## 🧪 Running Automated Tests

Run the test suite with `pytest`:

```bash
pytest tests/test_pipeline.py -v
```

All 7 tests validate:
1. NCBI PubMed XML parsing (`test_pubmed_xml_parsing`)
2. 5-section Pydantic schema conformance (`test_summarizer_schema_conformance`)
3. Factual verification score passing (`test_verifier_factual_consistency_pass`)
4. Verifier rejection of hallucinated statistics (`test_verifier_flags_hallucinated_statistics`)
5. End-to-end single abstract execution (`test_pipeline_single_abstract`)
6. End-to-end batch processing (`test_pipeline_batch_execution`)
7. Strict non-patient synthetic dataset constraints (`test_synthetic_data_integrity`)

---

## 📊 Summary Structure & Quality Bar

Every abstract is transformed into 5 standardized sections:
1. **🎯 Objective**: Core clinical question or hypothesis.
2. **🔬 Methodology**: Cohort size, study design, arms, and treatment duration.
3. **📊 Key Findings**: Precise statistical results (HRs, CIs, p-values, endpoints).
4. **🏥 Clinical Relevance**: Translational and clinical practice implications.
5. **⚠️ Limitations**: Explicitly noted constraints or study boundaries.

### Quality Gating Rule
$$\text{Status} = \begin{cases} \mathbf{PASSED}, & \text{Confidence Score} \ge 85\% \text{ and 0 flagged claims} \\ \mathbf{REVIEW\ NEEDED}, & \text{Confidence Score} < 85\% \text{ or flagged claims exist} \end{cases}$$

---

## 📜 Documentation

- Detailed architecture and design rationale: [`docs/approach.md`](docs/approach.md)
- Step-by-step milestone progress log: [`docs/progress-log.md`](docs/progress-log.md)
