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
                'fixture_id', 'fixture_key', 'source_fixture_id', 'scope')


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
