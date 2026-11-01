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
# STREAMLIT BASKETBALL MONTE CARLO WEB APP (ROI & BANKROLL)
# ============================================================

st.set_page_config(
    page_title="Basketball Monte Carlo Predictor",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

ITERATIONS = 500_000  
HISTORY_FILE = "basketball_predictions_history.csv"
VALUE_THRESHOLD_PCT = 4.99
MIN_PROB_TO_SAVE = 60.0  
MAX_DEVIATION_PCT = 15.0 

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
    "mavericks": {"name": "Dallas Mavericks", "avg_pf": 116.5, "std_pf": 9.5, "avg_pa": 113.5, "std_pa": 9.0, "rest_days": 2},
    "besiktas": {"name": "Besiktas", "avg_pf": 81.0, "std_pf": 8.5, "avg_pa": 79.0, "std_pa": 8.0, "rest_days": 3}
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
        response = session.get(url, params=params, timeout=15)
        if response.status_code == 200: return response.json()
    except Exception: pass
    return None

@st.cache_data(ttl=1800)
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
            if not (start_date <= game_date <= end_date): continue
            gid = str(event.get("id") or f"{game_date}|{home.get('team', {}).get('displayName')}|{away.get('team', {}).get('displayName')}")
            if gid in seen: continue
            seen.add(gid)
            parsed.append({"date": game_date, "home": home.get("team", {}).get("displayName", ""), "away": away.get("team", {}).get("displayName", ""), "home_score": hs, "away_score": aws})
        return parsed

    date_range = f"{start_date:%Y%m%d}-{end_date:%Y%m%d}"
    data = api_get(url, params={"dates": date_range, "limit": 1000})
    out.extend(parse_events(data))
    if len(out) < 12:
        for offset in range((end_date - start_date).days + 1):
            day = end_date - timedelta(days=offset)
            daily = api_get(url, params={"dates": day.strftime("%Y%m%d"), "limit": 100})
            out.extend(parse_events(daily))
            if len(out) >= 100: break
    out.sort(key=lambda g: g["date"])
    return out

def get_automatic_team_stats(team_name, league_name=""):
    norm_name = normalize(team_name)
    for key, stats in AUTO_TEAMS_DB.items():
        if key in norm_name or norm_name in key or difflib.SequenceMatcher(None, norm_name, key).ratio() >= 0.7:
            return stats.copy()
    default_pts = 112.0 if "nba" in league_name.lower() or "nba" in norm_name else 80.0
    return {"name": team_name, "avg_pf": default_pts, "std_pf": 9.0, "avg_pa": default_pts, "std_pa": 9.0, "rest_days": 2}

def get_team_stats(team_name, league, target_date):
    games = []
    source = "ενσωματωμένοι μέσοι όροι (αρχή σεζόν)"
    if league.get("type") == "euroleague":
        games = _euroleague_completed_games(target_date)
        source = "EuroLeague API"
    elif league.get("type") == "espn":
        games = _espn_games_range(league["code"], target_date - timedelta(days=400), target_date)
        source = "ESPN scoreboard"

    team_games = []
    for g in games:
        if _team_match(team_name, g["home"]):
            team_games.append({"date": g["date"], "pf": g["home_score"], "pa": g["away_score"]})
        elif _team_match(team_name, g["away"]):
            team_games.append({"date": g["date"], "pf": g["away_score"], "pa": g["home_score"]})
    team_games.sort(key=lambda x: x["date"])
    
    if len(team_games) < 2:
        stats = get_automatic_team_stats(team_name, league.get("name", ""))
        stats.update({"data_source": "ενσωματωμένοι μέσοι όροι (αρχή σεζόν)", "games_used": len(team_games), "confidence": "ΧΑΜΗΛΗ"})
        return stats

    last10 = team_games[-10:]
    season_pf = float(np.mean([g["pf"] for g in team_games]))
    season_pa = float(np.mean([g["pa"] for g in team_games]))
    recent_pf = float(np.mean([g["pf"] for g in last10]))
    recent_pa = float(np.mean([g["pf"] for g in last10]))
    blend = min(len(last10) / 10.0, 1.0) * 0.60
    avg_pf = blend * recent_pf + (1 - blend) * season_pf
    avg_pa = blend * recent_pa + (1 - blend) * season_pa
    pf_values = [g["pf"] for g in team_games]
    pa_values = [g["pa"] for g in team_games]
    last_date = team_games[-1]["date"]
    rest_days = max(0, (target_date - last_date).days)
    confidence = "ΥΨΗΛΗ" if len(team_games) >= 15 else ("ΜΕΣΑΙΑ" if len(team_games) >= 6 else "ΧΑΜΗΛΗ")
    return {"name": team_name, "avg_pf": avg_pf, "std_pf": max(float(np.std(pf_values[-10:])), 5.0),
            "avg_pa": avg_pa, "std_pa": max(float(np.std(pa_values[-10:])), 5.0),
            "rest_days": rest_days, "data_source": source, "games_used": len(team_games), "confidence": confidence}

def save_prediction(row):
    fields = ["created_at", "game_date", "league", "home", "away", "mu_home", "mu_away", "p_home", "p_away",
              "line_ou", "p_over", "p_under", "handicap", "p_handicap", "odds_home", "odds_away", "odds_over",
              "odds_under", "odds_handicap", "confidence", "data_source", "actual_home", "actual_away", "market", "market_odds", "market_prob", "ev", "stake"]
    exists = os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        if not exists: writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fields})

