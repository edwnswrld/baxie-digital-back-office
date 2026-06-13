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
    ChangeOrder, Invoice, Reminder, EmailDraft, Job, AgentEvent, Status,
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

# Seeded project the change comes into, so the GC sees the before -> after.
PROJECT = {
    "name": "Kitchen Remodel - 1423 Oak St",
    "address": "1423 Oak St, Vallejo, CA (synthetic)",
    "client_name": "Jordan Avery",
    "client_email": "jordan.avery@example.com",
    "cost_before": 42000.0,   # current contract value
    "days_before": 25,        # current schedule length
}

# The change is specified, not fabricated: a code-compliant egress window.
WINDOW_SIZE = '36" W x 48" H egress window'
CO_DATE = "June 13, 2026"


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

def _estimator_step(job, feed, live):
    """Estimator. Live agent self-corrects on Opus (org credits); else scripted."""
    if live:
        try:
            from agents.live_workers import live_estimate
            feed.add("estimator", Status.WORKING, "Pricing the window add, then checking it.")
            est, attempts = live_estimate(job)
            had_fix = False
            for v in attempts:
                if not v["ok"]:
                    had_fix = True
                    feed.add("estimator", Status.FLAGGED,
                             f"Checker caught it: {v['violations'][0]['detail']}. Fixing.")
            feed.add("estimator", Status.REPAIRED if had_fix else Status.DONE,
                     f"Clean estimate: subtotal ${est.subtotal:,.0f}, ${est.total:,.0f} with "
                     f"markup. Verified by the checker.",
                     document={"type": "estimate", **_doc(est),
                               "subtotal": est.subtotal, "total": est.total})
            return est
        except Exception:
            feed.add("estimator", Status.WORKING, "(falling back to the verified draft)")

    est_bad = first_pass_estimate()
    vb = check_estimate(est_bad, job)
    feed.add("estimator", Status.WORKING,
             "Pricing the window: framing, the unit, flashing, drywall patch, paint.")
    if not vb["ok"]:
        feed.add("estimator", Status.FLAGGED,
                 "My own double-check caught a mistake: I counted the framing labor twice. "
                 "Fixing it.")
    est = repaired_estimate()
    assert check_estimate(est, job)["ok"]
    feed.add("estimator", Status.REPAIRED,
             f"Fixed and double-checked. The window adds ${est.total:,.0f}.",
             document={"type": "estimate", **_doc(est), "subtotal": est.subtotal,
                       "total": est.total, "updated": True,
                       "what_changed": f"Added {len(est.lines)} line items for the window"})
    return est


def _scheduler_step(job, est, feed, live):
    """Scheduler. Live agent self-corrects on Opus (org credits); else scripted."""
    if live:
        try:
            from agents.live_workers import live_schedule
            feed.add("scheduler", Status.WORKING, "Working the window into the schedule.")
            sch, attempts = live_schedule(job, est, _baseline_tasks())
            had_fix = False
            for v in attempts:
                if not v["ok"]:
                    had_fix = True
                    feed.add("scheduler", Status.FLAGGED,
                             f"Checker caught it: {v['violations'][0]['detail']}. Re-sequencing.")
            feed.add("scheduler", Status.REPAIRED if had_fix else Status.DONE,
                     f"Clean schedule. Job finishes in {sch.duration_days} days. Verified.",
                     document={"type": "schedule", **_doc(sch), "duration_days": sch.duration_days})
            return sch
        except Exception:
            feed.add("scheduler", Status.WORKING, "(falling back to the verified draft)")

    sch_bad = first_pass_schedule()
    sb = check_schedule(sch_bad, est, job)
    feed.add("scheduler", Status.WORKING, "Fitting the window into the timeline.")
    if not sb["ok"]:
        feed.add("scheduler", Status.FLAGGED,
                 "My check caught an out-of-order step: I had the window framing after the "
                 "drywall, which can't happen. Putting framing first.")
    sch = repaired_schedule()
    assert check_schedule(sch, est, job)["ok"]
    days_after = PROJECT["days_before"] + 2
    feed.add("scheduler", Status.REPAIRED,
             f"Fixed. Framing now comes before drywall. Timeline goes from "
             f"{PROJECT['days_before']} to {days_after} days.",
             document={"type": "schedule", **_doc(sch), "duration_days": days_after,
                       "updated": True,
                       "what_changed": "Added window framing + drywall patch, +2 days"})
    return sch


