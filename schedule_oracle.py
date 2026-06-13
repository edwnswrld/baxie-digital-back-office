"""Deterministic schedule oracle.

check_schedule() is both a TOOL the Scheduler agent calls and the GRADER for the
gold set. It encodes residential trade-sequencing logic, so a schedule that puts
drywall before framing is provably wrong with no human in the loop.

Returns a verdict dict:
  {
    "ok": bool,
    "violations": [ {"rule": str, "detail": str}, ... ],
    "duration_days": int,
    "binding": str | None,
  }
"""

from __future__ import annotations

from schemas import (
    Schedule, Estimate, Job, Trade, trade_rank, REQUIRED_INSPECTIONS,
)


def _has_cycle(tasks_by_id: dict[str, "ScheduleTask"]) -> bool:  # type: ignore[name-defined]
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tasks_by_id}

    def visit(tid: str) -> bool:
        color[tid] = GRAY
        for dep in tasks_by_id[tid].depends_on:
            if dep not in tasks_by_id:
                continue
            if color[dep] == GRAY:
                return True
            if color[dep] == WHITE and visit(dep):
                return True
        color[tid] = BLACK
        return False

    return any(color[tid] == WHITE and visit(tid) for tid in tasks_by_id)


def check_schedule(schedule: Schedule, estimate: Estimate | None, job: Job) -> dict:
    violations: list[dict] = []
    tasks = schedule.tasks
    by_id = {t.id: t for t in tasks}

    # Rule 1: dependencies resolve + acyclic.
    for t in tasks:
        for dep in t.depends_on:
            if dep not in by_id:
                violations.append({
                    "rule": "dangling_dependency",
                    "detail": f"task '{t.name}' depends on unknown task '{dep}'",
                })
    if by_id and _has_cycle(by_id):
        violations.append({
            "rule": "cyclic_dependency",
            "detail": "the schedule has a circular dependency (not a valid DAG)",
        })

    # Rule 2: finish-to-start — a task can't start before its dependencies finish,
    # and a dependency can't be from a strictly later trade.
    for t in tasks:
        for dep in t.depends_on:
            d = by_id.get(dep)
            if d is None:
                continue
            if d.end_day > t.start_day:
                violations.append({
                    "rule": "starts_before_prereq",
                    "detail": (
                        f"'{t.name}' starts day {t.start_day} but prereq "
                        f"'{d.name}' finishes day {d.end_day}"
                    ),
                })
            if trade_rank(d.trade) > trade_rank(t.trade):
                violations.append({
                    "rule": "prereq_later_trade",
                    "detail": (
                        f"'{t.name}' ({t.trade.value}) depends on later-trade "
                        f"'{d.name}' ({d.trade.value})"
                    ),
                })

    # Rule 3: trade inversion — an earlier-trade task fully scheduled AFTER a
    # later-trade task finished. Catches the demo's window-framing-after-drywall.
    for a in tasks:
        for b in tasks:
            if a is b:
                continue
            if trade_rank(a.trade) < trade_rank(b.trade) and a.start_day > b.end_day:
                violations.append({
                    "rule": "trade_inversion",
                    "detail": (
                        f"'{a.name}' ({a.trade.value}) starts day {a.start_day}, "
                        f"after '{b.name}' ({b.trade.value}) ends day {b.end_day}; "
                        f"{a.trade.value} must precede {b.trade.value}"
                    ),
                })

    # Rule 4: required inspections present and gated.
    trades_present = {t.trade for t in tasks}
    for insp in REQUIRED_INSPECTIONS:
        if insp not in trades_present:
            violations.append({
                "rule": "missing_inspection",
                "detail": f"required {insp.value} is missing from the schedule",
            })
    # Rough inspection must come after framing/MEP and before drywall.
    rough = [t for t in tasks if t.trade == Trade.ROUGH_INSPECTION]
    drywall = [t for t in tasks if t.trade == Trade.DRYWALL]
    for ri in rough:
        for dw in drywall:
            if ri.start_day > dw.start_day:
                violations.append({
                    "rule": "inspection_gating",
                    "detail": (
                        f"rough inspection (day {ri.start_day}) must precede "
                        f"drywall '{dw.name}' (day {dw.start_day})"
                    ),
                })

    # Rule 5: labor sanity — scheduled labor hours cover the estimate's hours.
    if estimate is not None and tasks:
        scheduled_hours = sum(t.crew_size * t.duration_days * 8 for t in tasks)
        needed = estimate.total_labor_hours
        if scheduled_hours + 1e-6 < needed * 0.5:
            violations.append({
                "rule": "labor_undersized",
                "detail": (
                    f"scheduled ~{scheduled_hours}h covers <50% of estimate "
                    f"{needed}h of labor"
                ),
            })

    # de-dupe identical violations (pairwise scans can repeat)
    seen, deduped = set(), []
    for v in violations:
        key = (v["rule"], v["detail"])
        if key not in seen:
            seen.add(key)
            deduped.append(v)

    return {
        "ok": len(deduped) == 0,
        "violations": deduped,
        "duration_days": schedule.duration_days,
        "binding": deduped[0]["rule"] if deduped else None,
    }
