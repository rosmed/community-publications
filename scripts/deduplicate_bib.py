#!/usr/bin/env python3
"""
Interactively find and remove duplicate entries from publications.bib.

Detection strategies (in order of confidence):
  1. Identical DOI (after normalisation)  — almost certainly the same paper
  2. Title similarity ≥ 0.92              — very likely the same paper
  3. Title similarity ≥ 0.75              — probable duplicate; show for review

For each suspected duplicate you can:
  [1] keep entry A   — discard B
  [2] keep entry B   — discard A
  [m] merge          — combine both, preferring richer field values
  [s] skip           — leave both in the file (not a duplicate)
  [q] quit           — stop reviewing; save any changes made so far

Usage:
    python3 scripts/deduplicate_bib.py
    python3 scripts/deduplicate_bib.py --bib path/to/file.bib
    python3 scripts/deduplicate_bib.py --dry-run   # report only, no writes
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_doi(doi: str) -> str:
    doi = doi.lower().strip()
    for prefix in (
        "https://doi.org/", "http://doi.org/",
        "https://dx.doi.org/", "http://dx.doi.org/",
        "doi:",
    ):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def normalize_title(title: str) -> str:
    """Lowercase, strip LaTeX, remove punctuation, collapse whitespace."""
    title = re.sub(r"\\[a-zA-Z]+(?:\{[^}]*\})?", " ", title)
    title = re.sub(r"\{([^}]*)\}", r"\1", title)
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def title_similarity(t1: str, t2: str) -> float:
    return SequenceMatcher(None, normalize_title(t1), normalize_title(t2)).ratio()


def entry_doi(entry: dict) -> str | None:
    raw = entry.get("doi", "").strip()
    return normalize_doi(raw) if raw else None


def entry_display_fields(entry: dict) -> list[str]:
    return [k for k in entry if k not in ("ENTRYTYPE", "ID")]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicates(
    entries: list[dict],
    min_doi_title_sim: float = 0.50,
) -> tuple[list[tuple[dict, dict, str, float]], dict[str, list[dict]]]:
    pairs: list[tuple[dict, dict, str, float]] = []
    seen: set[frozenset] = set()
    bad_doi_groups: dict[str, list[dict]] = {}

    doi_groups: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        d = entry_doi(e)
        if d:
            doi_groups[d].append(e)

    for doi, group in doi_groups.items():
        if len(group) < 2:
            continue

        if len(group) >= 3:
            bad_doi_groups[doi] = group
            continue

        a, b = group[0], group[1]
        t_a = a.get("title", "")
        t_b = b.get("title", "")
        sim = title_similarity(t_a, t_b) if (t_a and t_b) else 0.0

        if sim < min_doi_title_sim:
            bad_doi_groups[doi] = group
            continue

        key = frozenset([a["ID"], b["ID"]])
        if key not in seen:
            seen.add(key)
            pairs.append((a, b, "doi", 1.0))

    # --- Step 2: pairwise title similarity ---
    for a, b in combinations(entries, 2):
        key = frozenset([a["ID"], b["ID"]])
        if key in seen:
            continue

        t_a = a.get("title", "")
        t_b = b.get("title", "")
        if not t_a or not t_b:
            continue

        sim = title_similarity(t_a, t_b)

        if sim >= 0.92:
            seen.add(key)
            pairs.append((a, b, "title-high", sim))
        elif sim >= 0.75:
            seen.add(key)
            pairs.append((a, b, "title-mid", sim))

    CONF_ORDER = {"doi": 0, "title-high": 1, "title-mid": 2}
    pairs.sort(key=lambda x: (CONF_ORDER[x[2]], -x[3]))

    return pairs, bad_doi_groups


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

CONFIDENCE_LABEL = {
    "doi":        "⚠️   DOI match",
    "title-high": "🔶  High similarity (title ≥ 0.92)",
    "title-mid":  "🔷  Moderate similarity (title ≥ 0.75)",
}


def display_entry(label: str, e: dict) -> None:
    authors = e.get("author", "Unknown")
    if len(authors) > 70:
        authors = authors[:67] + "..."
    title = e.get("title", "No title")
    year = e.get("year", "????")
    venue = e.get("journal") or e.get("booktitle") or e.get("howpublished") or ""
    doi = e.get("doi", "")
    pkg = e.get("package", "")

    fields = [k for k in entry_display_fields(e) if e[k].strip()]
    f_str = ", ".join(sorted(fields))
    wrapped = []
    while len(f_str) > 60:
        idx = f_str.rfind(", ", 0, 60)
        if idx == -1:
            idx = 60
        wrapped.append(f_str[:idx])
        f_str = f_str[idx:].lstrip(", ")
    if f_str:
        wrapped.append(f_str)

    print(f"  ┌─ [{label}]  @{e.get('ENTRYTYPE','?')}{{{e['ID']},")
    print(f"  │  Title:  {title}")
    print(f"  │  Author: {authors}")
    print(f"  │  Year:   {year}   Venue: {venue[:50]}")
    if doi:
        print(f"  │  DOI:    https://doi.org/{normalize_doi(doi)}")
    if pkg:
        print(f"  │  Package:{pkg}")
    print(f"  │  Fields: {wrapped[0] if wrapped else ''} ({len(fields)} total)")
    for wl in wrapped[1:]:
        print(f"  │          {wl}")
    print(f"  └{'─'*65}")


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

UNION_FIELDS = {
    "doi", "semanticscholar", "arxiv", "ieeexplore", "url",
    "package", "abstract", "keywords", "pages", "volume",
    "number", "isbn", "issn", "openaccesspdf", "pdf",
}

PREFER_RICHER = {
    "author", "title", "journal", "booktitle", "year",
    "publisher", "school", "month", "address",
}


def merge_entries(a: dict, b: dict) -> dict:
    a_fields = [k for k in a if k not in ("ENTRYTYPE", "ID") and a[k].strip()]
    b_fields = [k for k in b if k not in ("ENTRYTYPE", "ID") and b[k].strip()]
    if len(b_fields) > len(a_fields):
        base, other = dict(b), dict(a)
    else:
        base, other = dict(a), dict(b)

    for field, value in other.items():
        if field in ("ENTRYTYPE", "ID"):
            continue
        value = value.strip() if isinstance(value, str) else value
        existing = base.get(field, "").strip() if isinstance(base.get(field), str) else ""

        if field == "date_added":
            if not existing:
                base[field] = value
            elif value:
                base[field] = min(existing, value)
        elif field == "package":
            if not existing:
                base[field] = value
            elif existing != value:
                pkgs = set(p.strip() for p in (existing + " and " + value).split(" and ") if p.strip())
                base[field] = " and ".join(sorted(pkgs))
        elif field in UNION_FIELDS:
            if not existing:
                base[field] = value
            elif value and len(value) > len(existing):
                base[field] = value
        elif field in PREFER_RICHER:
            if not existing:
                base[field] = value
        else:
            if not existing and value:
                base[field] = value

    return base


# ---------------------------------------------------------------------------
# BibTeX I/O
# ---------------------------------------------------------------------------

FIELD_ORDER = [
    "author", "title", "journal", "booktitle", "year", "volume", "number",
    "pages", "month", "publisher", "school", "editor", "series", "collection",
    "address", "organization", "issn", "isbn",
    "doi", "url", "urldate", "ieeexplore",
    "semanticscholar", "arxiv", "arxivid", "archiveprefix", "primaryclass", "eprint",
    "pdf", "openaccesspdf", "howpublished", "pubstate", "date", "tppubtype",
    "copyright", "language",
    "package", "date_added",
    "keywords", "abstract",
]


def load_bib(path: str) -> bibtexparser.bibdatabase.BibDatabase:
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    with open(path, "r", encoding="utf-8") as f:
        return bibtexparser.load(f, parser=parser)


def write_bib(path: str, db: bibtexparser.bibdatabase.BibDatabase) -> None:
    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None
    writer.display_order = FIELD_ORDER
    writer.add_trailing_comma = True
    with open(path, "w", encoding="utf-8") as f:
        bibtexparser.dump(db, f, writer=writer)


def main():
    default_bib = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "publications.bib"
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bib", default=default_bib, help="Path to publications.bib")
    parser.add_argument("--dry-run", action="store_true", help="Report candidates without making any changes")
    parser.add_argument("--min-sim", type=float, default=0.75, help="Minimum title similarity threshold (default 0.75)")
    args = parser.parse_args()

    print(f"Loading {args.bib}...")
    try:
        db = load_bib(args.bib)
    except FileNotFoundError:
        print(f"Error: {args.bib} not found.")
        sys.exit(1)

    entries = db.entries
    print(f"Loaded {len(entries)} entries. Scanning for duplicates...\n")

    pairs, bad_doi_groups = find_duplicates(entries)

    if bad_doi_groups:
        print(f"⚠️  {len(bad_doi_groups)} container / shared DOI group(s) detected:")
        for doi, grp in bad_doi_groups.items():
            print(f"   DOI https://doi.org/{doi} shared by {len(grp)} entries:")
            for e in grp:
                print(f"     - [{e['ID']}] {e.get('title','?')[:60]}")
        print()

    if not pairs:
        print("✅ No duplicate entries found.")
        return

    print(f"Found {len(pairs)} candidate duplicate pair(s).\n")

    if args.dry_run:
        for i, (a, b, reason, conf) in enumerate(pairs, 1):
            print(f"[{i:02d}] {CONFIDENCE_LABEL[reason]}  (conf={conf:.2f})")
            print(f"     A: [{a['ID']}] {a.get('title','?')[:65]}")
            print(f"     B: [{b['ID']}] {b.get('title','?')[:65]}")
        print(f"\nDry-run complete. Run without --dry-run to review interactively.")
        return

    backup = args.bib + ".dedup-bak"
    shutil.copyfile(args.bib, backup)
    print(f"Backup saved to {backup}\n")

    to_remove: set[str] = set()
    replacements: dict[str, dict] = {}

    for i, (a, b, reason, conf) in enumerate(pairs, 1):
        if a["ID"] in to_remove or b["ID"] in to_remove:
            continue

        print("=" * 70)
        print(f"  Duplicate {i}/{len(pairs)}  |  {CONFIDENCE_LABEL[reason]}  (conf={conf:.2f})")
        print("=" * 70)
        display_entry("A", a)
        display_entry("B", b)

        while True:
            choice = input("\n  [1] keep A / [2] keep B / [m] merge / [s] skip / [q] quit: ").lower().strip()
            if choice == "1":
                to_remove.add(b["ID"])
                print(f"  ✅ Keeping {a['ID']}, removing {b['ID']}")
                break
            elif choice == "2":
                to_remove.add(a["ID"])
                print(f"  ✅ Keeping {b['ID']}, removing {a['ID']}")
                break
            elif choice in ("m", "merge"):
                merged = merge_entries(a, b)
                winner_id = a["ID"] if len(entry_display_fields(a)) >= len(entry_display_fields(b)) else b["ID"]
                loser_id = b["ID"] if winner_id == a["ID"] else a["ID"]
                merged["ID"] = winner_id
                replacements[winner_id] = merged
                to_remove.add(loser_id)
                merged_fields = [k for k in merged if k not in ("ENTRYTYPE", "ID")]
                print(f"  🔀 Merged into {winner_id} ({len(merged_fields)} fields), removed {loser_id}")
                break
            elif choice in ("s", "skip"):
                print("  ⏭  Skipped — both entries retained.")
                break
            elif choice in ("q", "quit"):
                print("Stopping review.")
                break
            else:
                print("  Please type 1, 2, m, s, or q.")
        if choice in ("q", "quit"):
            break

    if not to_remove and not replacements:
        print("\nNo changes made.")
        return

    new_entries = []
    for e in entries:
        eid = e["ID"]
        if eid in to_remove:
            continue
        if eid in replacements:
            new_entries.append(replacements[eid])
        else:
            new_entries.append(e)

    db.entries = new_entries
    print(f"\nRemoved {len(to_remove)} entries; {len(replacements)} merge(s) applied.")
    print(f"Writing {len(new_entries)} entries back to {args.bib}...")
    write_bib(args.bib, db)
    print("Done. Run 'python3 scripts/cleanup_bib.py' to normalise formatting.")


if __name__ == "__main__":
    main()
