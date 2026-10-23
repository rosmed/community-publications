# SlicerROS2 & ROS2-IGTL Community Publications

Curated bibliography of research publications, theses, preprints, and open-source works that integrate **3D Slicer** with **ROS 2** (Robot Operating System 2), focusing on:
* **[SlicerROS2](https://github.com/rosmed/slicer_ros2_module)** (`slicer_ros2_module`): native ROS 2 node communication, `tf2` coordinate frame integration, and real-time robot visualization in 3D Slicer.
* **[ros2_igtl_bridge](https://github.com/openigtlink/ros2_igtl_bridge)**: OpenIGTLink protocol bridge facilitating network streaming between ROS 2 and medical navigation/computing software.

The live web interface allows searching, filtering by package and publication type, viewing abstracts, and exporting citations (BibTeX, APA, IEEE, RIS).

---

## Web Interface

To browse the publications locally:

```zsh
# Start a simple local HTTP server:
python3 -m http.server 8000

# Open in your browser:
# http://localhost:8000
```

When hosted via GitHub Pages, the site runs directly from the root of this repository.

---

## Custom BibTeX Fields

In addition to standard BibTeX fields (`author`, `title`, `year`, `journal`, `doi`, `abstract`, etc.), entries in `publications.bib` support the following custom fields:

### `rosmed_library`
Indicates the software package(s) or library used or discussed in the work:
* `rosmed_library={SlicerROS2}`: works using or extending `SlicerROS2`
* `rosmed_library={ROS2_IGTL}`: works using `ros2_igtl_bridge` (ROS 2 OpenIGTLink bridge)
* `rosmed_library={ROS_IGTL}`: works using `ROS-IGTL-Bridge` (ROS 1 OpenIGTLink bridge)
* `rosmed_library={SlicerROS2 and ROS2_IGTL}`: works using or benchmarking multiple libraries

### `date_added`
Records the date (in `YYYY-MM-DD` ISO format) when the entry was added to the database:
* `date_added={2026-08-31}`

---

## How to Contribute

If you published work using SlicerROS2 or ros2_igtl_bridge, or know of a paper that should be included:

1. **Fork** this repository.
2. Add your entry to `publications.bib`.
3. Run the cleanup script to format and sort the file:
   ```zsh
   python3 scripts/cleanup_bib.py
   ```
4. Submit a **Pull Request**.

---

## Maintenance Scripts

Utility scripts for searching new papers, normalizing BibTeX, and deduplicating entries are provided in `scripts/`:

* **`python3 scripts/find_new_papers.py`**: Interactively searches OpenAlex, CrossRef, and arXiv for new matching papers.
* **`python3 scripts/cleanup_bib.py`**: Formats, sorts chronologically, and cleans up `publications.bib`.
* **`python3 scripts/deduplicate_bib.py`**: Detects duplicate entries by DOI and title similarity.
* **`python3 scripts/enrich_metadata.py`**: Fetches missing abstracts and open access PDF links via OpenAlex.

See [scripts/README.md](scripts/README.md) for full instructions and dependencies.
