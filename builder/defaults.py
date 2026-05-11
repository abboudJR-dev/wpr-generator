"""Default Week-20 content used to seed the editable WPR state.

Loaded from `reference/scaffolding/build*.js` content — the verified Week-20 deck
data. The user can edit any of these in the Streamlit review screen before
generation. Numeric figures (manpower, submittals) get overwritten by extracted
values; narrative text is what defaults are most useful for.
"""
from __future__ import annotations

from .state import (
    AOCEntry, ActivityRow, ConcreteRow, LookaheadRow,
    ManpowerDay, NCREntry, ProgrammeRow,
)


DEFAULT_MANPOWER_PLANNED = [80, 80, 80, 80, 80, 80, 0]


def default_manpower_days(date_labels: list[str], actuals: list[int]) -> list[ManpowerDay]:
    """Combine extracted actuals with the static planned series to make 7 days."""
    out: list[ManpowerDay] = []
    for i, label in enumerate(date_labels[:7]):
        planned = DEFAULT_MANPOWER_PLANNED[i] if i < len(DEFAULT_MANPOWER_PLANNED) else 80
        actual = actuals[i] if i < len(actuals) else 0
        out.append(ManpowerDay(label=label, planned=planned, actual=actual))
    return out


DEFAULT_ZONE_A_ACTIVITIES = [
    ActivityRow(
        activity="Steel reinforcement — columns, retaining walls, lift & staircase walls",
        start_date="12-Apr-26", status_kind="completed", status_label="COMPLETED",
        progress="100%",
        remarks="All columns, retaining, staircase & lift walls reinforcement complete on 30-Apr-26",
    ),
    ActivityRow(
        activity="Carpentry / formwork — retaining walls and columns",
        start_date="20-Apr-26", status_kind="completed", status_label="COMPLETED",
        progress="100%", remarks="All retaining wall and column formwork completed",
    ),
    ActivityRow(
        activity="Concrete casting — staircase & lift walls",
        start_date="28-Apr-26", status_kind="completed", status_label="COMPLETED",
        progress="100%", remarks="Staircase walls cast 28-Apr; lift walls cast 30-Apr",
    ),
    ActivityRow(
        activity="Formwork — basement slab and beams",
        start_date="24-Apr-26", status_kind="progress", status_label="IN PROGRESS",
        progress="80%", remarks="Targeting completion by 15-May-26",
    ),
    ActivityRow(
        activity="Concrete casting — basement floor columns (75 No.)",
        start_date="20-Apr-26", status_kind="progress", status_label="IN PROGRESS",
        progress="96%", remarks="72 of 75 columns cast",
    ),
    ActivityRow(
        activity="Concrete casting — retaining walls (180 LM)",
        start_date="20-Apr-26", status_kind="progress", status_label="IN PROGRESS",
        progress="85%", remarks="150 LM of 180 LM cast",
    ),
    ActivityRow(
        activity="MEP first fix — retaining walls, columns, lift & staircase walls (CES)",
        start_date="12-Apr-26", status_kind="progress", status_label="IN PROGRESS",
        progress="85%", remarks="Trades coordinated; remaining tie-ins this week",
    ),
    ActivityRow(
        activity="Removal of shoring H-Beams",
        start_date="02-May-26", status_kind="progress", status_label="IN PROGRESS",
        progress="30%", remarks="30 of 100 beams removed",
    ),
]

DEFAULT_ZONE_B_ACTIVITIES = [
    ActivityRow(
        activity="Casting of Higher Raft",
        start_date="29-Apr-26", status_kind="completed", status_label="COMPLETED",
        progress="100%", remarks="Higher raft cast 29–30 Apr; concrete curing in progress",
    ),
    ActivityRow(
        activity="Surface finishing — Higher Raft (power float)",
        start_date="30-Apr-26", status_kind="completed", status_label="COMPLETED",
        progress="100%", remarks="7× power-float machines deployed for level/finish on 30-Apr",
    ),
    ActivityRow(
        activity="Steel reinforcement — columns",
        start_date="01-May-26", status_kind="progress", status_label="IN PROGRESS",
        progress="20%", remarks="Reinforcement work commenced for column starts",
    ),
]