def run_change_order(message: str = "", live: bool = False) -> dict:
    """Dispatch: live agents handle the real request; otherwise the deterministic
    window scenario. Any live failure falls back to the scripted demo, so the
    workspace always renders something."""
    from agents.base import agents_enabled
    if live and agents_enabled():
        try:
            return run_change_order_live(message)
        except Exception:
            pass
    return _run_scripted(message)


def _plain(verdict: dict) -> str:
    """Plain-English version of an oracle violation for the feed."""
    b = verdict.get("binding")
    return {
        "quantity_mismatch": "I double-counted some of the work",
        "coverage": "I missed pricing part of the scope",
        "trade_inversion": "I had the work out of order",
        "starts_before_prereq": "I scheduled a step before its prerequisite",
        "prereq_later_trade": "I had a step depending on later work",
        "missing_inspection": "I left out a required inspection",
    }.get(b, "something didn't check out")


def run_change_order_live(message: str) -> dict:
    """Genuinely agentic path: the Office Manager turns the real request into scope,
    then the Estimator and Scheduler price/schedule and self-correct on Opus."""
    from agents.intake import derive_change, build_job
    from agents.live_workers import live_estimate, live_schedule

    feed = Feed()
    change = derive_change(message)
    if not change["in_scope"]:
        feed.add("office_manager", Status.DECLINED,
                 f'"{message}" is outside the back office. I handle estimating, '
                 "scheduling, and paperwork for your jobs. Want me to take something else off your plate?")
        return _result(feed, None, None, {}, None)

    title = change["title"]
    job = build_job(change["scope"])
    feed.add("office_manager", Status.DELEGATING,
             f"On it. {title}. I'll have the team price it, schedule it, and write up the change order.")
    feed.add("coordinator", Status.WORKING, "Logged the change. Pricing and scheduling it now.")

    # Estimator (live, self-correcting)
    feed.add("estimator", Status.WORKING, f"Pricing: {title}.")
    est, e_attempts = live_estimate(job)
    for v in e_attempts:
        if not v["ok"]:
            feed.add("estimator", Status.FLAGGED, f"My own double-check caught a mistake: {_plain(v)}. Fixing it.")
    feed.add("estimator", Status.REPAIRED if any(not a["ok"] for a in e_attempts) else Status.DONE,
             f"Priced and double-checked. This adds ${est.total:,.0f}.",
             document={"type": "estimate", **_doc(est), "subtotal": est.subtotal,
                       "total": est.total, "updated": True})

    # Scheduler (live, self-correcting)
    feed.add("scheduler", Status.WORKING, "Fitting it into the timeline.")
    sch, s_attempts = live_schedule(job, est, _baseline_tasks(), change_desc=title)
    for v in s_attempts:
        if not v["ok"]:
            feed.add("scheduler", Status.FLAGGED, f"My check caught an out-of-order step: {_plain(v)}. Re-sequencing.")
    baseline_days = Schedule("kitchen-1423", tasks=_baseline_tasks()).duration_days
    days_delta = max(0, sch.duration_days - baseline_days)
    cost_before = PROJECT["cost_before"]
    cost_after = round(cost_before + est.total, 2)
    days_before = PROJECT["days_before"]
    days_after = days_before + days_delta
    feed.add("scheduler", Status.REPAIRED if any(not a["ok"] for a in s_attempts) else Status.DONE,
             f"Scheduled and double-checked. Timeline goes from {days_before} to {days_after} days.",
             document={"type": "schedule", **_doc(sch), "duration_days": days_after, "updated": True})

    # Office Admin: change order + invoice + client email
    co = ChangeOrder(
        number="CO #001", job_id=job.id, description=title,
        cost_delta=est.total, schedule_delta_days=days_delta,
        project_name=PROJECT["name"], project_address=PROJECT["address"],
        client_name=PROJECT["client_name"], client_email=PROJECT["client_email"],
        window_size=title, date=CO_DATE,
        line_items=[{"desc": l.description, "amount": l.line_total} for l in est.lines]
                   + [{"desc": "Overhead & profit (20%)", "amount": round(est.total - est.subtotal, 2)}],
        cost_before=cost_before, cost_after=cost_after,
        days_before=days_before, days_after=days_after,
    )
    inv = Invoice("INV-002", job.id,
                  line_items=[{"desc": f"Change Order #001 - {title}", "amount": est.total}],
                  amount_due=est.total, note="Billed once the change order is approved.")
    rem = Reminder("Change Order #001 is ready for your signature, then it goes to the client.",
                   due="today", owner_action_required=True)
    email = EmailDraft(
        to_name=PROJECT["client_name"], to_email=PROJECT["client_email"],
        subject=f"Change Order #001 for your {PROJECT['name']} project",
        body=(f"Hi {PROJECT['client_name'].split()[0]},\n\n"
              f"We've prepared Change Order #001: {title}.\n\n"
              f"  Added cost:   ${est.total:,.0f}\n"
              f"  New project total: ${cost_after:,.0f}\n"
              f"  Added time:   {days_delta} days (now {days_after} days)\n\n"
              "Please review and approve at the link below so we can schedule the work.\n\n"
              "[ Review & approve Change Order #001 ]\n\nThanks,\nYour project team"))
    feed.add("office_admin", Status.DONE,
             f"Wrote up Change Order #001 for ${est.total:,.0f}, the invoice, and a client "
             "email. Ready for you to review and sign.",
             document={"type": "change_order", **_doc(co)})
    feed.add("office_admin", Status.DONE, "Invoice drafted.", document={"type": "invoice", **_doc(inv)})
    feed.add("office_manager", Status.DONE,
             f"Done. This adds ${est.total:,.0f} and {days_delta} days. Review and sign the "
             "change order, then I'll email it to the client for their approval.")

    assets = {
        "estimate": {"before_total": cost_before, "after_total": cost_after,
                     "added": [{"desc": l.description, "amount": l.line_total} for l in est.lines]},
        "schedule": {"before_days": days_before, "after_days": days_after,
                     "added": [{"name": t.name, "trade": t.trade.value} for t in sch.tasks
                               if t.id.startswith("co")]},
    }
    summary = {
        "headline": title, "cost_before": cost_before, "cost_after": cost_after,
        "cost_delta": est.total, "days_before": days_before, "days_after": days_after,
        "days_delta": days_delta, "needs_signature": True, "assets": assets,
    }
    documents = {"change_order": _doc(co), "invoice": _doc(inv),
                 "reminder": _doc(rem), "client_email": _doc(email)}
    return _result(feed, est, sch, documents, summary)


