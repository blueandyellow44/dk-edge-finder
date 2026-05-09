#!/usr/bin/env python3
from __future__ import annotations
"""Player Prop Edge Scanner: sport dispatcher.

The shared math + Odds API + ESPN plumbing lives in props_kernel.py. Each
sport has its own plugin module (props_nba, props_nhl, props_mlb, props_soccer)
that supplies the small per-sport tables and adjustment hooks. This file
selects the right plugin for a given sport name and forwards to the kernel
orchestrator.

Public surface (kept stable for callers like scripts/scan_edges.py):
    scan_props(sport, bankroll=500.0, max_lookups=30, game_margins=None) -> list[dict]
"""

import props_kernel
import props_nba
import props_nhl
import props_mlb
import props_soccer


PLUGINS = {
    "nba": props_nba,
    "nhl": props_nhl,
    "mlb": props_mlb,
}
PLUGINS.update(props_soccer.PLUGINS)


def scan_props(sport: str = "nba", bankroll: float = 500.0, max_lookups: int = 30,
               game_margins: dict | None = None) -> list[dict]:
    plugin = PLUGINS.get(sport.lower())
    if not plugin:
        print(f"  Sport '{sport}' not supported for props yet")
        return []
    return props_kernel.scan_props(plugin, bankroll=bankroll, max_lookups=max_lookups,
                                   game_margins=game_margins or {})


if __name__ == "__main__":
    print("=== Player Prop Edge Scanner (Real DK Odds) ===\n")
    edges = scan_props("nba", bankroll=570.57, max_lookups=20)
    print(f"\nFound {len(edges)} edges:")
    for e in edges[:10]:
        print(f"  {e['pick']} ({e['odds']}) | {e['edge']}% edge | Proj: {e['our_projection']}, Line: {e['line']}")