def evaluate_bet_win(r):
    try:
        hs = float(r["actual_home"])
        aws = float(r["actual_away"])
    except Exception:
        return False

    market = str(r.get("market", ""))
    home_name = str(r.get("home", ""))
    away_name = str(r.get("away", ""))
    total_score = hs + aws

    if "Over" in market:
        match = re.search(r'([\d]+\.?[\d]*)', market)
        if match: return total_score > float(match.group(1))
        elif r.get("line_ou") not in [None, ""]:
            try: return total_score > float(r["line_ou"])
            except ValueError: pass
        return total_score > 160.5

    if "Under" in market:
        match = re.search(r'([\d]+\.?[\d]*)', market)
        if match: return total_score < float(match.group(1))
        elif r.get("line_ou") not in [None, ""]:
            try: return total_score < float(r["line_ou"])
            except ValueError: pass
        return total_score < 160.5

    if "Handicap" in market:
        match = re.search(r'([+-]?[\d]+\.?[\d]*)', market)
        if match:
            hc = float(match.group(1))
            if home_name in market or "1" in market: return (hs + hc) > aws
            else: return (aws + hc) > hs
        return (hs + 8.5) > aws

    if f"Νίκη {home_name}" in market or market.startswith("Νίκη 1") or (market.startswith("Νίκη") and home_name in market):
        return hs > aws

    if f"Νίκη {away_name}" in market or market.startswith("Νίκη 2") or (market.startswith("Νίκη") and away_name in market):
        return hs < aws

    return hs > aws

# --- STREAMLIT UI ---
st.title("🏀 Basketball Monte Carlo Predictor")
st.markdown("Προσομοιώσεις Monte Carlo για αγώνες μπάσκετ με αυτόματη ανάκτηση δεδομένων, Value Bets και παρακολούθηση ιστορικού.")

# Sidebar options
st.sidebar.header("⚙️ Ρυθμίσεις Αγώνα")
league_key = st.sidebar.selectbox("Επιλογή Διοργάνωσης:", list(LEAGUES.keys()))
league = LEAGUES[league_key]

target_date = st.sidebar.date_input("Ημερομηνία Αγώνα", datetime.now().date())

if "prev_league" not in st.session_state or st.session_state["prev_league"] != league_key:
    st.session_state["prev_league"] = league_key
    if "last_sim_data" in st.session_state: del st.session_state["last_sim_data"]

