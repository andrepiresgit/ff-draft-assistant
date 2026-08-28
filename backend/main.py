import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crosswalk import build_from_guide, attach_espn, normalize_name
from draft_position import load_draft_position, next_picks_espn, next_picks_manual
from espn_poller import get_drafted_espn_ids, drafted_names_from_espn_ids
from ingestion.xlsx_parser import load_players
from player_notes import build_notes_index, note_for_player, tags_for_player
from ranking_engine import (
    add_keeper,
    annotate_with_pick_estimates,
    best_available,
    drafted_names_from_keepers,
    load_keepers,
    off_the_board_from_keepers,
    positional_summary,
    remove_keeper,
)

load_dotenv()

BASE_DIR = os.path.dirname(__file__)
RANKINGS_PATH = r"C:\Users\T991158\Downloads\RankingsTiersMarketScore_2026.xlsx"
DRAFT_GUIDE_PATH = r"C:\Users\T991158\Downloads\LateRoundDraftGuide2026_August26.pdf"
KEEPERS_DIR = os.path.join(BASE_DIR, "keepers")
MANUAL_PICKS_DIR = os.path.join(BASE_DIR, "manual_picks")
DRAFT_POSITION_DIR = os.path.join(BASE_DIR, "draft_position")
os.makedirs(MANUAL_PICKS_DIR, exist_ok=True)

LEAGUES = {
    "kings": {"name": "Kings League", "platform": "espn", "keeper_file": None, "espn_team_id": 6},
    "rfn": {"name": "RFN League", "platform": "manual", "keeper_file": "rfn.json", "position_file": "rfn.json"},
    "dirty_boys": {"name": "Dirty Boys League", "platform": "manual", "keeper_file": "dirty_boys.json", "position_file": "dirty_boys.json"},
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

guide_players, _ = load_players(RANKINGS_PATH)
canonical = build_from_guide(guide_players)
notes_index = build_notes_index(DRAFT_GUIDE_PATH)

_espn_league = None


def get_espn_league():
    global _espn_league
    if _espn_league is None:
        from espn_api.football import League

        _espn_league = League(
            league_id=int(os.environ["ESPN_KINGS_LEAGUE_ID"]),
            year=2026,
            espn_s2=os.environ["ESPN_S2"],
            swid=os.environ["ESPN_SWID"],
        )
        attach_espn(canonical, _espn_league.free_agents(size=500))
    return _espn_league


def manual_picks_path(league_key):
    return os.path.join(MANUAL_PICKS_DIR, f"{league_key}.json")


def load_manual_picks(league_key):
    """Manual picks format: [{"player": "...", "by": "me"|"other"}, ...].
    Used as the sole pick source for manual-platform leagues (RFN, Dirty
    Boys), and merged additively on top of live ESPN data for Kings - a
    backup in case ESPN's draft feed doesn't reflect reality (this
    happened during mock/practice draft testing; real scheduled drafts
    are expected to work, but this costs nothing to have ready)."""
    path = manual_picks_path(league_key)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manual_picks(league_key, picks):
    with open(manual_picks_path(league_key), "w", encoding="utf-8") as f:
        json.dump(picks, f, indent=2)


def keeper_file_path(league_key):
    keeper_file = LEAGUES[league_key].get("keeper_file")
    return os.path.join(KEEPERS_DIR, keeper_file) if keeper_file else None


def league_keeper_costs(league_key):
    path = keeper_file_path(league_key)
    if not path or not os.path.exists(path):
        return {}
    return drafted_names_from_keepers(load_keepers(path))


def annotate_with_notes(players):
    out = []
    for p in players:
        entry = dict(p)
        entry["notes"] = tags_for_player(notes_index, p["player"])
        out.append(entry)
    return out


class ManualPick(BaseModel):
    player: str
    by: str = "other"  # "me" or "other"


class KeeperIn(BaseModel):
    player: str
    cost_round: int


@app.get("/leagues")
def list_leagues():
    return [{"key": k, "name": v["name"], "platform": v["platform"]} for k, v in LEAGUES.items()]


@app.get("/best-available/{league_key}")
def get_best_available(league_key: str):
    if league_key not in LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_key}")

    league_cfg = LEAGUES[league_key]
    keeper_costs = league_keeper_costs(league_key)
    off_the_board = off_the_board_from_keepers(guide_players, keeper_costs)
    manual_picks = load_manual_picks(league_key)
    drafted_names = set(keeper_costs) | {normalize_name(p["player"]) for p in manual_picks}

    if league_cfg["platform"] == "espn":
        try:
            espn_league = get_espn_league()
            drafted_espn_ids = get_drafted_espn_ids(espn_league)
        except Exception as e:
            raise HTTPException(502, f"ESPN connection failed: {e}")

        drafted_names |= drafted_names_from_espn_ids(canonical, drafted_espn_ids)
        available = best_available(guide_players, drafted_names=drafted_names)

        raw_picks = espn_league.espn_request.get_league_draft().get("draftDetail", {}).get("picks", [])
        team_count = len(espn_league.teams)
        my_next_picks = next_picks_espn(raw_picks, league_cfg["espn_team_id"], team_count)
        available = annotate_with_pick_estimates(available, len(drafted_names), team_count)
    else:
        available = best_available(guide_players, drafted_names=drafted_names)

        position_path = os.path.join(DRAFT_POSITION_DIR, LEAGUES[league_key]["position_file"])
        position_cfg = load_draft_position(position_path)
        my_next_picks = next_picks_manual(position_cfg, picks_made_count=len(manual_picks))
        available = annotate_with_pick_estimates(available, len(drafted_names), position_cfg["team_count"])

    return {
        "league": league_key,
        "platform": league_cfg["platform"],
        "available": annotate_with_notes(available),
        "off_the_board": off_the_board,
        "manual_picks": manual_picks,
        "positional_summary": positional_summary(available),
        "my_next_picks": my_next_picks,
    }


