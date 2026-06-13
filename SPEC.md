# SPEC: Baxie Digital Back Office — digital employee crew for residential GCs

**Claude Build Day 2026-06-13. Solo. Submit 5:00 PM sharp. This file is the build
spec; it becomes `SPEC.md` in the repo and is the shared context for parallel
build subagents.**

## Northstar (locked)

A back office for residential GCs. **Humans run the physical world (the jobsite); a
crew of digital employees runs the business (the office).** A new GC gets the crew
on day one; a 2-person shop operates like a 10-person one. The owner signs every
check. One sentence: **"You run the jobsite. Your agents run the office."**

This is a **Baxie feature** (Baxie = the Margin OS for GCs, the main app). Today's
submission is a standalone, clean-room instance of Baxie's digital employees.
**Product is the star; the dev-orchestration is the "how I directed Claude" beat.**

## Locked decisions

- **Crew (5 roles):** Office Manager (single human contact + orchestrator),
  Estimator + Scheduler (pre-con), Project Coordinator (during construction: RFIs,
  progress vs schedule, margin-leak flags), Office Admin (paperwork, reminders,
  invoicing, change orders).
- **Hero scenario:** kitchen remodel mid-construction, homeowner adds a window.
  Two oracle-verified self-corrections (numbers below).
- **Workspace:** Baxie-branded (Foreman brand: Ink/Safety Orange/Paper, Archivo +
  JetBrains Mono) **team activity feed** — chat with the Office Manager + per-agent
  cards showing who's doing what + the documents they drop. GC-familiar,
  non-technical. NOT a metrics dashboard (avoids auto-DQ).
- **Schema:** live demo uses Edwin's **staging Supabase** (seeded, no client data)
  via a **gitignored** `.env`; public repo ships a generic synthetic mirror + seed
  so judges can run it DB-free. Schema-revealing files gitignored.
- **Branding split:** Baxie brand public; Baxie code/schema/staging connection
  gitignored.
- **Done = all:** 5 roles visible in the run; on-screen oracle-confirmed
  self-correction; public repo + 1-min video + live URL + `rubric.md`; gold-set
  scoreboard. Optimize breadth-for-clarity (the whole picture legible) over deep
  rigor on a few parts.
- **Demo reliability:** the hero run plays a deterministic **cached** run in the
  workspace so it can't stall on a live API; the URL can also run live.

## Concrete demo numbers (deterministic, so the oracles are testable)

- Base job: **Kitchen remodel**, mid-construction, baseline contract ~$42,000.
- Change: add an **egress window** in the kitchen.
- **Estimator self-correction (estimate oracle):** first pass **double-counts the
  framing labor** for the rough opening (header framed twice, ~6 hrs / ~$540
  inflated). `check_estimate` flags qty/total reconciliation → estimator repairs →
  correct change-order delta ≈ **$1,850** (framing, window unit, flashing, drywall
  patch, trim, paint, siding patch).
- **Scheduler self-correction (schedule oracle):** first pass schedules **window
  rough-framing AFTER drywall** (illegal: cannot frame a new opening once the wall
  is closed). `check_schedule` flags the trade-order violation → scheduler repairs
  (framing before rough-in/inspection/drywall) → valid schedule, **+2 days**.
- **Office Admin:** issues **Change Order #001** ($1,850, +2 days) + updated invoice
  + reminder "CO #001 needs owner signature." Owner signs.

## Deterministic oracles (the heart — both tools and graders)

`check_estimate(estimate, job) -> verdict`:
1. every scope item has ≥1 priced line; 2. no phantom line (each line maps to
scope); 3. quantities reconcile to scope (catches the double-count); 4. labor hrs +
material $ within sane per-trade bounds; 5. line totals = labor$ + material$ and
estimate total sums; 6. markup/overhead within range.

`check_schedule(schedule, estimate, job) -> verdict`:
1. dependency graph is a DAG; 2. trades in legal order per `TRADE_ORDER` (no
successor before predecessor — catches drywall-before-framing); 3. required
inspections present + correctly gated; 4. crew labor/period ≤ estimate labor; 5.
durations derive from estimate hrs / crew size; 6. change-order work integrated
without violating order.

Legal residential `TRADE_ORDER` (simplified DAG): demo/site → rough framing → MEP
rough-in → rough inspection → insulation → drywall → finish carpentry/trim → paint
→ final inspection.

Each verdict returns: `{ok: bool, violations: [{rule, detail}], ...}`.

## Module contracts (so subagents build in parallel against fixed interfaces)

- `schemas.py` — `Job, ScopeItem, EstimateLine, Estimate, ScheduleTask, Schedule,
  ChangeOrder, Invoice, Reminder, Trade(enum), TRADE_ORDER, AgentEvent, Document`;
  `JobSource` protocol (synthetic impl public, staging impl gitignored).
- `estimate_oracle.py` / `schedule_oracle.py` — the two functions above.
- `agents/base.py` — Anthropic SDK Opus 4.8 tool-use loop; `run_agent(role, prompt,
  tools) -> (result, events)`; emits `AgentEvent{agent, role, status:
  working|done|flagged|repaired, message, document?}` for the feed.
- `agents/{office_manager,estimator,scheduler,coordinator,office_admin,reviewer}.py`
  — role prompts + tool wiring. Tools: `check_estimate`, `check_schedule`.
