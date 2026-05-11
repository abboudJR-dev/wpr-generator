# Weekly Progress Report (WPR) Generator

A Streamlit app that ingests the week's **daily construction reports (DCRs)** plus the **project logs workbook** and auto-generates a polished 15-slide Weekly Progress Report PowerPoint.

## Live demo

Hosted on Streamlit Community Cloud — open the app, drag-drop your DCRs and logs, edit any tab, download the deck.

## Local dev

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Usage

1. Drag-drop the 7 DCR PDFs + project logs `.xlsx`.
2. Click **Extract & build draft state** (~10-15 seconds for parsing).
3. Review/edit each tab: Metadata, Manpower, Activities, Lookahead, Quality, AOCs, Programme, Photos.
4. Click **Generate PPTX** and download.

## CLI / scripting

```python
from pathlib import Path
from extractors.dcr import parse_dcrs
from extractors.logs import parse_logs
from builder.build import state_from_inputs, build_pptx

dcrs = parse_dcrs(sorted(Path("path/to/dcrs").glob("*.pdf")))
logs = parse_logs("path/to/logs.xlsx")
state = state_from_inputs(dcrs, logs, week_no=21, issue_date="13 May 2026")
build_pptx(state, "output/Weekly_Report_No_021.pptx")
```

## Project layout

```
wpr-generator/
├── app.py                    # Streamlit UI
├── launcher.py               # Entrypoint for the bundled Windows EXE
├── extractors/
│   ├── dcr.py               # DCR PDF parser (manpower, activities, photos) — PyMuPDF
│   └── logs.py              # Logs xlsx parser (9 summary blocks) — openpyxl
├── builder/
│   ├── design.py            # Color/font tokens + reusable layout primitives
│   ├── defaults.py          # Default narrative content
│   ├── state.py             # WPRState dataclass — all build inputs
│   ├── build.py             # Orchestrator: state → 15 slides → .pptx
│   └── slides/
│       ├── cover.py         # Slides 1-3
│       ├── manpower.py      # Slide 4 (with bar chart)
│       ├── activities.py    # Slides 5-6
│       ├── quality.py       # Slide 7
│       ├── aoc.py           # Slide 8
│       ├── programme.py     # Slide 9
│       └── photos.py        # Slides 10-15
├── assets/                   # Branding (logos, building render)
└── .streamlit/config.toml    # Streamlit theme
```

## Architecture notes

- **PDF parsing** uses PyMuPDF (`fitz`) with `sort=True` for reading-order text and a `ThreadPoolExecutor` for per-photo resize. ~10 seconds for 7 DCRs.
- **PowerPoint generation** uses `python-pptx`. Coordinates ported 1:1 from a reference `pptxgenjs` scaffolding — see commit history for the design tokens (palette, typography, layout primitives).
- **Photos** are downscaled to 1400px max dim at JPEG q82 before going into Streamlit session state, keeping memory well under 100 MB per session.

## What's auto-extracted vs editable

**Auto-extracted from inputs:**

- Daily sub-contractor totals → slide 4 manpower row
- Site photos (pages 3+) → available for selection on slides 10-15
- Submittal counts (PQD, TEC, MIR, NCR, RFI, DTS, WIR, WIR (MEP), SAMPLE) → slide 7 dashboard
- RFI received / under-review counts → footnote
- Reporting period from DCR dates

**Editable (defaults pre-loaded):**

- Project metadata (week #, period, issue date, ref)
- Activity narrative (Zone A / Zone B tables, week summary)
- Lookahead activities + key focus bullets
- NCR register, concrete quality, AOCs, programme rows
- Photo selection + captions per day

## Deployment

### Streamlit Community Cloud (recommended)

1. Push to a GitHub repo.
2. Visit [share.streamlit.io](https://share.streamlit.io).
3. Click **New app**, pick this repo, set:
   - Branch: `main`
   - Main file path: `app.py`
   - Python version: 3.11+
4. Click **Deploy**. First build takes ~5 minutes.

### Windows portable EXE

PyInstaller bundles the app into a self-contained folder. See `WPR-Generator.spec` and `launcher.py`. Run:

```bash
pyinstaller --noconfirm WPR-Generator.spec
```

Output lands in `dist/WPR-Generator/`. Double-click `WPR-Generator.exe` to launch.