DEFAULT_WEEK_SUMMARY = (
    "Lower raft column casting reached 96% (72/75); retaining walls 85% (150/180 LM). "
    "Higher raft cast 29–30 Apr; column rebar lifted on 01-May. Shoring removal initiated "
    "02-May at 30%."
)


DEFAULT_ZONE_A_LOOKAHEAD = [
    LookaheadRow("Formwork — basement slab and beams", "85% complete", "Complete by 15-May-26"),
    LookaheadRow("Steel reinforcement — basement slab (beams and mesh)", "Not started yet", "Commence"),
    LookaheadRow("MEP first fix — basement slab (beams and mesh)", "Not started yet", "Commence"),
    LookaheadRow("Concrete casting — basement floor columns (75 No.)", "72 of 75 columns cast", "No further casting required"),
    LookaheadRow("Concrete casting — retaining walls (180 LM)", "150 LM of 180 LM cast", "No further casting required"),
    LookaheadRow("Concrete casting — water tank walls", "Shuttering / MEP provision in progress", "To be cast"),
    LookaheadRow("Shuttering works for ramp", "Not started yet", "Commence"),
]

DEFAULT_ZONE_B_LOOKAHEAD = [
    LookaheadRow("Steel reinforcement — columns at higher raft level", "To be started", "Advance to 40%"),
    LookaheadRow("MEP first fix — columns at wall between two rafts", "To be started", "Advance to 80%"),
]

DEFAULT_LOOKAHEAD_BULLETS = [
    "Close out basement slab formwork to allow rebar / MEP first fix to begin.",
    "Commence water tank wall casting and ramp shuttering to free up the critical path.",
    "Mobilise steel and MEP crews on Higher Raft to lift column starts towards 40 / 80%.",
]


DEFAULT_NCRS = [
    NCREntry("NCR-001", "Safety Violation — Waterproofing Works", "14-Mar-26", "08-Apr-26"),
    NCREntry("NCR-002", "Safety Violation — Vehicle Access", "14-Mar-26", "08-Apr-26"),
    NCREntry("NCR-003", "Unauthorised Covering of Excavation Works", "25-Mar-26", "12-Apr-26"),
    NCREntry("NCR-004", "Unauthorised Covering of Waterproofing Works", "26-Mar-26", "03-Apr-26"),
    NCREntry("NCR-005", "Unauthorised Covering of Waterproofing Works", "26-Mar-26", "03-Apr-26"),
    NCREntry("NCR-006", "Unauthorised Covering of Excavation Works", "26-Mar-26", "12-Apr-26"),
]

DEFAULT_NCR_NOTE = (
    "No new NCRs were issued during Week 20. Corrective and preventive actions "
    "continue to be monitored; the Contractor maintains strict hold-point and "
    "inspection procedures."
)


DEFAULT_CONCRETE = [
    ConcreteRow("Lower Raft Foundation", "C40/20", "Acceptable (Doc-0029)", "Acceptable (Doc-0032)", "PENDING", "pending"),
    ConcreteRow("Raft Blinding / PCC", "C30/20", "Acceptable", "Acceptable", "ACCEPTABLE", "completed"),
]


