"""Snake-draft pick math for the 'my next picks' indicator.

Two paths:
  - ESPN (Kings): fully automatic. ESPN's own draft data assigns a teamId
    to every pick slot in the whole draft, and reflects trades directly
    (ESPN processes trades before the draft), so 'my next picks' is just
    filtering the raw picks array for slots owned by my team.
  - Manual leagues (RFN, Dirty Boys): no live feed, so pick ownership is
    computed from a config file (team count, my default slot, total
    rounds) plus per-round overrides for any round a trade changed -
    empty list means no pick that round, multiple slots means extra
    picks. A slot of `null` means the exact acquired slot isn't known
    yet; it's surfaced as TBD until the config is updated.
"""

import json


def load_draft_position(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def snake_pick_number(round_num, slot, team_count):
    if round_num % 2 == 1:
        return (round_num - 1) * team_count + slot
    return (round_num - 1) * team_count + (team_count - slot + 1)


def my_pick_numbers(config):
    """Returns every pick I own across the draft, sorted by overall pick
    number (unknown/TBD slots sort last within their round)."""
    team_count = config["team_count"]
    total_rounds = config["total_rounds"]
    my_slot = config["my_slot"]
    overrides = config.get("pick_overrides", {})

    picks = []
    for round_num in range(1, total_rounds + 1):
        slots = overrides.get(str(round_num), [my_slot])
        for slot in slots:
            if slot is None:
                picks.append({"round": round_num, "slot": None, "overall_pick": None, "pick_in_round": None})
            else:
                overall = snake_pick_number(round_num, slot, team_count)
                pick_in_round = ((overall - 1) % team_count) + 1
                picks.append({"round": round_num, "slot": slot, "overall_pick": overall, "pick_in_round": pick_in_round})

    picks.sort(key=lambda p: (p["overall_pick"] is None, p["overall_pick"] or 0, p["round"]))
    return picks


def next_picks_manual(config, picks_made_count, n=5):
    all_picks = my_pick_numbers(config)
    upcoming = [p for p in all_picks if p["overall_pick"] is None or p["overall_pick"] > picks_made_count]
    return upcoming[:n]


def next_picks_espn(raw_picks, my_team_id, team_count, n=5):
    upcoming = [
        {
            "round": p["roundId"],
            "pick_in_round": p["roundPickNumber"],
            "overall_pick": p["overallPickNumber"],
        }
        for p in raw_picks
        if p.get("teamId") == my_team_id and p.get("playerId", -1) == -1
    ]
    upcoming.sort(key=lambda p: p["overall_pick"])
    return upcoming[:n]
