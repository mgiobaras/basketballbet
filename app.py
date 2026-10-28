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

# --- UI INTERFACE ---
st.title("🏀 Basketball Monte Carlo Predictor")
st.markdown("Καλωσήρθατε στην εφαρμογή ανάλυσης αγώνων μπάσκετ με προσομοιώσεις Monte Carlo.")

# Sidebar for inputs
st.sidebar.header("⚙️ Ρυθμίσεις Αγώνα")
league_choice = st.sidebar.selectbox("Επιλέξτε διοργάνωση:", list(LEAGUES.keys()))

home_team = st.sidebar.text_input("Γηπεδούχος Ομάδα", "Olympiacos Piraeus")
away_team = st.sidebar.text_input("Φιλοξενώμενη Ομάδα", "Panathinaikos Athens")

home_mu = st.sidebar.number_input("Μ.Ο. Πόντων Υπέρ (Γηπεδούχος)", value=83.5)
home_std = st.sidebar.number_input("Standard Deviation (Γηπεδούχος)", value=7.5)

away_mu = st.sidebar.number_input("Μ.Ο. Πόντων Υπέρ (Φιλοξενώμενος)", value=78.5)
away_std = st.sidebar.number_input("Standard Deviation (Φιλοξενώμενος)", value=7.5)

line_ou = st.sidebar.number_input("Line Over/Under", value=160.5)
handicap = st.sidebar.number_input("Handicap (π.χ. -3.5)", value=-3.5)

if st.sidebar.button("🚀 Εκτέλεση Προσομοίωσης"):
    st.info(f"Εκτέλεση προσομοίωσης 500.000 επαναλήψεων για {home_team} vs {away_team}...")
    
    # Monte Carlo Logic
    np.random.seed(42)
    home_sims = np.random.normal(home_mu, home_std, ITERATIONS)
    away_sims = np.random.normal(away_mu, away_std, ITERATIONS)
    
    home_wins = np.sum(home_sims > away_sims)
    away_wins = np.sum(home_sims < away_sims)
    draws = ITERATIONS - home_wins - away_wins
    
    p_home = (home_wins / ITERATIONS) * 100
    p_away = (away_wins / ITERATIONS) * 100
    
    total_points = home_sims + away_sims
    p_over = (np.sum(total_points > line_ou) / ITERATIONS) * 100
    p_under = 100 - p_over
    
    hcp_diff = home_sims - away_sims
    p_hcp = (np.sum(hcp_diff > abs(handicap)) / ITERATIONS) * 100
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Νίκη {home_team}", f"{p_home:.1f}%")
    col2.metric("Ισοπαλία", f"{(draws/ITERATIONS)*100:.1f}%")
    col3.metric(f"Νίκη {away_team}", f"{p_away:.1f}%")
    
    st.success("Η προσομοίωση ολοκληρώθηκε με επιτυχία!")
    st.write(f"📊 **Over {line_ou} Pi[cite: 1]thanotita:** {p_over:.1f}%")
    st.write(f"📊 **Under {line_ou} Pithanotita:** {p_under:.1f}%")
else:
    st.warning("Πατήστε το κουμπί **'Εκτέλεση Προσομοίωσης'** στην πλαϊνή μπάρα για να τρέξετε τα αποτελέσματα.")
