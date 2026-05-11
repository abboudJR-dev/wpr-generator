"""Streamlit UI for the Weekly Progress Report Generator.

Workflow:
1. Upload — drag-drop the 7 DCR PDFs + logs xlsx
2. Auto-extract — show extracted manpower, activities, submittals
3. Review tabs — edit metadata, manpower, activities, submittals, NCRs, AOCs, photos
4. Generate — produce the .pptx and offer download
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from dataclasses import asdict
from datetime import date as Date, datetime, timedelta
from pathlib import Path
from typing import Optional

import streamlit as st


def _output_dir() -> Path:
    """Where to write generated decks. In dev: `./output/`. In a bundled EXE:
    next to the EXE so the user can find it without digging into _internal/."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    out = base / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


OUTPUT_DIR = _output_dir()

from builder.build import WEEKDAY_NAMES, build_pptx, state_from_inputs
from builder.state import (
    AOCEntry, ActivityRow, ConcreteRow, DayPhotos, LookaheadRow,
    ManpowerDay, NCREntry, ProgrammeRow, SubContractor, WPRState,
)
from extractors.captioner import CaptionRequest, generate_captions_parallel
from extractors.dcr import DCRData, parse_dcrs
from extractors.logs import LogsData, parse_logs

from PIL import Image


def _resolve_gemini_key() -> Optional[str]:
    """Look for the Gemini key in: st.secrets → env var → session state.

    Streamlit Cloud users set `GEMINI_API_KEY` in the app's Secrets UI
    (Settings → Secrets); local users can `set GEMINI_API_KEY=…` or enter
    it via the in-app prompt (kept in session memory only). Get a free
    key at https://aistudio.google.com/app/apikey (no credit card).
    """
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            key = st.secrets.get(env_name)
            if key:
                return key
        except (FileNotFoundError, KeyError, AttributeError):
            pass
        env_key = os.environ.get(env_name)
        if env_key:
            return env_key
    return st.session_state.get("gemini_api_key")


@st.cache_data(show_spinner=False)
def _thumbnail(photo_bytes: bytes, max_side: int = 320) -> bytes:
    """Downscale a photo for in-UI preview to keep browser memory in check.

    Cached on the photo's content so reruns are instant. Full-resolution
    bytes are still used at deck-generation time."""
    img = Image.open(io.BytesIO(photo_bytes))
    img.thumbnail((max_side, max_side))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue()


st.set_page_config(
    page_title="WPR Generator — Emirates Pearl Construction",
    page_icon="📊",
    layout="wide",
)


# ---- Helpers ----------------------------------------------------------------

