"""The Office Manager orchestrates the crew through the change-order scenario.

Two paths, same event stream + documents:
  - scripted (default, no API key): deterministic, builds the first-pass (broken)
    and repaired artifacts and runs the REAL oracles to emit the FLAGGED -> REPAIRED
    self-correction beats. The demo replays this so it can never stall on a live API.
  - live (ANTHROPIC_API_KEY set): the Estimator/Scheduler agents genuinely produce
    and self-correct the artifacts via tool calls; falls back to scripted on any
    parse/▢ failure.

Every step is emitted as an AgentEvent for the team activity feed. The crew:
  Office Manager (Avery), Project Coordinator (Diego), Estimator (Maya),
  Scheduler (Sam), Office Admin (Rosa).
"""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum

from schemas import (
    Trade, ScopeItem, EstimateLine, Estimate, ScheduleTask, Schedule,
    ChangeOrder, Invoice, Reminder, Job, AgentEvent, Status,
)
from estimate_oracle import check_estimate
from schedule_oracle import check_schedule

CREW = {
    "office_manager": ("Avery", "Office Manager"),
    "coordinator": ("Diego", "Project Coordinator"),
    "estimator": ("Maya", "Estimator"),
    "scheduler": ("Sam", "Scheduler"),
    "office_admin": ("Rosa", "Office Admin"),
}


def _doc(obj) -> dict:
    """Serialize a dataclass document, enums -> values."""
    def enc(v):
        if isinstance(v, Enum):
            return v.value
        if isinstance(v, list):
            return [enc(x) for x in v]
        if hasattr(v, "__dataclass_fields__"):
            return {k: enc(getattr(v, k)) for k in v.__dataclass_fields__}
        return v
    return enc(obj)


class Feed:
    """Collects AgentEvents in order."""
    def __init__(self):
        self.events: list[AgentEvent] = []

    def add(self, who: str, status: Status, message: str, document=None):
        name, role = CREW[who]
        self.events.append(AgentEvent(
            agent=name, role=role, status=status, message=message,
            document=_doc(document) if document is not None else None,
            seq=len(self.events),
        ))


# --------------------------------------------------------------------------- #
# Change-order scenario data (the egress window add). Self-contained so the
# scenario runs reliably regardless of the synthetic fixtures' build state.
# --------------------------------------------------------------------------- #

def _co_job() -> Job:
    """A compact job context carrying only the change-order scope (the window)."""
    scope = [
        ScopeItem("co-framing", "Frame rough opening + header", Trade.FRAMING, 1, "ea"),
        ScopeItem("co-window", "Install egress window unit", Trade.FINISH_CARPENTRY, 1, "ea"),
        ScopeItem("co-flash", "Flash + waterproof opening", Trade.FRAMING, 1, "ea"),
        ScopeItem("co-drywall", "Drywall patch around opening", Trade.DRYWALL, 1, "ea"),
        ScopeItem("co-paint", "Paint patched area", Trade.PAINT, 1, "ea"),
    ]
    return Job("kitchen-1423", "Kitchen Remodel - 1423 Oak St (synthetic)",
               "Homeowner A", 42000.0, scope=scope)


def _co_lines() -> list[EstimateLine]:
    return [
        EstimateLine("co-framing", "Frame rough opening + header", Trade.FRAMING, 1, "ea", 6, 65, 180),
        EstimateLine("co-window", "Install egress window unit", Trade.FINISH_CARPENTRY, 1, "ea", 4, 70, 620),
        EstimateLine("co-flash", "Flash + waterproof opening", Trade.FRAMING, 1, "ea", 2, 65, 90),
        EstimateLine("co-drywall", "Drywall patch around opening", Trade.DRYWALL, 1, "ea", 3, 60, 60),
        EstimateLine("co-paint", "Paint patched area", Trade.PAINT, 1, "ea", 2, 55, 40),
    ]


