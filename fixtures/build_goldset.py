"""Build the self-grading gold set.

Run from the repo root:

    python fixtures/build_goldset.py

Writes fixtures/goldset.json: a list of 12 labeled cases used to self-grade the
agents. Every label is produced by CALLING the deterministic oracles
(check_estimate / check_schedule) on the case input. Nothing here is
hand-labeled. The "binding" rule recorded in each label is whatever the oracle
returns, so the gold set can never silently disagree with the grader.

Spread:
  3 clean estimates, 3 broken estimates (one is the demo's double-counted
  framing -> quantity_mismatch),
  3 clean schedules, 3 broken schedules (one is window-framing-after-drywall ->
  trade_inversion).

The base job is a synthetic kitchen remodel, the same hero scenario the crew
demos. No real client data.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from enum import Enum

# Make the repo root importable when run from anywhere.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from schemas import (  # noqa: E402
    Estimate,
    EstimateLine,
    Job,
    Schedule,
    ScheduleTask,
    ScopeItem,
    Trade,
)
from estimate_oracle import check_estimate  # noqa: E402
from schedule_oracle import check_schedule  # noqa: E402


# --------------------------------------------------------------------------- #
# Serialization helper: dataclasses -> JSON-safe dict, enums -> .value
# --------------------------------------------------------------------------- #

def _enum_safe(obj):
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_enum_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _enum_safe(v) for k, v in obj.items()}
    return obj


def serialize(obj):
    """dataclasses.asdict + enum coercion. Returns a JSON-safe structure."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _enum_safe(dataclasses.asdict(obj))
    return _enum_safe(obj)


# --------------------------------------------------------------------------- #
# Base synthetic job: kitchen remodel, the hero scenario.
# --------------------------------------------------------------------------- #

def base_job() -> Job:
    scope = [
        ScopeItem("S-01", "Demo + site protection", Trade.SITE, 1, "ls"),
        ScopeItem("S-02", "Reframe sink wall", Trade.FRAMING, 24, "lf"),
        ScopeItem("S-03", "MEP rough-in for new layout", Trade.MEP_ROUGH, 1, "ls"),
        ScopeItem("S-04", "Insulate exterior wall", Trade.INSULATION, 180, "sf"),
        ScopeItem("S-05", "Hang + finish drywall", Trade.DRYWALL, 420, "sf"),
        ScopeItem("S-06", "Install cabinets + trim", Trade.FINISH_CARPENTRY, 1, "ls"),
        ScopeItem("S-07", "Paint kitchen", Trade.PAINT, 420, "sf"),
    ]
    return Job(
        id="JOB-KITCHEN-001",
        name="Kitchen Remodel - 1423 Oak St (synthetic)",
        client_label="Synthetic Homeowner A",
        baseline_contract=68_000.0,
        scope=scope,
    )


def _line(scope_id, desc, trade, qty, unit, hours, rate, material) -> EstimateLine:
    return EstimateLine(
        scope_id=scope_id,
        description=desc,
        trade=trade,
        quantity=qty,
        unit=unit,
        labor_hours=hours,
        labor_rate=rate,
        material_cost=material,
    )


# --------------------------------------------------------------------------- #
# Clean estimate: one priced line per scope item, qty reconciles, rates in band.
# --------------------------------------------------------------------------- #

def clean_estimate(job: Job, markup: float = 0.20, label: str = "clean") -> Estimate:
    lines = [
        _line("S-01", "Demo + site protection", Trade.SITE, 1, "ls", 16, 70, 450),
        _line("S-02", "Reframe sink wall", Trade.FRAMING, 24, "lf", 20, 75, 900),
        _line("S-03", "MEP rough-in", Trade.MEP_ROUGH, 1, "ls", 40, 95, 2200),
        _line("S-04", "Insulate exterior wall", Trade.INSULATION, 180, "sf", 8, 55, 320),
        _line("S-05", "Hang + finish drywall", Trade.DRYWALL, 420, "sf", 36, 65, 1100),
        _line("S-06", "Cabinets + trim", Trade.FINISH_CARPENTRY, 1, "ls", 48, 80, 6800),
        _line("S-07", "Paint kitchen", Trade.PAINT, 420, "sf", 24, 55, 600),
    ]
    return Estimate(job_id=job.id, lines=lines, markup=markup, label=label)


