"""Fast, natural Office Manager voice.

The conversational lines (acknowledge a request, report back) come from Haiku 4.5
so they sound like a real person and vary, without the multi-second Opus latency.
Falls back to varied scripted lines when there's no key, so the demo is instant and
never stalls on the public URL.
"""

from __future__ import annotations

from agents.base import have_key

HAIKU = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are Avery, the Office Manager for a residential general contractor's back "
    "office. Write ONE short line to the owner: warm, sharp, plain-spoken, like a "
    "great assistant texting them. Max two sentences. No corporate fluff, no emoji, "
    "no lists. Never use em dashes; use commas or periods. Vary your phrasing each time."
)


def _haiku(prompt: str) -> str | None:
    if not have_key():
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=HAIKU, max_tokens=120, system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ").replace("–", ", ")
        return text or None
    except Exception:
        return None


def opener(request: str, title: str) -> str:
    line = _haiku(
        f"The owner just asked: \"{request}\". You're kicking it off and looping in "
        f"the crew to price and schedule it ({title}). Tell them you're on it.")
    if line:
        return line
    # varied scripted fallback (deterministic, no randomness)
    opts = [
        f"On it. {title} coming up. I'll get the crew pricing and scheduling it now.",
        f"Got it. Putting the team on {title.lower()} right now, pricing and timeline.",
        f"Say no more. {title} is in the works, I'll have numbers and a change order shortly.",
    ]
    return opts[len(request) % len(opts)]


def closer(title: str, cost: float, days: int, total_after: float) -> str:
    line = _haiku(
        f"The crew finished. {title} adds ${cost:,.0f} and {days} days "
        f"(new project total ${total_after:,.0f}). The change order is ready for the "
        f"owner to review and sign, then it goes to the client. Report back warmly.")
    if line:
        return line
    opts = [
        f"All set. {title} adds ${cost:,.0f} and {days} days. Review and sign the "
        f"change order and I'll send it to your client.",
        f"Done. That's ${cost:,.0f} and {days} more days. Give the change order a look, "
        f"sign it, and it's off to the client for approval.",
    ]
    return opts[int(cost) % len(opts)]
