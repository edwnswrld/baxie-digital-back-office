"""Shared data contracts for the Baxie Digital Back Office.

This file is the single source of truth that every agent, oracle, and the
orchestrator builds against. Plain dataclasses + enums, no external deps, so the
oracles stay deterministic and the whole thing runs offline for judges.

Domain: a residential GC job. The crew (Office Manager, Estimator, Scheduler,
Project Coordinator, Office Admin) produces an Estimate, a Schedule, and office
documents (ChangeOrder, Invoice, Reminder). Two deterministic oracles grade the
Estimate and the Schedule.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Protocol


# --------------------------------------------------------------------------- #
# Trades and the legal residential build order (the schedule oracle's backbone)
# --------------------------------------------------------------------------- #

class Trade(str, Enum):
    SITE = "site_prep"
    FRAMING = "rough_framing"
    MEP_ROUGH = "mep_rough_in"          # mechanical / electrical / plumbing rough
    ROUGH_INSPECTION = "rough_inspection"
    INSULATION = "insulation"
    DRYWALL = "drywall"
    FINISH_CARPENTRY = "finish_carpentry"
    PAINT = "paint"
    FINAL_INSPECTION = "final_inspection"


# Canonical legal order. A task on a later trade may not start before an earlier
# trade's work it depends on. Index = position in the sequence.
TRADE_ORDER: list[Trade] = [
    Trade.SITE,
    Trade.FRAMING,
    Trade.MEP_ROUGH,
    Trade.ROUGH_INSPECTION,
    Trade.INSULATION,
    Trade.DRYWALL,
    Trade.FINISH_CARPENTRY,
    Trade.PAINT,
    Trade.FINAL_INSPECTION,
]


def trade_rank(trade: Trade) -> int:
    return TRADE_ORDER.index(trade)


# Inspections that must be present and correctly gated.
REQUIRED_INSPECTIONS: list[Trade] = [Trade.ROUGH_INSPECTION, Trade.FINAL_INSPECTION]


# Sane per-trade bounds for the estimate oracle (labor $/hr and material sanity).
# Used to flag absurd lines, not to price. (national-ish residential ranges)
LABOR_RATE_MIN = 45.0     # $/hr fully burdened low end
LABOR_RATE_MAX = 150.0    # $/hr high end
MARKUP_MIN = 0.10         # 10%
MARKUP_MAX = 0.35         # 35%


# --------------------------------------------------------------------------- #
# Estimate
# --------------------------------------------------------------------------- #

@dataclass
class ScopeItem:
    """One unit of work the job requires. The estimate must price every one."""
    id: str
    description: str
    trade: Trade
    quantity: float
    unit: str                      # e.g. "ea", "sf", "lf"


@dataclass
class EstimateLine:
    """A priced line. Must trace back to exactly one ScopeItem via scope_id."""
    scope_id: str
    description: str
    trade: Trade
    quantity: float
    unit: str
    labor_hours: float
    labor_rate: float              # $/hr
    material_cost: float           # total material $ for this line

    @property
    def labor_cost(self) -> float:
        return round(self.labor_hours * self.labor_rate, 2)

    @property
    def line_total(self) -> float:
        return round(self.labor_cost + self.material_cost, 2)


@dataclass
class Estimate:
    job_id: str
    lines: list[EstimateLine] = field(default_factory=list)
    markup: float = 0.20           # fraction, e.g. 0.20 = 20%
    label: str = ""                # e.g. "baseline" or "CO #001 delta"

    @property
    def subtotal(self) -> float:
        return round(sum(l.line_total for l in self.lines), 2)

    @property
    def total(self) -> float:
        return round(self.subtotal * (1 + self.markup), 2)

    @property
    def total_labor_hours(self) -> float:
        return round(sum(l.labor_hours for l in self.lines), 2)


# --------------------------------------------------------------------------- #
# Schedule
# --------------------------------------------------------------------------- #

@dataclass
class ScheduleTask:
    """A scheduled chunk of work. depends_on lists task ids that must finish first."""
    id: str
    name: str
    trade: Trade
    start_day: int                 # day index from job start
    duration_days: int
    crew_size: int = 1
    depends_on: list[str] = field(default_factory=list)

    @property
    def end_day(self) -> int:
        return self.start_day + self.duration_days


@dataclass
class Schedule:
    job_id: str
    tasks: list[ScheduleTask] = field(default_factory=list)
    label: str = ""

    @property
    def duration_days(self) -> int:
        return max((t.end_day for t in self.tasks), default=0)


# --------------------------------------------------------------------------- #
# Office documents (Office Admin produces these)
# --------------------------------------------------------------------------- #

@dataclass
class ChangeOrder:
    number: str                    # "CO #001"
    job_id: str
    description: str
    cost_delta: float
    schedule_delta_days: int
    status: str = "draft"          # draft | contractor_signed | client_approved
    # reviewable-document fields (so the GC and the client can both approve)
    project_name: str = ""
    project_address: str = ""
    client_name: str = ""
    client_email: str = ""
    window_size: str = ""
    line_items: list = field(default_factory=list)   # [{desc, amount}]
    date: str = ""
    cost_before: float = 0.0
    cost_after: float = 0.0
    days_before: int = 0
    days_after: int = 0
    contractor_signature: str = ""
    client_signature: str = ""


@dataclass
class Invoice:
    number: str                    # "INV-001"
    job_id: str
    line_items: list[dict] = field(default_factory=list)   # {desc, amount}
    amount_due: float = 0.0
    note: str = ""


@dataclass
class Reminder:
    text: str
    due: str                       # human date string, e.g. "by Fri"
    owner_action_required: bool = True


# --------------------------------------------------------------------------- #
# The job + a change-order event
# --------------------------------------------------------------------------- #

@dataclass
class ChangeEvent:
    """A field change that flows through the back office."""
    id: str
    description: str               # "homeowner wants to add an egress window"
    raised_during: Trade           # phase of construction when it came in


@dataclass
class Job:
    id: str
    name: str                      # "Kitchen Remodel - 1423 Oak St (synthetic)"
    client_label: str              # synthetic label, never a real client name
    baseline_contract: float
    scope: list[ScopeItem] = field(default_factory=list)
    baseline_estimate: Optional[Estimate] = None
    baseline_schedule: Optional[Schedule] = None


# --------------------------------------------------------------------------- #
# Activity-feed event (what the workspace renders; agents emit these)
# --------------------------------------------------------------------------- #

class Status(str, Enum):
    WORKING = "working"
    DONE = "done"
    FLAGGED = "flagged"            # QA / oracle caught a problem
    REPAIRED = "repaired"          # agent fixed it and re-verified
    DELEGATING = "delegating"      # Office Manager routing work
    DECLINED = "declined"          # guardrail: out-of-scope ask refused


@dataclass
class AgentEvent:
    """One line in the team activity feed."""
    agent: str                     # display name, e.g. "Maya"
    role: str                      # e.g. "Estimator"
    status: Status
    message: str                   # plain-English what's happening
    document: Optional[dict] = None    # a produced doc (serialized) if any
    seq: int = 0                   # ordering

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


# --------------------------------------------------------------------------- #
# JobSource: the seam to data. Public synthetic impl ships; a Baxie staging impl
# lives in private/ (gitignored) and is selected via env. Code references the
# shape, never Baxie's schema.
# --------------------------------------------------------------------------- #

class JobSource(Protocol):
    def get_job(self, job_id: str) -> Job: ...
    def get_change_event(self, job_id: str) -> ChangeEvent: ...
