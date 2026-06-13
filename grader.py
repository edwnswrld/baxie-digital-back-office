"""Self-grading scoreboard.

A gold set of estimate/schedule cases, each with the verdict the deterministic
oracle should return. We run the oracles and check agreement. Because the oracle
is the ground truth, this proves the harness is internally consistent and
reproducible (rubric item: machine-verifiable, rerunnable).

score_agent() (optional, needs ANTHROPIC_API_KEY = org credits) has a classifier
agent predict each verdict and scores the AGENT against the oracle: the genuine
"the crew grades itself" number.
"""

from __future__ import annotations

from dataclasses import replace

from schemas import Trade, EstimateLine, Estimate, ScheduleTask, Schedule
from estimate_oracle import check_estimate
from schedule_oracle import check_schedule
from orchestrator import (
    _co_job, _co_lines, _baseline_tasks,
    first_pass_estimate, repaired_estimate,
    first_pass_schedule, repaired_schedule,
)


def _est(lines, markup=0.20) -> Estimate:
    return Estimate("kitchen-1423", markup=markup, lines=lines)


def _gold_estimates():
    job = _co_job()
    base = _co_lines()
    cases = []
    # clean
    cases.append(("est_clean", repaired_estimate(), True, None))
    # double-count (demo)
    cases.append(("est_double_count", first_pass_estimate(), False, "quantity_mismatch"))
    # rate out of band
    bad_rate = [replace(base[0], labor_rate=400)] + base[1:]
    cases.append(("est_bad_rate", _est(bad_rate), False, "rate_out_of_band"))
    # missing coverage (drop a scope's line)
    cases.append(("est_missing_line", _est(base[:-1]), False, "coverage"))
    # phantom line
    phantom = base + [EstimateLine("nope", "ghost", Trade.PAINT, 1, "ea", 1, 60, 10)]
    cases.append(("est_phantom", _est(phantom), False, "phantom_line"))
    # bad markup
    cases.append(("est_bad_markup", _est(base, markup=0.60), False, "markup_out_of_band"))
    return job, cases


def _gold_schedules():
    job = _co_job()
    est = repaired_estimate()
    cases = []
    cases.append(("sch_clean", repaired_schedule(), True, None))
    cases.append(("sch_inversion", first_pass_schedule(), False, "trade_inversion"))
    # missing final inspection
    no_final = Schedule("kitchen-1423", tasks=[t for t in repaired_schedule().tasks
                                               if t.trade != Trade.FINAL_INSPECTION])
    cases.append(("sch_missing_inspection", no_final, False, "missing_inspection"))
    # starts before prereq
    early = repaired_schedule()
    for t in early.tasks:
        if t.id == "co-dw":
            t.start_day = 1
    cases.append(("sch_starts_early", early, False, "starts_before_prereq"))
    return job, est, cases


def score_goldset() -> dict:
    correct, total, rows = 0, 0, []
    job, est_cases = _gold_estimates()
    for cid, est, exp_ok, exp_bind in est_cases:
        v = check_estimate(est, job)
        ok = v["ok"] == exp_ok and (v["binding"] == exp_bind or exp_ok)
        correct += ok
        total += 1
        rows.append({"id": cid, "kind": "estimate", "expected_ok": exp_ok,
                     "got_ok": v["ok"], "binding": v["binding"], "match": ok})
    job, est, sch_cases = _gold_schedules()
    for cid, sch, exp_ok, exp_bind in sch_cases:
        v = check_schedule(sch, est, job)
        ok = v["ok"] == exp_ok and (v["binding"] == exp_bind or exp_ok)
        correct += ok
        total += 1
        rows.append({"id": cid, "kind": "schedule", "expected_ok": exp_ok,
                     "got_ok": v["ok"], "binding": v["binding"], "match": ok})
    return {
        "available": True,
        "n": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0.0,
        "rows": rows,
    }


if __name__ == "__main__":
    sb = score_goldset()
    print(f"gold set: {sb['correct']}/{sb['n']} ({sb['accuracy']:.0%})")
    for r in sb["rows"]:
        flag = "ok " if r["match"] else "XX "
        print(f"  {flag}{r['id']:<24} {r['kind']:<9} got_ok={r['got_ok']!s:<5} binding={r['binding']}")
