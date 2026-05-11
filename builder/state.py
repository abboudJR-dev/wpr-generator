"""State container for the WPR build.

Aggregates extracted DCR + logs data plus user-edited metadata into one object
that's passed to every slide builder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from extractors.dcr import DCRData, DCRPhoto
from extractors.logs import CategoryStats, LogsData


# ----- Static project facts (rarely change between weeks) -----------------------

@dataclass
class ProjectInfo:
    name: str = "Proposed B+G+4 Typical Floor + Roof Residential Building"
    short_name: str = "B+G+4 Typical Floor + Roof  •  Residential Building"
    short_name_plain: str = "B+G+4 Typical Floor + Roof Residential Building"
    location: str = "Ras Al Khor Industrial Area\nFirst, Dubai — UAE"
    location_inline: str = "Ras Al Khor Industrial Area — First, Dubai, UAE"
    location_cover: str = "Ras Al Khor Industrial Area, Dubai — UAE"
    plot: str = "612-9825"
    employer: str = "M/S East & West International Group\nSole Proprietorship LLC"
    employer_overview: str = "M/S East & West International\nGroup Sole Proprietorship LLC"
    employer_short: str = "M/S East & West International Group"
    consultant: str = "Al Hadara Consulting & Engineering"
    contractor: str = "Emirates Pearl Construction CCS Company"
    contractor_short: str = "Emirates Pearl Construction CCS Company"
    contract_value_orig: str = "AED 78,800,000"
    contract_value_revised: str = "AED 78,800,000"
    contract_value_short: str = "AED 78.8M"
    duration: str = "24 Months"
    duration_full: str = "24 Months  •  20 Dec 2025 → 19 Dec 2027"
    commencement: str = "20 Dec 25"
    planned_completion: str = "19 Dec 27"
    commencement_full: str = "20 Dec 2025"
    planned_completion_full: str = "19 Dec 2027"
    phase: str = "Substructure Works"
    baseline_ref: str = "DB36-EPCC-AHC-DOC-0012 Rev. 03"
    baseline_approval: str = "12 April 2026"


# ----- Sub-contractors table -----

@dataclass
class SubContractor:
    trade: str
    name: str
    status: str = "Active"


DEFAULT_SUBS = [
    SubContractor("MEP Works", "Current Engineering Services (CES)"),
    SubContractor("Shoring Works", "Power Axes International Foundation"),
    SubContractor("Dewatering Works", "Dwex Technical Services"),
    SubContractor("Substructure Waterproofing", "Advanced Insight Insulation"),
    SubContractor("Fire-Fighting & Fire Alarm", "NAFFCO"),
    SubContractor("Rebar / Steel Supply", "CICON"),
    SubContractor("Elevator Installation", "Emirates International Facility Mgmt (EIFM)"),
    SubContractor("Joinery Works", "Calibers Industry LLC"),
]


# ----- Activity rows (zones A / B) -----

@dataclass
class ActivityRow:
    activity: str
    start_date: str
    status_kind: str  # 'completed' / 'progress' / 'pending' / 'risk'
    status_label: str
    progress: str
    remarks: str


# ----- Lookahead rows (next week) -----

@dataclass
class LookaheadRow:
    activity: str
    current_status: str
    target: str
    note: str = "—"


# ----- NCR register entry -----

@dataclass
class NCREntry:
    ref: str
    subject: str
    issued: str
    closed: str
    status: str = "● CLOSED"


# ----- Concrete-quality summary row -----

@dataclass
class ConcreteRow:
    element: str
    grade: str
    day3: str
    day7: str
    day28: str
    day28_kind: str = "completed"  # 'completed' or 'pending'


# ----- Programme phase row -----

@dataclass
class ProgrammeRow:
    work_package: str
    planned_start: str
    planned_finish: str
    progress_this_week: str
    pct_complete: str
    status: str  # 'complete' / 'progress'


# ----- Areas of Concern -----

@dataclass
class AOCEntry:
    ref: str
    title: str
    responsible: str
    target: str
    impact: str
    impact_kind: str = "success"  # 'success' / 'amber' / 'risk'


# ----- HSE -----

@dataclass
class HSESummary:
    lti: int = 0
    open_ncrs: int = 0
    closed_ncrs: int = 6
    safety_officer_status: str = "APPROVED"
    safety_officer_doc: str = "Doc-0027"


# ----- Photo selection per day -----

@dataclass
class DayPhotos:
    """Two photos for a single day's photo slide."""

    photo_a_bytes: Optional[bytes] = None
    photo_a_ext: str = "png"
    photo_b_bytes: Optional[bytes] = None
    photo_b_ext: str = "png"
    caption_a: str = ""
    caption_b: str = ""


# ----- Manpower per day (planned + actual) -----

@dataclass
class ManpowerDay:
    label: str  # e.g. "Mon 27-Apr"
    planned: int
    actual: int

    @property
    def variance(self) -> int:
        return self.actual - self.planned


# ----- Top-level WPR state ----------------------------------------------------

@dataclass
class WPRState:
    project: ProjectInfo = field(default_factory=ProjectInfo)
    week_no: int = 20
    week_no_str: str = "20"
    period: str = "27 April – 03 May 2026"
    period_short: str = "27 Apr – 03 May 2026"
    issue_date: str = "06 May 2026"
    report_ref: str = "DB36-EPCC-WR-020"
    weeks_elapsed: int = 21
    weeks_total: int = 104
    time_elapsed_pct: str = "20.2%"
    next_week_no: int = 21
    next_week_period: str = "04 – 10 May 2026"

    subs: list[SubContractor] = field(default_factory=lambda: list(DEFAULT_SUBS))

    manpower_days: list[ManpowerDay] = field(default_factory=list)
    manpower_observations: list[tuple[str, str, str]] = field(default_factory=list)
    # Each tuple: (header label, header color kind, body text)
    # color kind: 'success' / 'amber' / 'steel' / 'risk'

    zone_a_label: str = "ZONE A — LOWER RAFT LEVEL  ( EL = −4.50 M  |  +0.77 DMD )"
    zone_b_label: str = "ZONE B — HIGHER RAFT LEVEL  ( EL = −3.07 M  |  +2.40 DMD )"
    zone_a_activities: list[ActivityRow] = field(default_factory=list)
    zone_b_activities: list[ActivityRow] = field(default_factory=list)
    week_summary_text: str = ""

    zone_a_lookahead: list[LookaheadRow] = field(default_factory=list)
    zone_b_lookahead: list[LookaheadRow] = field(default_factory=list)
    lookahead_focus_bullets: list[str] = field(default_factory=list)

    ncrs: list[NCREntry] = field(default_factory=list)
    ncr_note: str = ""
    concrete_rows: list[ConcreteRow] = field(default_factory=list)

    submittal_categories: list[CategoryStats] = field(default_factory=list)
    rfi_footnote: str = ""

    hse: HSESummary = field(default_factory=HSESummary)

    aocs: list[AOCEntry] = field(default_factory=list)
    aoc_assessment: str = ""

    programme_rows: list[ProgrammeRow] = field(default_factory=list)
    programme_statement: str = ""

    photo_days: list[DayPhotos] = field(default_factory=list)
    # 6 entries — one per photo slide (10-15) covering days 1-6 of the week.
    # Last day (day 7 / Sun) is excluded by the reference deck.
    photo_dates: list[date] = field(default_factory=list)
    photo_day_labels: list[str] = field(default_factory=list)

    output_path: Optional[Path] = None
