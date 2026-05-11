"""Slide 9: Programme Status Overview."""
from __future__ import annotations

from pptx.util import Inches

from builder.design import (
    C, Run, SLIDE_W,
    add_blank_slide, add_footer, add_header, add_rect, add_text_box,
    fill_cell, section_label, set_cell_border, set_slide_background,
    style_cell_text,
)
from builder.state import ProgrammeRow, WPRState


def _add_programme_table(slide, x, y, w, rows: list[ProgrammeRow]):
    n_rows = len(rows) + 1
    n_cols = 6
    col_widths = [3.40, 1.35, 1.35, 4.10, 1.10, 1.15]
    row_h = 0.30

    table_shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
                                         Inches(w), Inches(row_h * n_rows))
    table = table_shape.table
    for ci, cw in enumerate(col_widths):
        table.columns[ci].width = Inches(cw)
    for ri in range(n_rows):
        table.rows[ri].height = Inches(row_h)

    headers = ["WORK PACKAGE", "PLANNED START", "PLANNED FINISH",
               "PROGRESS THIS WEEK", "% COMPLETE", "STATUS"]
    aligns = ["left", "center", "center", "left", "center", "center"]
    for ci, (h, a) in enumerate(zip(headers, aligns)):
        cell = table.cell(0, ci)
        fill_cell(cell, C.navy)
        style_cell_text(cell, h, color=C.white, bold=True, size=9,
                        align=a, valign="middle", char_spacing=1.5)
        set_cell_border(cell, C.line, 0.5)

    for ri, row in enumerate(rows, start=1):
        stripe = C.white if ri % 2 == 1 else C.panel
        is_complete = row.status == "complete"
        stat_color = C.success if is_complete else C.teal_dark
        stat_label = "● COMPLETE" if is_complete else "● IN PROGRESS"
        cells_def = [
            (row.work_package,        C.ink,       True,  "left"),
            (row.planned_start,       C.graphite,  False, "center"),
            (row.planned_finish,      C.graphite,  False, "center"),
            (row.progress_this_week,  C.graphite,  False, "left"),
            (row.pct_complete,        stat_color,  True,  "center"),
            (stat_label,              stat_color,  True,  "center"),
        ]
        for ci, (text, color, bold, align) in enumerate(cells_def):
            cell = table.cell(ri, ci)
            fill_cell(cell, stripe)
            style_cell_text(cell, text, color=color, bold=bold, size=9,
                            align=align, valign="middle")
            set_cell_border(cell, C.line, 0.5)


def build_slide_programme(prs, state: WPRState):
    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    add_header(
        slide,
        title="PROGRAMME STATUS OVERVIEW",
        subtitle=f"Baseline: {state.project.baseline_ref}  |  Approved {state.project.baseline_approval}",
    )
    add_footer(slide, 8, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # Top KPIs
    k_y = 1.05
    kpis = [
        (f"{state.weeks_elapsed} / {state.weeks_total}", "Weeks Elapsed / Total", C.steel),
        (state.time_elapsed_pct,                          "Time Elapsed",          C.teal),
        (state.project.commencement,                      "Commencement",          C.steel),
        (state.project.planned_completion,                "Planned Completion",    C.teal),
    ]
    kw = (SLIDE_W - 0.90 - 0.30) / 4
    for i, (v, l, fill) in enumerate(kpis):
        cx = 0.45 + i * (kw + 0.10)
        add_rect(slide, cx, k_y, kw, 0.95, fill)
        add_text_box(
            slide, cx, k_y + 0.10, kw, 0.55,
            [Run(text=v, size=22, bold=True, color=C.white)],
            align="center", valign="middle", margin=0,
        )
        add_text_box(
            slide, cx, k_y + 0.65, kw, 0.25,
            [Run(text=l.upper(), size=8.5, color=C.white, char_spacing=2.5)],
            align="center", valign="middle", margin=0,
        )

    # Substructure works table
    section_label(slide, 0.45, 2.20, 12.5,
                  f"CURRENT CONSTRUCTION PHASE — {state.project.phase.upper()}")
    _add_programme_table(slide, 0.45, 2.55, SLIDE_W - 0.90, state.programme_rows)

    # Bottom callout
    n_y = 6.30
    add_rect(slide, 0.45, n_y, SLIDE_W - 0.90, 0.75, C.teal_soft)
    add_rect(slide, 0.45, n_y, 0.06, 0.75, C.teal)
    add_text_box(
        slide, 0.65, n_y, SLIDE_W - 1.30, 0.75,
        [
            Run(text="PROGRAMME STATEMENT  ", bold=True, color=C.teal,
                char_spacing=3, size=9.5),
            Run(text="—  ", color=C.teal_dark, size=9.5),
            Run(text=state.programme_statement, color=C.graphite, size=9.5),
        ],
        valign="middle", margin=0,
    )

    return slide
