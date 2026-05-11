"""Slides 10-15: Site progress photos (one slide per day)."""
from __future__ import annotations

import io
from datetime import date as Date
from pathlib import Path

from pptx.util import Inches

from builder.design import (
    C, Run, SLIDE_W,
    add_blank_slide, add_footer, add_header, add_image, add_rect, add_text_box,
    set_slide_background,
)
from builder.state import DayPhotos, WPRState


def _save_temp_photo(photo_bytes: bytes, ext: str, idx: int) -> Path:
    """python-pptx needs a filesystem path or BytesIO — return BytesIO-ready buffer."""
    return io.BytesIO(photo_bytes)  # type: ignore[return-value]


def _add_photo_with_caption(slide, x, y, w, h, photo_bytes, ext, caption: str):
    # Subtle frame
    add_rect(slide, x, y, w, h, C.panel_alt, line_hex=C.line, line_width=0.75)

    # Image area (leave 0.55" at bottom for caption)
    img_x = x + 0.05
    img_y = y + 0.05
    img_w = w - 0.10
    img_h = h - 0.55
    if photo_bytes:
        buf = io.BytesIO(photo_bytes)
        slide.shapes.add_picture(buf, Inches(img_x), Inches(img_y), Inches(img_w), Inches(img_h))
    else:
        # Placeholder fill
        add_rect(slide, img_x, img_y, img_w, img_h, C.hairline)
        add_text_box(
            slide, img_x, img_y, img_w, img_h,
            [Run(text="(no photo selected)", size=11, italic=True, color=C.mute)],
            align="center", valign="middle", margin=0,
        )

    # Caption strip
    add_text_box(
        slide, img_x, y + h - 0.45, img_w, 0.40,
        [Run(text=caption or "Photograph", size=9.5, color=C.graphite)],
        align="center", valign="middle", margin=0,
    )


def build_slide_photos_for_day(prs, state: WPRState, day_index: int, page_num: int):
    """Build one photo slide for state.photo_days[day_index]."""
    if day_index >= len(state.photo_days):
        return None
    day_photos = state.photo_days[day_index]
    photo_date: Date | None = state.photo_dates[day_index] if day_index < len(state.photo_dates) else None
    day_label = state.photo_day_labels[day_index] if day_index < len(state.photo_day_labels) else ""

    date_str = photo_date.strftime("%d %B %Y") if photo_date else ""

    slide = add_blank_slide(prs)
    set_slide_background(slide, C.page)
    add_header(
        slide,
        title="SITE PROGRESS PHOTOS",
        subtitle=f"Week {state.week_no_str}  |  {day_label}, {date_str}",
    )
    add_footer(slide, page_num, period=state.period_short,
               company=state.project.contractor_short,
               report_no=f"Weekly Report No. {state.week_no_str.zfill(3)}")

    # Date block (left)
    db_x, db_y = 0.45, 1.05
    add_rect(slide, db_x, db_y, 1.85, 0.95, C.navy)
    add_rect(slide, db_x, db_y, 0.06, 0.95, C.teal)
    add_text_box(
        slide, db_x + 0.18, db_y + 0.10, 1.65, 0.25,
        [Run(text=day_label.upper(), size=9, bold=True, color=C.teal, char_spacing=3)],
        valign="middle", margin=0,
    )
    add_text_box(
        slide, db_x + 0.18, db_y + 0.32, 1.65, 0.55,
        [Run(text=date_str, size=18, bold=True, color=C.white)],
        valign="middle", margin=0,
    )

    # Site label panel (right of date block)
    add_rect(slide, 2.40, db_y, SLIDE_W - 2.85, 0.95, C.panel,
             line_hex=C.line, line_width=0.5)
    add_text_box(
        slide, 2.55, db_y + 0.10, 1.5, 0.20,
        [Run(text="SITE", size=8, bold=True, color=C.teal, char_spacing=2)],
        valign="middle", margin=0,
    )
    add_text_box(
        slide, 2.55, db_y + 0.30, SLIDE_W - 3.10, 0.30,
        [Run(text=f"Plot No. {state.project.plot}   |   {state.project.location_inline}",
             size=11, bold=True, color=C.ink)],
        valign="middle", margin=0,
    )
    add_text_box(
        slide, 2.55, db_y + 0.58, SLIDE_W - 3.10, 0.30,
        [Run(text=f"Project: {state.project.short_name_plain}   |   Phase: {state.project.phase}",
             size=9.5, color=C.slate)],
        valign="middle", margin=0,
    )

    # Photos (2 side-by-side)
    ph_y, ph_h = 2.20, 4.65
    ph_w = (SLIDE_W - 0.90 - 0.20) / 2

    _add_photo_with_caption(
        slide, 0.45, ph_y, ph_w, ph_h,
        day_photos.photo_a_bytes, day_photos.photo_a_ext, day_photos.caption_a,
    )
    _add_photo_with_caption(
        slide, 0.45 + ph_w + 0.20, ph_y, ph_w, ph_h,
        day_photos.photo_b_bytes, day_photos.photo_b_ext, day_photos.caption_b,
    )

    return slide


def build_all_photo_slides(prs, state: WPRState, start_page: int = 9):
    """Build slides 10-15 (6 photo slides covering days 1-6)."""
    for i in range(6):
        build_slide_photos_for_day(prs, state, i, start_page + i)
