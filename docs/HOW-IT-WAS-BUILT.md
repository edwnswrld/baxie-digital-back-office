# How This App Was Built

The interesting part of this project isn't just *what* it does. It's that we built
it the same way it works.

The product is a crew of digital employees that gets work done by handing tasks to
the right specialist and checking each one against hard rules. The *team that built
the product* had exactly the same shape: a lead who set the rules, a manager who ran
a crew of workers in parallel, and a quality reviewer checking every piece against the
same hard rules the product uses. The dev crew is a mirror of the product crew.

Here's the story, told like a team, with no code.

---

## The people on the build

**The Orchestrator (the human lead).** This is the person directing the whole thing.
Before any worker touched anything, the Orchestrator did the most important job:
wrote down the shared rules. What a job looks like, what an estimate is, what a
schedule is, what "correct" means. Everyone on the crew built against that one shared
rule book, so nobody's work could drift out of agreement with anyone else's. The
Orchestrator set the goal, locked the contract, and then got out of the way.

**The Build Manager.** The Orchestrator didn't hand tasks to workers one at a time and
wait. That's slow. Instead the Build Manager took the plan and ran a crew of worker
agents *in parallel*, each one scoped to a clear, separate piece. While one worker
built the part that prices the work, another built the part that sequences it, another
built the workspace you see on screen. The Build Manager's whole job was keeping those
hand-offs clean and making sure every worker built against the same shared rules.

**The Workers.** Each worker was a focused agent with one assignment and a tight
scope. A worker didn't get to wander into someone else's piece. It got told exactly
what to build, built it, and handed it back. Same discipline as the product: stay in
your lane, hand off the rest.

**The QA Reviewers.** This is the part that makes it trustworthy. Every worker had a
quality reviewer paired with it. The reviewer didn't just eyeball the work. It ran the
*same deterministic checks* the product itself runs: the estimate grader and the
schedule grader. If a worker's piece didn't pass those hard rules, it went back for
repair before it counted as done. No silent mistakes, on the build side or the product
side.

---

## The shape of the build crew

```
                 ┌─────────────────────────┐
                 │      ORCHESTRATOR        │
                 │      (human lead)        │
                 │  writes the shared rules │
                 │  sets the goal, locks    │
                 │  the contract            │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │      BUILD MANAGER       │
                 │  runs the crew in        │
                 │  parallel, keeps the     │
                 │  hand-offs clean         │
                 └────────────┬────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │   WORKER    │     │   WORKER    │     │   WORKER    │
   │  (one piece │     │  (one piece │     │  (one piece │
   │   of the    │     │   of the    │     │   of the    │
   │   build)    │     │   build)    │     │   build)    │
   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ QA REVIEWER │     │ QA REVIEWER │     │ QA REVIEWER │
   │  runs the   │     │  runs the   │     │  runs the   │
   │ same hard   │     │ same hard   │     │ same hard   │
   │ checks the  │     │ checks the  │     │ checks the  │
   │ product uses│     │ product uses│     │ product uses│
   └─────────────┘     └─────────────┘     └─────────────┘
```

---

## Why this matters

Look at that diagram, then look at how the product works:

- The **Orchestrator** writing one shared rule book is the same idea as the product's
  shared contract that every digital employee builds against.
- The **Build Manager** running workers in parallel is the same idea as the Office
  Manager routing work to the right specialist instead of doing it all alone.
- The **QA Reviewers** running deterministic checks is the same idea as the Estimator
  and Scheduler grading their own work against hard rules and repairing mistakes
  before anything reaches a human.

So the way this app was directed and assembled is a working demonstration of the same
pattern it sells: a human sets the rules and the goal, a manager fans the work out to
focused specialists, and every piece gets checked against hard truth before it ships.

You run the jobsite. Your agents run the office. And the office that built the office
worked exactly the same way.