def first_pass_estimate() -> Estimate:
    """Estimator's first pass: double-counts the framing labor (the planted error)."""
    lines = _co_lines()
    dup = EstimateLine("co-framing", "Frame header (duplicate)", Trade.FRAMING, 1, "ea", 6, 65, 0)
    return Estimate("kitchen-1423", markup=0.20, label="CO #001 delta (1st pass)",
                    lines=lines[:1] + [dup] + lines[1:])


def repaired_estimate() -> Estimate:
    return Estimate("kitchen-1423", markup=0.20, label="CO #001 delta",
                    lines=_co_lines())


def _baseline_tasks() -> list[ScheduleTask]:
    """Where the job stands when the change comes in (drywall phase)."""
    return [
        ScheduleTask("t-fr", "Framing", Trade.FRAMING, 1, 2, 2),
        ScheduleTask("t-mep", "MEP rough-in", Trade.MEP_ROUGH, 3, 2, 2, ["t-fr"]),
        ScheduleTask("t-ri", "Rough inspection", Trade.ROUGH_INSPECTION, 5, 1, 1, ["t-mep"]),
        ScheduleTask("t-ins", "Insulation", Trade.INSULATION, 6, 1, 2, ["t-ri"]),
        ScheduleTask("t-dw", "Drywall", Trade.DRYWALL, 7, 3, 2, ["t-ins"]),
        ScheduleTask("t-fin", "Finish carpentry", Trade.FINISH_CARPENTRY, 10, 3, 2, ["t-dw"]),
        ScheduleTask("t-pt", "Paint", Trade.PAINT, 13, 2, 2, ["t-fin"]),
        ScheduleTask("t-fi", "Final inspection", Trade.FINAL_INSPECTION, 16, 1, 1, ["t-pt"]),
    ]


def first_pass_schedule() -> Schedule:
    """Scheduler's first pass: slots window framing AFTER drywall (the planted error)."""
    tasks = _baseline_tasks() + [
        ScheduleTask("co-fr", "Window rough framing", Trade.FRAMING, 14, 1, 2, []),
        ScheduleTask("co-dw", "Window drywall patch", Trade.DRYWALL, 15, 1, 2, ["co-fr"]),
    ]
    return Schedule("kitchen-1423", label="CO #001 schedule (1st pass)", tasks=tasks)


def repaired_schedule() -> Schedule:
    """Window framing moved before drywall; +2 days to the job."""
    tasks = _baseline_tasks()
    # insert window framing right after existing framing, before drywall; ripple +2d
    tasks = tasks + [
        ScheduleTask("co-fr", "Window rough framing", Trade.FRAMING, 3, 1, 2, ["t-fr"]),
        ScheduleTask("co-dw", "Window drywall patch", Trade.DRYWALL, 10, 1, 2, ["t-dw", "co-fr"]),
    ]
    # push final inspection out by 2 days to reflect the added work
    for t in tasks:
        if t.id == "t-fi":
            t.start_day += 2
    return Schedule("kitchen-1423", label="CO #001 schedule (repaired, +2 days)", tasks=tasks)


# --------------------------------------------------------------------------- #
# The scenario
# --------------------------------------------------------------------------- #