def _save_uploaded(file_uploader_value, suffix: str) -> Path:
    """Persist a Streamlit UploadedFile to a temp path and return it."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(file_uploader_value.read())
    tmp.flush()
    return Path(tmp.name)


def _ensure_state():
    """Initialise st.session_state keys we depend on."""
    ss = st.session_state
    ss.setdefault("dcrs", None)
    ss.setdefault("logs", None)
    ss.setdefault("wpr", None)
    ss.setdefault("dcr_files", None)
    ss.setdefault("logs_file", None)
    ss.setdefault("generated_path", None)


# ---- UI sections ------------------------------------------------------------

def section_upload():
    st.subheader("1.  Upload weekly inputs")
    col_a, col_b = st.columns(2)
    with col_a:
        dcr_files = st.file_uploader(
            "Daily Construction Reports (7 PDFs)",
            type=["pdf"],
            accept_multiple_files=True,
            key="upload_dcrs",
        )
    with col_b:
        logs_file = st.file_uploader(
            "Project logs workbook (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=False,
            key="upload_logs",
        )
    return dcr_files, logs_file


def section_metadata(state: WPRState):
    st.subheader("Project metadata")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        state.week_no = int(st.number_input("Week number", min_value=1, max_value=200,
                                            value=state.week_no, step=1, key="meta_week"))
        state.week_no_str = str(state.week_no)
        state.next_week_no = state.week_no + 1
    with col_b:
        state.issue_date = st.text_input("Issue date", value=state.issue_date, key="meta_issue")
        state.report_ref = st.text_input("Report reference", value=state.report_ref, key="meta_ref")
    with col_c:
        state.period = st.text_input("Reporting period (long)", value=state.period, key="meta_period")
        state.period_short = st.text_input("Reporting period (short)", value=state.period_short,
                                           key="meta_period_short")
        state.next_week_period = st.text_input("Next week period",
                                               value=state.next_week_period, key="meta_next")

    st.markdown("##### Programme")
    pcol_a, pcol_b, pcol_c = st.columns(3)
    with pcol_a:
        state.weeks_elapsed = int(st.number_input("Weeks elapsed", min_value=0, max_value=300,
                                                  value=state.weeks_elapsed, key="meta_we"))
    with pcol_b:
        state.weeks_total = int(st.number_input("Weeks total", min_value=1, max_value=300,
                                                value=state.weeks_total, key="meta_wt"))
    with pcol_c:
        state.time_elapsed_pct = st.text_input("Time elapsed %", value=state.time_elapsed_pct,
                                               key="meta_te")


def section_manpower(state: WPRState):
    st.subheader("Daily manpower")
    st.caption("Actual headcount auto-filled from DCR sub-contractor totals. Edit below as needed.")
    rows = []
    for i, d in enumerate(state.manpower_days):
        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1])
            with cols[0]:
                d.label = st.text_input(f"Day {i+1} label", value=d.label, key=f"mp_label_{i}")
            with cols[1]:
                d.planned = int(st.number_input("Planned", min_value=0, max_value=999,
                                                value=d.planned, key=f"mp_plan_{i}"))
            with cols[2]:
                d.actual = int(st.number_input("Actual", min_value=0, max_value=999,
                                               value=d.actual, key=f"mp_act_{i}"))
            with cols[3]:
                st.metric("Variance", d.variance, delta=d.variance, label_visibility="visible")
        rows.append(d)
    state.manpower_days = rows

    # Refresh observations
    from builder.slides.manpower import default_observations
    state.manpower_observations = default_observations(state)


def section_activities(state: WPRState):
    st.subheader("Site activities — current week")
    st.caption("Edit Zone A (Lower Raft) and Zone B (Higher Raft) activity tables.")

    state.zone_a_label = st.text_input("Zone A banner", value=state.zone_a_label, key="zone_a_label")
    state.zone_a_activities = _edit_activity_list("zone_a", state.zone_a_activities)

    state.zone_b_label = st.text_input("Zone B banner", value=state.zone_b_label, key="zone_b_label")
    state.zone_b_activities = _edit_activity_list("zone_b", state.zone_b_activities)

    state.week_summary_text = st.text_area(
        "Week summary callout",
        value=state.week_summary_text, key="week_summary", height=80,
    )


def _edit_activity_list(prefix: str, rows: list[ActivityRow]) -> list[ActivityRow]:
    """Use st.data_editor to edit ActivityRow list."""
    if not rows:
        st.info(f"No {prefix} activities yet.")
        return rows
    df_data = [
        {
            "Activity": r.activity,
            "Start": r.start_date,
            "Status": r.status_label,
            "Status kind": r.status_kind,
            "Progress": r.progress,
            "Remarks": r.remarks,
        }
        for r in rows
    ]
    edited = st.data_editor(
        df_data,
        num_rows="dynamic",
        column_config={
            "Status kind": st.column_config.SelectboxColumn(
                options=["completed", "progress", "pending", "risk"], required=True,
            ),
        },
        key=f"{prefix}_editor",
        use_container_width=True,
    )
    return [
        ActivityRow(
            activity=row.get("Activity", "") or "",
            start_date=row.get("Start", "") or "",
            status_kind=row.get("Status kind", "progress") or "progress",
            status_label=row.get("Status", "") or "",
            progress=row.get("Progress", "") or "",
            remarks=row.get("Remarks", "") or "",
        )
        for row in edited if (row.get("Activity") or "").strip()
    ]


def section_lookahead(state: WPRState):
    st.subheader(f"Lookahead — Week {state.next_week_no}")

    state.zone_a_lookahead = _edit_lookahead("look_a", state.zone_a_lookahead)
    state.zone_b_lookahead = _edit_lookahead("look_b", state.zone_b_lookahead)

    bullets = "\n".join(state.lookahead_focus_bullets)
    new_bullets = st.text_area("Key Focus bullets (one per line)",
                               value=bullets, key="focus_bullets", height=110)
    state.lookahead_focus_bullets = [b.strip() for b in new_bullets.split("\n") if b.strip()]


def _edit_lookahead(prefix: str, rows: list[LookaheadRow]) -> list[LookaheadRow]:
    df_data = [
        {"Activity": r.activity, "Current Status": r.current_status, "Target": r.target, "Note": r.note}
        for r in rows
    ]
    edited = st.data_editor(df_data, num_rows="dynamic", key=f"{prefix}_ed", use_container_width=True)
    return [
        LookaheadRow(
            activity=row.get("Activity", "") or "",
            current_status=row.get("Current Status", "") or "",
            target=row.get("Target", "") or "",
            note=row.get("Note", "—") or "—",
        )
        for row in edited if (row.get("Activity") or "").strip()
    ]


def section_quality(state: WPRState):
    st.subheader("Quality, NCRs, Submittals")
    st.caption("Submittal counts are auto-filled from the logs workbook. NCRs / Concrete are editable.")

    st.markdown("**NCR Register**")
    df_ncr = [
        {"Ref": n.ref, "Subject": n.subject, "Issued": n.issued, "Closed": n.closed, "Status": n.status}
        for n in state.ncrs
    ]
    edited_ncr = st.data_editor(df_ncr, num_rows="dynamic", key="ncrs_ed", use_container_width=True)
    state.ncrs = [
        NCREntry(
            ref=row.get("Ref", "") or "",
            subject=row.get("Subject", "") or "",
            issued=row.get("Issued", "") or "",
            closed=row.get("Closed", "") or "",
            status=row.get("Status", "● CLOSED") or "● CLOSED",
        )
        for row in edited_ncr if (row.get("Ref") or "").strip()
    ]
    state.ncr_note = st.text_area("NCR commentary callout", value=state.ncr_note,
                                  key="ncr_note", height=70)

    st.markdown("**Concrete Quality**")
    df_conc = [
        {"Element": c.element, "Grade": c.grade, "3-Day": c.day3, "7-Day": c.day7,
         "28-Day": c.day28, "28-Day kind": c.day28_kind}
        for c in state.concrete_rows
    ]
    edited_conc = st.data_editor(
        df_conc, num_rows="dynamic", key="conc_ed", use_container_width=True,
        column_config={
            "28-Day kind": st.column_config.SelectboxColumn(options=["completed", "pending"], required=True),
        },
    )
    state.concrete_rows = [
        ConcreteRow(
            element=row.get("Element", "") or "",
            grade=row.get("Grade", "") or "",
            day3=row.get("3-Day", "") or "",
            day7=row.get("7-Day", "") or "",
            day28=row.get("28-Day", "") or "",
            day28_kind=row.get("28-Day kind", "completed") or "completed",
        )
        for row in edited_conc if (row.get("Element") or "").strip()
    ]

    if state.submittal_categories:
        st.markdown("**Submittal Status Dashboard (auto)**")
        rows = [c.display_row() for c in state.submittal_categories]
        st.dataframe(
            {h: col for h, col in zip(["Category", "TOTAL", "A", "B", "C/D", "E", "F"], zip(*rows))},
            use_container_width=True,
        )
        st.caption(state.rfi_footnote)


def section_aocs(state: WPRState):
    st.subheader("Areas of Concern")
    df = [
        {"Ref": a.ref, "Title": a.title, "Responsible": a.responsible, "Target": a.target,
         "Impact": a.impact, "Impact kind": a.impact_kind}
        for a in state.aocs
    ]
    edited = st.data_editor(
        df, num_rows="dynamic", key="aocs_ed", use_container_width=True,
        column_config={
            "Impact kind": st.column_config.SelectboxColumn(
                options=["success", "amber", "risk"], required=True,
            ),
        },
    )
    state.aocs = [
        AOCEntry(
            ref=row.get("Ref", "") or "",
            title=row.get("Title", "") or "",
            responsible=row.get("Responsible", "") or "",
            target=row.get("Target", "") or "",
            impact=row.get("Impact", "") or "",
            impact_kind=row.get("Impact kind", "success") or "success",
        )
        for row in edited if (row.get("Ref") or "").strip()
    ]
    state.aoc_assessment = st.text_area("Overall assessment callout",
                                        value=state.aoc_assessment, height=80,
                                        key="aoc_assess")


def section_programme(state: WPRState):
    st.subheader("Programme status")
    df = [
        {
            "Work package": r.work_package,
            "Planned start": r.planned_start,
            "Planned finish": r.planned_finish,
            "Progress this week": r.progress_this_week,
            "% Complete": r.pct_complete,
            "Status": r.status,
        }
        for r in state.programme_rows
    ]
    edited = st.data_editor(
        df, num_rows="dynamic", key="prog_ed", use_container_width=True,
        column_config={
            "Status": st.column_config.SelectboxColumn(options=["complete", "progress"], required=True),
        },
    )
    state.programme_rows = [
        ProgrammeRow(
            work_package=row.get("Work package", "") or "",
            planned_start=row.get("Planned start", "") or "",
            planned_finish=row.get("Planned finish", "") or "",
            progress_this_week=row.get("Progress this week", "") or "",
            pct_complete=row.get("% Complete", "") or "",
            status=row.get("Status", "progress") or "progress",
        )
        for row in edited if (row.get("Work package") or "").strip()
    ]
    state.programme_statement = st.text_area("Programme statement callout",
                                             value=state.programme_statement, height=110,
                                             key="prog_stmt")


def section_photos(state: WPRState, dcrs: list[DCRData]):
    st.subheader("Site progress photos")
    st.caption("Pick two photos per day. The deck shows 6 photo slides (Mon-Sat).")
    if not dcrs:
        st.info("Upload DCRs first.")
        return

    new_days: list[DayPhotos] = []
    new_dates = []
    new_labels = []

    for i, dcr in enumerate(dcrs[:6]):
        st.markdown(f"### Day {i+1} — {WEEKDAY_NAMES[dcr.date.weekday()] if dcr.date else 'TBD'}, "
                    f"{dcr.date.strftime('%d %B %Y') if dcr.date else 'no date'}")
        if not dcr.photos:
            st.warning("No photos extracted from this DCR.")
            new_days.append(DayPhotos())
            if dcr.date:
                new_dates.append(dcr.date)
                new_labels.append(WEEKDAY_NAMES[dcr.date.weekday()])
            continue

        # Photo grid (use small thumbnails to keep browser memory low —
        # full-res bytes are kept in dcr.photos[i].bytes_ for the deck build)
        cols = st.columns(min(len(dcr.photos), 6))
        for p_idx, photo in enumerate(dcr.photos):
            with cols[p_idx % len(cols)]:
                st.image(_thumbnail(photo.bytes_), caption=f"#{p_idx + 1}",
                         use_container_width=True)

        labels = [f"#{j+1}" for j in range(len(dcr.photos))]
        # Default captions come from state.photo_days (which the build module
        # seeded from each DCR's date) — generic placeholders the user edits.
        existing = state.photo_days[i] if i < len(state.photo_days) else None
        c1, c2 = st.columns(2)
        with c1:
            sel_a = st.selectbox(f"Day {i+1} — Photo A", labels,
                                 index=0, key=f"sel_a_{i}")
            cap_a = st.text_input(f"Caption A",
                                  value=(existing.caption_a if existing else ""),
                                  key=f"cap_a_{i}")
        with c2:
            default_b = labels[1] if len(labels) > 1 else labels[0]
            sel_b = st.selectbox(f"Day {i+1} — Photo B", labels,
                                 index=min(1, len(labels) - 1), key=f"sel_b_{i}")
            cap_b = st.text_input(f"Caption B",
                                  value=(existing.caption_b if existing else ""),
                                  key=f"cap_b_{i}")

        a_idx = labels.index(sel_a)
        b_idx = labels.index(sel_b)
        photo_a = dcr.photos[a_idx]
        photo_b = dcr.photos[b_idx]
        new_days.append(DayPhotos(
            photo_a_bytes=photo_a.bytes_, photo_a_ext=photo_a.ext, caption_a=cap_a,
            photo_b_bytes=photo_b.bytes_, photo_b_ext=photo_b.ext, caption_b=cap_b,
        ))
        if dcr.date:
            new_dates.append(dcr.date)
            new_labels.append(WEEKDAY_NAMES[dcr.date.weekday()])

    state.photo_days = new_days
    state.photo_dates = new_dates
    state.photo_day_labels = new_labels

    # ---- AI captioning (uses each day's activity list as context) ----
    st.divider()
    _render_ai_caption_block(state, dcrs)


def _render_ai_caption_block(state: WPRState, dcrs: list[DCRData]) -> None:
    """The "Generate captions with AI" panel inside the Photos tab.

    Sends each selected A/B photo to Claude Haiku 4.5 with that day's
    activity list as context, runs them in parallel via ThreadPoolExecutor,
    and writes the results back to state.photo_days. Clears the caption
    text-input widget keys before rerun so the new values render.
    """
    st.subheader("AI caption generator")
    st.caption(
        "Sends the selected Photo A / Photo B for each day to Google Gemini 2.5 Flash, "
        "along with that day's recorded site activities, and asks for a one-sentence "
        "caption in the same tone as the reference deck. ~10-20 seconds for 12 photos. "
        "Free key: https://aistudio.google.com/app/apikey (no credit card)."
    )

    api_key = _resolve_gemini_key()
    if not api_key:
        st.info(
            "Enter your free Gemini API key to enable AI captioning. "
            "Get one at https://aistudio.google.com/app/apikey (no credit card). "
            "Set `GEMINI_API_KEY` in Streamlit Cloud Secrets to skip this every visit."
        )
        user_key = st.text_input(
            "Gemini API key", type="password", key="api_key_input",
            placeholder="AIza…",
        )
        if user_key:
            st.session_state["gemini_api_key"] = user_key
            api_key = user_key

    gen_btn = st.button(
        "Generate captions with AI",
        disabled=not api_key, type="primary", key="gen_captions_btn",
    )

    # If a previous run generated captions, show them inline below the button so
    # the user can see what was produced without scrolling back up to the per-day
    # caption fields. Lives in session_state because the button click rerenders.
    last_results = st.session_state.get("ai_caption_results")
    if last_results:
        st.markdown("### Generated captions")
        success_count = sum(1 for r in last_results if not r["caption"].startswith("(AI caption failed"))
        if success_count == len(last_results):
            st.success(f"Generated {success_count} captions and wrote them into the fields above. Edit any as needed.")
        elif success_count == 0:
            st.error(
                f"Captioning failed for all {len(last_results)} photos. "
                "Common causes: invalid Gemini API key, quota exhausted, or network issue. "
                "See the error text below each row for the specific reason."
            )
        else:
            st.warning(f"Generated {success_count} of {len(last_results)} captions. The others failed — see below.")

        for r in last_results:
            failed = r["caption"].startswith("(AI caption failed")
            icon = "❌" if failed else "✅"
            st.markdown(
                f"{icon} **{r['day_label']} — Photo {r['slot'].upper()}** ({r['date']}): "
                f"{r['caption']}"
            )

    if gen_btn and api_key:
        # Map each selected A/B photo to a captioning request, with the DCR's
        # activity list passed in as context.
        reqs: list[CaptionRequest] = []
        slot_map: list[tuple[int, str]] = []  # (day_index, "a"|"b")
        for i, dp in enumerate(state.photo_days):
            activities = dcrs[i].activities if i < len(dcrs) else []
            if dp.photo_a_bytes:
                reqs.append(CaptionRequest(
                    image_bytes=dp.photo_a_bytes,
                    media_type=("image/png" if dp.photo_a_ext == "png" else "image/jpeg"),
                    activities=activities,
                ))
                slot_map.append((i, "a"))
            if dp.photo_b_bytes:
                reqs.append(CaptionRequest(
                    image_bytes=dp.photo_b_bytes,
                    media_type=("image/png" if dp.photo_b_ext == "png" else "image/jpeg"),
                    activities=activities,
                ))
                slot_map.append((i, "b"))

        if not reqs:
            st.warning("No photos selected — pick at least one per day above first.")
            return

        progress = st.progress(0.0, text=f"Captioning 0/{len(reqs)}…")

        def _on_progress(done: int, total: int) -> None:
            progress.progress(done / max(total, 1), text=f"Captioning {done}/{total}…")

        captions = generate_captions_parallel(
            reqs, api_key=api_key, progress_cb=_on_progress,
        )
        progress.empty()

        # Write captions back to state
        results_for_display = []
        for caption, (i, slot) in zip(captions, slot_map):
            if slot == "a":
                state.photo_days[i].caption_a = caption
            else:
                state.photo_days[i].caption_b = caption
            day_label = state.photo_day_labels[i] if i < len(state.photo_day_labels) else f"Day {i+1}"
            date_str = state.photo_dates[i].strftime("%d %b %Y") if i < len(state.photo_dates) else ""
            results_for_display.append({
                "day_label": day_label,
                "slot": slot,
                "date": date_str,
                "caption": caption,
            })

        # Persist for inline display after the rerun
        st.session_state["ai_caption_results"] = results_for_display

        # Clear the per-day caption text-input widget keys so they re-init
        # from state.photo_days on the next render (Streamlit text inputs
        # otherwise stick to whatever was previously typed).
        for i in range(len(state.photo_days)):
            for slot in ("a", "b"):
                key = f"cap_{slot}_{i}"
                if key in st.session_state:
                    del st.session_state[key]

        st.rerun()


# ---- Main ------------------------------------------------------------------

def main():
    _ensure_state()
    ss = st.session_state

    st.title("Weekly Progress Report Generator")
    st.caption(
        "Auto-generates the 15-slide WPR deck from 7 daily reports + the project logs "
        "workbook. Match the design of the reference Week-20 deck."
    )

    dcr_files, logs_file = section_upload()

    extract_clicked = st.button(
        "Extract & build draft state", type="primary",
        disabled=not (dcr_files and len(dcr_files) >= 1 and logs_file),
    )

    if extract_clicked and dcr_files and logs_file:
        progress = st.progress(0.0, text="Saving uploads…")
        dcr_paths = [_save_uploaded(f, ".pdf") for f in dcr_files]
        logs_path = _save_uploaded(logs_file, ".xlsx")

        def _on_progress(done: int, total: int, current_name):
            text = (
                f"Parsing DCR {done}/{total} — {current_name}"
                if current_name else f"Parsing DCRs (0/{total})…"
            )
            progress.progress(min(done / max(total, 1), 1.0), text=text)

        dcrs = parse_dcrs(dcr_paths, progress_cb=_on_progress)
        progress.progress(1.0, text="Parsing logs workbook…")
        logs = parse_logs(logs_path)
        progress.progress(1.0, text="Building draft state…")
        ss.dcrs = dcrs
        ss.logs = logs
        # week_no, issue_date, report_ref, period etc. all auto-derive from DCR dates
        ss.wpr = state_from_inputs(dcrs, logs)
        ss.generated_path = None
        progress.empty()
        st.success(
            f"Parsed {len(dcrs)} DCRs and {len(logs.categories)} log categories. "
            f"Detected Week {ss.wpr.week_no} ({ss.wpr.period}). "
            "Review every tab — narrative content (activities, AOCs, programme rows) "
            "is pre-filled with Week 20 examples; edit them for your week."
        )

    if not ss.wpr:
        st.info("Upload files and click **Extract** to begin.")
        return

    st.divider()
    st.subheader("2.  Review & edit")

    tabs = st.tabs([
        "Metadata", "Manpower", "Activities", "Lookahead",
        "Quality", "AOCs", "Programme", "Photos",
    ])

    with tabs[0]:
        section_metadata(ss.wpr)
    with tabs[1]:
        section_manpower(ss.wpr)
    with tabs[2]:
        section_activities(ss.wpr)
    with tabs[3]:
        section_lookahead(ss.wpr)
    with tabs[4]:
        section_quality(ss.wpr)
    with tabs[5]:
        section_aocs(ss.wpr)
    with tabs[6]:
        section_programme(ss.wpr)
    with tabs[7]:
        section_photos(ss.wpr, ss.dcrs or [])

    st.divider()
    st.subheader("3.  Generate deck")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        out_name = st.text_input(
            "Output filename",
            value=f"Weekly_Report_No_{str(ss.wpr.week_no).zfill(3)}_GENERATED.pptx",
            key="out_name",
        )
    with col_b:
        st.write("")  # spacer
        gen_clicked = st.button("Generate PPTX", type="primary")

    if gen_clicked:
        out_path = OUTPUT_DIR / out_name
        with st.spinner("Building deck…"):
            build_pptx(ss.wpr, out_path)
        ss.generated_path = out_path
        st.success(f"Generated **{out_path}** ({out_path.stat().st_size:,} bytes).")

    if ss.generated_path and ss.generated_path.exists():
        with open(ss.generated_path, "rb") as f:
            st.download_button(
                "Download .pptx", data=f.read(),
                file_name=ss.generated_path.name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )


if __name__ == "__main__":
    main()
