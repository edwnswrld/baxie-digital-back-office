# rubric.md: machine-verifiable definition of "done"

This is the Orchestration score. Every criterion below is checkable by a script or
by watching the run, not by opinion. The two deterministic oracles
(`estimate_oracle.check_estimate`, `schedule_oracle.check_schedule`) are the graders.
A verdict is `{ok, violations:[{rule, detail}], binding, ...}` where `binding` is the
first (most important) violated rule, or `None` when `ok` is `True`.

## Criteria

### (1) The crew produces oracle-clean artifacts for the change-order scenario

Given the egress-window change-order scenario, the crew's final estimate and final
schedule both pass their oracle.

- `check_estimate(final_estimate, job)` returns `ok == True`.
- `check_schedule(final_schedule, final_estimate, job)` returns `ok == True`.

Pass condition: both `ok` flags are `True` on the final (post-repair) artifacts.

### (2) The run visibly shows an agent catching its own mistake

At least one agent emits an oracle-flagged first pass and then a repaired pass, on
screen and in the event stream.

- An `AgentEvent` with `status == FLAGGED` appears, carrying the oracle's `binding`
  rule (the estimate run flags `quantity_mismatch`; the schedule run flags
  `trade_inversion`).
- A later `AgentEvent` with `status == REPAIRED` appears for the same agent, and the
  re-checked artifact returns `ok == True`.

Pass condition: at least one FLAGGED -> REPAIRED pair exists where the post-repair
oracle verdict is `ok == True`. The hero run shows two (Estimator and Scheduler).

### (3) Gold-set classification accuracy >= 0.85

On the ~12-case gold set (`fixtures/goldset.json`), the self-grader's predicted label
matches the oracle's label on at least 85% of cases. A case label is a pair:

- ok-state: predicted `ok` matches the oracle `ok`.
- binding rule: when `ok == False`, predicted `binding` matches the oracle `binding`.

A case counts as correct only when BOTH the ok-state AND the binding rule match the
oracle label. Mixed estimate and schedule cases.

Pass condition: `correct_cases / total_cases >= 0.85`.

### (4) Office Admin produces the owner-facing paperwork

The Office Admin closes the loop with three artifacts for the change-order scenario.

- A `ChangeOrder` (number set, `cost_delta` and `schedule_delta_days` populated,
  `status == "pending_signature"`).
- An `Invoice` (number set, `line_items` populated, `amount_due` populated).
- A `Reminder` with `owner_action_required == True` naming the owner signature on the
  change order.

Pass condition: all three objects are produced and attached to the event stream as
documents.

### (5) Reproducible in one command, and the live URL matches

- A single command runs the scenario end to end and exits `0`:
  `python run.py --scenario change_order`.
- The live FastAPI URL serves the same scenario; `POST /run` returns the same final
  trace and documents as the CLI (the hero run replays from a deterministic cache so
  it cannot stall on a live API).

Pass condition: the command exits `0` and the live URL returns the same final
estimate total, schedule duration, and change-order delta.

## Scoreboard (what the grader prints)

```
[1] estimate ok ............. PASS / FAIL
[1] schedule ok ............. PASS / FAIL
[2] self-correction shown ... PASS / FAIL   (FLAGGED -> REPAIRED pairs: N)
[3] gold-set accuracy ....... 0.XX  (>= 0.85 PASS / FAIL)
[4] CO + invoice + reminder . PASS / FAIL
[5] one-command exit 0 ...... PASS / FAIL
```
