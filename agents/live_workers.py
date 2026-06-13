"""Live agentic workers: the Estimator and Scheduler running for real on Opus.

These prove the system is truly agentic and make a run draw from the $500 org
pool. Each worker reasons, calls a submit tool that runs the deterministic oracle,
reads the violations, and self-corrects until the oracle passes. Guardrails live
in the system prompt (stay in scope) and in the tool set (a worker only gets the
tools for its job).

Every call is wrapped by the orchestrator in try/except: any failure falls back
to the proven scripted artifacts, so the demo is always safe.
"""

from __future__ import annotations

from schemas import Trade, EstimateLine, Estimate, ScheduleTask, Schedule, Job
from estimate_oracle import check_estimate
from schedule_oracle import check_schedule
from agents.base import run_agent, Tool, have_key

TRADE_VALUES = [t.value for t in Trade]


def _scope_text(job: Job) -> str:
    return "\n".join(
        f"- id={s.id} | {s.description} | trade={s.trade.value} | qty={s.quantity} {s.unit}"
        for s in job.scope
    )


# --------------------------------------------------------------------------- #
# Estimator
# --------------------------------------------------------------------------- #

def live_estimate(job: Job):
    """Run the real Estimator agent. Returns (Estimate, attempts) or raises."""
    if not have_key():
        raise RuntimeError("no API key")

    state = {"estimate": None, "attempts": []}

    def submit_estimate(inp: dict) -> dict:
        lines = []
        for l in inp.get("lines", []):
            lines.append(EstimateLine(
                scope_id=l["scope_id"], description=l["description"],
                trade=Trade(l["trade"]), quantity=float(l["quantity"]), unit=l["unit"],
                labor_hours=float(l["labor_hours"]), labor_rate=float(l["labor_rate"]),
                material_cost=float(l["material_cost"]),
            ))
        est = Estimate(job.id, lines=lines, markup=float(inp.get("markup", 0.20)),
                       label="CO #001 delta")
        verdict = check_estimate(est, job)
        state["attempts"].append(verdict)
        if verdict["ok"]:
            state["estimate"] = est
        return verdict

    tool = Tool(
        name="submit_estimate",
        description="Submit your estimate line items for the deterministic checker. "
                    "Returns ok plus any violations. Fix violations and submit again until ok.",
        input_schema={
            "type": "object",
            "properties": {
                "lines": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "scope_id": {"type": "string"},
                        "description": {"type": "string"},
                        "trade": {"type": "string", "enum": TRADE_VALUES},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string"},
                        "labor_hours": {"type": "number"},
                        "labor_rate": {"type": "number"},
                        "material_cost": {"type": "number"},
                    },
                    "required": ["scope_id", "description", "trade", "quantity", "unit",
                                 "labor_hours", "labor_rate", "material_cost"],
                }},
                "markup": {"type": "number"},
            },
            "required": ["lines", "markup"],
        },
        impl=submit_estimate,
    )

    system = (
        "You are Maya, the Estimator for a residential GC back office. Price the "
        "change-order scope into line items, one line per scope id, and call "
        "submit_estimate. A deterministic checker validates it and returns violations. "
        "Read them, fix them, and submit again until ok is true. Rules: exactly one "
        "priced line per scope id (never double-count), labor_rate between 45 and 150 "
        "$/hr, markup between 0.10 and 0.35. Stay strictly in scope; you only estimate."
    )
    user = f"Change-order scope to price:\n{_scope_text(job)}\nSubmit your estimate."

    run_agent(system, user, tools=[tool])
    if state["estimate"] is None:
        raise RuntimeError("estimator did not reach a clean estimate")
    return state["estimate"], state["attempts"]


# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #

def live_schedule(job: Job, estimate: Estimate, baseline_tasks: list[ScheduleTask]):
    """Run the real Scheduler agent. Returns (Schedule, attempts) or raises."""
    if not have_key():
        raise RuntimeError("no API key")

    state = {"schedule": None, "attempts": []}
    base = [
        {"id": t.id, "name": t.name, "trade": t.trade.value,
         "start_day": t.start_day, "duration_days": t.duration_days}
        for t in baseline_tasks
    ]

    def submit_schedule(inp: dict) -> dict:
        tasks = []
        for t in baseline_tasks:  # keep the existing baseline tasks
            tasks.append(t)
        for t in inp.get("new_tasks", []):
            tasks.append(ScheduleTask(
                id=t["id"], name=t["name"], trade=Trade(t["trade"]),
                start_day=int(t["start_day"]), duration_days=int(t["duration_days"]),
                crew_size=int(t.get("crew_size", 2)), depends_on=t.get("depends_on", []),
            ))
        sch = Schedule(job.id, tasks=tasks, label="CO #001 schedule")
        verdict = check_schedule(sch, estimate, job)
        state["attempts"].append(verdict)
        if verdict["ok"]:
            state["schedule"] = sch
        return verdict

    tool = Tool(
        name="submit_schedule",
        description="Submit the NEW tasks to add for the change order (the baseline "
                    "tasks are kept automatically). Returns ok plus violations. Fix and "
                    "resubmit until ok.",
        input_schema={
            "type": "object",
            "properties": {
                "new_tasks": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "trade": {"type": "string", "enum": TRADE_VALUES},
                        "start_day": {"type": "integer"},
                        "duration_days": {"type": "integer"},
                        "crew_size": {"type": "integer"},
                        "depends_on": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "name", "trade", "start_day", "duration_days"],
                }},
            },
            "required": ["new_tasks"],
        },
        impl=submit_schedule,
    )

    system = (
        "You are Sam, the Scheduler for a residential GC back office. Add the new tasks "
        "needed for the change order to the existing schedule and call submit_schedule. "
        "A deterministic checker validates trade sequencing and returns violations. Read "
        "them, fix them, resubmit until ok is true. Key rule: trades must run in legal "
        "order (framing before mep_rough_in before rough_inspection before insulation "
        "before drywall before finish_carpentry before paint before final_inspection); "
        "you cannot frame a new opening after drywall is up. Stay strictly in scope."
    )
    import json
    user = (f"Existing baseline tasks:\n{json.dumps(base, indent=2)}\n\n"
            f"Add tasks to frame and finish a new egress window. Submit your new tasks.")

    run_agent(system, user, tools=[tool])
    if state["schedule"] is None:
        raise RuntimeError("scheduler did not reach a clean schedule")
    return state["schedule"], state["attempts"]