matches = []
if league["type"] == "espn":
    matches = get_espn_matches(league["code"], target_date)
elif league["type"] == "euroleague":
    matches = get_euroleague_matches(target_date)

match_options = [f"{m['home']} vs {m['away']}" for m in matches] if matches else []
match_options.append("➕ Χειροκίνητη Εισαγωγή Ομάδων")

selected_match_str = st.sidebar.selectbox("Επιλογή Αγώνα:", match_options)

home_name, away_name = "", ""
if selected_match_str != "➕ Χειροκίνητη Εισαγωγή Ομάδων" and matches:
    idx = match_options.index(selected_match_str)
    home_name = matches[idx]["home"]
    away_name = matches[idx]["away"]
else:
    home_name = st.sidebar.text_input("Γηπεδούχος Ομάδα", "Olympiacos Piraeus")
    away_name = st.sidebar.text_input("Φιλοξενούμενη Ομάδα", "Panathinaikos Athens")

if st.sidebar.button("🔄 Καθαρισμός / Ανανέωση"):
    if "last_sim_data" in st.session_state: del st.session_state["last_sim_data"]
    st.rerun()

if home_name and away_name:
    with st.spinner("Ανάκτηση στατιστικών από API..."):
        home_stats = get_team_stats(home_name, league, target_date)
        away_stats = get_team_stats(away_name, league, target_date)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Στατιστικά Ομάδων")
    st.sidebar.markdown(f"**🏠 {home_stats['name']}**\n- Μ.Ο. Πόντων: `{home_stats['avg_pf']:.1f}`\n- Πηγή: `{home_stats['data_source']}`")
    st.sidebar.markdown(f"**✈️ {away_stats['name']}**\n- Μ.Ο. Πόντων: `{away_stats['avg_pf']:.1f}`\n- Πηγή: `{away_stats['data_source']}`")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Προσαρμογές & Αγορές")
    home_adjustment = st.sidebar.number_input(f"Προσαρμογή {home_name} (απουσίες)", value=0.0, step=0.5)
    away_adjustment = st.sidebar.number_input(f"Προσαρμογή {away_name} (απουσίες)", value=0.0, step=0.5)
    line_ou = st.sidebar.number_input("Line Over/Under", value=165.5, step=0.5)
    handicap_val = st.sidebar.number_input(f"Handicap {home_name} (π.χ. -5.5)", value=-3.5, step=0.5)

    st.sidebar.markdown("💰 **Αποδόσεις Bookmakers**")
    odds = {
        "1": st.sidebar.number_input(f"1 (Νίκη {home_name})", value=1.85, min_value=1.01, step=0.01),
        "2": st.sidebar.number_input(f"2 (Νίκη {away_name})", value=1.95, min_value=1.01, step=0.01),
        "over": st.sidebar.number_input("Over Odds", value=1.90, min_value=1.01, step=0.01),
        "under": st.sidebar.number_input("Under Odds", value=1.90, min_value=1.01, step=0.01),
        "handicap": st.sidebar.number_input("Handicap Odds", value=1.90, min_value=1.01, step=0.01)
    }

    if st.button("🚀 Εκτέλεση Προσομοίωσης Monte Carlo") or st.session_state.get("sim_run", False):
        st.session_state["sim_run"] = True
        
        if "last_sim_data" not in st.session_state:
            with st.spinner(f"Εκτέλεση {ITERATIONS:,} προσομοιώσεων... Παρακαλώ περιμένετε."):
                home_rest = home_stats.get("rest_days", 2)
                away_rest = away_stats.get("rest_days", 2)
                home_rest_mult = 0.97 if home_rest <= 1 else (1.01 if home_rest >= 4 else 1.0)
                away_rest_mult = 0.95 if away_rest <= 1 else (1.01 if away_rest >= 4 else 1.0)

                mu_home = max(((home_stats["avg_pf"] + away_stats["avg_pa"]) / 2) * home_rest_mult + 2.0 + home_adjustment, 65.0)
                mu_away = max(((away_stats["avg_pf"] + home_stats["avg_pa"]) / 2) * away_rest_mult + away_adjustment, 65.0)
                sigma_home = max((home_stats["std_pf"] + away_stats["std_pa"]) / 2, 5.0)
                sigma_away = max((away_stats["std_pf"] + home_stats["std_pa"]) / 2, 5.0)

                np.random.seed(42)
                hg = np.clip(np.round(np.random.normal(mu_home, sigma_home, ITERATIONS)), 50, 160)
                ag = np.clip(np.round(np.random.normal(mu_away, sigma_away, ITERATIONS)), 50, 160)
                
                p_home = (np.mean(hg > ag) + 0.5 * np.mean(hg == ag)) * 100
                p_away = 100.0 - p_home
                total_pts = hg + ag
                p_over = float(np.mean(total_pts > line_ou) * 100) if line_ou is not None else None
                p_under = float(100.0 - p_over) if line_ou is not None else None
                p_handicap_home = float(np.mean((hg + handicap_val) > ag) * 100) if handicap_val is not None else None

                confidence_levels = [home_stats.get("confidence", "ΧΑΜΗΛΗ"), away_stats.get("confidence", "ΧΑΜΗΛΗ")]
                confidence = "ΥΨΗΛΗ" if all(c == "ΥΨΗΛΗ" for c in confidence_levels) else ("ΜΕΣΑΙΑ" if all(c != "ΧΑΜΗΛΗ" for c in confidence_levels) else "ΧΑΜΗΛΗ")
                sources = sorted(set([home_stats.get("data_source", "στατικά δεδομένα"), away_stats.get("data_source", "στατικά δεδομένα")]))
                data_source = " + ".join(sources)

                st.session_state["last_sim_data"] = {
                    "p_home": p_home, "p_away": p_away, "mu_home": mu_home, "mu_away": mu_away,
                    "p_over": p_over, "p_under": p_under, "p_handicap_home": p_handicap_home,
                    "confidence": confidence, "data_source": data_source
                }

        sim = st.session_state["last_sim_data"]

        st.success("Η προσομοίωση ολοκληρώθηκε με επιτυχία!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"Νίκη {home_stats['name']}", f"{sim['p_home']:.1f}%")
        col2.metric("Εκτιμώμενο Σκορ", f"{sim['mu_home']:.1f} - {sim['mu_away']:.1f}")
        col3.metric(f"Νίκη {away_stats['name']}", f"{sim['p_away']:.1f}%")

        st.markdown("---")
        st.subheader("📈 Ανάλυση Over/Under & Handicap")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric(f"Over {line_ou}", f"{sim['p_over']:.1f}%")
        col_b.metric(f"Under {line_ou}", f"{sim['p_under']:.1f}%")
        col_c.metric(f"Handicap ({handicap_val:+g})", f"{sim['p_handicap_home']:.1f}%")

        st.markdown("---")
        st.subheader("💡 Επιλογή Value Bets & Αποθήκευση στο Ιστορικό")
        
        raw_odds_12 = [odds.get("1"), odds.get("2")]
        fair_probs_12 = [None, None]
        if all(o is not None and o > 1 for o in raw_odds_12):
            implied_probs = [1.0 / o for o in raw_odds_12]
            total_prob = sum(implied_probs)
            fair_probs_12 = [(p / total_prob) * 100 for p in implied_probs]

        markets = [
            (f"Νίκη {home_stats['name']} (1)", sim['p_home'], odds.get("1"), fair_probs_12[0]),
            (f"Νίκη {away_stats['name']} (2)", sim['p_away'], odds.get("2"), fair_probs_12[1]),
            (f"Over {line_ou}", sim['p_over'], odds.get("over"), None), 
            (f"Under {line_ou}", sim['p_under'], odds.get("under"), None),
            (f"Handicap {home_stats['name']} ({handicap_val:+g})", sim['p_handicap_home'], odds.get("handicap"), None)
        ]

        valid_value_bets = []

        for market, prob, odd, fair_prob in markets:
            if prob is None or odd is None or odd <= 1: continue
            
            if fair_prob is not None and abs(prob - fair_prob) > MAX_DEVIATION_PCT:
                continue

            ev = ((prob / 100.0) * odd - 1.0) * 100.0
            b_val = odd - 1.0
            p_win = prob / 100.0
            kelly_full = (b_val * p_win - (1 - p_win)) / b_val if b_val > 0 else 0.0
            stake = min(max(kelly_full * 0.15 * 100, 0), 2.0)

            if ev > VALUE_THRESHOLD_PCT:
                valid_value_bets.append({
                    "market": market, "prob": prob, "odd": odd, "ev": ev, "stake": stake
                })

        if valid_value_bets:
            st.write("Επιλέξτε ποια από τα παρακάτω Value Bets θέλετε να προσθέσετε στο ιστορικό σας:")
            
            selected_bets_to_save = []
            for i, vb in enumerate(valid_value_bets):
                label = f"🔥 {vb['market']} | Απόδοση: {vb['odd']:.2f} | Πιθανότητα: {vb['prob']:.1f}% | EV: +{vb['ev']:.2f}% | Stake: {vb['stake']:.1f}%"
                is_checked = st.checkbox(label, value=True, key=f"session_chk_{i}")
                if is_checked:
                    selected_bets_to_save.append(vb)

            if st.button("💾 Αποθήκευση Επιλεγμένων στο Ιστορικό", key="btn_save_session"):
                if selected_bets_to_save:
                    saved_count = 0
                    for vb in selected_bets_to_save:
                        bet_entry = {
                            "created_at": datetime.now().isoformat(),
                            "game_date": target_date.isoformat(), 
                            "league": league_key,
                            "home": home_stats["name"], 
                            "away": away_stats["name"],
                            "mu_home": round(sim['mu_home'], 2), 
                            "mu_away": round(sim['mu_away'], 2),
                            "p_home": round(sim['p_home'], 3), 
                            "p_away": round(sim['p_away'], 3),
                            "line_ou": line_ou,
                            "market": vb["market"], 
                            "market_odds": vb["odd"], 
                            "market_prob": vb["prob"],
                            "ev": vb["ev"], 
                            "stake": vb["stake"], 
                            "confidence": sim['confidence'],
                            "data_source": sim['data_source'], 
                            "actual_home": "", 
                            "actual_away": ""
                        }
                        save_prediction(bet_entry)
                        saved_count += 1
                    
                    st.success(f"Αποθηκεύτηκαν επιτυχώς {saved_count} επιλογές στο ιστορικό!")
                    if "last_sim_data" in st.session_state:
                        del st.session_state["last_sim_data"]
                    st.rerun()
                else:
                    st.warning("Δεν έχετε επιλέξει καμία πρόταση προς αποθήκευση.")
        else:
            st.info("Δεν βρέθηκαν Value Bets που να ξεπερνούν το όριο EV για αυτόν τον αγώνα.")

# --- ΕΛΕΓΧΟΣ ΙΣΤΟΡΙΚΟΥ, ROI & ΜΠΑΝΚΑΣ ---
st.markdown("---")
st.subheader("📂 Ιστορικό, ROI & Παρακολούθηση Μπάνκας")

if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    
    if rows:
        st.write(f"Συνολικά αποθηκευμένες προτάσεις: **{len(rows)}**")
        
        pending_rows = [r for r in rows if r.get("actual_home", "") == "" or r.get("actual_away", "") == ""]
        
        if pending_rows:
            with st.expander("📝 Εισαγωγή Τελικών Σκόρ για Εκκρεμή Στοιχήματα"):
                for idx, r in enumerate(pending_rows):
                    st.write(f"🏀 **{r['game_date']}** | {r['home']} vs {r['away']} | Επιλογή: `{r['market']}`")
                    col_h, col_a, col_btn = st.columns([2, 2, 2])
                    
                    h_score = col_h.number_input(f"Πόντοι {r['home']}", min_value=0, value=0, key=f"h_{idx}")
                    a_score = col_a.number_input(f"Πόντοι {r['away']}", min_value=0, value=0, key=f"a_{idx}")
                    
                    if col_btn.button("💾 Αποθήκευση Σκόρ", key=f"btn_{idx}"):
                        if h_score > 0 or a_score > 0:
                            for orig_r in rows:
                                if orig_r == r:
                                    orig_r["actual_home"] = str(h_score)
                                    orig_r["actual_away"] = str(a_score)
                                    break
                            
                            fields = list(rows[0].keys())
                            with open(HISTORY_FILE, "w", newline="", encoding="utf-8-sig") as f_out:
                                writer = csv.DictWriter(f_out, fieldnames=fields, extrasaction='ignore')
                                writer.writeheader()
                                writer.writerows(rows)
                            
                            st.success(f"Το σκόρ {h_score}-{a_score} αποθηκεύτηκε!")
                            st.rerun()

        settled = [r for r in rows if r.get("actual_home", "") != "" and r.get("actual_away", "") != ""]
        
        if settled:
            correct = sum([1 for r in settled if evaluate_bet_win(r)])
            win_rate = (correct / len(settled)) * 100
            
            # Ypologismos Mpankas & ROI
            total_staked = 0.0
            total_return = 0.0
            
            for r in settled:
                try: stake = float(r.get("stake", 1.0))
                except ValueError: stake = 1.0
                try: odds_val = float(r.get("market_odds", 1.90))
                except ValueError: odds_val = 1.90
                
                total_staked += stake
                if evaluate_bet_win(r):
                    total_return += stake * odds_val
                    
            net_profit = total_return - total_staked
            roi = (net_profit / total_staked) * 100 if total_staked > 0 else 0.0
            
            st.markdown("### 📊 Συνολικά Στατιστικά & Μπάνκα")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Ποσοστό Επιτυχίας", f"{win_rate:.1f}%", f"{correct} / {len(settled)}")
            col_m2.metric("Καθάρο Κέρδος/Ζημιά", f"{net_profit:+.2f} μ.")
            col_m3.metric("ROI (%)", f"{roi:+.2f}%")
            col_m4.metric("Συνολικό Ποντάρισμα", f"{total_staked:.2f} μ.")
            
            display_data = []
            for r in settled:
                is_won = evaluate_bet_win(r)
                try: stake_val = float(r.get("stake", 1.0))
                except ValueError: stake_val = 1.0
                try: odd_val = float(r.get("market_odds", 1.90))
                except ValueError: odd_val = 1.90
                
                profit_loss = (stake_val * odd_val - stake_val) if is_won else (-stake_val)
                bet_roi = (profit_loss / stake_val) * 100 if stake_val > 0 else 0.0
                
                display_data.append({
                    "Ημερομηνία": r.get("game_date", ""),
                    "Αγώνας": f"{r.get('home')} - {r.get('away')}",
                    "Επιλογή": r.get("market", ""),
                    "Απόδοση": f"{odd_val:.2f}",
                    "Σκόρ": f"{r.get('actual_home')}-{r.get('actual_away')}",
                    "Κατάσταση": "🟢 ΚΕΡΔΟΣ" if is_won else "🔴 ΧΑΜΕΝΟ",
                    "Κέρδος/Ζημιά": f"{profit_loss:+.2f} μ.",
                    "ROI (%)": f"{bet_roi:+.1f}%"
                })
            
            st.dataframe(display_data, use_container_width=True)
        else:
            st.info("Δεν υπάρχουν ακόμα ολοκληρωμένα στοιχήματα με καταχωρημένο σκόρ.")
    else:
        st.info("Δεν υπάρχουν ακόμη αποθηκευμένες προτάσεις στο ιστορικό.")
else:
    st.info("Το αρχείο ιστορικού θα δημιουργηθεί αυτόματα με την πρώτη αποθήκευση πρότασης.")
