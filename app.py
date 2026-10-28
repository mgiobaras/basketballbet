import streamlit as st
import requests
import numpy as np
import unicodedata
import re
import difflib
import csv
import os
from datetime import datetime, timedelta

# ============================================================
# STREAMLIT BASKETBALL MONTE CARLO WEB APP (COMPLETE)
# ============================================================

st.set_page_config(page_title="Basketball Monte Carlo App", page_icon="🏀", layout="wide")

ITERATIONS = 500_000  
HISTORY_FILE = "basketball_predictions_history.csv"
VALUE_THRESHOLD_PCT = 4.99
MIN_PROB_TO_SAVE = 60.0  
MAX_DEVIATION_PCT = 15.0 

# --- ΑΥΤΟΜΑΤΗ ΔΗΜΙΟΥΡΓΙΑ ΑΡΧΕΙΟΥ ΙΣΤΟΡΙΚΟΥ ΑΝ ΔΕΝ ΥΠΑΡΧΕΙ ---
HISTORY_FIELDS = [
    "created_at", "game_date", "league", "home", "away", "mu_home", "mu_away", 
    "p_home", "p_away", "line_ou", "p_over", "p_under", "handicap", "p_handicap", 
    "odds_home", "odds_away", "odds_over", "odds_under", "odds_handicap", 
    "confidence", "data_source", "actual_home", "actual_away", "market", 
    "market_odds", "market_prob", "ev", "stake"
]

if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        writer.writeheader()

LEAGUES = {
    "NBA": {"code": "basketball/nba", "type": "espn"},
    "EuroLeague": {"code": "euroleague", "type": "euroleague"},
    "Ελλάδα - Basket League": {"code": "basketball/gre", "type": "auto_db"}
}

AUTO_TEAMS_DB = {
    "olympiacos": {"name": "Olympiacos Piraeus", "avg_pf": 83.5, "std_pf": 7.5, "avg_pa": 76.2, "std_pa": 7.0, "rest_days": 3},
    "panathinaikos": {"name": "Panathinaikos Athens", "avg_pf": 85.0, "std_pf": 8.0, "avg_pa": 78.5, "std_pa": 7.5, "rest_days": 3},
    "aek": {"name": "AEK Athens", "avg_pf": 79.0, "std_pf": 8.5, "avg_pa": 79.0, "std_pa": 8.0, "rest_days": 4},
    "real madrid": {"name": "Real Madrid", "avg_pf": 86.5, "std_pf": 8.5, "avg_pa": 80.0, "std_pa": 8.0, "rest_days": 3},
    "barcelona": {"name": "FC Barcelona", "avg_pf": 82.0, "std_pf": 7.5, "avg_pa": 77.0, "std_pa": 7.0, "rest_days": 3},
    "fenerbahce": {"name": "Fenerbahce Beko", "avg_pf": 83.0, "std_pf": 8.0, "avg_pa": 77.5, "std_pa": 7.5, "rest_days": 3},
    "celtics": {"name": "Boston Celtics", "avg_pf": 118.0, "std_pf": 9.0, "avg_pa": 109.0, "std_pa": 8.5, "rest_days": 2},
    "lakers": {"name": "LA Lakers", "avg_pf": 115.0, "std_pf": 9.5, "avg_pa": 114.0, "std_pa": 9.0, "rest_days": 2},
    "warriors": {"name": "Golden State Warriors", "avg_pf": 116.0, "std_pf": 10.0, "avg_pa": 113.0, "std_pa": 9.0, "rest_days": 2},
    "bucks": {"name": "Milwaukee Bucks", "avg_pf": 117.0, "std_pf": 9.5, "avg_pa": 114.0, "std_pa": 9.0, "rest_days": 2},
    "nuggets": {"name": "Denver Nuggets", "avg_pf": 114.5, "std_pf": 8.5, "avg_pa": 109.5, "std_pa": 8.0, "rest_days": 2},
    "mavericks": {"name": "Dallas Mavericks", "avg_pf": 116.5, "std_pf": 9.5, "avg_pa": 113.5, "std_pa": 9.0, "rest_days": 2}
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Accept": "application/json"
})

def normalize(text):
    if text is None: return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9α-ωΑ-Ω\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def api_get(url, params=None):
    try:
        response = session.get(url, params=params, timeout=10)
        if response.status_code == 200: return response.json()
    except Exception: pass
    return None

