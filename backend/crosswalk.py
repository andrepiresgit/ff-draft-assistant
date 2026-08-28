"""Canonical player-identity crosswalk.

Maps player-name strings from the draft guide, plus ESPN player IDs and
Yahoo player keys, onto one canonical record per player. The guide's
Rankings and Tiers list is used as the seed/canonical name list (it's the
most complete, cleanest source we have); ESPN and Yahoo IDs get attached
onto those canonical records by matching normalized names.

Matching key is (normalized_name, position) rather than name alone, to
avoid collisions between different real players who happen to share a
name (e.g. multiple historical "Michael Thomas"es).
"""

import re
import unicodedata


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Known nickname/full-name variants that differ between the guide and a
# platform (e.g. "Kenny Gainwell" vs "Kenneth Gainwell"). Normalization
# can't resolve these generically — add an entry here whenever a weekly
# crosswalk run reports a new unmatched name that turns out to be this
# kind of variant, rather than building generic nickname-matching logic.
NAME_ALIASES = {
    "kenneth gainwell": "kenny gainwell",
    "nick singleton": "nicholas singleton",
}


def normalize_name(name):
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace(".", "").replace("'", "")
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    tokens = name.split(" ")
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    normalized = " ".join(tokens)
    return NAME_ALIASES.get(normalized, normalized)


def match_key(name, position):
    return (normalize_name(name), (position or "").upper())


def build_from_guide(guide_players):
    canonical = {}
    for i, gp in enumerate(guide_players):
        key = match_key(gp["player"], gp["position"])
        canonical[key] = {
            "canonical_id": f"guide-{i}",
            "name": gp["player"],
            "position": gp["position"],
            "guide_name": gp["player"],
            "espn_id": None,
            "espn_team": None,
            "yahoo_key": None,
        }
    return canonical


def attach_espn(canonical, espn_players):
    """espn_players: iterable of objects with .playerId, .name, .position, .proTeam"""
    unmatched_espn = []
    for ep in espn_players:
        key = match_key(ep.name, ep.position)
        if key in canonical:
            canonical[key]["espn_id"] = ep.playerId
            canonical[key]["espn_team"] = ep.proTeam
        else:
            unmatched_espn.append((ep.playerId, ep.name, ep.position))
    return unmatched_espn


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from dotenv import load_dotenv
    from espn_api.football import League

    from ingestion.xlsx_parser import load_players

    load_dotenv()

    guide_players, _ = load_players(r"C:\Users\T991158\Downloads\RankingsTiersMarketScore_2026.xlsx")
    canonical = build_from_guide(guide_players)

    league = League(
        league_id=int(os.environ["ESPN_KINGS_LEAGUE_ID"]),
        year=2026,
        espn_s2=os.environ["ESPN_S2"],
        swid=os.environ["ESPN_SWID"],
    )
    espn_players = league.free_agents(size=500)
    unmatched_espn = attach_espn(canonical, espn_players)

    matched = [c for c in canonical.values() if c["espn_id"] is not None]
    unmatched_guide = [c for c in canonical.values() if c["espn_id"] is None]

    print(f"guide players: {len(canonical)}")
    print(f"matched to ESPN: {len(matched)}")
    print(f"guide players with NO espn match: {len(unmatched_guide)}")
    for c in unmatched_guide:
        print("  guide-only:", c["name"], c["position"])
    print(f"espn players with NO guide match (sample, out of {len(unmatched_espn)}):")
    for pid, name, pos in unmatched_espn[:15]:
        print("  espn-only:", name, pos)
