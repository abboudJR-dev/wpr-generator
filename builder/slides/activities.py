"""Slides 5-6: Current Week Activities + Lookahead."""
from __future__ import annotations

from pptx.util import Inches, Pt

from builder.design import (
    C, Run, SLIDE_W,
    add_blank_slide, add_bulleted_text, add_footer, add_header, add_oval,
    add_rect, add_text_box, fill_cell, set_cell_border, set_slide_background,
    style_cell_text, zone_banner,
)
from builder.state import ActivityRow, LookaheadRow, WPRState


# Status -> text color
STATUS_COLOR = {
    "completed": C.success,
    "progress":  C.teal_dark,
    "pending":   C.amber,
    "risk":      C.risk,
}


def _add_activity_table(slide, x, y, w, rows: list[ActivityRow]):
    n_rows = len(rows) + 1  # +1 for header
    n_cols = 5
    col_widths = [4.40, 1.20, 1.55, 1.10, 4.20]
    row_h = 0.28
    table_h = row_h * n_rows

    table_shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
                                         Inches(w), Inches(table_h))
    table = table_shape.table
    for ci, cw in enumerate(col_widths):
        table.columns[ci].width = Inches(cw)
    for ri in range(n_rows):
        table.rows[ri].height = Inches(row_h)

    headers = ["ACTIVITY", "START DATE", "STATUS", "PROGRESS", "REMARKS"]
    for ci, h in enumerate(headers):
        cell = table.cell(0, ci)
        fill_cell(cell, C.navy)
        align = "center" if ci in (1, 2, 3) else "left"
        style_cell_text(cell, h, color=C.white, bold=True, size=9,
                        align=align, valign="middle", char_spacing=1.5)
        set_cell_border(cell, C.line, 0.5)

    for ri, row in enumerate(rows, start=1):
        stripe = C.white if ri % 2 == 1 else C.panel
        cells_def = [
            (row.activity,     C.ink,      False, "left",   False),
            (row.start_date,   C.graphite, False, "center", False),
            (row.status_label, STATUS_COLOR.get(row.status_kind, C.ink), True, "center", False),
            (row.progress,     C.graphite, True,  "center", False),
            (row.remarks,      C.graphite, False, "left",   False),
        ]
        for ci, (text, color, bold, align, _) in enumerate(cells_def):
            cell = table.cell(ri, ci)
            fill_cell(cell, stripe)
            style_cell_text(cell, text, color=color, bold=bold, size=9,
                            align=align, valign="middle")
            set_cell_border(cell, C.line, 0.5)


def _add_lookahead_table(slide, x, y, w, rows: list[LookaheadRow]):
    n_rows = len(rows) + 1
    n_cols = 4
    col_widths = [4.30, 3.20, 3.40, 1.55]
    row_h = 0.30
    table_h = row_h * n_rows

    table_shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
                                         Inches(w), Inches(table_h))
    table = table_shape.table
    for ci, cw in enumerate(col_widths):
        table.columns[ci].width = Inches(cw)
    for ri in range(n_rows):
        table.rows[ri].height = Inches(row_h)

    headers = ["PLANNED ACTIVITY", "CURRENT STATUS", "WEEK 21 TARGET", "NOTE"]
    for ci, h in enumerate(headers):
        cell = table.cell(0, ci)
        fill_cell(cell, C.navy)
        align = "center" if ci == 3 else "left"
        style_cell_text(cell, h, color=C.white, bold=True, size=9.5,
                        align=align, valign="middle", char_spacing=1.5)
        set_cell_border(cell, C.line, 0.5)

    for ri, row in enumerate(rows, start=1):
        stripe = C.white if ri % 2 == 1 else C.panel
        cells_def = [
            (row.activity,        C.ink,       False, "left"),
            (row.current_status,  C.graphite,  False, "left"),
            (row.target,          C.teal_dark, True,  "left"),
            (row.note,            C.mute,      False, "center"),
        ]
        for ci, (text, color, bold, align) in enumerate(cells_def):
            cell = table.cell(ri, ci)
            fill_cell(cell, stripe)
            style_cell_text(cell, text, color=color, bold=bold, size=9.5,
                            align=align, valign="middle")
            set_cell_border(cell, C.line, 0.5)


