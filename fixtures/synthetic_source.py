"""Synthetic JobSource for the Baxie Digital Back Office.

Implements the JobSource protocol from schemas.py with one fully-built, oracle-
clean job: a kitchen remodel mid-construction. All data is invented. No real
client names, no Baxie schema, safe for the public repo.

The baseline estimate passes check_estimate() and the baseline schedule passes
check_schedule(). That clean baseline is the floor every agent builds on: when
the homeowner adds an egress window, the crew's job is to price and schedule the
delta without ever pushing a violation past the oracles.
"""

from __future__ import annotations

from schemas import (
    Job,
    ScopeItem,
    Estimate,
    EstimateLine,
    Schedule,
    ScheduleTask,
    ChangeEvent,
    Trade,
)

JOB_ID = "kitchen-1423"


# --------------------------------------------------------------------------- #
# Scope: a real residential kitchen remodel, walked through the trades in order.
# Each item carries a sensible quantity + unit. Nine items, one per major chunk.
# --------------------------------------------------------------------------- #

def _scope() -> list[ScopeItem]:
    return [
        ScopeItem(
            id="sc-site",
            description="Demo old kitchen + protect/prep work area",
            trade=Trade.SITE,
            quantity=180.0,
            unit="sf",
        ),
        ScopeItem(
            id="sc-framing",
            description="Reframe pantry wall + new header for relocated opening",
            trade=Trade.FRAMING,
            quantity=24.0,
            unit="lf",
        ),
        ScopeItem(
            id="sc-mep",
            description="MEP rough-in: outlets, range circuit, sink supply/drain",
            trade=Trade.MEP_ROUGH,
            quantity=1.0,
            unit="ea",
        ),
        ScopeItem(
            id="sc-insulation",
            description="Batt insulation at exterior kitchen wall",
            trade=Trade.INSULATION,
            quantity=180.0,
            unit="sf",
        ),
        ScopeItem(
            id="sc-drywall",
            description="Hang, tape, and finish drywall in kitchen",
            trade=Trade.DRYWALL,
            quantity=420.0,
            unit="sf",
        ),
        ScopeItem(
            id="sc-cabinets",
            description="Set base + wall cabinets, level and scribe",
            trade=Trade.FINISH_CARPENTRY,
            quantity=22.0,
            unit="lf",
        ),
        ScopeItem(
            id="sc-counters",
            description="Template, fabricate, and install quartz countertops",
            trade=Trade.FINISH_CARPENTRY,
            quantity=46.0,
            unit="sf",
        ),
        ScopeItem(
            id="sc-trim",
            description="Install baseboard, door casing, and toe-kick trim",
            trade=Trade.FINISH_CARPENTRY,
            quantity=64.0,
            unit="lf",
        ),
        ScopeItem(
            id="sc-paint",
            description="Prime and paint kitchen walls + ceiling, two coats",
            trade=Trade.PAINT,
            quantity=600.0,
            unit="sf",
        ),
    ]


# --------------------------------------------------------------------------- #
# Baseline estimate: one priced line per scope item, quantities matching exactly,
# rates inside the 45-150 band, markup 0.20. Passes check_estimate().
# --------------------------------------------------------------------------- #

def _baseline_estimate() -> Estimate:
    lines = [
        EstimateLine(
            scope_id="sc-site",
            description="Demo old kitchen + protect/prep work area",
            trade=Trade.SITE,
            quantity=180.0,
            unit="sf",
            labor_hours=16.0,
            labor_rate=55.0,
            material_cost=350.0,
        ),
        EstimateLine(
            scope_id="sc-framing",
            description="Reframe pantry wall + new header for relocated opening",
            trade=Trade.FRAMING,
            quantity=24.0,
            unit="lf",
            labor_hours=20.0,
            labor_rate=68.0,
            material_cost=620.0,
        ),
        EstimateLine(
            scope_id="sc-mep",
            description="MEP rough-in: outlets, range circuit, sink supply/drain",
            trade=Trade.MEP_ROUGH,
            quantity=1.0,
            unit="ea",
            labor_hours=28.0,
            labor_rate=95.0,
            material_cost=900.0,
        ),
        EstimateLine(
            scope_id="sc-insulation",
            description="Batt insulation at exterior kitchen wall",
            trade=Trade.INSULATION,
            quantity=180.0,
            unit="sf",
            labor_hours=8.0,
            labor_rate=52.0,
            material_cost=280.0,
        ),
        EstimateLine(
            scope_id="sc-drywall",
            description="Hang, tape, and finish drywall in kitchen",
            trade=Trade.DRYWALL,
            quantity=420.0,
            unit="sf",
            labor_hours=36.0,
            labor_rate=58.0,
            material_cost=640.0,
        ),
        EstimateLine(
            scope_id="sc-cabinets",
            description="Set base + wall cabinets, level and scribe",
            trade=Trade.FINISH_CARPENTRY,
            quantity=22.0,
            unit="lf",
            labor_hours=30.0,
            labor_rate=82.0,
            material_cost=6800.0,
        ),
        EstimateLine(
            scope_id="sc-counters",
            description="Template, fabricate, and install quartz countertops",
            trade=Trade.FINISH_CARPENTRY,
            quantity=46.0,
            unit="sf",
            labor_hours=14.0,
            labor_rate=90.0,
            material_cost=3450.0,
        ),
        EstimateLine(
            scope_id="sc-trim",
            description="Install baseboard, door casing, and toe-kick trim",
            trade=Trade.FINISH_CARPENTRY,
            quantity=64.0,
            unit="lf",
            labor_hours=18.0,
            labor_rate=72.0,
            material_cost=540.0,
        ),
        EstimateLine(
            scope_id="sc-paint",
            description="Prime and paint kitchen walls + ceiling, two coats",
            trade=Trade.PAINT,
            quantity=600.0,
            unit="sf",
            labor_hours=24.0,
            labor_rate=50.0,
            material_cost=480.0,
        ),
    ]
    return Estimate(job_id=JOB_ID, lines=lines, markup=0.20, label="baseline")


