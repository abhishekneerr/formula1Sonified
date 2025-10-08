## Repository structure

```text
formula1/
│
├── modules/            # Core modules for loading, analysis, plotting, utils
│   ├── analysis.py
│   ├── data_loader.py
│   ├── plotting.py
│   ├── telemetry.py
│   ├── utils.py
│
├── pages/              # Streamlit multipage UI
│   ├── 2_Drivers.py
│   ├── 3_Analysis.py
│   ├── 4_Plots.py
│
├── notebooks/          # Jupyter exploration notebooks
│   ├── Copy_of_F1_WC.ipynb
│   ├── F1_Segments_2025 (1).ipynb
│   ├── F1_WC.ipynb
│
├── data/               # Local cache & datasets (gitignored)
│   └── CacheFormulaOne/…   # FastF1 cache (sessions, telemetry, etc.)
│
├── Formula1.py    # Entry script for Streamlit
├── LICENSE  # CC0 1.0
├── README.md  # Project overview (this file)
├── requirements.txt  # Python dependencies
└── .gitignore          # Excludes cache/venv/artefacts

```
### Key modules

- `modules/analysis.py` — analysis helpers (laps/sections, per-driver/per-session rollups, etc.).
- `modules/data_loader.py` — data access & caching utilities (FastF1 sessions, telemetry, cache plumbing).
- `modules/plotting.py` — plotting helpers used by the Streamlit pages (matplotlib-based).
- `modules/telemetry.py` — telemetry-specific transforms/helpers.
- `modules/utils.py` — small shared utilities.

### Streamlit pages

- `2_Drivers.py` — pick drivers/seasons, compare basic stats or telemetry slices.
- `3_Analysis.py` — higher-level analysis views (segments, deltas, aggregates).
- `4_Plots.py` — curated plot gallery / quick visual checks.

### Notebooks

- `notebooks/*.ipynb` — exploratory notebooks used to prototype segments, world-championship views, etc.
  (Not required for the app, but useful for research context.)

### Data & cache

- `data/CacheFormulaOne/…` — **FastF1** HTTP/telemetry cache (auto-populated).  
  This directory can be large and is typically **gitignored**.
- If you need to rebuild the cache, delete subfolders under `data/CacheFormulaOne/` and reload sessions.

---

## Dependencies

Core stack (see `requirements.txt` for versions and full list):
- **fastf1**, **pandas**, **numpy**, **matplotlib**, **streamlit**

---