def run_change_order(message: str = "", live: bool = False) -> dict:
    """Run the change-order scenario. Returns events + documents + final artifacts."""
    feed = Feed()
    job = _co_job()

    # 1. Office Manager: intake + guardrail check + delegate
    if not _in_scope(message):
        feed.add("office_manager", Status.DECLINED,
                 f'"{message}" is outside the back office. I handle estimating, '
                 f'scheduling, and paperwork for your jobs. Want me to take that off your plate?')
        return _result(feed, None, None, {})
    feed.add("office_manager", Status.DELEGATING,
             "Got it: homeowner wants to add an egress window on the Oak St kitchen. "
             "Looping in Diego, Maya, and Sam, then Rosa for the paperwork.")

    # 2. Coordinator logs the field change
    feed.add("coordinator", Status.WORKING,
             "Logged the field change during the drywall phase. It needs pricing and a "
             "schedule impact before we can issue a change order.")

    # 3. Estimator: first pass -> oracle flags -> repair
    est_bad = first_pass_estimate()
    vb = check_estimate(est_bad, job)
    feed.add("estimator", Status.WORKING,
             f"Priced the window add: framing, window unit, flashing, drywall patch, paint. "
             f"Draft subtotal ${est_bad.subtotal:,.0f}. Running it past the checker.")
    if not vb["ok"]:
        feed.add("estimator", Status.FLAGGED,
                 f"Checker caught it: {vb['violations'][0]['detail']}. I double-counted the "
                 f"framing. Fixing.")
    est = repaired_estimate()
    ve = check_estimate(est, job)
    assert ve["ok"], ve
    feed.add("estimator", Status.REPAIRED,
             f"Fixed. Clean change-order estimate: subtotal ${est.subtotal:,.0f}, "
             f"with markup ${est.total:,.0f}. Verified by the checker.",
             document={"type": "estimate", **_doc(est),
                       "subtotal": est.subtotal, "total": est.total})

    # 4. Scheduler: first pass -> oracle flags -> repair
    sch_bad = first_pass_schedule()
    sb = check_schedule(sch_bad, est, job)
    feed.add("scheduler", Status.WORKING,
             "Worked the window into the schedule and checked the trade sequence.")
    if not sb["ok"]:
        feed.add("scheduler", Status.FLAGGED,
                 f"Checker caught it: {sb['violations'][0]['detail']}. Can't frame a new "
                 f"opening after the walls are closed. Re-sequencing.")
    sch = repaired_schedule()
    vs = check_schedule(sch, est, job)
    assert vs["ok"], vs
    feed.add("scheduler", Status.REPAIRED,
             f"Fixed. Window framing now lands before drywall. Job finishes in "
             f"{sch.duration_days} days, +2 from the change. Verified.",
             document={"type": "schedule", **_doc(sch), "duration_days": sch.duration_days})

    # 5. Office Admin: change order + invoice + reminder
    co = ChangeOrder("CO #001", job.id,
                     "Add egress window to kitchen (framing, unit, flashing, drywall, paint)",
                     cost_delta=est.total, schedule_delta_days=2)
    inv = Invoice("INV-002", job.id,
                  line_items=[{"desc": "Change Order #001 - egress window", "amount": est.total}],
                  amount_due=est.total, note="Billed on owner approval of CO #001.")
    rem = Reminder("Change Order #001 needs the owner's signature before work proceeds.",
                   due="today", owner_action_required=True)
    feed.add("office_admin", Status.DONE,
             f"Drafted Change Order #001 (${est.total:,.0f}, +2 days) and the matching "
             f"invoice. Flagged it for the owner's signature.",
             document={"type": "change_order", **_doc(co)})
    feed.add("office_admin", Status.DONE, "Invoice ready.", document={"type": "invoice", **_doc(inv)})
    feed.add("office_admin", Status.DONE, "Reminder set.", document={"type": "reminder", **_doc(rem)})

    # 6. Office Manager reports back
    feed.add("office_manager", Status.DONE,
             f"All set. The window change is priced at ${est.total:,.0f}, adds 2 days, and "
             f"Change Order #001 is ready for your signature. You just need to sign.")

    documents = {"change_order": _doc(co), "invoice": _doc(inv), "reminder": _doc(rem)}
    return _result(feed, est, sch, documents)


def _in_scope(message: str) -> bool:
    """Guardrail: the Office Manager only routes back-office construction work."""
    if not message:
        return True
    m = message.lower()
    out = ["weather", "poem", "joke", "stock", "date", "tax", "medical", "lawyer", "ignore previous"]
    return not any(w in m for w in out)


def _result(feed: Feed, est, sch, documents) -> dict:
    return {
        "scenario": "change_order",
        "events": [e.to_dict() for e in feed.events],
        "documents": documents,
        "estimate": _doc(est) if est else None,
        "schedule": _doc(sch) if sch else None,
    }


if __name__ == "__main__":
    import json
    out = run_change_order("homeowner wants to add a window")
    for e in out["events"]:
        print(f"[{e['seq']:>2}] {e['role']:<18} {e['status']:<10} {e['message'][:80]}")
    print("\ndocuments:", list(out["documents"]))