def _run_scripted(message: str = "") -> dict:
    """The deterministic window scenario. Returns events + documents + artifacts."""
    feed = Feed()
    job = _co_job()

    # 1. Office Manager: intake + guardrail check + delegate
    if not _in_scope(message):
        feed.add("office_manager", Status.DECLINED,
                 f'"{message}" is outside the back office. I handle estimating, '
                 f'scheduling, and paperwork for your jobs. Want me to take that off your plate?')
        return _result(feed, None, None, {}, None)
    from agents.converse import opener, closer
    title = f"Add a {WINDOW_SIZE}"
    feed.add("office_manager", Status.DELEGATING, opener(message or title, title))

    # 2. Coordinator logs the field change
    feed.add("coordinator", Status.WORKING,
             "Logged the change. The window is a known size, so we can price and "
             "schedule it now.")

    # 3. Estimator: first pass -> flag -> repair (deterministic)
    est = _estimator_step(job, feed, False)

    # 4. Scheduler: first pass -> flag -> repair (deterministic)
    sch = _scheduler_step(job, est, feed, False)

    # before -> after rollup (so the GC sees the change)
    cost_before = PROJECT["cost_before"]
    cost_after = round(cost_before + est.total, 2)
    days_before = PROJECT["days_before"]
    days_after = days_before + 2

    # 5. Office Admin: a reviewable change order + invoice + reminder
    co = ChangeOrder(
        number="CO #001", job_id=job.id,
        description=f"Add a {WINDOW_SIZE} to the kitchen: frame the rough opening, "
                    "install and flash the unit, patch drywall, and paint.",
        cost_delta=est.total, schedule_delta_days=2,
        project_name=PROJECT["name"], project_address=PROJECT["address"],
        client_name=PROJECT["client_name"], client_email=PROJECT["client_email"],
        window_size=WINDOW_SIZE, date=CO_DATE,
        line_items=[{"desc": l.description, "amount": l.line_total} for l in est.lines]
                   + [{"desc": "Overhead & profit (20%)", "amount": round(est.total - est.subtotal, 2)}],
        cost_before=cost_before, cost_after=cost_after,
        days_before=days_before, days_after=days_after,
    )
    inv = Invoice("INV-002", job.id,
                  line_items=[{"desc": f"Change Order #001 - {WINDOW_SIZE}", "amount": est.total}],
                  amount_due=est.total, note="Billed once the change order is approved.")
    rem = Reminder("Change Order #001 is ready for your signature, then it goes to the client.",
                   due="today", owner_action_required=True)
    email = EmailDraft(
        to_name=PROJECT["client_name"], to_email=PROJECT["client_email"],
        subject=f"Change Order #001 for your {PROJECT['name']} project",
        body=(f"Hi {PROJECT['client_name'].split()[0]},\n\n"
              f"We've prepared Change Order #001 to add a {WINDOW_SIZE} to your kitchen.\n\n"
              f"  Added cost:   ${est.total:,.0f}\n"
              f"  New project total: ${cost_after:,.0f}\n"
              f"  Added time:   2 days (now {days_after} days)\n\n"
              "Please review and approve the change order at the link below so we can "
              "schedule the work.\n\n"
              "[ Review & approve Change Order #001 ]\n\n"
              "Thanks,\nYour project team"))
    feed.add("office_admin", Status.DONE,
             f"Wrote up Change Order #001 for ${est.total:,.0f}, the invoice, and a "
             "client email. Ready for you to review and sign.",
             document={"type": "change_order", **_doc(co),
                       "what_changed": f"New {WINDOW_SIZE}, +${est.total:,.0f}, +2 days"})
    feed.add("office_admin", Status.DONE, "Invoice updated to match.",
             document={"type": "invoice", **_doc(inv),
                       "what_changed": "Added the change-order amount"})

    # 6. Office Manager reports back (natural, varied)
    feed.add("office_manager", Status.DONE, closer(title, est.total, 2, cost_after))

    # before -> after asset snapshots (the GC can see what actually changed)
    assets = {
        "estimate": {
            "before_total": cost_before, "after_total": cost_after,
            "added": [{"desc": l.description, "amount": l.line_total} for l in est.lines],
        },
        "schedule": {
            "before_days": days_before, "after_days": days_after,
            "added": [{"name": t.name, "trade": t.trade.value} for t in sch.tasks
                      if t.id in ("co-fr", "co-dw")],
        },
    }

    summary = {
        "headline": f"Add a {WINDOW_SIZE}",
        "cost_before": cost_before, "cost_after": cost_after, "cost_delta": est.total,
        "days_before": days_before, "days_after": days_after, "days_delta": 2,
        "needs_signature": True, "assets": assets,
    }
    documents = {"change_order": _doc(co), "invoice": _doc(inv),
                 "reminder": _doc(rem), "client_email": _doc(email)}
    return _result(feed, est, sch, documents, summary)


def _in_scope(message: str) -> bool:
    """Guardrail: the Office Manager only routes back-office construction work."""
    if not message:
        return True
    m = message.lower()
    out = ["weather", "poem", "joke", "stock", "date", "tax", "medical", "lawyer", "ignore previous"]
    return not any(w in m for w in out)


def _result(feed: Feed, est, sch, documents, summary) -> dict:
    return {
        "scenario": "change_order",
        "summary": summary,
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
