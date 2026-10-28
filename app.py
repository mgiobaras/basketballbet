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
# STREAMLIT BASKETBALL MONTE CARLO WEB APP (FULL TEAMS DATABASE)
# ============================================================

st.set_page_config(page_title="Basketball Monte Carlo App", page_icon="🏀", layout="wide")

ITERATIONS = 500_000  
HISTORY_FILE = "basketball_predictions_history.csv"

# --- PLHRHS VASH DEDOMENWN OLES OI OMADES ---
TEAMS_DB = {
    # --- NBA (30 Omades) ---
    "Atlanta Hawks": {"avg_pf": 115.0, "std_pf": 9.5},
    "Boston Celtics": {"avg_pf": 118.0, "std_pf": 9.0},
    "Brooklyn Nets": {"avg_pf": 108.5, "std_pf": 9.0},
    "Charlotte Hornets": {"avg_pf": 107.0, "std_pf": 9.5},
    "Chicago Bulls": {"avg_pf": 111.0, "std_pf": 9.0},
    "Cleveland Cavaliers": {"avg_pf": 113.5, "std_pf": 8.5},
    "Dallas Mavericks": {"avg_pf": 116.5, "std_pf": 9.5},
    "Denver Nuggets": {"avg_pf": 114.5, "std_pf": 8.5},
    "Detroit Pistons": {"avg_pf": 108.0, "std_pf": 9.0},
    "Golden State Warriors": {"avg_pf": 116.0, "std_pf": 10.0},
    "Houston Rockets": {"avg_pf": 112.0, "std_pf": 8.5},
    "Indiana Pacers": {"avg_pf": 120.0, "std_pf": 10.5},
    "LA Clippers": {"avg_pf": 113.0, "std_pf": 8.5},
    "LA Lakers": {"avg_pf": 115.0, "std_pf": 9.5},
    "Memphis Grizzlies": {"avg_pf": 111.0, "std_pf": 9.0},
    "Miami Heat": {"avg_pf": 110.0, "std_pf": 8.0},
    "Milwaukee Bucks": {"avg_pf": 117.0, "std_pf": 9.5},
    "Minnesota Timberwolves": {"avg_pf": 112.5, "std_pf": 8.0},
    "New Orleans Pelicans": {"avg_pf": 113.0, "std_pf": 9.0},
    "New York Knicks": {"avg_pf": 112.5, "std_pf": 8.5},
    "Oklahoma City Thunder": {"avg_pf": 119.0, "std_pf": 9.0},
    "Orlando Magic": {"avg_pf": 110.5, "std_pf": 8.5},
    "Philadelphia 76ers": {"avg_pf": 114.0, "std_pf": 9.0},
    "Phoenix Suns": {"avg_pf": 113.0, "std_pf": 9.0},
    "Portland Trail Blazers": {"avg_pf": 107.5, "std_pf": 9.5},
    "Sacramento Kings": {"avg_pf": 115.5, "std_pf": 9.5},
    "San Antonio Spurs": {"avg_pf": 111.0, "std_pf": 10.0},
    "Toronto Raptors": {"avg_pf": 109.5, "std_pf": 9.0},
    "Utah Jazz": {"avg_pf": 111.5, "std_pf": 9.5},
    "Washington Wizards": {"avg_pf": 107.0, "std_pf": 10.0},

    # --- EUROLEAGUE (18 Omades) ---
    "Alba Berlin": {"avg_pf": 79.5, "std_pf": 9.0},
    "Anadolu Efes": {"avg_pf": 84.0, "std_pf": 9.0},
    "ASVEL": {"avg_pf": 78.5, "std_pf": 8.5},
    "Baskonia": {"avg_pf": 83.0, "std_pf": 9.5},
    "Bayern Munich": {"avg_pf": 80.0, "std_pf": 8.5},
    "Crvena Zvezda": {"avg_pf": 80.5, "std_pf": 8.0},
    "EA7 Emporio Armani Milan": {"avg_pf": 81.0, "std_pf": 8.0},
    "FC Barcelona": {"avg_pf": 82.0, "std_pf": 7.5},
    "Fenerbahce Beko": {"avg_pf": 83.0, "std_pf": 8.0},
    "Maccabi Playtika Tel Aviv": {"avg_pf": 85.5, "std_pf": 9.0},
    "Monaco": {"avg_pf": 82.5, "std_pf": 8.0},
    "Olympiacos Piraeus": {"avg_pf": 83.5, "std_pf": 7.5},
    "Panathinaikos AKTOR Athens": {"avg_pf": 85.0, "std_pf": 8.0},
    "Paris Basketball": {"avg_pf": 85.0, "std_pf": 9.5},
    "Partizan Mozzart Bet Belgrade": {"avg_pf": 82.0, "std_pf": 8.5},
    "Real Madrid": {"avg_pf": 86.5, "std_pf": 8.5},
    "Virtus Segafredo Bologna": {"avg_pf": 81.5, "std_pf": 8.0},
    "Zalgiris Kaunas": {"avg_pf": 78.0, "std_pf": 7.5},

    # --- ELLADA - BASKET LEAGUE (GStoL / GBL) ---
    "AEK Athens": {"avg_pf": 79.0, "std_pf": 8.5},
    "Aris": {"avg_pf": 75.5, "std_pf": 7.5},
    "Karditsa": {"avg_pf": 74.0, "std_pf": 8.0},
    "Kolossos Rhodes": {"avg_pf": 76.5, "std_pf": 8.0},
    "Lavrio": {"avg_pf": 75.0, "std_pf": 8.5},
    "Maroussi": {"avg_pf": 77.0, "std_pf": 8.5},
    "Panionios": {"avg_pf": 75.0, "std_pf": 8.0},
    "PAOK": {"avg_pf": 77.0, "std_pf": 8.0},
    "Peristeri": {"avg_pf": 76.0, "std_pf": 7.5},
    "Promitheas Patras": {"avg_pf": 78.0, "std_pf": 8.0},
    "Olympiacos Piraeus (GR)": {"avg_pf": 85.0, "std_pf": 7.5},
    "Panathinaikos Athens (GR)": {"avg_pf": 86.0, "std_pf": 8.0},
    
    # --- TURKISH & OTHER COMPETITIVE EUROPEAN TEAMS ---
    "Besiktas": {"avg_pf": 81.0, "std_pf": 8.5},
    "Galatasaray": {"avg_pf": 80.0, "std_pf": 8.5},
    "Fenerbahce (TR)": {"avg_pf": 83.5, "std_pf": 8.0},
    "Anadolu Efes (TR)": {"avg_pf": 84.5, "std_pf": 9.0},
    "Valencia Basket": {"avg_pf": 82.0, "std_pf": 8.0},
    "Unicaja Malaga": {"avg_pf": 84.0, "std_pf": 8.0}
}

