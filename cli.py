#!/usr/bin/env python3
"""CLI Entrypoint for Medical Literature Summarization Tool.

Supports three operational modes:
1. Live PubMed Query:
   python cli.py --query "cancer immunotherapy" [--max-results 3]
2. Single Abstract File:
   python cli.py --file abstract.txt
3. Local Batch JSON File:
   python cli.py --batch-file data/synthetic_abstracts.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pipeline import batch_summarize, summarize_abstract
from tools.pubmed_tool import fetch_abstracts


def format_terminal_box(title: str, char: str = "=", width: int = 80) -> str:
    """Format a decorative section header."""
    pad = (width - len(title) - 2) // 2
    pad = max(2, pad)
    return f"{char * pad} {title} {char * pad}"


def print_formatted_result(res: dict[str, Any], index: int | None = None, total: int | None = None) -> None:
    """Prints a single summarized and verified abstract in a clean structured format."""
    summary = res.get("summary") or {}
    score = res.get("confidence_score", 0)
    passed = res.get("passed", False)
    flagged = res.get("flagged_claims", [])
    notes = res.get("verification_notes", "N/A")

    title = res.get("title") or "Medical Abstract"
    pmid = res.get("pmid") or summary.get("source_pmid") or "N/A"
    authors = res.get("authors") or "N/A"
    pub_date = res.get("pub_date") or "N/A"

    counter_str = f" [{index}/{total}]" if index and total else ""
    print()
    print("=" * 80)
    print(f"📄 ABSTRACT SUMMARY{counter_str}: {title}")
    print("=" * 80)
    print(f"PMID: {pmid}  |  Pub Date: {pub_date}")
    print(f"Authors: {authors}")
    print("-" * 80)

    # Status Banner
    status_icon = "✅ PASSED" if passed else "⚠️ FLAGGED"
    print(f"VERIFIER QUALITY GATE: {status_icon} (Confidence: {score}% | Quality Bar: >=85%)")
    print("-" * 80)

    # Structured Sections
    print("\n1. 🎯 OBJECTIVE:")
    print(f"   {summary.get('objective', 'N/A')}")

    print("\n2. 🔬 METHODOLOGY:")
    print(f"   {summary.get('methodology', 'N/A')}")

    print("\n3. 📊 KEY FINDINGS:")
    print(f"   {summary.get('key_findings', 'N/A')}")

    print("\n4. 🏥 CLINICAL / RESEARCH RELEVANCE:")
    print(f"   {summary.get('relevance', 'N/A')}")

    print("\n5. ⚠️ LIMITATIONS:")
    print(f"   {summary.get('limitations', 'N/A')}")

    print("-" * 80)
    print("🛡️ VERIFIER AUDIT REPORT:")
    print(f"   • Confidence Score: {score}/100")
    print(f"   • Quality Bar Met: {'YES (>= 85%)' if passed else 'NO (< 85%)'}")
    print(f"   • Notes: {notes}")
    if flagged:
        print("   • Flagged Claims:")
        for fc in flagged:
            print(f"     - {fc}")
    else:
        print("   • Flagged Claims: None (Zero factual discrepancies detected)")
    print("=" * 80)
    print()


def run_query_mode(query: str, max_results: int, output_file: str | None = None) -> None:
    """Fetch live abstracts from PubMed and summarize them."""
    print(f"\n🔍 Searching PubMed for: '{query}' (Max results: {max_results})...")
    abstracts = fetch_abstracts(query=query, max_results=max_results)

    if not abstracts:
        print(f"❌ No abstracts found on PubMed for query: '{query}'")
        return

    print(f"📥 Retrieved {len(abstracts)} articles from PubMed. Processing pipeline...\n")
    results = batch_summarize(abstracts)

    for idx, res in enumerate(results, 1):
        print_formatted_result(res, index=idx, total=len(results))

    _print_batch_summary(results)

    if output_file:
        _save_output(results, output_file)


def run_file_mode(file_path: str, output_file: str | None = None) -> None:
    """Summarize a single abstract from a plain text file."""
    path = Path(file_path)
    if not path.is_file():
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    print(f"\n📖 Reading single abstract from: {file_path}...")
    text = path.read_text(encoding="utf-8").strip()

    if not text:
        print(f"❌ Error: File {file_path} is empty.")
        sys.exit(1)

    res = summarize_abstract(text, pmid=None)
    res["title"] = path.stem.replace("_", " ").title()
    print_formatted_result(res)

    if output_file:
        _save_output([res], output_file)


def run_batch_file_mode(batch_file: str, output_file: str | None = None) -> None:
    """Summarize multiple abstracts from a local JSON file."""
    path = Path(batch_file)
    if not path.is_file():
        print(f"❌ Error: Batch file not found: {batch_file}")
        sys.exit(1)

    print(f"\n📦 Loading batch abstracts from: {batch_file}...")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error parsing JSON batch file: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        print("❌ Error: Batch JSON must contain a list of abstract objects.")
        sys.exit(1)

    print(f"🚀 Loaded {len(data)} abstracts. Executing batch Summarizer-Verifier pipeline...\n")
    results = batch_summarize(data)

    for idx, res in enumerate(results, 1):
        print_formatted_result(res, index=idx, total=len(results))

    _print_batch_summary(results)

    if output_file:
        _save_output(results, output_file)


def _print_batch_summary(results: list[dict[str, Any]]) -> None:
    """Print aggregate metrics across batch run."""
    total = len(results)
    if total == 0:
        return
    passed = sum(1 for r in results if r.get("passed", False))
    scores = [r.get("confidence_score", 0) for r in results]
    avg_score = sum(scores) / total if total else 0.0

    print("=" * 80)
    print("📈 BATCH RUN SUMMARY")
    print("-" * 80)
    print(f"Total Abstracts Processed: {total}")
    print(f"Passed Quality Bar (>= 85%): {passed}/{total} ({(passed/total)*100:.1f}%)")
    print(f"Average Verifier Confidence: {avg_score:.1f}%")
    print("=" * 80)


def _save_output(results: list[dict[str, Any]], output_file: str) -> None:
    """Save results as JSON to disk."""
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Full results saved to: {out_path.resolve()}")


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Medical Literature Summarization & Verification Tool (TCS Tech Day AI Agent)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cli.py --query "cancer immunotherapy" --max-results 3
  python cli.py --file data/sample_abstract.txt
  python cli.py --batch-file data/synthetic_abstracts.json
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--query",
        "-q",
        type=str,
        help="Search query to fetch live abstracts from PubMed via E-utilities",
    )
    group.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to a text file containing a single medical abstract",
    )
    group.add_argument(
        "--batch-file",
        "-b",
        type=str,
        help="Path to a JSON file containing a list of abstract dictionaries",
    )

    parser.add_argument(
        "--max-results",
        "-m",
        type=int,
        default=3,
        help="Maximum PubMed abstracts to fetch in --query mode (default: 3)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to write results as a JSON file",
    )

    args = parser.parse_args()

    if args.query:
        run_query_mode(args.query, max_results=args.max_results, output_file=args.output)
    elif args.file:
        run_file_mode(args.file, output_file=args.output)
    elif args.batch_file:
        run_batch_file_mode(args.batch_file, output_file=args.output)


if __name__ == "__main__":
    main()
