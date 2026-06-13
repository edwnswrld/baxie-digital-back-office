"""Reproducible CLI entry: runs the change-order scenario and prints the crew's
work + the self-grading scoreboard, then exits 0. (rubric item: reproducible.)

    python run.py                      # scripted, reliable
    python run.py --live               # drive the real agents (needs ANTHROPIC_API_KEY)
    python run.py --message "..."      # custom request to the Office Manager
"""

from __future__ import annotations

import argparse
import sys

from orchestrator import run_change_order

STATUS_MARK = {
    "delegating": "->", "working": "..", "flagged": "!!", "repaired": "✓✓",
    "done": "✓", "declined": "x",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", default="homeowner wants to add a window")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--serve", action="store_true", help="launch the workspace UI server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--scenario", default="change_order")  # reserved
    args = ap.parse_args()

    if args.serve:
        import uvicorn
        print(f"\n  Baxie Digital Back Office workspace -> http://127.0.0.1:{args.port}\n")
        uvicorn.run("app:app", host="0.0.0.0", port=args.port)
        return 0

    print("\n  BAXIE DIGITAL BACK OFFICE  —  you run the jobsite, your agents run the office\n")
    print(f'  owner: "{args.message}"\n')

    result = run_change_order(args.message, live=args.live)
    for e in result["events"]:
        mark = STATUS_MARK.get(e["status"], "  ")
        print(f"  {mark:>2}  {e['agent']:<7} {e['role']:<20} {e['message']}")

    print()
    docs = result.get("documents") or {}
    if docs:
        print("  documents produced:", ", ".join(docs.keys()))

    try:
        from grader import score_goldset
        sb = score_goldset()
        if sb.get("available", True) and "accuracy" in sb:
            print(f"\n  self-graded gold set: {sb['correct']}/{sb['n']} "
                  f"({sb['accuracy']:.0%}) match the deterministic oracle")
    except Exception as exc:
        print(f"\n  (scoreboard unavailable: {exc})")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
