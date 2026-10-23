#!/usr/bin/env python3
"""
Enrich publications.bib metadata using OpenAlex and Semantic Scholar APIs.
Fetches missing abstracts, open access PDFs, DOIs, and URLs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time

import requests

CACHE_DIR = "cache"
POLITE_MAILTO = "anton.deguet@jhu.edu"


def get_cache_path(identifier: str) -> str:
    hash_obj = hashlib.md5(identifier.encode("utf-8"))
    return os.path.join(CACHE_DIR, f"{hash_obj.hexdigest()}.json")


def is_cache_valid(cache_path: str, max_days: int) -> bool:
    if max_days == 0 or not os.path.exists(cache_path):
        return False
    age_days = (time.time() - os.path.getmtime(cache_path)) / 86400
    return age_days <= max_days


def load_cache(cache_path: str) -> dict | None:
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(cache_path: str, data: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error writing cache: {e}")


def fetch_openalex_by_doi(doi: str, max_days: int = 180) -> dict | None:
    cache_path = get_cache_path(f"openalex:doi:{doi.lower()}")
    if is_cache_valid(cache_path, max_days):
        return load_cache(cache_path)

    url = f"https://api.openalex.org/works/https://doi.org/{doi}?mailto={POLITE_MAILTO}"
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            data = r.json()
            save_cache(cache_path, data)
            return data
    except Exception:
        pass
    return None


def fetch_openalex_by_title(title: str, max_days: int = 180) -> dict | None:
    cache_path = get_cache_path(f"openalex:title:{title.lower()[:60]}")
    if is_cache_valid(cache_path, max_days):
        return load_cache(cache_path)

    url = f"https://api.openalex.org/works?search={requests.utils.quote(title)}&mailto={POLITE_MAILTO}&per-page=3"
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                best = results[0]
                save_cache(cache_path, best)
                return best
    except Exception:
        pass
    return None


def extract_abstract_from_openalex(data: dict) -> str:
    inv = data.get("abstract_inverted_index")
    if not inv:
        return ""
    words = []
    for word, positions in inv.items():
        for pos in positions:
            words.append((pos, word))
    words.sort()
    return " ".join(w for _, w in words)


def enrich_bib(file_path: str, max_cache_days: int = 180):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = re.split(r"(?m)^@", content)
    enriched = []
    updated_count = 0

    for idx, raw in enumerate(entries):
        if not raw.strip():
            if idx == 0:
                enriched.append(raw)
            continue

        raw = "@" + raw
        has_doi = re.search(r"\bdoi\s*=\s*\{([^}]+)\}", raw, re.IGNORECASE)
        has_abstract = re.search(r"\babstract\s*=\s*\{([^}]+)\}", raw, re.IGNORECASE)
        has_oa_pdf = re.search(r"\bopenaccesspdf\s*=\s*\{([^}]+)\}", raw, re.IGNORECASE)
        title_m = re.search(r"\btitle\s*=\s*\{([^}]+)\}", raw, re.IGNORECASE)

        doi_val = has_doi.group(1).strip() if has_doi else None
        title_val = title_m.group(1).strip() if title_m else None

        # If already has abstract, doi, openaccesspdf, nothing to enrich
        if has_abstract and has_oa_pdf and has_doi:
            enriched.append(raw)
            continue

        data = None
        if doi_val:
            data = fetch_openalex_by_doi(doi_val, max_cache_days)
        if not data and title_val:
            data = fetch_openalex_by_title(title_val, max_cache_days)

        if data:
            modified = False
            # Add abstract
            if not has_abstract:
                abstract = extract_abstract_from_openalex(data)
                if abstract:
                    clean_abs = abstract.replace("{", "").replace("}", "")
                    raw = re.sub(r",\s*\n", lambda m: f",\n  abstract = {{{clean_abs}}},\n", raw, count=1)
                    modified = True

            # Add OA PDF
            if not has_oa_pdf:
                oa_url = (data.get("open_access") or {}).get("oa_url")
                if oa_url:
                    raw = re.sub(r",\s*\n", lambda m: f",\n  openaccesspdf = {{{oa_url}}},\n", raw, count=1)
                    modified = True

            # Add DOI if missing
            if not has_doi:
                new_doi = data.get("doi")
                if new_doi:
                    clean_doi = new_doi.replace("https://doi.org/", "")
                    raw = re.sub(r",\s*\n", lambda m: f",\n  doi = {{{clean_doi}}},\n", raw, count=1)
                    modified = True

            if modified:
                updated_count += 1

        enriched.append(raw)
        time.sleep(0.1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("".join(enriched))

    print(f"Enrichment complete. Updated {updated_count} entries.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bib", default="publications.bib", help="Path to publications.bib")
    parser.add_argument("--days", type=int, default=180, help="Cache validity in days")
    args = parser.parse_args()

    enrich_bib(args.bib, max_cache_days=args.days)


if __name__ == "__main__":
    main()
