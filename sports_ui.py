"""Light sports styling and history formatting, shared by the two Streamlit apps."""
from datetime import datetime
from math import isfinite
from urllib.parse import quote
from zoneinfo import ZoneInfo

import streamlit as st


def history_order(kickoff, probability):
    try:
        start = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
        timestamp = start.timestamp() if start.tzinfo else float('inf')
    except (ValueError, TypeError, AttributeError):
        timestamp = float('inf')
    try:
        chance = float(probability)
        chance = chance if isfinite(chance) and 0 <= chance <= 1 else -1
    except (ValueError, TypeError):
        chance = -1
    return timestamp, -chance


def history_time(kickoff):
    try:
        start = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
        return start.astimezone(ZoneInfo('Europe/Athens')).strftime('%d/%m/%Y %H:%M') if start.tzinfo else '—'
    except (ValueError, TypeError, AttributeError):
        return '—'


def apply_theme(sport):
    if sport == 'football':
        drawing = '''<rect x="30" y="30" width="580" height="360" rx="5"/>
        <path d="M320 30v360M30 130h100v160H30m580-160H510v160h100"/>
        <circle cx="320" cy="210" r="62"/><circle cx="320" cy="210" r="3"/>
        <path d="M30 170h36v80H30m580-80h-36v80h36"/>'''
        accent = '#168151'
    else:
        drawing = '''<rect x="30" y="30" width="580" height="360" rx="5"/>
        <path d="M320 30v360M30 135h120v150H30m580-150H490v150h120"/>
        <circle cx="320" cy="210" r="52"/><circle cx="150" cy="210" r="52"/>
        <circle cx="490" cy="210" r="52"/><path d="M65 178v64m510-64v64"/>
        <path d="M30 60h40a165 165 0 0 1 0 300H30m580-300h-40a165 165 0 0 0 0 300h40"/>'''
        accent = '#b96718'
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420"><g fill="none" stroke="{accent}" stroke-opacity=".16" stroke-width="2">{drawing}</g></svg>'
    background = 'url("data:image/svg+xml,'+quote(svg, safe='')+'")'
    st.markdown('''<style>
    [data-testid="stAppViewContainer"] {
        background-color: #fff;
        background-image: var(--sports-background);
        background-size: 640px 420px;
        color: #17352b;
    }
    [data-testid="stHeader"] {background: rgba(255,255,255,.96);}
    [data-testid="stSidebar"] {background: #f2f8f4; border-right: 1px solid #dcece2;}
    .stMainBlockContainer {
        max-width: 1180px; padding: 2rem 2rem 3rem;
        margin-top: 1rem; margin-bottom: 1rem;
        background: rgba(255,255,255,.78); border: 1px solid #e3eee7;
        border-radius: 22px; box-shadow: 0 12px 40px #163c2710;
    }
    h1, h2, h3 {color: #145c3a; letter-spacing: -.025em;}
    [data-testid="stCaptionContainer"] p {color: #526b5e;}
    h1 {font-size: clamp(1.6rem, 4.5vw, 2.35rem) !important;}
    [data-testid="stTabs"] [role="tab"] {font-weight: 600;}
    [data-testid="stTabs"] [aria-selected="true"] {color: #16794c;}
    [data-testid="stMetric"] {
        background: #f8fbf9; border: 1px solid #e0ece4;
        border-radius: 14px; padding: .75rem .9rem;
    }
    [data-testid="stMetricValue"] {font-size: clamp(1.25rem, 3.8vw, 1.85rem);}
    [data-testid="stMetricLabel"] p {font-size: .85rem;}
    .st-key-history_counts [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important; gap: .6rem !important; align-items: stretch;
    }
    .st-key-history_counts [data-testid="stColumn"] {
        min-width: 0 !important; width: 0 !important; flex: 1 1 0 !important;
    }
    .st-key-history_counts [data-testid="stMetric"] {padding: .75rem .5rem; text-align: center;}
    .st-key-history_counts [data-testid="stMetricLabel"] {display: flex; justify-content: center; width: 100%;}
    .st-key-history_counts [data-testid="stMetricLabel"] p {
        font-size: clamp(.78rem, 3.2vw, .9rem); white-space: nowrap;
        overflow: visible; text-overflow: clip;
    }
    .st-key-history_counts [data-testid="stMetricValue"] {
        font-size: clamp(1.45rem, 5.5vw, 2rem); font-weight: 700;
    }
    .st-key-history_counts [data-testid="stColumn"]:nth-child(1) [data-testid="stMetric"] {
        background: #edf8f0; border-color: #c8e7d2; color: #116739;
    }
    .st-key-history_counts [data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] {
        background: #fff2f1; border-color: #f0d5d2; color: #a63131;
    }
    .st-key-history_counts [data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] {
        background: #fff8e9; border-color: #ebdfbc; color: #805b13;
    }
    [data-testid="stDataFrame"] {border: 1px solid #dcebe2; border-radius: 12px; overflow: hidden;}
    .stButton button, .stDownloadButton button {border-radius: 10px;}
    button[kind="primary"] {box-shadow: 0 3px 12px #16815120;}
    @media (max-width: 640px) {
        .stMainBlockContainer {padding: 1.2rem .8rem 2rem; margin-top: .25rem; border-radius: 16px;}
        .st-key-history_counts [data-testid="stHorizontalBlock"] {gap: .35rem !important;}
        .st-key-history_counts [data-testid="stMetric"] {padding: .65rem .2rem; border-radius: 10px;}
    }
    </style>'''.replace('var(--sports-background)', background), unsafe_allow_html=True)
