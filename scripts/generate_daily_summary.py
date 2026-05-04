#!/usr/bin/env python3
"""Generate AI daily summaries of resolved bets via the Anthropic API.

Runs after resolve_bets.py inside the resolve-bets cron. For each date
in data.json.bets[] that has resolved bets but does not yet have a
summary in daily_summaries.json, sends the day's bet outcomes to Claude
and stashes the response. Idempotent: dates already summarized are
skipped (saves API spend).

Graceful skip when ANTHROPIC_API_KEY is not set in env, so the cron
keeps running while Max is still wiring the secret.

Storage: daily_summaries.json at repo root, dict keyed on YYYY-MM-DD
date string. Worker reads it via env.ASSETS to enrich /api/activity.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data.json"
SUMMARIES = REPO / "daily_summaries.json"
PICK_HISTORY = REPO / "pick_history.json"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5"  # cheap and fast; ~1-2 paragraph summaries
MAX_TOKENS = 400


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def get_pick_history_index(history: list) -> dict:
    """Index pick_history by (date, pick, event) -> entry for metadata lookup."""
    idx = {}
    for h in history:
        date = h.get("scan_date", "")
        pick = h.get("pick", "")
        event = h.get("event", "")
        if not date or not pick or not event:
            continue
        key = (date, pick, event)
        if key not in idx:
            idx[key] = h
    return idx


def format_bet_for_prompt(bet: dict, ph: dict | None) -> str:
    """One-line description of a bet for the LLM prompt."""
    sport = bet.get("sport", "?")
    pick = bet.get("pick", "?")
    event = bet.get("event", "?")
    odds = bet.get("odds", "?")
    wager = bet.get("wager", 0)
    outcome = bet.get("outcome", "?")
    pnl = bet.get("pnl", 0)
    final = bet.get("final_score", "")

    extra = ""
    if ph:
        edge = ph.get("edge", "")
        tier = ph.get("tier", "")
        confidence = ph.get("confidence", "")
        model = ph.get("model", "")
        if edge or tier:
            parts = []
            if edge != "":
                parts.append(f"edge {edge}%")
            if tier:
                parts.append(f"{tier} tier")
            if confidence:
                parts.append(f"{confidence} conf")
            if model:
                parts.append(f"model {model}")
            extra = f" ({', '.join(parts)})"

    return (
        f"- {sport} {pick} @ {odds}, ${wager:.2f} -> {outcome.upper()} "
        f"({pnl:+.2f}){', ' + final if final else ''}{extra}"
    )


def build_prompt(date: str, bets: list, history_idx: dict) -> str:
    wins = sum(1 for b in bets if b.get("outcome") == "win")
    losses = sum(1 for b in bets if b.get("outcome") == "loss")
    pushes = sum(1 for b in bets if b.get("outcome") == "push")
    net = sum(b.get("pnl", 0) for b in bets)
    total_wagered = sum(b.get("wager", 0) for b in bets)

    lines = []
    for b in bets:
        ph = history_idx.get(
            (b.get("date", ""), b.get("pick", ""), b.get("event", ""))
        )
        lines.append(format_bet_for_prompt(b, ph))

    return f"""Date: {date}
Record: {wins}W-{losses}L{f"-{pushes}P" if pushes else ""}
Net P/L: ${net:+.2f} on ${total_wagered:.2f} risked

Bets:
{chr(10).join(lines)}

Write a 2-3 sentence commentary on this day's betting results. Be specific:
call out which bets actually moved the needle (the wins / losses with the
biggest pnl), and notice patterns where the model's confidence either lined
up with or fought the outcomes. Plain English, no hedging, no greeting.
Skip the "today was..." framing; jump straight into what happened."""


def call_anthropic(prompt: str, api_key: str) -> str | None:
    body = json.dumps({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_API,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "DKEdgeFinder/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  Anthropic HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Anthropic call failed: {e}", file=sys.stderr)
        return None

    blocks = payload.get("content", [])
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text.strip() or None


def main(force: bool = False) -> int:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("ANTHROPIC_API_KEY not set; skipping daily summary generation.")
        return 0

    if not DATA.exists():
        print("data.json missing; skipping.", file=sys.stderr)
        return 1

    data = load_json(DATA, {})
    summaries = load_json(SUMMARIES, {})
    history = load_json(PICK_HISTORY, [])
    history_idx = get_pick_history_index(history)

    bets = [
        b for b in data.get("bets", [])
        if b.get("outcome") in ("win", "loss", "push") and b.get("date")
    ]
    by_date: dict[str, list[dict]] = {}
    for b in bets:
        by_date.setdefault(b["date"], []).append(b)

    target_dates = sorted(by_date.keys(), reverse=True)
    generated = 0
    for date in target_dates:
        if not force and date in summaries:
            continue
        prompt = build_prompt(date, by_date[date], history_idx)
        print(f"Generating summary for {date} ({len(by_date[date])} bets)...")
        text = call_anthropic(prompt, api_key)
        if not text:
            print(f"  failed; skipping {date}.")
            continue
        summaries[date] = {
            "summary": text,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": MODEL,
        }
        generated += 1

    if generated == 0:
        print("No new summaries to generate.")
        return 0

    SUMMARIES.write_text(json.dumps(summaries, indent=2) + "\n")
    print(f"Wrote {generated} new summary(ies) to daily_summaries.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
