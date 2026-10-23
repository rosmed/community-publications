#!/usr/bin/env python3
"""
Search for new SlicerROS2 and ros2-igtl publications and interactively
add them to publications.bib.

Search sources:
  1. OpenAlex          — broad open index; abstracts, affiliations, open access
  2. CrossRef          — published journals and conference proceedings
  3. arXiv             — preprints and open-access articles
  4. Semantic Scholar  — citation graphs and abstracts (optional key)

BibTeX is fetched directly from doi.org via content negotiation when available.

Usage:
    python3 scripts/find_new_papers.py --start-year 2021 --end-year 2026
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET

import requests

SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
REJECTED_FILE = "rejected_papers.json"
POLITE_MAILTO = "anton.deguet@jhu.edu"

DEFAULT_QUERIES = [
    "SlicerROS2",
    "slicer_ros2",
    "slicer-ros2",
    "ros2_igtl_bridge",
    "ros2-igtl",
    "ros2_igtl",
    '"3D Slicer" ROS2',
    '"3D Slicer" "ROS 2"',
    "OpenIGTLink ROS2",
    'OpenIGTLink "ROS 2"',
]

DISQUALIFIERS = [
    "reactive oxygen species",
    "intracellular ros",
    "ros generation",
    "ros levels",
    "ros accumulation",
    "ros signaling",
    "ros production",
    "3d food printing",
    "meat slicer",
    "vegetable slicer",
    "gcode slicer",
    "cura slicer",
    "slicer software for 3d printing",
    "laser slicing",
]

RELEVANCE_TERMS = [
    "slicer", "ros2", "ros 2", "robot", "igtl", "openigtlink",
    "surgical", "intervention", "medical", "haptic", "teleoperat",
    "needle", "tracking", "navigation", "biomedical"
]


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.lower().strip()
    for prefix in (
        "https://doi.org/", "http://doi.org/",
        "https://dx.doi.org/", "http://dx.doi.org/",
        "doi:",
    ):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip()


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = re.sub(r"\\[a-zA-Z]+(?:\{[^}]*\})?", " ", title)
    t = re.sub(r"\{([^}]*)\}", r"\1", t)
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def is_relevant(title: str, abstract: str = "", venue: str = "") -> bool:
    combined = f"{title} {abstract} {venue}".lower()
    if any(d in combined for d in DISQUALIFIERS):
        return False
    matches = sum(1 for term in RELEVANCE_TERMS if term in combined)
    return matches >= 2


def guess_package(text: str) -> str:
    lower = text.lower()
    has_slicer = "slicerros2" in lower or "slicer_ros2" in lower or "slicer-ros2" in lower or ("slicer" in lower and ("ros2" in lower or "ros 2" in lower))
    has_igtl = "igtl" in lower or "openigtlink" in lower or "ros2_igtl" in lower or "ros2-igtl" in lower

    if has_slicer and has_igtl:
        return "slicer_ros2 and ros2_igtl"
    if has_igtl:
        return "ros2_igtl"
    return "slicer_ros2"


def load_existing_data(bib_path: str) -> tuple[set[str], set[str]]:
    dois = set()
    titles = set()
    if not os.path.exists(bib_path):
        return dois, titles

    with open(bib_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    for m in re.finditer(r"\bdoi\s*=\s*\{([^}]+)\}", content, re.IGNORECASE):
        dois.add(normalize_doi(m.group(1)))

    for m in re.finditer(r"\btitle\s*=\s*\{([^}]+)\}", content, re.IGNORECASE):
        titles.add(normalize_title(m.group(1)))

    return dois, titles


def load_rejected(path: str = REJECTED_FILE) -> tuple[set[str], set[str]]:
    dois = set()
    titles = set()
    if not os.path.exists(path):
        return dois, titles
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                if item.get("doi"):
                    dois.add(normalize_doi(item["doi"]))
                if item.get("title"):
                    titles.add(normalize_title(item["title"]))
    except Exception as e:
        print(f"Warning: could not read {path}: {e}")
    return dois, titles


def save_rejected(paper: dict, path: str = REJECTED_FILE) -> None:
    data = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

    data.append({
        "title": paper.get("title"),
        "doi": normalize_doi(paper.get("doi", "")),
        "year": paper.get("year"),
        "rejected_on": datetime.date.today().isoformat(),
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def doi_to_bibtex(doi: str) -> str | None:
    norm = normalize_doi(doi)
    if not norm:
        return None
    url = f"https://doi.org/{norm}"
    headers = {"Accept": "application/x-bibtex; charset=utf-8"}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200 and r.text.strip().startswith("@"):
            return r.text.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def search_openalex(query: str, start_year: int, end_year: int, existing_dois: set[str], existing_titles: set[str], rejected_dois: set[str], rejected_titles: set[str]) -> list[dict]:
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": f"publication_year:{start_year}-{end_year}",
        "per-page": 50,
        "mailto": POLITE_MAILTO,
    }
    print(f"Searching OpenAlex for '{query}' ({start_year}–{end_year})...")
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        print(f"  OpenAlex error: {e}")
        return []

    results = []
    for item in data.get("results", []):
        doi = normalize_doi(item.get("doi") or "")
        title = item.get("title") or ""
        norm_title = normalize_title(title)

        if doi and (doi in existing_dois or doi in rejected_dois):
            continue
        if norm_title in existing_titles or norm_title in rejected_titles:
            continue

        abstract = ""
        inv = item.get("abstract_inverted_index")
        if inv:
            w_pos = []
            for w, positions in inv.items():
                for p in positions:
                    w_pos.append((p, w))
            w_pos.sort()
            abstract = " ".join(w for _, w in w_pos)

        venue = (item.get("primary_location") or {}).get("source", {}).get("display_name") or ""

        if not is_relevant(title, abstract, venue):
            continue

        authors = [a.get("author", {}).get("display_name") for a in item.get("authorships", []) if a.get("author")]
        year = item.get("publication_year")

        open_access_pdf = (item.get("open_access") or {}).get("oa_url")
        url_link = (item.get("primary_location") or {}).get("landing_page_url")

        results.append({
            "source": "OpenAlex",
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "abstract": abstract,
            "venue": venue,
            "openaccesspdf": open_access_pdf,
            "url": url_link,
            "arxiv": None,
        })
    print(f"  -> {len(results)} relevant candidate(s)")
    return results


def search_crossref(query: str, start_year: int, end_year: int, existing_dois: set[str], existing_titles: set[str], rejected_dois: set[str], rejected_titles: set[str]) -> list[dict]:
    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "filter": f"from-pub-date:{start_year}-01,until-pub-date:{end_year}-12",
        "rows": 40,
        "mailto": POLITE_MAILTO,
    }
    print(f"Searching CrossRef for '{query}' ({start_year}–{end_year})...")
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return []
        items = r.json().get("message", {}).get("items", [])
    except Exception as e:
        print(f"  CrossRef error: {e}")
        return []

    results = []
    for item in items:
        doi = normalize_doi(item.get("DOI") or "")
        titles = item.get("title") or []
        title = titles[0] if titles else ""
        norm_title = normalize_title(title)

        if doi and (doi in existing_dois or doi in rejected_dois):
            continue
        if norm_title in existing_titles or norm_title in rejected_titles:
            continue

        venue = (item.get("container-title") or [""])[0]
        abstract = item.get("abstract", "")
        abstract = re.sub(r"<[^>]+>", " ", abstract).strip()

        if not is_relevant(title, abstract, venue):
            continue

        authors = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            authors.append(f"{given} {family}".strip())

        issued = item.get("issued", {}).get("date-parts", [[None]])[0][0]

        results.append({
            "source": "CrossRef",
            "title": title,
            "authors": authors,
            "year": issued,
            "doi": doi,
            "abstract": abstract,
            "venue": venue,
            "url": item.get("URL"),
            "openaccesspdf": None,
            "arxiv": None,
        })
    print(f"  -> {len(results)} relevant candidate(s)")
    return results


def search_arxiv(query: str, start_year: int, end_year: int, existing_dois: set[str], existing_titles: set[str], rejected_dois: set[str], rejected_titles: set[str]) -> list[dict]:
    clean_q = query.replace('"', '')
    encoded_query = urllib.parse.quote(f'all:"{clean_q}"')
    url = f"https://export.arxiv.org/api/query?search_query={encoded_query}&max_results=30&sortBy=submittedDate&sortOrder=descending"
    print(f"Searching arXiv for '{query}'...")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.text)
    except Exception as e:
        print(f"  arXiv error: {e}")
        return []

    results = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        title = re.sub(r"\s+", " ", title_el.text.strip()) if title_el is not None else ""
        norm_title = normalize_title(title)
        if norm_title in existing_titles or norm_title in rejected_titles:
            continue

        published = entry.find("atom:published", ns)
        pub_year = int(published.text[:4]) if (published is not None and len(published.text) >= 4) else None
        if pub_year and (pub_year < start_year or pub_year > end_year):
            continue

        doi_el = entry.find("atom:doi", ns)
        doi = normalize_doi(doi_el.text) if doi_el is not None else ""
        if doi and (doi in existing_dois or doi in rejected_dois):
            continue

        summary_el = entry.find("atom:summary", ns)
        abstract = re.sub(r"\s+", " ", summary_el.text.strip()) if summary_el is not None else ""

        if not is_relevant(title, abstract, "arXiv"):
            continue

        id_el = entry.find("atom:id", ns)
        arxiv_url = id_el.text.strip() if id_el is not None else ""

        authors = [a.find("atom:name", ns).text.strip() for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]

        results.append({
            "source": "arXiv",
            "title": title,
            "authors": authors,
            "year": pub_year,
            "doi": doi,
            "abstract": abstract,
            "venue": "arXiv preprint",
            "url": arxiv_url,
            "openaccesspdf": arxiv_url.replace("abs", "pdf") if "abs" in arxiv_url else None,
            "arxiv": arxiv_url,
        })
    print(f"  -> {len(results)} relevant candidate(s)")
    return results


def append_to_bib(paper: dict, bib_path: str, package_tag: str) -> bool:
    bib = paper.get("bibtex")
    today = datetime.date.today().isoformat()

    if bib:
        # Inject package, date_added, and abstract if missing
        if "package" not in bib:
            bib = re.sub(r",\s*\n", f",\n  package = {{{package_tag}}},\n", bib, count=1)
        if "date_added" not in bib:
            bib = re.sub(r",\s*\n", f",\n  date_added = {{{today}}},\n", bib, count=1)
        if paper.get("abstract") and "abstract" not in bib:
            escaped_abstract = paper["abstract"].replace("{", "").replace("}", "")
            bib = re.sub(r",\s*\n", lambda m: f",\n  abstract = {{{escaped_abstract}}},\n", bib, count=1)
        entry_text = bib.strip() + "\n\n"
    else:
        # Fallback manual BibTeX entry
        first_author = "Unknown"
        if paper.get("authors"):
            parts = paper["authors"][0].split()
            first_author = parts[-1] if parts else "Author"
        first_author = re.sub(r"[^\w]", "", first_author)
        year = str(paper.get("year") or datetime.date.today().year)
        key = f"{first_author}{year}"

        authors_str = " and ".join(paper.get("authors") or ["Unknown"])
        doi_line = f"  doi = {{{paper['doi']}}},\n" if paper.get("doi") else ""
        url_line = f"  url = {{{paper['url']}}},\n" if paper.get("url") else ""
        arxiv_line = f"  arxiv = {{{paper['arxiv']}}},\n" if paper.get("arxiv") else ""
        abstract_line = f"  abstract = {{{paper['abstract']}}},\n" if paper.get("abstract") else ""

        entry_text = (
            f"@misc{{{key},\n"
            f"  author = {{{authors_str}}},\n"
            f"  title = {{{paper['title']}}},\n"
            f"  year = {{{year}}},\n"
            f"{doi_line}{url_line}{arxiv_line}{abstract_line}"
            f"  package = {{{package_tag}}},\n"
            f"  date_added = {{{today}}},\n"
            f"}}\n\n"
        )

    try:
        with open(bib_path, "a", encoding="utf-8") as f:
            f.write(entry_text)
        print(f"  Added to {bib_path}!")
        return True
    except Exception as e:
        print(f"Error appending to bib: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-year", type=int, default=2021, help="Start publication year (default: 2021)")
    parser.add_argument("--end-year", type=int, default=2026, help="End publication year (default: 2026)")
    parser.add_argument("--bib", default="publications.bib", help="Path to publications.bib")
    parser.add_argument("--query", nargs="*", default=DEFAULT_QUERIES, help="Search queries")
    args = parser.parse_args()

    existing_dois, existing_titles = load_existing_data(args.bib)
    rejected_dois, rejected_titles = load_rejected(REJECTED_FILE)
    print(f"Loaded {len(existing_dois)} existing DOIs, {len(existing_titles)} existing titles, "
          f"{len(rejected_dois)} rejected DOIs, {len(rejected_titles)} rejected titles.\n")

    all_candidates: list[dict] = []
    seen: set[str] = set()

    for q in args.query:
        # 1. OpenAlex
        for item in search_openalex(q, args.start_year, args.end_year, existing_dois, existing_titles, rejected_dois, rejected_titles):
            t = normalize_title(item["title"])
            if t and t not in seen:
                seen.add(t)
                all_candidates.append(item)
        time.sleep(0.3)

        # 2. CrossRef
        for item in search_crossref(q, args.start_year, args.end_year, existing_dois, existing_titles, rejected_dois, rejected_titles):
            t = normalize_title(item["title"])
            if t and t not in seen:
                seen.add(t)
                all_candidates.append(item)
        time.sleep(0.5)

        # 3. arXiv
        for item in search_arxiv(q, args.start_year, args.end_year, existing_dois, existing_titles, rejected_dois, rejected_titles):
            t = normalize_title(item["title"])
            if t and t not in seen:
                seen.add(t)
                all_candidates.append(item)
        time.sleep(0.5)

    print("\n" + "=" * 70)
    print(f"Search complete: {len(all_candidates)} new unique candidate(s) to review.")
    print("=" * 70)

    for i, paper in enumerate(all_candidates, 1):
        print(f"\n[{i}/{len(all_candidates)}] Source: {paper['source']}")
        print(f"  Title:   {paper['title']}")
        print(f"  Authors: {', '.join(paper['authors'][:5])}{' et al.' if len(paper['authors']) > 5 else ''}")
        print(f"  Year:    {paper.get('year')}   Venue: {paper.get('venue')}")
        if paper.get("doi"):
            print(f"  DOI:     https://doi.org/{paper['doi']}")
        if paper.get("abstract"):
            print(f"  Abstract: {paper['abstract'][:250]}...")

        # Fetch BibTeX
        if paper.get("doi"):
            print("  Fetching BibTeX from doi.org...", end=" ", flush=True)
            bib = doi_to_bibtex(paper["doi"])
            if bib:
                paper["bibtex"] = bib
                print("✓")
            else:
                print("failed, will use metadata fallback.")

        # Default package guess
        combined_text = f"{paper['title']} {paper.get('abstract', '')}"
        guessed_pkg = guess_package(combined_text)

        # Open in browser?
        open_url = f"https://doi.org/{paper['doi']}" if paper.get("doi") else (paper.get("arxiv") or paper.get("url"))

        while True:
            choice = input("\n  Add? [y]es / [n]o (reject) / [o]pen url / [s]kip / [q]uit: ").lower().strip()
            if choice in ("o", "open"):
                if open_url:
                    webbrowser.open(open_url)
                else:
                    print("  No URL available.")
                continue
            elif choice in ("y", "yes"):
                pkg_input = input(f"  Package tag [1: slicer_ros2, 2: ros2_igtl, 3: both] (default: {guessed_pkg}): ").strip()
                if pkg_input == "1":
                    selected_pkg = "slicer_ros2"
                elif pkg_input == "2":
                    selected_pkg = "ros2_igtl"
                elif pkg_input == "3":
                    selected_pkg = "slicer_ros2 and ros2_igtl"
                elif pkg_input:
                    selected_pkg = pkg_input
                else:
                    selected_pkg = guessed_pkg

                if append_to_bib(paper, args.bib, selected_pkg):
                    existing_titles.add(normalize_title(paper["title"]))
                    if paper.get("doi"):
                        existing_dois.add(normalize_doi(paper["doi"]))
                break
            elif choice in ("n", "no"):
                save_rejected(paper, REJECTED_FILE)
                print("  ❌ Rejected and saved to rejected_papers.json.")
                break
            elif choice in ("s", "skip"):
                print("  ⏭  Skipped.")
                break
            elif choice in ("q", "quit"):
                print("Exiting.")
                sys.exit(0)
            else:
                print("  Please type y, n, o, s, or q.")

    print("\n" + "=" * 70)
    print("Review complete. Run 'python3 scripts/cleanup_bib.py' to normalise the bib file.")


if __name__ == "__main__":
    main()