def build_slide_current_week(prs, state: WPRState):
    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    # Reference subtitle format: "27 Apr – 03 May 2026  |  All progress figures are
    # Contractor assessments at 03-May-2026"
    last_dt = state.photo_dates[-1] if state.photo_dates else None
    if last_dt and len(state.photo_dates) >= 6:
        # photo_dates only has 6 entries (days 1-6); week ends on day 7 (Sun)
        from datetime import timedelta
        end_dt = last_dt + timedelta(days=1)
        as_at = end_dt.strftime("%d-%b-%Y")
    else:
        as_at = state.issue_date
    add_header(
        slide,
        title=f"CURRENT WEEK SITE ACTIVITIES — WEEK {state.week_no_str}",
        subtitle=f"{state.period_short}  |  All progress figures are Contractor assessments at {as_at}",
    )
    add_footer(slide, 4, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # Status legend (top of content)
    leg_y = 1.05
    legends = [
        (C.success, "COMPLETED"),
        (C.teal,    "IN PROGRESS"),
        (C.amber,   "PENDING / NOT STARTED"),
        (C.risk,    "DELAYED / AT RISK"),
    ]
    for i, (color, label) in enumerate(legends):
        lx = 0.45 + i * 2.15
        add_oval(slide, lx, leg_y + 0.08, 0.16, 0.16, color)
        add_text_box(
            slide, lx + 0.22, leg_y, 1.85, 0.32,
            [Run(text=label, size=9, bold=True, color=C.graphite, char_spacing=1.5)],
            valign="middle", margin=0,
        )

    # ZONE A
    zone_banner(slide, 0.45, 1.45, SLIDE_W - 0.90, state.zone_a_label, C.steel)
    _add_activity_table(slide, 0.45, 1.78, SLIDE_W - 0.90, state.zone_a_activities)

    # ZONE B
    zb_y = 4.45
    zone_banner(slide, 0.45, zb_y, SLIDE_W - 0.90, state.zone_b_label, C.teal_dark)
    _add_activity_table(slide, 0.45, zb_y + 0.33, SLIDE_W - 0.90, state.zone_b_activities)

    # Bottom callout: weekly summary
    c_y = 6.20
    add_rect(slide, 0.45, c_y, SLIDE_W - 0.90, 0.70, C.teal_soft)
    add_rect(slide, 0.45, c_y, 0.06, 0.70, C.teal)
    add_text_box(
        slide, 0.65, c_y, SLIDE_W - 1.30, 0.70,
        [
            Run(text=f"WEEK {state.week_no_str} SUMMARY  ", bold=True, color=C.teal,
                char_spacing=3, size=10),
            Run(text="—  ", color=C.teal_dark, size=10),
            Run(text="Substructure activities advanced steadily across both zones. ",
                bold=True, color=C.graphite, size=10),
            Run(text=state.week_summary_text, color=C.graphite, size=10),
        ],
        valign="middle", margin=0,
    )

    return slide


def build_slide_lookahead(prs, state: WPRState):
    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    add_header(
        slide,
        title=f"LOOKAHEAD — WEEK {state.next_week_no} PLANNED ACTIVITIES",
        subtitle=f"{state.next_week_period}  |  Subject to site conditions and Consultant approvals",
    )
    add_footer(slide, 5, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # ZONE A
    zone_banner(slide, 0.45, 1.10, SLIDE_W - 0.90, state.zone_a_label, C.steel)
    _add_lookahead_table(slide, 0.45, 1.43, SLIDE_W - 0.90, state.zone_a_lookahead)

    # ZONE B
    zb_y = 4.45
    zone_banner(slide, 0.45, zb_y, SLIDE_W - 0.90, state.zone_b_label, C.teal_dark)
    _add_lookahead_table(slide, 0.45, zb_y + 0.33, SLIDE_W - 0.90, state.zone_b_lookahead)

    # Bottom focus callout
    n_y = 5.85
    add_rect(slide, 0.45, n_y, SLIDE_W - 0.90, 1.15, C.panel, line_hex=C.line, line_width=0.5)
    add_rect(slide, 0.45, n_y, 0.06, 1.15, C.steel)
    add_text_box(
        slide, 0.65, n_y + 0.12, 6, 0.25,
        [Run(text=f"KEY FOCUS — WEEK {state.next_week_no}",
             size=10, bold=True, color=C.steel, char_spacing=3)],
        valign="middle", margin=0,
    )
    if state.lookahead_focus_bullets:
        add_bulleted_text(
            slide, 0.75, n_y + 0.40, SLIDE_W - 1.40, 0.75,
            state.lookahead_focus_bullets,
            bullet_char="■", color=C.graphite, size=9.5,
        )
    else:
        add_text_box(
            slide, 0.75, n_y + 0.40, SLIDE_W - 1.40, 0.75,
            [Run(text="(no key focus items recorded.)", color=C.slate, italic=True, size=9.5)],
            valign="top", margin=0,
        )

    return slide