# --------------------------------------------------------------------------- #
# Baseline schedule: tasks follow TRADE_ORDER with finish-to-start dependencies.
# ROUGH_INSPECTION sits after MEP rough and gates drywall; FINAL_INSPECTION caps
# the job after paint. Passes check_schedule().
# --------------------------------------------------------------------------- #

def _baseline_schedule() -> Schedule:
    tasks = [
        ScheduleTask(
            id="t-site",
            name="Demo + site prep",
            trade=Trade.SITE,
            start_day=0,
            duration_days=2,
            crew_size=2,
            depends_on=[],
        ),
        ScheduleTask(
            id="t-framing",
            name="Rough framing",
            trade=Trade.FRAMING,
            start_day=2,
            duration_days=3,
            crew_size=2,
            depends_on=["t-site"],
        ),
        ScheduleTask(
            id="t-mep",
            name="MEP rough-in",
            trade=Trade.MEP_ROUGH,
            start_day=5,
            duration_days=4,
            crew_size=2,
            depends_on=["t-framing"],
        ),
        ScheduleTask(
            id="t-rough-insp",
            name="Rough inspection",
            trade=Trade.ROUGH_INSPECTION,
            start_day=9,
            duration_days=1,
            crew_size=1,
            depends_on=["t-mep"],
        ),
        ScheduleTask(
            id="t-insulation",
            name="Insulation",
            trade=Trade.INSULATION,
            start_day=10,
            duration_days=1,
            crew_size=2,
            depends_on=["t-rough-insp"],
        ),
        ScheduleTask(
            id="t-drywall",
            name="Drywall hang + finish",
            trade=Trade.DRYWALL,
            start_day=11,
            duration_days=4,
            crew_size=2,
            depends_on=["t-insulation", "t-rough-insp"],
        ),
        ScheduleTask(
            id="t-cabinets",
            name="Set cabinets + countertops",
            trade=Trade.FINISH_CARPENTRY,
            start_day=15,
            duration_days=4,
            crew_size=2,
            depends_on=["t-drywall"],
        ),
        ScheduleTask(
            id="t-trim",
            name="Trim + finish carpentry",
            trade=Trade.FINISH_CARPENTRY,
            start_day=19,
            duration_days=2,
            crew_size=2,
            depends_on=["t-cabinets"],
        ),
        ScheduleTask(
            id="t-paint",
            name="Paint",
            trade=Trade.PAINT,
            start_day=21,
            duration_days=3,
            crew_size=2,
            depends_on=["t-trim"],
        ),
        ScheduleTask(
            id="t-final-insp",
            name="Final inspection",
            trade=Trade.FINAL_INSPECTION,
            start_day=24,
            duration_days=1,
            crew_size=1,
            depends_on=["t-paint"],
        ),
    ]
    return Schedule(job_id=JOB_ID, tasks=tasks, label="baseline")


def _build_job() -> Job:
    return Job(
        id=JOB_ID,
        name="Kitchen Remodel - 1423 Oak St (synthetic)",
        client_label="Homeowner A",
        baseline_contract=42000.0,
        scope=_scope(),
        baseline_estimate=_baseline_estimate(),
        baseline_schedule=_baseline_schedule(),
    )


class SyntheticJobSource:
    """Public-safe JobSource backed by one hand-built, oracle-clean job."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {JOB_ID: _build_job()}
        self._events: dict[str, ChangeEvent] = {
            JOB_ID: ChangeEvent(
                id="co-001",
                description="Homeowner wants to add an egress window in the kitchen",
                raised_during=Trade.DRYWALL,
            )
        }

    def get_job(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise KeyError(f"unknown job_id '{job_id}'")
        return self._jobs[job_id]

    def get_change_event(self, job_id: str) -> ChangeEvent:
        if job_id not in self._events:
            raise KeyError(f"no change event for job_id '{job_id}'")
        return self._events[job_id]