LEAGUES_TEAMS = {
    "NBA": sorted([
        "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets", 
        "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets", 
        "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers", 
        "LA Clippers", "LA Lakers", "Memphis Grizzlies", "Miami Heat", "Milwaukee Bucks", 
        "Minnesota Timberwolves", "New Orleans Pelicans", "New York Knicks", 
        "Oklahoma City Thunder", "Orlando Magic", "Philadelphia 76ers", "Phoenix Suns", 
        "Portland Trail Blazers", "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors", 
        "Utah Jazz", "Washington Wizards"
    ]),
    "EuroLeague": sorted([
        "Alba Berlin", "Anadolu Efes", "ASVEL", "Baskonia", "Bayern Munich", 
        "Crvena Zvezda", "EA7 Emporio Armani Milan", "FC Barcelona", "Fenerbahce Beko", 
        "Maccabi Playtika Tel Aviv", "Monaco", "Olympiacos Piraeus", 
        "Panathinaikos AKTOR Athens", "Paris Basketball", "Partizan Mozzart Bet Belgrade", 
        "Real Madrid", "Virtus Segafredo Bologna", "Zalgiris Kaunas", "Besiktas", "Valencia Basket"
    ]),
    "Ellada - Basket League": sorted([
        "AEK Athens", "Aris", "Karditsa", "Kolossos Rhodes", "Lavrio", 
        "Maroussi", "Panionios", "PAOK", "Peristeri", "Promitheas Patras", 
        "Olympiacos Piraeus", "Panathinaikos Athens"
    ])
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Accept": "application/json"
})

# --- UI INTERFACE ---
st.title("🏀 Basketball Monte Carlo Predictor")
st.markdown("Kalsorhsate sthn efarmogh analyshs agwnwn mpasket me prosomoiwseis Monte Carlo.")

# Sidebar for inputs
st.sidebar.header("⚙️ Rythmiseis Agwna")
league_choice = st.sidebar.selectbox("Epilexte diorganwsh:", list(LEAGUES_TEAMS.keys()))

available_teams = LEAGUES_TEAMS[league_choice]

home_team = st.sidebar.selectbox("Gipedouxos Omada", available_teams, index=0)
away_team = st.sidebar.selectbox("Filoksenoumenh Omada", available_teams, index=1 if len(available_teams) > 1 else 0)

# Pairnoume ta stats apo th plhrh vash dedomenwn
home_stats = TEAMS_DB.get(home_team, {"avg_pf": 80.0, "std_pf": 8.0})
away_stats = TEAMS_DB.get(away_team, {"avg_pf": 80.0, "std_pf": 8.0})

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Aythmatopoiimena Stats")
st.sidebar.write(f"🏠 **{home_team}**")
st.sidebar.write(f"• M.O. Pontwn: `{home_stats['avg_pf']}`")
st.sidebar.write(f"• Std Deviation: `{home_stats['std_pf']}`")

st.sidebar.write(f"✈️ **{away_team}**")
st.sidebar.write(f"• M.O. Pontwn: `{away_stats['avg_pf']}`")
st.sidebar.write(f"• Std Deviation: `{away_stats['std_pf']}`")
st.sidebar.markdown("---")

home_mu = home_stats["avg_pf"]
home_std = home_stats["std_pf"]
away_mu = away_stats["avg_pf"]
away_std = away_stats["std_pf"]

line_ou = st.sidebar.number_input("Line Over/Under", value=160.5)
handicap = st.sidebar.number_input("Handicap (p.x. -3.5)", value=-3.5)

if st.sidebar.button("🚀 Ektelesh Prosomoiwshs"):
    st.info(f"Ektelesh prosomoiwshs 500.000 epanalypsewn gia {home_team} vs {away_team}...")
    
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
    col1.metric(f"Nikh {home_team}", f"{p_home:.1f}%")
    col2.metric("Isopalia", f"{(draws/ITERATIONS)*100:.1f}%")
    col3.metric(f"Nikh {away_team}", f"{p_away:.1f}%")
    
    st.success("H prosomoiwsh oloklhrwthike me epityxia!")
    st.write(f"📊 **Over {line_ou} Pithanotita:** {p_over:.1f}%")
    st.write(f"📊 **Under {line_ou} Pithanotita:** {p_under:.1f}%")
else:
    st.warning("Patiste to koumpi **'Ektelesh Prosomoiwshs'** sthn plainh mpara gia na trexete ta apotelesmata.")
