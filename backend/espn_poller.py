"""Live ESPN draft polling for the Kings League.

Note: the espn-api library's own League.refresh_draft()/`.draft` only
populates once the ENTIRE draft is marked complete (draftDetail.drafted
== true) - it stays empty throughout a live, in-progress draft. We bypass
that wrapper and read draftDetail.picks directly instead: it always
contains one entry per pick slot in the whole draft, with playerId == -1
for slots not yet picked. Filtering on playerId != -1 gives the real
in-progress state regardless of the drafted/inProgress flags.

Matching drafted picks back to guide players goes through ESPN player ID
(via the crosswalk's espn_id field) rather than name — more robust than
re-normalizing names on every poll.
"""

from crosswalk import normalize_name
from ranking_engine import best_available


def get_drafted_espn_ids(league):
    data = league.espn_request.get_league_draft()
    picks = data.get("draftDetail", {}).get("picks", [])
    return {p["playerId"] for p in picks if p.get("playerId", -1) != -1}


def drafted_names_from_espn_ids(canonical, drafted_espn_ids):
    return {
        normalize_name(c["name"])
        for c in canonical.values()
        if c["espn_id"] in drafted_espn_ids
    }


def poll_best_available(league, canonical, guide_players, extra_drafted_names=None):
    """One poll cycle: fetch current ESPN draft state, return best-available
    guide players excluding anyone ESPN has drafted plus any extra names
    (e.g. keepers) the caller wants excluded too."""
    drafted_espn_ids = get_drafted_espn_ids(league)
    drafted_names = drafted_names_from_espn_ids(canonical, drafted_espn_ids)
    if extra_drafted_names:
        drafted_names |= extra_drafted_names
    return best_available(guide_players, drafted_names=drafted_names), drafted_espn_ids


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from dotenv import load_dotenv
    from espn_api.football import League

    from crosswalk import build_from_guide, attach_espn
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
    attach_espn(canonical, league.free_agents(size=500))

    available, drafted_ids = poll_best_available(league, canonical, guide_players)
    print(f"drafted so far: {len(drafted_ids)}")
    print("Top 10 available:")
    for p in available[:10]:
        print(f"  {p['overall_rank']:>3}. {p['player']} ({p['position']})")
