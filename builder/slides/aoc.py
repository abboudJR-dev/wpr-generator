"""Slide 8: Areas of Concern & Outstanding Items."""
from __future__ import annotations

from builder.design import (
    C, Run, SLIDE_W,
    add_blank_slide, add_footer, add_header, add_rect, add_text_box,
    kpi_card_inline, section_label, set_slide_background,
)
from builder.state import AOCEntry, WPRState


def _impact_accent(kind: str) -> str:
    return {"amber": C.amber, "risk": C.risk, "success": C.success}.get(kind, C.success)


def _impact_soft(kind: str) -> str:
    return {"amber": C.amber_soft, "risk": C.risk_soft, "success": C.success_soft}.get(kind, C.success_soft)


def _draw_aoc_card(slide, x, y, w, h, aoc: AOCEntry):
    accent = _impact_accent(aoc.impact_kind)
    soft = _impact_soft(aoc.impact_kind)

    # Card body + top accent bar
    add_rect(slide, x, y, w, h, C.page, line_hex=C.line, line_width=0.75)
    add_rect(slide, x, y, w, 0.10, accent)

    # Reference badge (top-left)
    add_rect(slide, x + 0.20, y + 0.22, 0.85, 0.30, C.navy)
    add_text_box(
        slide, x + 0.20, y + 0.22, 0.85, 0.30,
        [Run(text=aoc.ref, size=9, bold=True, color=C.white, char_spacing=1.5)],
        align="center", valign="middle", margin=0,
    )

    # Impact pill (top-right)
    pill_w = 1.55
    add_rect(slide, x + w - pill_w - 0.20, y + 0.22, pill_w, 0.30, soft)
    add_text_box(
        slide, x + w - pill_w - 0.20, y + 0.22, pill_w, 0.30,
        [Run(text=aoc.impact.upper(), size=7.5, bold=True, color=accent, char_spacing=1.2)],
        align="center", valign="middle", margin=0,
    )

    # Title
    add_text_box(
        slide, x + 0.20, y + 0.62, w - 0.40, 0.78,
        [Run(text=aoc.title, size=11, bold=True, color=C.ink)],
        valign="top", margin=0,
    )

    # Responsible
    meta_y = y + 1.42
    add_text_box(
        slide, x + 0.20, meta_y, w - 0.40, 0.16,
        [Run(text="RESPONSIBLE", size=7, bold=True, color=C.teal, char_spacing=2)],
        valign="middle", margin=0,
    )
    add_text_box(
        slide, x + 0.20, meta_y + 0.16, w - 0.40, 0.20,
        [Run(text=aoc.responsible, size=9, color=C.graphite)],
        valign="top", margin=0,
    )

    # Target
    add_text_box(
        slide, x + 0.20, meta_y + 0.40, w - 0.40, 0.14,
        [Run(text="TARGET", size=7, bold=True, color=C.teal, char_spacing=2)],
        valign="middle", margin=0,
    )
    target_color = C.amber if aoc.target.lower() == "pending" else C.graphite
    add_text_box(
        slide, x + 0.20, meta_y + 0.52, w - 0.40, 0.18,
        [Run(text=aoc.target, size=9, bold=True, color=target_color)],
        valign="top", margin=0,
    )


def build_slide_aoc(prs, state: WPRState):
    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    add_header(
        slide,
        title="AREAS OF CONCERN & OUTSTANDING ITEMS",
        subtitle=f"Week {state.week_no_str}  |  As at {state.period_as_at()}",
    )
    add_footer(slide, 7, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # Top KPI cards (4)
    open_count = len(state.aocs)
    medium = sum(1 for a in state.aocs if a.impact_kind == "amber")
    low = sum(1 for a in state.aocs if a.impact_kind == "success")
    high = sum(1 for a in state.aocs if a.impact_kind == "risk")

    sums = [
        (str(open_count), "Open Items",          C.steel),
        (str(medium),     "Medium Impact",       C.amber),
        (str(low),        "Low / Administrative", C.success),
        (str(high),       "High Impact",         C.teal),
    ]
    sum_y = 1.05
    sw = (SLIDE_W - 0.90 - 0.30) / 4
    for i, (v, l, fill) in enumerate(sums):
        cx = 0.45 + i * (sw + 0.10)
        add_rect(slide, cx, sum_y, sw, 0.75, fill)
        add_text_box(
            slide, cx + 0.20, sum_y + 0.05, 0.80, 0.65,
            [Run(text=v, size=28, bold=True, color=C.white)],
            align="left", valign="middle", margin=0,
        )
        add_text_box(
            slide, cx + 1.05, sum_y + 0.18, sw - 1.20, 0.40,
            [Run(text=l.upper(), size=9, bold=True, color=C.white, char_spacing=2)],
            valign="middle", margin=0,
        )

    # AOC cards (3+2 grid, all same size)
    section_label(slide, 0.45, 2.05, 12.5, "OPEN AREAS OF CONCERN")
    card_w = (SLIDE_W - 0.90 - 0.40) / 3
    card_h = 1.95
    for i, aoc in enumerate(state.aocs[:6]):
        col = i % 3
        row = i // 3
        cx = 0.45 + col * (card_w + 0.20)
        cy = 2.40 + row * (card_h + 0.20)
        _draw_aoc_card(slide, cx, cy, card_w, card_h, aoc)

    # Bottom callout: overall assessment
    c_y = 6.65
    add_rect(slide, 0.45, c_y, SLIDE_W - 0.90, 0.40, C.teal_soft)
    add_rect(slide, 0.45, c_y, 0.06, 0.40, C.teal)
    add_text_box(
        slide, 0.65, c_y, SLIDE_W - 1.30, 0.40,
        [
            Run(text="OVERALL ASSESSMENT  ", bold=True, color=C.teal,
                char_spacing=3, size=10),
            Run(text="—  ", color=C.teal_dark, size=10),
            Run(text=state.aoc_assessment, color=C.graphite, size=10),
        ],
        valign="middle", margin=0,
    )

    return slide