DEFAULT_AOCS = [
    AOCEntry(
        "AOC-01", "Outstanding shop drawings & material submittals",
        "Main Contractor / Sub-Contractors", "On-going",
        "Low — being managed", impact_kind="success",
    ),
    AOCEntry(
        "AOC-02", "Resubmission of submittal logs addressing Consultant remarks",
        "Main Contractor", "Immediate", "Low — administrative",
        impact_kind="success",
    ),
    AOCEntry(
        "AOC-03", "Developer confirmation of proposed FIC location and finished levels",
        "Employer / Developer", "Pending", "Medium",
        impact_kind="amber",
    ),
    AOCEntry(
        "AOC-04", "Obtaining Electrical NOC as per actual load",
        "Consultant / Client", "On-going", "Low — administrative",
        impact_kind="success",
    ),
    AOCEntry(
        "AOC-05", "Civil Work Inspection Requests — 14 entries rejected (status D)",
        "Main Contractor", "Resubmit / rectify", "Medium",
        impact_kind="amber",
    ),
]

DEFAULT_AOC_ASSESSMENT = (
    "AOC-03 (FIC location) awaits Developer confirmation. AOC-05 (14 Civil WIRs in status "
    "D — Rejected) requires resubmission / rectification. Remaining items are administrative "
    "and tracked through routine submittal logs."
)


DEFAULT_PROGRAMME_ROWS = [
    ProgrammeRow("Shoring Works",                              "Dec 2025", "Jan 2026", "—", "100%", "complete"),
    ProgrammeRow("Excavation Works",                           "Dec 2025", "Feb 2026", "—", "100%", "complete"),
    ProgrammeRow("Dewatering System",                          "Jan 2026", "Apr 2026", "—", "100%", "complete"),
    ProgrammeRow("PCC / Blinding Works",                       "Feb 2026", "Mar 2026", "—", "100%", "complete"),
    ProgrammeRow("Substructure Waterproofing",                 "Feb 2026", "Apr 2026", "—", "100%", "complete"),
    ProgrammeRow("Raft Foundation Steel",                      "Mar 2026", "Apr 2026", "Lower: COMPLETE  |  Higher: COMPLETE", "100%", "complete"),
    ProgrammeRow("Raft Foundation Casting",                    "Apr 2026", "Apr 2026", "Lower raft cast 11-Apr; Higher raft cast 29–30 Apr", "100%", "complete"),
    ProgrammeRow("Basement Columns & Walls",                   "Apr 2026", "May 2026", "Column casting 96%; retaining walls 85%", "90%", "progress"),
    ProgrammeRow("MEP First Fix — Basement Floor Horizontals", "Apr 2026", "May 2026", "First-fix progressing in line with formwork", "90%", "progress"),
    ProgrammeRow("Basement Slab Shuttering & Reinforcement",   "Apr 2026", "May 2026", "Formwork at 80%; rebar to commence", "30%", "progress"),
]

DEFAULT_PROGRAMME_STATEMENT = (
    "The Contractor is working to maintain the approved baseline programme. The approved "
    "programme (DB36-EPCC-AHC-DOC-0012 Rev. 04) was formally accepted on 27-Apr-2026. "
    "Substructure works are progressing ahead of the original Rev. 03 targets. Any impacts "
    "arising will be notified in accordance with the Contract."
)


DEFAULT_PHOTO_CAPTIONS = [
    # Per day: two captions matching the reference deck.
    [
        "Substructure works in progress — column reinforcement and formwork visible across raft level.",
        "Lower raft column rebar and timber formwork — view from south-east.",
    ],
    [
        "Crew engaged in steel reinforcement and formwork tie-in across raft slab area.",
        "Higher raft area with column rebar and crane lift in progress.",
    ],
    [
        "Concrete pump and boom positioned for higher raft casting operation.",
        "Higher raft pour in progress — concrete placement and vibration team at work.",
    ],
    [
        "Night-shift activity at the substructure works — site lighting active.",
        "Cured raft surface — finishing work and surface check post-pour.",
    ],
    [
        "Rebar mat for basement slab installed across area; column starters visible.",
        "Retaining-wall reinforcement and formwork prepared for next casting cycle.",
    ],
    [
        "Substructure overview — both raft levels visible with column starters.",
        "Tower crane in operation — slab steel laid out across higher raft area.",
    ],
]
