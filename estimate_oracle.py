"""Deterministic estimate oracle.

check_estimate() is both a TOOL the Estimator agent calls and the GRADER the
gold set is scored against. It encodes construction-estimating logic, not model
opinion, so "done" is machine-verifiable and the Estimator cannot ship a wrong
estimate past it.

Returns a verdict dict:
  {
    "ok": bool,
    "violations": [ {"rule": str, "detail": str}, ... ],
    "totals": {"subtotal": float, "total": float, "labor_hours": float},
    "binding": str | None,   # the first/most important violation rule, for the UI
  }
"""

from __future__ import annotations

from schemas import (
    Estimate, Job, LABOR_RATE_MIN, LABOR_RATE_MAX, MARKUP_MIN, MARKUP_MAX,
)

QTY_TOL = 0.01


def check_estimate(estimate: Estimate, job: Job) -> dict:
    violations: list[dict] = []
    scope_by_id = {s.id: s for s in job.scope}

    # Rule 1: coverage — every scope item has at least one priced line.
    priced_scope_ids = {l.scope_id for l in estimate.lines}
    for s in job.scope:
        if s.id not in priced_scope_ids:
            violations.append({
                "rule": "coverage",
                "detail": f"scope item '{s.id}' ({s.description}) is not priced",
            })

    # Rule 2: no phantom — every line maps to a real scope item.
    for l in estimate.lines:
        if l.scope_id not in scope_by_id:
            violations.append({
                "rule": "phantom_line",
                "detail": f"line '{l.description}' references unknown scope '{l.scope_id}'",
            })

    # Rule 3: quantity reconciliation — summed line qty per scope == scope qty.
    # This catches the demo's double-counted framing (two lines summing to 2x).
    qty_by_scope: dict[str, float] = {}
    for l in estimate.lines:
        qty_by_scope[l.scope_id] = qty_by_scope.get(l.scope_id, 0.0) + l.quantity
    for sid, est_qty in qty_by_scope.items():
        s = scope_by_id.get(sid)
        if s is None:
            continue
        if abs(est_qty - s.quantity) > QTY_TOL:
            violations.append({
                "rule": "quantity_mismatch",
                "detail": (
                    f"scope '{sid}' ({s.description}): estimated qty {est_qty} "
                    f"!= scope qty {s.quantity} {s.unit} "
                    f"(double-count or omission)"
                ),
            })

    # Rule 4: sanity — labor rate in band, no negatives.
    for l in estimate.lines:
        if not (LABOR_RATE_MIN <= l.labor_rate <= LABOR_RATE_MAX):
            violations.append({
                "rule": "rate_out_of_band",
                "detail": (
                    f"line '{l.description}' labor rate ${l.labor_rate}/hr outside "
                    f"${LABOR_RATE_MIN}-${LABOR_RATE_MAX}"
                ),
            })
        if l.labor_hours < 0 or l.material_cost < 0:
            violations.append({
                "rule": "negative_value",
                "detail": f"line '{l.description}' has a negative hours/material value",
            })

    # Rule 5: markup in band.
    if not (MARKUP_MIN <= estimate.markup <= MARKUP_MAX):
        violations.append({
            "rule": "markup_out_of_band",
            "detail": (
                f"markup {estimate.markup:.0%} outside "
                f"{MARKUP_MIN:.0%}-{MARKUP_MAX:.0%}"
            ),
        })

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "totals": {
            "subtotal": estimate.subtotal,
            "total": estimate.total,
            "labor_hours": estimate.total_labor_hours,
        },
        "binding": violations[0]["rule"] if violations else None,
    }
