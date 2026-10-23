# SlicerROS2 Publications Scripts

Utility scripts for maintaining and updating `publications.bib`.

## Setup

```zsh
# Create virtual environment (once)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r scripts/requirements.txt
```

---

## Available Scripts

### `find_new_papers.py` — Search for new publications

Searches OpenAlex, CrossRef, and arXiv for papers mentioning `SlicerROS2`, `ros2_igtl_bridge`, and related 3D Slicer / ROS 2 keywords. Each result is presented interactively with a relevance filter to exclude non-robotics matches (such as biological reactive oxygen species).

```zsh
# Search a specific year range
python3 scripts/find_new_papers.py --start-year 2024 --end-year 2026

# Search with custom queries
python3 scripts/find_new_papers.py --query "SlicerROS2" "ros2_igtl_bridge"
```

**Interactive prompts:**
* `y` — add to `publications.bib` (you will be prompted to select the library: `SlicerROS2`, `ROS2_IGTL`, `ROS_IGTL`, or `SlicerROS2 and ROS2_IGTL`)
* `n` — reject (saved to `rejected_papers.json` so it won't be suggested again)
* `o` — open publication URL / DOI in your web browser
* `s` — skip (will be suggested again on future runs)
* `q` — quit

---

### `cleanup_bib.py` — Normalise and sort the bib file

Normalises month strings to standard 3-letter macros, standardises field order and 2-space indentation, and sorts entries chronologically (newest first). **Run this after any addition or edit.**

```zsh
python3 scripts/cleanup_bib.py
```

---

### `deduplicate_bib.py` — Find and remove duplicate entries

Detects identical DOIs and high-similarity titles, allowing you to interactively keep one entry or merge fields from both.

```zsh
# Interactive review
python3 scripts/deduplicate_bib.py

# Dry-run report only (no writes)
python3 scripts/deduplicate_bib.py --dry-run
```

---

### `enrich_metadata.py` — Back-fill missing metadata

Queries OpenAlex using polite API access to automatically fill in missing abstracts, open access PDF links, and DOIs. Results are cached in `cache/` to avoid redundant network calls.

```zsh
python3 scripts/enrich_metadata.py
```

---

## Recommended Update Workflow

```zsh
# 1. Search for new papers
python3 scripts/find_new_papers.py --start-year 2025 --end-year 2026

# 2. Enrich missing abstracts / OA links
python3 scripts/enrich_metadata.py

# 3. Clean and sort
python3 scripts/cleanup_bib.py

# 4. Check git diff and commit
git status
git add publications.bib rejected_papers.json
git commit -m "Add new publications for SlicerROS2 and ros2-igtl"
```