@app.get("/note/{player}")
def get_note(player: str):
    return note_for_player(notes_index, player)


@app.post("/manual-pick/{league_key}")
def add_manual_pick(league_key: str, pick: ManualPick):
    if league_key not in LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_key}")

    valid_names = {normalize_name(p["player"]) for p in guide_players}
    if normalize_name(pick.player) not in valid_names:
        raise HTTPException(400, f"'{pick.player}' not found in guide rankings")

    picks = load_manual_picks(league_key)
    if normalize_name(pick.player) in {normalize_name(p["player"]) for p in picks}:
        raise HTTPException(400, f"'{pick.player}' is already marked as drafted")

    picks.append({"player": pick.player, "by": pick.by})
    save_manual_picks(league_key, picks)
    return {"ok": True, "picks": picks}


@app.delete("/manual-pick/{league_key}/{player}")
def remove_manual_pick(league_key: str, player: str):
    if league_key not in LEAGUES:
        raise HTTPException(404, f"Unknown league: {league_key}")

    picks = load_manual_picks(league_key)
    target = normalize_name(player)
    picks = [p for p in picks if normalize_name(p["player"]) != target]
    save_manual_picks(league_key, picks)
    return {"ok": True, "picks": picks}


@app.get("/keepers/{league_key}")
def get_keepers(league_key: str):
    path = keeper_file_path(league_key)
    if not path:
        raise HTTPException(404, f"{league_key} has no keepers")
    return load_keepers(path) if os.path.exists(path) else []


@app.post("/keepers/{league_key}")
def add_keeper_endpoint(league_key: str, keeper: KeeperIn):
    path = keeper_file_path(league_key)
    if not path:
        raise HTTPException(404, f"{league_key} has no keepers")

    valid_names = {normalize_name(p["player"]) for p in guide_players}
    if normalize_name(keeper.player) not in valid_names:
        raise HTTPException(400, f"'{keeper.player}' not found in guide rankings")

    return {"ok": True, "keepers": add_keeper(path, keeper.player, keeper.cost_round)}


@app.delete("/keepers/{league_key}/{player}")
def remove_keeper_endpoint(league_key: str, player: str):
    path = keeper_file_path(league_key)
    if not path:
        raise HTTPException(404, f"{league_key} has no keepers")
    return {"ok": True, "keepers": remove_keeper(path, player)}