def get_espn_matches(league_code, target_date):
    date_str = target_date.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/{league_code}/scoreboard"
    data = api_get(url, params={"dates": date_str, "limit": 50})
    if not data or not data.get("events"): return []
    matches = []
    for event in data.get("events", []):
        comps = event.get("competitions", [])
        if not comps: continue
        competitors = comps[0].get("competitors", [])
        if len(competitors) < 2: continue
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if home and away:
            matches.append({
                "home": home.get("team", {}).get("displayName", ""),
                "away": away.get("team", {}).get("displayName", "")
            })
    return matches

def _extract_team_name(value):
    if isinstance(value, str): return value.strip()
    if isinstance(value, dict):
        for key in ("name", "clubName", "teamName", "displayName", "internationalName", "shortName"):
            if value.get(key): return str(value[key]).strip()
        for key in ("club", "team"):
            if isinstance(value.get(key), dict):
                found = _extract_team_name(value[key])
                if found: return found
    return ""

def _parse_game_date(game):
    for key in ("date", "gameDate", "startDate", "utcDate", "dateTime"):
        value = game.get(key)
        if not value: continue
        if isinstance(value, (int, float)):
            stamp = value / 1000 if value > 10_000_000_000 else value
            try: return datetime.fromtimestamp(stamp).date()
            except Exception: continue
        if isinstance(value, str):
            value = value.strip()
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%d/%m/%Y"):
                try: return datetime.strptime(value, fmt).date()
                except ValueError: pass
    return None

def get_euroleague_matches(target_date):
    season_year = target_date.year if target_date.month >= 7 else target_date.year - 1
    season_code = f"E{season_year}"
    url = f"https://api-live.euroleague.net/v2/competitions/E/seasons/{season_code}/games"
    data = api_get(url, params={"limit": 500})
    if not data: return []
    games = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(games, list): return []
    matches = []
    for game in games:
        if not isinstance(game, dict): continue
        game_date = _parse_game_date(game)
        if game_date != target_date: continue
        home = _extract_team_name(game.get("local") or game.get("localTeam") or game.get("home"))
        away = _extract_team_name(game.get("road") or game.get("roadTeam") or game.get("away"))
        if home and away: matches.append({"home": home, "away": away})
    return matches

def _extract_score(value):
    if isinstance(value, (int, float)): return float(value)
    if isinstance(value, str):
        try: return float(value.strip())
        except ValueError: return None
    if isinstance(value, dict):
        for key in ("score", "points", "value"):
            if value.get(key) is not None: return _extract_score(value[key])
    return None

def _team_match(a, b):
    na, nb = normalize(a), normalize(b)
    if not na or not nb: return False
    if na == nb or na in nb or nb in na: return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.78

def _euroleague_completed_games(target_date):
    season_year = target_date.year if target_date.month >= 7 else target_date.year - 1
    season_code = f"E{season_year}"
    url = f"https://api-live.euroleague.net/v2/competitions/E/seasons/{season_code}/games"
    data = api_get(url, params={"limit": 500})
    games = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(games, list): return []
    out = []
    for game in games:
        if not isinstance(game, dict): continue
        dt = _parse_game_date(game)
        home_obj = game.get("local") or game.get("localTeam") or game.get("home")
        away_obj = game.get("road") or game.get("roadTeam") or game.get("away")
        home, away = _extract_team_name(home_obj), _extract_team_name(away_obj)
        home_score = _extract_score((home_obj or {}).get("score") if isinstance(home_obj, dict) else None)
        away_score = _extract_score((away_obj or {}).get("score") if isinstance(away_obj, dict) else None)
        if home_score is None: home_score = _extract_score(game.get("localScore", game.get("homeScore")))
        if away_score is None: away_score = _extract_score(game.get("roadScore", game.get("awayScore")))
        if dt and dt <= target_date and home and away and home_score is not None and away_score is not None and (home_score + away_score) > 0:
            out.append({"date": dt, "home": home, "away": away, "home_score": home_score, "away_score": away_score})
    return out

def _espn_games_range(league_code, start_date, end_date):
    url = f"https://site.api.espn.com/apis/site/v2/sports/{league_code}/scoreboard"
    out, seen = [], set()
    def parse_events(data):
        parsed = []
        if not data or not isinstance(data, dict): return parsed
        for event in data.get("events", []):
            comps = event.get("competitions", [])
            if not comps: continue
            comp = comps[0]
            status = comp.get("status", {}).get("type", {}).get("completed", False)
            competitors = comp.get("competitors", [])
            if len(competitors) < 2: continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home or not away: continue
            hs, aws = _extract_score(home.get("score")), _extract_score(away.get("score"))
            if hs is None or aws is None or hs + aws <= 0 or not status: continue
            date_text = event.get("date", "")
            try: game_date = datetime.fromisoformat(date_text.replace("Z", "+00:00")).date()
            except Exception: continue
