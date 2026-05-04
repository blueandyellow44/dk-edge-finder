#!/usr/bin/env python3
"""Sync Cloudflare KV placements -> data.json.bets[] as pending bets.

Runs at the top of the resolve-bets cron, BEFORE resolve_bets.py. For
every placement (action='placed') in KV state records for the user that
is not yet in data.json.bets[], appends a new entry with outcome=pending.
The subsequent resolve_bets.py step fetches scores and grades it.

This closes the structural gap that caused session 14's bankroll
staleness: the SPA writes placements to KV, the cron only reads
data.json.bets[]; without this bridge KV placements never flowed back
into the canonical bet log. After this lands the manual one-shot
backfill (scripts/backfill_kv_placements.py) becomes obsolete.

Requires CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID env vars (added
as repo secrets in GitHub Actions). Skips silently when either is
missing so the cron keeps running while Max wires the secrets.

Idempotent on (date, pick) so re-running is safe.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data.json"
HISTORY = REPO / "pick_history.json"

# EDGE_STATE namespace from wrangler.jsonc; load-bearing if changed.
KV_NAMESPACE = "7dca36afc97d4d86bebed2e2948d6e83"

# Currently single-user. To extend to additional emails, list them and
# fan out the prefix-list call.
USER_EMAIL = "max.sheahan@gmail.com"

# Pre-session-13 placements lack a wager field (the schema was added
# 2026-05-04). Use Max's stated flat stake for those legacy records.
# Post-session-13 placements carry placement.wager so this fallback
# only matters for records placed before that fix shipped.
DEFAULT_WAGER = 14.0


def kv_request(path: str, account_id: str, token: str) -> Any:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{KV_NAMESPACE}{path}"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "DKEdgeFinder/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  KV API HTTP {e.code} on {path}: {e.read().decode()[:200]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  KV API error on {path}: {e}", file=sys.stderr)
        return None


def list_state_keys(account_id: str, token: str) -> list[str]:
    prefix = urllib.parse.quote(f"state:{USER_EMAIL}:", safe="")
    resp = kv_request(
        f"/keys?prefix={prefix}",
        account_id,
        token,
    )
    if not resp or not resp.get("success"):
        return []
    return [k["name"] for k in resp.get("result", [])]


def get_state_value(key: str, account_id: str, token: str) -> dict | None:
    """Read a state record's JSON value. Cloudflare's /values endpoint
    returns the raw value body (not wrapped in {success, result}); needs
    direct urlopen + parse rather than the kv_request helper."""
    encoded_key = urllib.parse.quote(key, safe="")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{KV_NAMESPACE}/values/{encoded_key}"
    )
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "DKEdgeFinder/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  KV value get HTTP {e.code} on {key}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  KV value get error on {key}: {e}", file=sys.stderr)
        return None


def odds_to_int(s: Any) -> int:
    if isinstance(s, int):
        return s
    try:
        return int(str(s).lstrip("+"))
    except (ValueError, TypeError):
        return -110


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not token or not account_id:
        print(
            "CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID not set; "
            "skipping KV sync.",
        )
        return 0

    if not DATA.exists():
        print("data.json missing; skipping.", file=sys.stderr)
        return 1

    data = json.loads(DATA.read_text())
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else []

    # Index pick_history by (scan_date, pick, event) -> entry. First
    # write wins; same pattern as the worker's enrichment join.
    history_idx: dict[tuple[str, str, str], dict] = {}
    for h in history:
        d = h.get("scan_date", "")
        p = h.get("pick", "").strip() if isinstance(h.get("pick"), str) else ""
        e = h.get("event", "").strip() if isinstance(h.get("event"), str) else ""
        if d and p and e:
            history_idx.setdefault((d, p, e), h)

    bets = data.setdefault("bets", [])
    existing = {(b.get("date", ""), b.get("pick", "")) for b in bets}

    keys = list_state_keys(account_id, token)
    if not keys:
        print("No KV state records found for", USER_EMAIL)
        return 0

    print(f"Found {len(keys)} KV state record(s) for {USER_EMAIL}.")
    added = 0
    skipped_no_history = 0

    for key in keys:
        # Key shape: state:email:YYYY-MM-DD
        scan_date = key.rsplit(":", 1)[-1]
        state = get_state_value(key, account_id, token)
        if not state or not isinstance(state, dict):
            continue
        for placement in state.get("placements", []) or []:
            if placement.get("action") != "placed":
                continue
            pkey = placement.get("key", "")
            if not isinstance(pkey, str) or "|" not in pkey:
                continue
            pick, event = pkey.split("|", 1)
            pick = pick.strip()
            event = event.strip()
            if (scan_date, pick) in existing:
                continue

            ph = history_idx.get((scan_date, pick, event))
            if not ph:
                print(
                    f"  WARN {scan_date} {pick}: not in pick_history; "
                    "skipping until next scan adds it.",
                    file=sys.stderr,
                )
                skipped_no_history += 1
                continue

            sport_raw = ph.get("sport", "?")
            sport = sport_raw.upper() if isinstance(sport_raw, str) else "?"
            american = odds_to_int(ph.get("odds", -110))
            wager_raw = placement.get("wager")
            wager = (
                wager_raw
                if isinstance(wager_raw, (int, float))
                else DEFAULT_WAGER
            )

            bets.append({
                "date": scan_date,
                "pick": pick,
                "event": event,
                "sport": sport,
                "wager": wager,
                "odds": american,
                "outcome": "pending",
                "pnl": 0,
                "final_score": "",
            })
            existing.add((scan_date, pick))
            added += 1
            print(f"  + KV-synced as pending: {scan_date} {pick}")

    if added == 0:
        print(
            "All KV placements already in data.json.bets[]. "
            f"({skipped_no_history} skipped for missing pick_history match.)"
        )
        return 0

    DATA.write_text(json.dumps(data, indent=2) + "\n")
    print(
        f"\nSynced {added} placement(s) into data.json as pending. "
        "resolve_bets.py will grade them when scores final."
    )
    if skipped_no_history:
        print(f"({skipped_no_history} skipped for missing pick_history match.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