# --------------------------------------------------------------------------- #
# Clean schedule: legal trade order, deps resolve, inspections present + gated.
# --------------------------------------------------------------------------- #

def clean_schedule(job: Job, label: str = "clean") -> Schedule:
    tasks = [
        ScheduleTask("T-01", "Demo + protect", Trade.SITE, 0, 2, 2),
        ScheduleTask("T-02", "Reframe sink wall", Trade.FRAMING, 2, 3, 2, ["T-01"]),
        ScheduleTask("T-03", "MEP rough-in", Trade.MEP_ROUGH, 5, 3, 2, ["T-02"]),
        ScheduleTask("T-04", "Rough inspection", Trade.ROUGH_INSPECTION, 8, 1, 1, ["T-03"]),
        ScheduleTask("T-05", "Insulation", Trade.INSULATION, 9, 1, 2, ["T-04"]),
        ScheduleTask("T-06", "Hang + finish drywall", Trade.DRYWALL, 10, 4, 3, ["T-05"]),
        ScheduleTask("T-07", "Cabinets + trim", Trade.FINISH_CARPENTRY, 14, 4, 2, ["T-06"]),
        ScheduleTask("T-08", "Paint", Trade.PAINT, 18, 2, 2, ["T-07"]),
        ScheduleTask("T-09", "Final inspection", Trade.FINAL_INSPECTION, 20, 1, 1, ["T-08"]),
    ]
    return Schedule(job_id=job.id, tasks=tasks, label=label)


# --------------------------------------------------------------------------- #
# Case builders. Each returns (id, kind, estimate_or_schedule, job).
# --------------------------------------------------------------------------- #

def build_cases():
    """Return a list of (case_id, kind, payload_obj, job) tuples."""
    cases = []

    # ---- 3 clean estimates -------------------------------------------------
    job = base_job()
    cases.append(("est-clean-baseline", "estimate", clean_estimate(job), job))

    job = base_job()
    cases.append(("est-clean-markup-25", "estimate",
                  clean_estimate(job, markup=0.25, label="clean markup 25%"), job))

    # Clean estimate where one scope item is split across two lines that still
    # sum to the scope quantity (legal: reconciliation passes).
    job = base_job()
    est = clean_estimate(job, label="clean split-line")
    est.lines = [l for l in est.lines if l.scope_id != "S-05"]
    est.lines.append(_line("S-05", "Hang drywall", Trade.DRYWALL, 220, "sf", 18, 65, 600))
    est.lines.append(_line("S-05", "Finish + tape drywall", Trade.DRYWALL, 200, "sf", 18, 65, 500))
    cases.append(("est-clean-split-line", "estimate", est, job))

    # ---- 3 broken estimates ------------------------------------------------
    # (1) THE DEMO CASE: double-counted framing -> quantity_mismatch.
    # Two framing lines each price the full 24 lf, summing to 48 (2x scope).
    job = base_job()
    est = clean_estimate(job, label="DEMO double-counted framing")
    est.lines = [l for l in est.lines if l.scope_id != "S-02"]
    est.lines.append(_line("S-02", "Reframe sink wall", Trade.FRAMING, 24, "lf", 20, 75, 900))
    est.lines.append(_line("S-02", "Reframe sink wall (dup)", Trade.FRAMING, 24, "lf", 20, 75, 900))
    cases.append(("est-broken-double-count-framing", "estimate", est, job))

    # (2) Coverage miss: a scope item left unpriced -> coverage.
    job = base_job()
    est = clean_estimate(job, label="missing paint line")
    est.lines = [l for l in est.lines if l.scope_id != "S-07"]
    cases.append(("est-broken-missing-coverage", "estimate", est, job))

    # (3) Labor rate out of band -> rate_out_of_band.
    job = base_job()
    est = clean_estimate(job, label="absurd labor rate")
    est.lines = [l for l in est.lines if l.scope_id != "S-03"]
    est.lines.append(_line("S-03", "MEP rough-in", Trade.MEP_ROUGH, 1, "ls", 40, 400, 2200))
    cases.append(("est-broken-rate-out-of-band", "estimate", est, job))

    # ---- 3 clean schedules -------------------------------------------------
    job = base_job()
    cases.append(("sch-clean-baseline", "schedule", clean_schedule(job), job))

    # Clean schedule with a slightly longer drywall window (still legal order).
    job = base_job()
    sch = clean_schedule(job, label="clean longer drywall")
    for t in sch.tasks:
        if t.id == "T-06":
            t.duration_days = 5
        if t.id == "T-07":
            t.start_day = 15
        if t.id == "T-08":
            t.start_day = 19
        if t.id == "T-09":
            t.start_day = 21
    cases.append(("sch-clean-longer-drywall", "schedule", sch, job))

    # Clean schedule with bigger crews (still legal order + gating).
    job = base_job()
    sch = clean_schedule(job, label="clean bigger crews")
    for t in sch.tasks:
        t.crew_size = max(t.crew_size, 2)
    cases.append(("sch-clean-bigger-crews", "schedule", sch, job))

    # ---- 3 broken schedules ------------------------------------------------
    # (1) THE DEMO CASE: window framing scheduled AFTER drywall -> trade_inversion.
    # A FRAMING task starts after a DRYWALL task has finished.
    job = base_job()
    sch = clean_schedule(job, label="DEMO window framing after drywall")
    sch.tasks.append(
        ScheduleTask("T-10", "Frame new egress window", Trade.FRAMING,
                     start_day=16, duration_days=2, crew_size=2)
    )
    cases.append(("sch-broken-window-framing-after-drywall", "schedule", sch, job))

    # (2) Missing required final inspection -> missing_inspection.
    job = base_job()
    sch = clean_schedule(job, label="missing final inspection")
    sch.tasks = [t for t in sch.tasks if t.trade != Trade.FINAL_INSPECTION]
    cases.append(("sch-broken-missing-inspection", "schedule", sch, job))

    # (3) Task starts before its prerequisite finishes -> starts_before_prereq.
    job = base_job()
    sch = clean_schedule(job, label="drywall starts before insulation done")
    for t in sch.tasks:
        if t.id == "T-06":  # drywall depends on T-05 (insulation, ends day 10)
            t.start_day = 9  # starts before insulation finishes
    cases.append(("sch-broken-starts-before-prereq", "schedule", sch, job))

    return cases


