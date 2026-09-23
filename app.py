"""Streamlit Web UI for Medical Literature Summarization Tool.

Provides an interactive demo UI showcasing:
1. Batch evaluation of synthetic abstracts (offline safety net for demo video)
2. Live PubMed query retrieval and multi-abstract summarization
3. Custom abstract text input
4. Factual verification scores (85%+ quality rating display)
"""

from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from pipeline import batch_summarize, summarize_abstract
from tools.pubmed_tool import fetch_abstracts

st.set_page_config(
    page_title="MedLit Summarizer | AI Clinical Literature Agent",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #28a745;
        margin-bottom: 12px;
    }
    .badge-pass {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.9em;
    }
    .badge-fail {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.9em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/caduceus.png", width=64)
    st.title("MedLit AI Agent")
    st.caption("TCS Technology Day Challenge")
    st.markdown("---")
    st.markdown("### System Specifications")
    st.markdown("• **Architecture**: Two-Agent ADK Pipeline")
    st.markdown("• **Summarizer**: Medically Tuned Agent")
    st.markdown("• **Verifier**: Adversarial Peer Reviewer")
    st.markdown("• **Quality Standard**: >= 85% Confidence")
    st.markdown("• **Source Data**: NCBI PubMed / Synthetic")
    st.markdown("---")
    st.info("🔒 Zero patient-identifiable data used. Purely public/synthetic literature abstracts.")

# Header
st.title("🩺 Medical Literature Summarization & Verification Tool")
st.markdown(
    "Automated clinical abstract summarization with domain-specific prompt tuning and rigorous "
    "claim-level verification ensuring strict compliance with the **>= 85% quality bar**."
)

tab_batch, tab_pubmed, tab_manual = st.tabs([
    "📦 Synthetic Dataset (Batch Demo)",
    "🔍 Live PubMed Search",
    "📝 Custom Abstract Input",
])


def render_result_card(res: dict, index: int, total: int):
    """Renders a single summarized result as an interactive Streamlit card."""
    summary = res.get("summary") or {}
    score = res.get("confidence_score", 0)
    passed = res.get("passed", False)
    flagged = res.get("flagged_claims", [])
    notes = res.get("verification_notes", "")
    title = res.get("title", f"Abstract #{index}")
    pmid = res.get("pmid") or summary.get("source_pmid") or "N/A"
    pub_date = res.get("pub_date", "N/A")
    authors = res.get("authors", "N/A")

    badge_html = (
        f"<span class='badge-pass'>✅ PASSED ({score}%)</span>"
        if passed
        else f"<span class='badge-fail'>⚠️ REVIEW NEEDED ({score}%)</span>"
    )

    with st.container():
        st.markdown(
            f"### {index}. {title} &nbsp; {badge_html}",
            unsafe_allow_html=True,
        )
        st.caption(f"**PMID**: {pmid} | **Date**: {pub_date} | **Authors**: {authors}")

        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**1. 🎯 Objective:** {summary.get('objective', 'N/A')}")
            st.markdown(f"**2. 🔬 Methodology:** {summary.get('methodology', 'N/A')}")
            st.markdown(f"**3. 📊 Key Findings:** {summary.get('key_findings', 'N/A')}")
            st.markdown(f"**4. 🏥 Clinical Relevance:** {summary.get('relevance', 'N/A')}")
            st.markdown(f"**5. ⚠️ Limitations:** {summary.get('limitations', 'N/A')}")

        with col2:
            st.metric("Verifier Confidence", f"{score}%", delta=f"{score - 85}% vs Target")
            st.markdown(f"**Quality Gate Met:** {'Yes' if passed else 'No'}")
            st.markdown(f"**Audit Notes:** {notes}")
            if flagged:
                st.error("Flagged Claims:\n" + "\n".join(f"- {c}" for c in flagged))
            else:
                st.success("No factual discrepancies detected.")

        st.markdown("---")


# TAB 1: Synthetic Dataset Demo
with tab_batch:
    st.subheader("Batch Evaluation on Synthetic Medical Abstracts")
    st.write(
        "Demonstrates sequential batch processing of 6 diverse clinical abstracts without patient data. "
        "Each abstract undergoes independent extraction and adversarial verification."
    )

    synthetic_file = Path("data/synthetic_abstracts.json")
    if synthetic_file.is_file():
        with open(synthetic_file, "r", encoding="utf-8") as f:
            sample_data = json.load(f)
        st.write(f"Loaded **{len(sample_data)}** benchmark abstracts across Oncology, Cardiology, Neurology, and more.")

        if st.button("🚀 Run Batch Summarization & Verification", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            results = []
            for i, item in enumerate(sample_data, 1):
                status_text.text(f"Processing abstract {i}/{len(sample_data)}: {item['title'][:40]}...")
                single_res = batch_summarize([item])[0]
                results.append(single_res)
                progress_bar.progress(i / len(sample_data))

            status_text.text("Batch processing complete!")

            # Aggregate Metrics
            total = len(results)
            passed = sum(1 for r in results if r.get("passed", False))
            avg_score = sum(r.get("confidence_score", 0) for r in results) / total

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Abstracts", total)
            m2.metric("Pass Rate (>=85%)", f"{(passed/total)*100:.1f}%", f"{passed}/{total} Passed")
            m3.metric("Average Confidence Score", f"{avg_score:.1f}%")

            st.markdown("---")
            for idx, res in enumerate(results, 1):
                render_result_card(res, idx, total)

            # Download JSON option
            st.download_button(
                label="📥 Download Batch Results (JSON)",
                data=json.dumps(results, indent=2),
                file_name="medlit_batch_results.json",
                mime="application/json",
            )
    else:
        st.warning("`data/synthetic_abstracts.json` not found.")


# TAB 2: Live PubMed Search
with tab_pubmed:
    st.subheader("Live PubMed Literature Retrieval & Summarization")
    st.write("Fetch real-time peer-reviewed abstracts using NCBI E-utilities (esearch + efetch).")

    col_q, col_n = st.columns([4, 1])
    with col_q:
        query = st.text_input("PubMed Search Query", value="cancer immunotherapy clinical trial 2024")
    with col_n:
        max_results = st.number_input("Max Results", min_value=1, max_value=10, value=3)

    if st.button("🔍 Fetch & Summarize PubMed Articles"):
        with st.spinner(f"Querying NCBI PubMed for '{query}'..."):
            abstracts = fetch_abstracts(query=query, max_results=max_results)

        if not abstracts:
            st.error(f"No articles found for '{query}'. Try a broader medical term.")
        else:
            st.success(f"Retrieved {len(abstracts)} articles. Running Summarizer and Verifier agents...")
            results = batch_summarize(abstracts)

            for idx, res in enumerate(results, 1):
                render_result_card(res, idx, len(results))


# TAB 3: Custom Abstract Input
with tab_manual:
    st.subheader("Manual Abstract Input")
    st.write("Paste any medical abstract text to generate a structured summary and factual audit.")

    sample_default = ""
    sample_path = Path("data/sample_abstract.txt")
    if sample_path.is_file():
        sample_default = sample_path.read_text(encoding="utf-8")

    user_text = st.text_area(
        "Abstract Text",
        value=sample_default,
        height=220,
        placeholder="Paste full medical abstract here...",
    )
    custom_pmid = st.text_input("Optional PMID", value="38291099")

    if st.button("🩺 Summarize & Verify"):
        if not user_text.strip():
            st.error("Please paste an abstract text.")
        else:
            with st.spinner("Executing Summarizer & Verifier agents..."):
                res = summarize_abstract(user_text, pmid=custom_pmid)
                res["title"] = "Custom Submitted Abstract"
                render_result_card(res, 1, 1)
