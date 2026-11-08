"""Private analysis snapshots, independent of the user's selected bets."""
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4


SQLITE_SCHEMA = '''CREATE TABLE IF NOT EXISTS app_prediction_log (
    id TEXT PRIMARY KEY, sport TEXT NOT NULL, captured_at TEXT NOT NULL,
    payload TEXT NOT NULL);'''

QUOTE_FIELDS = ('market', 'line', 'odds', 'source', 'bookmaker', 'bookmaker_id',
                'provider', 'source_url', 'price_kind', 'observed_at', 'updated_at',
                'fixture_id', 'fixture_key', 'source_fixture_id', 'source_market_id', 'scope')


def snapshot(sport, fixture, model, markets, absences, app_version, now=None, inputs=None):
    now = now or datetime.now(timezone.utc)
    kickoff = fixture['fixture']['date'] if sport == 'football' else fixture['kickoff']
    status = fixture['fixture']['status']['short'] if sport == 'football' else fixture['status']
    payload = dict(schema_version=1, fixture=fixture, model=model, markets=markets,
                   absences=absences, app_version=app_version, inputs=inputs,
                   eligible_for_evaluation=status == 'NS' and now < datetime.fromisoformat(kickoff.replace('Z', '+00:00')))
    # Freeze nested model/quote inputs before later UI changes can mutate them.
    return json.loads(json.dumps(dict(id=uuid4().hex, sport=sport,
        captured_at=now.isoformat(), payload=payload), ensure_ascii=False, allow_nan=False))


def quote_snapshot(quote):
    return {k: quote[k] for k in QUOTE_FIELDS if k in quote} if quote else None


def flush_predictions(store, state, sport):
    """Retry the same immutable ID after failures; never mix logs with bets."""
    pending = state.get('pending_prediction_log:'+sport, {})
    for key, packet in list(pending.items()):
        try:
            store.record_prediction(packet)
        except (RuntimeError, ValueError, OSError, sqlite3.Error):
            return ('Δεν αποθηκεύτηκε ακόμη η καταγραφή ανάλυσης. Αν δεν έχει γίνει η εγκατάσταση, '
                    'τρέξε το database/enable_prediction_logging.sql στο Supabase. '
                    'Θα ξαναδοκιμάσει όσο παραμένει ανοιχτή αυτή η συνεδρία. '
                    'Οι προβλέψεις και το ιστορικό επιλογών παραμένουν διαθέσιμα.')
        del pending[key]
    state['pending_prediction_log:'+sport] = pending
    return None


def queue_prediction(state, packet):
    key = 'pending_prediction_log:'+packet['sport']
    pending = state.get(key, {})
    pending[packet['id']] = packet
    state[key] = pending


def analysis_export(st, store, sport):
    """Owner-requested download; never render the private prediction records."""
    key = 'analysis_export:'+sport
    with st.expander('Πλήρης καταγραφή για ανάλυση', expanded=False):
        st.caption('Αρχείο με όλους τους καταγεγραμμένους υπολογισμούς και το ιστορικό επιλογών.')
        if st.button('Ετοιμασία αρχείου ανάλυσης', key='prepare_analysis:'+sport):
            st.session_state.pop(key, None)
            try:
                predictions = store.list_predictions(sport)
                bets = store.list()
                if not isinstance(predictions, list) or not isinstance(bets, list):
                    raise ValueError('Δεν επιβεβαιώθηκε η ανάγνωση της πλήρους καταγραφής.')
                known = {p['id'] for p in predictions}
                pending = [p for p in st.session_state.get('pending_prediction_log:'+sport, {}).values()
                           if p['id'] not in known]
                packet = dict(schema_version=1, sport=sport, exported_at=datetime.now(timezone.utc).isoformat(),
                              selected_bets=bets, prediction_log=predictions, pending_prediction_log=pending)
                st.session_state[key] = json.dumps(packet, ensure_ascii=False, allow_nan=False, indent=2)
                if not predictions:
                    st.info('Δεν βρέθηκαν αποθηκευμένοι υπολογισμοί στην καταγραφή της βάσης.')
            except (RuntimeError, ValueError, OSError, sqlite3.Error) as error:
                st.error('Δεν ετοιμάστηκε το αρχείο ανάλυσης: '+str(error))
        if key in st.session_state:
            st.download_button('Λήψη πλήρους αρχείου ανάλυσης JSON', st.session_state[key],
                               sport+'_analysis_backup.json', 'application/json', key='download_analysis:'+sport)
