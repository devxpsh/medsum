"""PubMed E-utilities retrieval tool for medical literature.

Provides functions to search PubMed for articles and fetch their abstracts,
titles, authors, and publication dates via NCBI E-utilities (esearch & efetch).
Also exposes `pubmed_fetch_tool` wrapped as a Google ADK FunctionTool.
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any
import requests

try:
    from google.adk.tools import FunctionTool
except ImportError:
    # Graceful fallback if ADK is imported in an environment before installation
    FunctionTool = None  # type: ignore

logger = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# NCBI rate limit: max 3 requests/sec without API key. We enforce polite spacing.
LAST_REQUEST_TIME = 0.0
MIN_REQUEST_INTERVAL = 0.35  # ~3 requests per second limit safe guard


def _rate_limit():
    """Enforce NCBI rate limits for unauthenticated requests."""
    global LAST_REQUEST_TIME
    elapsed = time.time() - LAST_REQUEST_TIME
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    LAST_REQUEST_TIME = time.time()


def _extract_full_text(element: ET.Element | None) -> str:
    """Extract all text inside an XML element including nested tags."""
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def parse_pubmed_xml(xml_content: str) -> list[dict[str, Any]]:
    """Parse PubMed XML string and extract article metadata and abstract text.

    Args:
        xml_content: Raw XML response string from NCBI efetch.

    Returns:
        List of dictionaries with keys: pmid, title, authors, pub_date, abstract_text.
    """
    results: list[dict[str, Any]] = []
    if not xml_content or not xml_content.strip():
        return results

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"Failed to parse PubMed XML: {e}")
        return results

    # Support both PubmedArticle and PubmedBookArticle
    articles = root.findall(".//PubmedArticle")
    if not articles:
        articles = root.findall(".//PubmedBookArticle")

    for article in articles:
        medline = article.find(".//MedlineCitation")
        article_meta = article.find(".//Article")
        if article_meta is None:
            continue

        # Extract PMID
        pmid_elem = medline.find("PMID") if medline is not None else article.find(".//PMID")
        pmid = pmid_elem.text.strip() if (pmid_elem is not None and pmid_elem.text) else "N/A"

        # Extract Title
        title_elem = article_meta.find("ArticleTitle")
        title = _extract_full_text(title_elem)

        # Extract Authors
        authors_list = []
        author_elems = article_meta.findall(".//AuthorList/Author")
        for auth in author_elems:
            last = auth.find("LastName")
            fore = auth.find("ForeName")
            initials = auth.find("Initials")
            last_text = last.text.strip() if (last is not None and last.text) else ""
            first_text = fore.text.strip() if (fore is not None and fore.text) else (initials.text.strip() if initials is not None and initials.text else "")
            if last_text and first_text:
                authors_list.append(f"{last_text} {first_text}")
            elif last_text:
                authors_list.append(last_text)
            else:
                collective = auth.find("CollectiveName")
                if collective is not None and collective.text:
                    authors_list.append(collective.text.strip())

        authors_str = ", ".join(authors_list) if authors_list else "Unknown Authors"

        # Extract Pub Date
        pub_date_elem = article_meta.find(".//JournalIssue/PubDate")
        pub_date_parts = []
        if pub_date_elem is not None:
            year = pub_date_elem.find("Year")
            month = pub_date_elem.find("Month")
            day = pub_date_elem.find("Day")
            medline_date = pub_date_elem.find("MedlineDate")

            if year is not None and year.text:
                pub_date_parts.append(year.text.strip())
            if month is not None and month.text:
                pub_date_parts.append(month.text.strip())
            if day is not None and day.text:
                pub_date_parts.append(day.text.strip())
            if not pub_date_parts and medline_date is not None and medline_date.text:
                pub_date_parts.append(medline_date.text.strip())

        pub_date_str = " ".join(pub_date_parts) if pub_date_parts else "N/A"

        # Extract Abstract
        abstract_elem = article_meta.find("Abstract")
        abstract_text = ""
        if abstract_elem is not None:
            text_sections = []
            for child in abstract_elem.findall("AbstractText"):
                label = child.get("Label")
                text = _extract_full_text(child)
                if text:
                    if label:
                        text_sections.append(f"{label}: {text}")
                    else:
                        text_sections.append(text)
            abstract_text = "\n\n".join(text_sections)

        if not abstract_text:
            abstract_text = "[No abstract available in PubMed record]"

        results.append({
            "pmid": pmid,
            "title": title,
            "authors": authors_str,
            "pub_date": pub_date_str,
            "abstract_text": abstract_text,
        })

    return results


def fetch_abstracts(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Searches PubMed via NCBI E-utilities and returns article abstracts with metadata.

    Args:
        query: Medical search query (e.g. 'diabetes treatment 2024', 'cancer immunotherapy').
        max_results: Maximum number of abstracts to retrieve (default: 5).

    Returns:
        A list of dictionaries, each containing:
            - pmid: PubMed ID string
            - title: Article title
            - authors: Formatted author string
            - pub_date: Publication date string
            - abstract_text: Full abstract text
    """
    if not query or not query.strip():
        return []

    headers = {
        "User-Agent": "MedLitSummarizer/1.0 (mailto:hackathon-demo@example.com)"
    }

    # Step 1: ESearch to find PMIDs
    _rate_limit()
    esearch_params = {
        "db": "pubmed",
        "term": query.strip(),
        "retmax": max_results,
        "retmode": "json",
        "sort": "pub_date",
    }

    try:
        esearch_resp = requests.get(ESEARCH_URL, params=esearch_params, headers=headers, timeout=15)
        esearch_resp.raise_for_status()
        search_data = esearch_resp.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        logger.error(f"Error during PubMed esearch for query '{query}': {e}")
        return []

    if not id_list:
        logger.info(f"No PubMed articles found for query: '{query}'")
        return []

    # Step 2: EFetch to get XML abstracts
    _rate_limit()
    efetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "rettype": "abstract",
        "retmode": "xml",
    }

    try:
        efetch_resp = requests.get(EFETCH_URL, params=efetch_params, headers=headers, timeout=20)
        efetch_resp.raise_for_status()
        xml_text = efetch_resp.text
    except Exception as e:
        logger.error(f"Error during PubMed efetch for IDs {id_list}: {e}")
        return []

    return parse_pubmed_xml(xml_text)


# Expose as an ADK FunctionTool
if FunctionTool is not None:
    pubmed_fetch_tool = FunctionTool(fetch_abstracts)
else:
    pubmed_fetch_tool = None


if __name__ == "__main__":
    import json
    test_query = "diabetes treatment 2024"
    print(f"Testing PubMed fetch standalone with query: '{test_query}'...")
    results = fetch_abstracts(test_query, max_results=2)
    print(f"Fetched {len(results)} abstracts:\n")
    for idx, r in enumerate(results, 1):
        print(f"--- Result {idx} ---")
        print(f"PMID: {r['pmid']}")
        print(f"Title: {r['title']}")
        print(f"Authors: {r['authors']}")
        print(f"Pub Date: {r['pub_date']}")
        print(f"Abstract Preview: {r['abstract_text'][:200]}...")
        print()