# --------------------------------------------------------------------------- #
# Build + label + write.
# --------------------------------------------------------------------------- #

def build_goldset() -> list[dict]:
    goldset = []
    for case_id, kind, payload, job in build_cases():
        if kind == "estimate":
            verdict = check_estimate(payload, job)
        elif kind == "schedule":
            # The schedule oracle's labor check needs an estimate; use the clean
            # one for the same job so labor sizing never falsely trips.
            verdict = check_schedule(payload, clean_estimate(job), job)
        else:
            raise ValueError(f"unknown kind {kind!r}")

        case = {
            "id": case_id,
            "kind": kind,
            "input": {
                "job": serialize(job),
                kind: serialize(payload),
            },
            "label": {
                "ok": verdict["ok"],
                "binding": verdict["binding"],
            },
        }
        goldset.append(case)
    return goldset


def main() -> None:
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goldset.json")
    goldset = build_goldset()
    with open(out_path, "w") as f:
        json.dump(goldset, f, indent=2)

    print(f"Wrote {len(goldset)} cases -> {out_path}\n")
    print(f"{'id':<42} {'kind':<9} {'ok':<6} binding")
    print("-" * 80)
    for c in goldset:
        print(f"{c['id']:<42} {c['kind']:<9} "
              f"{str(c['label']['ok']):<6} {c['label']['binding']}")

    # Confirm the two named demo cases carry the expected binding rules.
    by_id = {c["id"]: c for c in goldset}
    checks = [
        ("est-broken-double-count-framing", "quantity_mismatch"),
        ("sch-broken-window-framing-after-drywall", "trade_inversion"),
    ]
    print("\nDemo-case assertions:")
    all_ok = True
    for cid, expected in checks:
        actual = by_id[cid]["label"]["binding"]
        passed = actual == expected
        all_ok = all_ok and passed
        print(f"  [{'OK' if passed else 'FAIL'}] {cid}: "
              f"binding={actual} (expected {expected})")
    if not all_ok:
        raise SystemExit("Demo-case binding assertion failed.")
    print("\nAll demo-case bindings correct.")


if __name__ == "__main__":
    main()
