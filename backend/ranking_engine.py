"""Best-available ranking engine.

Ranking is just the guide's Overall Rank/Tier order (same for all 3
leagues, no VORP/lineup adjustment) filtered down to undrafted players.
Keepers are tracked and auto-excluded from availability (with their
cost round attached for display), but do not affect rank order.
"""

import json
import math
import os

from crosswalk import normalize_name


def load_keepers(path):
    """Keeper file format: [{"player": "...", "cost_round": N}, ...]"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def drafted_names_from_keepers(keepers):
    return {normalize_name(k["player"]): k["cost_round"] for k in keepers}


def best_available(guide_players, drafted_names=None):
    """
    guide_players: list of dicts from ingestion.xlsx_parser.load_players
    drafted_names: set of normalized player names already off the board
                   (keepers + live draft picks once sync is wired up)

    Returns guide_players sorted by overall_rank, excluding drafted players.
    """
    drafted_names = drafted_names or set()

    available = [p for p in guide_players if normalize_name(p["player"]) not in drafted_names]
    available.sort(key=lambda p: (p["overall_rank"] is None, p["overall_rank"]))
    return available


def annotate_with_pick_estimates(available_players, picks_made_so_far, team_count):
    """Rough 'which round will this player go in' estimate: assumes the
    draft continues in exact rank order from here. Naturally re-flows as
    picks_made_so_far grows and the available list shrinks - no separate
    recompute step needed, just re-run this on the next poll/refresh."""
    out = []
    for i, p in enumerate(available_players):
        entry = dict(p)
        overall = picks_made_so_far + i + 1
        entry["pick_estimate"] = overall
        entry["round_estimate"] = math.ceil(overall / team_count)
        out.append(entry)
    return out


POSITIONS = ["QB", "RB", "WR", "TE"]


def positional_summary(available_players):
    """For each position: best remaining player + tier, and a count of
    how many players remain at each tier (positional scarcity)."""
    summary = {}
    for pos in POSITIONS:
        players = [p for p in available_players if p["position"] == pos]
        if not players:
            summary[pos] = {"best_player": None, "best_tier": None, "tier_counts": {}}
            continue
        players_sorted = sorted(players, key=lambda p: p["overall_rank"])
        tier_counts = {}
        for p in players:
            t = p["tier"]
            tier_counts[t] = tier_counts.get(t, 0) + 1
        summary[pos] = {
            "best_player": players_sorted[0]["player"],
            "best_tier": players_sorted[0]["tier"],
            "tier_counts": dict(sorted(tier_counts.items())),
        }
    return summary


def save_keepers(path, keepers):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(keepers, f, indent=2)


def add_keeper(path, player, cost_round):
    keepers = load_keepers(path) if os.path.exists(path) else []
    keepers = [k for k in keepers if normalize_name(k["player"]) != normalize_name(player)]
    keepers.append({"player": player, "cost_round": cost_round})
    save_keepers(path, keepers)
    return keepers


def remove_keeper(path, player):
    keepers = load_keepers(path) if os.path.exists(path) else []
    keepers = [k for k in keepers if normalize_name(k["player"]) != normalize_name(player)]
    save_keepers(path, keepers)
    return keepers


def off_the_board_from_keepers(guide_players, keeper_costs):
    """Kept players with their cost round attached, for a separate
    'off the board' display — these are excluded from best_available,
    not ranked among it."""
    result = []
    for p in guide_players:
        key = normalize_name(p["player"])
        if key in keeper_costs:
            entry = dict(p)
            entry["keeper_cost_round"] = keeper_costs[key]
            result.append(entry)
    return result


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from ingestion.xlsx_parser import load_players

    guide_players, _ = load_players(r"C:\Users\T991158\Downloads\RankingsTiersMarketScore_2026.xlsx")

    keepers_path = os.path.join(os.path.dirname(__file__), "keepers", "rfn.json")
    keepers = load_keepers(keepers_path) if os.path.exists(keepers_path) else []
    keeper_costs = drafted_names_from_keepers(keepers)

    available = best_available(guide_players, drafted_names=set(keeper_costs))
    kept = off_the_board_from_keepers(guide_players, keeper_costs)

    print(f"{len(keepers)} keepers loaded, {len(available)} players available")
    if kept:
        print("Off the board (keepers):")
        for p in kept:
            print(f"  {p['player']} ({p['position']}) - kept, would've cost R{p['keeper_cost_round']}")
    print("Top 10 available:")
    for p in available[:10]:
        print(f"  {p['overall_rank']:>3}. {p['player']} ({p['position']})")
