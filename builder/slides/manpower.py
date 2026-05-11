"""Slide 4: Weekly Manpower Tracker with bar chart."""
from __future__ import annotations

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from builder.design import (
    C, Run, SLIDE_W,
    add_blank_slide, add_footer, add_header, add_rect, add_text_box,
    fill_cell, hex_to_rgb, kpi_card_inline, set_cell_border, set_slide_background,
    style_cell_text,
)
from builder.state import WPRState


def build_slide_manpower(prs, state: WPRState):
    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    add_header(
        slide,
        title=f"WEEKLY MANPOWER TRACKER — WEEK {state.week_no_str}",
        subtitle=f"Daily planned vs. actual headcount  |  {state.period_short}",
    )
    add_footer(slide, 3, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # ---- Top stat row (4 cards) ----
    import math
    days = state.manpower_days
    total_planned = sum(d.planned for d in days)
    total_actual = sum(d.actual for d in days)
    # Reference deck divides by working days (those with planned > 0). Sunday is
    # planned 0, so for a typical week the divisor is 6. Truncated to 1 decimal,
    # matching the reference (e.g. 481/6 = 80.166… → "80.1").
    work_days = sum(1 for d in days if d.planned > 0) or len(days) or 1
    raw_avg = (total_actual / work_days) if days else 0.0
    daily_avg = math.floor(raw_avg * 10) / 10
    variance = total_actual - total_planned
    variance_str = f"+{variance}" if variance > 0 else (str(variance) if variance != 0 else "0")
    variance_fill = C.success if variance >= 0 else C.risk

    stats = [
        (str(total_planned), "Total Planned (Week)", C.steel),
        (str(total_actual),  "Total Actual (Week)",  C.teal),
        (f"{daily_avg:.1f}", "Daily Average (Actual)", C.steel),
        (variance_str,       "Weekly Variance",       variance_fill),
    ]
    s_y = 1.10
    cw, cgap, base_x = 3.07, 0.10, 0.45
    for i, (v, l, fill) in enumerate(stats):
        cx = base_x + i * (cw + cgap)
        kpi_card_inline(slide, cx, s_y, cw, 0.95, value=v, label=l, fill=fill,
                        value_size=32 if len(v) <= 4 else 26, label_size=9)

    # ---- Daily breakdown table ----
    t_y = 2.30
    label_w = 2.10
    data_w = (SLIDE_W - 0.90 - label_w) / 8
    inner_w = SLIDE_W - 0.90  # 12.433"

    # Day headers row (single text row over a navy bg)
    day_labels = [d.label for d in days[:7]] + ["WEEKLY TOTAL"]
    add_rect(slide, 0.45, t_y, inner_w, 0.40, C.navy)
    for i, label in enumerate(day_labels):
        is_total = i == 7
        color = C.teal if is_total else C.white
        add_text_box(
            slide, 0.45 + label_w + i * data_w, t_y, data_w, 0.40,
            [Run(text=label, size=9, bold=True, color=color, char_spacing=1)],
            align="center", valign="middle", margin=0,
        )

    def _add_data_row(row_y, label, values, color_fn=None):
        add_rect(slide, 0.45, row_y, label_w, 0.40, C.panel, line_hex=C.line, line_width=0.5)
        add_text_box(
            slide, 0.55, row_y, label_w - 0.20, 0.40,
            [Run(text=label, size=9.5, bold=True, color=C.ink)],
            valign="middle", margin=0,
        )
        for i, v in enumerate(values):
            is_total = i == 7
            cell_fill = C.teal_soft if is_total else (C.white if i % 2 == 0 else C.hairline)
            cell_x = 0.45 + label_w + i * data_w
            add_rect(slide, cell_x, row_y, data_w, 0.40, cell_fill,
                     line_hex=C.line, line_width=0.5)
            txt_color = color_fn(v) if color_fn else C.ink
            add_text_box(
                slide, cell_x, row_y, data_w, 0.40,
                [Run(text=str(v), size=10, bold=is_total, color=txt_color)],
                align="center", valign="middle", margin=0,
            )

    planned = [d.planned for d in days[:7]] + [total_planned]
    actual_vals = [d.actual for d in days[:7]] + [total_actual]
    variances = [d.variance for d in days[:7]] + [variance]
    variance_strs = [(f"+{v}" if v > 0 else str(v)) for v in variances]

    _add_data_row(t_y + 0.40, "Planned Manpower", planned)
    _add_data_row(t_y + 0.80, "Actual Manpower",  actual_vals)
    _add_data_row(
        t_y + 1.20, "Daily Variance", variance_strs,
        color_fn=lambda v: C.risk if str(v).startswith("-") else (C.success if str(v).startswith("+") else C.ink),
    )

    # ---- Bar chart (planned vs. actual) ----
    chart_y = 4.10
    add_text_box(
        slide, 0.45, chart_y, 7.5, 0.28,
        [Run(text="DAILY HEADCOUNT — PLANNED VS ACTUAL",
             size=10, bold=True, color=C.steel, char_spacing=2)],
        valign="middle", margin=0,
    )

    chart_data = CategoryChartData()
    chart_data.categories = [d.label for d in days[:7]]
    chart_data.add_series("Planned", [d.planned for d in days[:7]])
    chart_data.add_series("Actual",  [d.actual for d in days[:7]])

    chart_shape = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.30), Inches(chart_y + 0.30),
        Inches(8.4), Inches(2.65),
        chart_data,
    )
    chart = chart_shape.chart
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.name = "Calibri"
    chart.legend.font.size = Pt(9)
    chart.legend.font.color.rgb = hex_to_rgb(C.graphite)

    # Series colors
    series_colors = [C.steel, C.teal]
    for series, color_hex in zip(chart.plots[0].series, series_colors):
        fill = series.format.fill
        fill.solid()
        fill.fore_color.rgb = hex_to_rgb(color_hex)
        line = series.format.line
        line.color.rgb = hex_to_rgb(color_hex)

    # Data labels
    for series in chart.plots[0].series:
        series.data_labels.show_value = True
        series.data_labels.font.size = Pt(8)
        series.data_labels.font.name = "Calibri"
        series.data_labels.font.color.rgb = hex_to_rgb(C.graphite)
        series.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END

    # Axis style
    cat_axis = chart.category_axis
    cat_axis.tick_labels.font.size = Pt(9)
    cat_axis.tick_labels.font.name = "Calibri"
    cat_axis.tick_labels.font.color.rgb = hex_to_rgb(C.slate)
    val_axis = chart.value_axis
    val_axis.tick_labels.font.size = Pt(9)
    val_axis.tick_labels.font.name = "Calibri"
    val_axis.tick_labels.font.color.rgb = hex_to_rgb(C.slate)

    # Gap width (smaller bars)
    chart.plots[0].gap_width = 60

    # ---- Right-side commentary box ----
    cb_x, cb_y, cb_w, cb_h = 9.10, chart_y + 0.30, 3.85, 2.65
    add_rect(slide, cb_x, cb_y, cb_w, cb_h, C.panel, line_hex=C.line, line_width=0.5)
    add_rect(slide, cb_x, cb_y, 0.06, cb_h, C.teal)
    add_text_box(
        slide, cb_x + 0.20, cb_y + 0.12, cb_w - 0.30, 0.25,
        [Run(text=f"WEEK {state.week_no_str} OBSERVATIONS",
             size=9.5, bold=True, color=C.teal, char_spacing=2.5)],
        valign="middle", margin=0,
    )
    runs = []
    color_map = {"success": C.success, "amber": C.amber, "steel": C.steel, "risk": C.risk}
    for i, (header, kind, body) in enumerate(state.manpower_observations):
        runs.append(Run(text=header, bold=True, color=color_map.get(kind, C.steel),
                        size=9, new_paragraph=(i > 0)))
        runs.append(Run(text=body, color=C.graphite, size=9, new_paragraph=True))

    if not runs:
        runs = [Run(text="(No observations recorded.)", color=C.slate, italic=True, size=9)]

    add_text_box(
        slide, cb_x + 0.20, cb_y + 0.42, cb_w - 0.40, cb_h - 0.50,
        runs, valign="top", margin=0,
    )

    return slide