- `orchestrator.py` — runs the change-order scenario; Office Manager delegates;
  loop-until oracle passes AND reviewer agrees; yields the event stream + final docs.
- `fixtures/` — `jobs.json` (kitchen remodel + baseline estimate/schedule),
  `change_order_event.json`, `goldset.json` (~10-12 labeled good/broken cases,
  labels from the oracles).
- `app.py` — FastAPI: serves the Baxie-branded workspace; streams orchestrator
  events (SSE or poll); `POST /run`, `GET /health`. `static/` = workspace HTML/CSS/JS.
- `run.py` — CLI runs scenario, prints feed + scoreboard, exits 0.
- `grader.py` — gold-set exact-match scoring (estimate + schedule correctness),
  target ≥0.85.
- `README.md` (northstar + crew org chart + dev-orchestration diagram + how-to-run),
  `rubric.md`, `requirements.txt`, `.env.example`, `.gitignore` (`.env`, `private/`,
  `baxie_*`).
- **Human-readable notes (plain English, no jargon):**
  - `docs/CREW.md` — each digital employee, what they CAN and CANNOT do, and how
    work flows between them (workers + flow + guardrails, for a non-technical GC).
  - `docs/HOW-IT-WAS-BUILT.md` — the dev story in non-technical terms: the
    orchestrator → manager → workers + QA crew explained like a team, with the
    diagram. Supports the "how I directed Claude" submission beat.

## Agent harness & guardrails

- **Harness:** Anthropic Python SDK, Opus 4.8 (`claude-opus-4-8`), **raw Messages
  API tool-use loop** in `agents/base.py` (not the Agent SDK — we want control +
  transparent step streaming for the activity feed). Verify exact model id/params
  against the claude-api reference when writing `base.py`.
- **Truly agentic where it counts:** workers do real multi-step tool use and
  self-correct (read the oracle violation → decide a fix → re-submit). The Office
  Manager does real routing (reads the request → decides which workers to involve).
  The scenario scaffolding is deterministic on purpose (reproducible, won't stall
  live). Pattern = agentic workers inside deterministic orchestration. Don't oversell
  as fully emergent.
- **Guardrails (4 layers):** 1. scoped system prompts (each worker refuses
  out-of-scope asks, defers to the Manager); 2. Office Manager is the sole
  human-facing gatekeeper (classifies, declines off-topic/unsafe/injection, routes
  only in-scope work; workers not directly addressable); 3. tool = capability =
  scope (Estimator has no scheduling tools, etc.); 4. data scoped to the current
  job (no cross-job/client leakage) + the deterministic oracle is a hard gate (a
  hallucinated artifact can't ship). Optional demo beat: Manager politely declines
  an out-of-scope ask.

## Dev-time orchestration (hybrid; illustrated in the submission)

- **Level 0 Orchestrator = me (main loop):** write `SPEC.md` + the shared contracts
  (`schemas.py`, oracle signatures, `agents/base.py`, API shape) FIRST, sequentially.
  Then integrate, deploy, record.
- **Level 1 Build Manager = one ultracode Workflow:** Phase A fans out the
  independent files in parallel (oracles, fixtures+schema mirror, each agent module,
  UI shell, rubric), each a fresh-context subagent given the contract, each paired
  with a **reviewer subagent** that runs the oracle tests (worker+QA, mirroring the
  product). Phase B integration pipeline (`orchestrator.py` + `app.py`). Phase C
  verify (oracle unit tests + smoke run).
- Dev crew shape == product crew shape (manager → workers → QA). That symmetry is
  the "how I directed Claude" beat; render it as a diagram for README + video.

## Build order
1. Scaffold repo + `.gitignore` + `requirements.txt`. 2. Contracts (schemas,
oracle sigs, `agents/base.py`, API shape) — me, sequential. 3. Launch ultracode
Build Manager (parallel leaves + reviewers). 4. Integrate orchestrator + app. 5.
Wire Baxie-branded workspace. 6. Gold-set grader + scoreboard. 7. Deploy live URL.
8. README + dev diagram + 1-min video. **Submit 5:00.**

## Dependencies
`anthropic` (Opus 4.8, `claude-opus-4-8`), `fastapi`, `uvicorn`. Synthetic/offline
for judges; staging Supabase optional via env.
- **Org credits (must verify):** agents use the build-day **organization** API key
  so usage draws from the **$500 org pool**, not a personal account. Set
  `ANTHROPIC_API_KEY` (the event-provided org key) in the gitignored `.env`. Before
  the full run, confirm the first call decrements the org credits in the Anthropic
  Console.

## Verification (end-to-end / definition of done)
1. `python run.py --scenario change_order` exits 0; Office Manager orchestrates all
   5 roles; shows the estimate self-correction (oracle-confirmed) + schedule
   self-correction; prints Change Order #001 + invoice.
2. Live URL serves the Baxie-branded workspace; `POST /run` returns the same trace +
   docs JSON; the cached hero run replays without a live-API dependency.
3. Gold-set scoreboard ≥0.85.
4. Public repo, synthetic-runnable, no Baxie code/schema, no metrics dashboard,
   rerunnable. 1-min video + dev-orchestration diagram included.

## Risks
- **Scope**: 5 roles + branded UI + scoreboard + deploy in the time left is a lot;
  build the clear end-to-end picture first, rigor (scoreboard/panels) is the flex.
- **Live API wobble**: cached hero run + deterministic oracles reproduce offline.
- **Time to 5:00 is the hard gate.**