def default_observations(state: WPRState) -> list[tuple[str, str, str]]:
    """Generate observations from manpower data."""
    days = state.manpower_days
    if not days:
        return []
    total_actual = sum(d.actual for d in days)
    total_planned = sum(d.planned for d in days)
    variance = total_actual - total_planned

    obs: list[tuple[str, str, str]] = []
    if variance >= 0:
        obs.append((
            "Weekly target met:",
            "success",
            f"Actual headcount of {total_actual} closed at "
            f"{'+' if variance > 0 else ''}{variance} over the planned {total_planned}.",
        ))
    else:
        obs.append((
            "Weekly shortfall:",
            "risk",
            f"Actual headcount of {total_actual} closed at {variance} below planned {total_planned}.",
        ))

    # Find the worst variance day
    worst_day = min(days[:7], key=lambda d: d.variance)
    if worst_day.variance < -10:
        # Find a recovery day with strong positive variance (use weekday only — "Sat" not "Sat 02-May")
        recovery = max(days[:7], key=lambda d: d.variance)
        recovery_short = recovery.label.split(" ")[0] if recovery.label else "later"
        obs.append((
            "Mid-week dip:",
            "amber",
            f"{worst_day.label} saw a {worst_day.variance} variance "
            f"({worst_day.actual} vs. {worst_day.planned})"
            + (f" — recovered {recovery_short} with +{recovery.variance} ({recovery.actual})."
               if recovery.variance > 5 else "."),
        ))

    # Sunday allocation
    sunday = days[6] if len(days) >= 7 else None
    if sunday and sunday.actual > 0 and sunday.planned == 0:
        obs.append((
            "Sunday allocation:",
            "steel",
            f"{sunday.actual} personnel deployed against zero plan to advance critical formwork.",
        ))

    return obs
