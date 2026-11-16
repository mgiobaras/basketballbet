"""BasketballBet: automatic real data, observed last-ten model and persistent bets."""
import csv
import hashlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

from basketball_data import BasketballData, DataError, LEAGUES
from basketball_model import MARKETS, analyse, distribution, instant, recent_games
from basketball_store import Store, SupabaseStore, StorageError
from personal_access import require_personal_access
from sports_ui import apply_theme, history_order, history_time
from prediction_log import snapshot, quote_snapshot, flush_predictions, analysis_export, log_forecast
from paf_browser import browser_quotes
from recommendations import apply_policy, show_recommendation
from player_absences import absence_inputs
from alternative_lines import LINE_MARKETS, VERSION as ALTERNATIVE_VERSION, select_alternatives, alternative_policy

ROOT = Path(__file__).resolve().parent
APP_VERSION = 'BASKET-2026-11-16-ALTERNATIVE-LINES1'
st.set_page_config(page_title='BasketballBet', page_icon='🏀', layout='wide')
apply_theme('basketball')
st.title('🏀 BasketballBet')
st.caption(f'Έκδοση {APP_VERSION} · app.py')
st.caption('Έως 10 πιο πρόσφατοι πραγματικοί αγώνες ανά ομάδα · 1 μονάδα ανά επιλογή · αποδόσεις ≥1,50. Ο στόχος 70% και η κερδοφορία δεν έχουν επιβεβαιωθεί.')


def setting(name, default=''):
    if name in os.environ:
        return os.environ[name]
    try:
        return st.secrets.get(name, default)
    except st.errors.StreamlitSecretNotFoundError:
        return default


def market_labels(fixture):
    home, away = [fixture['teams'][side]['name'] for side in ['home', 'away']]
    return dict(MARKETS, home=f'Νίκη {home}', away=f'Νίκη {away}',
                handicap_home=f'Handicap {home}', handicap_away=f'Handicap {away}')


url, key = setting('SUPABASE_URL'), setting('SUPABASE_SERVICE_ROLE_KEY')
remote = bool(url or key or str(setting('REQUIRE_REMOTE_DB', 'false')).lower() == 'true')
require_personal_access(st, setting('APP_PASSWORD'), required=remote)
try:
    if remote:
        if not url or not key:
            raise StorageError('Συμπλήρωσε SUPABASE_URL και SUPABASE_SERVICE_ROLE_KEY στα Secrets. Δεν ενεργοποιήθηκε τοπική αποθήκευση.')
        store = SupabaseStore(url, key)
        store.list()
        st.sidebar.success('Αποθήκευση: μόνιμη βάση Supabase')
    else:
        store = Store(os.environ.get('BET_DB_PATH', str(ROOT/'data/basketball.sqlite3')))
        st.sidebar.warning('Τοπική SQLite. Για μόνιμο ιστορικό στο Streamlit Cloud σύνδεσε Supabase σύμφωνα με το README.')
    legacy = ROOT/'basketball_predictions_history.csv'
    store.preserve_legacy(legacy)
except (StorageError, OSError, ValueError) as error:
    st.error(str(error))
    st.stop()

log_warning = flush_predictions(store, st.session_state, 'basketball')
if log_warning:
    st.warning(log_warning)
data = BasketballData(store, odds_key=setting('ODDS_API_KEY'))
match_tab, history_tab = st.tabs(['Αγώνας & επιλογές', 'Ιστορικό & αποτελέσματα'])
with match_tab:
    league_name = st.sidebar.selectbox('Διοργάνωση', list(LEAGUES))
    league = LEAGUES[league_name]
    day = st.sidebar.date_input('Ημερομηνία αγώνα', datetime.now(ZoneInfo('Europe/Athens')).date())
    st.info('Αυτόματη αναζήτηση σε επόμενη διαθέσιμη πηγή όταν λείπουν στοιχεία. Δεν επιλέγεις πηγή.')
    try:
        games = data.fixtures(league, day)
    except StorageError as error:
        games = []
        st.error(str(error))
    if not games:
        st.write('Δεν ανακτήθηκαν αγώνες για αυτή την ημέρα. Δεν δημιουργούνται υποθετικές ομάδες ή σκορ.')
    else:
        fixture_keys = [g['key'] for g in games]
        picker_key = f'fixture_picker_{league}_{day.isoformat()}'
        if st.session_state.get(picker_key) not in fixture_keys:
            st.session_state.pop(picker_key, None)
        selected = st.selectbox('Αγώνας', fixture_keys, key=picker_key,
                                format_func=lambda k: next(g['teams']['home']['name']+' — '+g['teams']['away']['name'] for g in games if g['key'] == k))
        game = next(g for g in games if g['key'] == selected)
        game_labels = market_labels(game)
        st.caption(f"Έναρξη: {instant(game['kickoff']).astimezone(ZoneInfo('Europe/Athens')).strftime('%d/%m/%Y %H:%M')} · {game['status']}")
        refresh_key = 'refresh:'+game['key']
        if st.button('Ανανέωση αποδόσεων'):
            st.session_state[refresh_key] = st.session_state.get(refresh_key, 0)+1
        try:
            quotes, errors = data.quotes(game, st.session_state.get(refresh_key, 0))
            data.errors.extend(errors)
            failure = data.paf.diagnostics.get('failed_request', {})
            if 'HTTP 410' in failure.get('error', '') and len({q['market'] for q in quotes}) < 6:
                browser_found, browser_notes, diagnostic = browser_quotes(st, store, game, st.session_state.get(refresh_key, 0))
                quotes.extend(q for q in browser_found if not any(old['market'] == q['market'] for old in quotes))
                data.errors.extend(browser_notes)
                data.paf.diagnostics['browser'] = diagnostic
                if browser_found:
                    st.caption('Αποδόσεις Paf: αυτόματη λήψη από τον browser και έλεγχος αγώνα από την εφαρμογή.')
        except StorageError as error:
            quotes = []
            st.error(str(error))
        by_market = {q['market']: q for q in quotes}
        st.subheader('Αποδόσεις αρχικών γραμμών')
        st.caption('Οι αγορές αφορούν τελικό σκορ μαζί με παράταση. Κάθε τιμή κρατά το δικό της line, εταιρεία και πηγή. Τα δημοσιευμένα snapshots μπορεί να έχουν αλλάξει στη στοιχηματική.')
        manual = st.checkbox('Χειροκίνητη καταχώριση / διόρθωση', key='manual:'+game['key'])
        company = st.text_input('Εταιρεία χειροκίνητων αποδόσεων', max_chars=100, key='company:'+game['key']).strip() if manual else ''
        offers = {}
        card_labels = {'home': '1', 'away': '2', 'handicap_home': 'Handicap 1',
                       'handicap_away': 'Handicap 2', 'over': 'Over', 'under': 'Under'}
        with st.container(key='odds_grid'):
            for row in [('home', 'away'), ('handicap_home', 'handicap_away'), ('over', 'under')]:
                for column, market in zip(st.columns(2), row):
                    with column, st.container(border=True, key='market_'+market):
                        q, label = by_market.get(market), game_labels[market]
                        if manual:
                            st.write(card_labels[market])
                            line = st.number_input('Line '+label, value=None, step=.5, key=f'line:{game["key"]}:{market}') if market not in {'home', 'away'} else None
                            price = st.number_input('Απόδοση '+label, min_value=1.01, value=None, step=.01, key=f'price:{game["key"]}:{market}')
                            if price is not None and (market in {'home', 'away'} or line is not None):
                                offers[market] = {'fixture_key': game['key'], 'market': market, 'line': line, 'odds': price,
                                                  'source': 'Χειροκίνητη καταχώριση', 'bookmaker': company, 'price_kind': 'manual',
                                                  'scope': 'including_overtime', 'observed_at': datetime.now(timezone.utc).isoformat()}
                        else:
                            line_label = '' if not q or q['line'] is None else f" {q['line']:+g}" if market.startswith('handicap') else f" {q['line']:g}"
                            st.metric(card_labels[market]+line_label, f"{q['odds']:.2f}" if q else '—',
                                      help=f"{q['source']} / {q.get('bookmaker') or q.get('bookmaker_id')}" if q else None)
                            if q:
                                offers[market] = q
                        if market in {'home', 'away', 'handicap_home', 'handicap_away'}:
                            side = 'home' if market in {'home', 'handicap_home'} else 'away'
                            st.caption(game['teams'][side]['name'])
        if not manual and offers:
            with st.expander('Πηγές αποδόσεων'):
                for market, q in offers.items():
                    company_label = q.get('bookmaker') or f"πάροχος ID {q.get('bookmaker_id')} (δεν δηλώθηκε εταιρεία)"
                    st.caption(f"{game_labels[market]} · {q['source']} / {company_label} · {q['price_kind']} · λήψη {q['observed_at']}")
        if not offers:
            st.info('Δεν βρέθηκαν επιβεβαιωμένες τιμές με τις αντίστοιχες γραμμές. Τα κενά δεν αντικαθίστανται με 1,90 ή υποθετικά lines.')
            if league in {'euroleague', 'nba'} and not setting('ODDS_API_KEY'):
                st.info('Εναλλακτική αυτόματη πηγή: ενεργοποίησε το The Odds API προσθέτοντας ODDS_API_KEY στα Secrets του Streamlit. Διαθέτει δωρεάν πρόγραμμα με όριο χρήσης.')
        absences = absence_inputs(st, data, game)
        st.session_state.pop('model_mode', None)
        st.caption('Μοντέλο: Κλασικό · πραγματικοί πρόσφατοι πόντοι υπέρ/κατά, χωρίς νεότερες προσαρμογές.')
        easier_lines = st.checkbox('Ευκολότερες γραμμές κοντά στο 1,70', value=True, key='easier_lines:'+game['key'])
        if easier_lines:
            st.caption('Αναζήτηση πραγματικών εναλλακτικών Paf: 2–5 πόντοι ευκολότερα, απόδοση 1,60–1,80 (προτίμηση 1,70) και εκτιμώμενο EV ≥3%. Αν δεν βρεθεί κατάλληλη τιμή, παραμένει η αρχική. Η αρχική και η εναλλακτική καταγράφονται χωριστά για αξιολόγηση.')
        model_key = 'analysis:'+game['key']+':classic-restored1'
        if st.button('Υπολογισμός με πραγματικά δεδομένα', type='primary'):
            st.session_state.pop(model_key, None)
            try:
                with st.spinner('Αναζήτηση έως 10 πιο πρόσφατων πραγματικών αγώνων ανά ομάδα…'):
                    history = data.history(game)
                    model = analyse(game, history)
                if model:
                    model['base_model_version'] = model['model_version']
                    model['model_version'] = 'basket-classic-restored-v1'
                    model['calculated_at'] = datetime.now(timezone.utc).isoformat()
                    st.session_state[model_key] = model
                    st.session_state[model_key+':inputs'] = {side: recent_games(history, game, side) for side in ['home', 'away']}
                else:
                    counts = {game['teams'][s]['name']: len(recent_games(history, game, s)) for s in ['home', 'away']}
                    st.warning(f'Αποχή: χρειάζεται τουλάχιστον 1 ολοκληρωμένος αγώνας ανά ομάδα πριν από τον επιλεγμένο αγώνα. Διαθέσιμοι: {counts}.')
            except (DataError, StorageError, ValueError) as error:
                st.error(str(error))
        model = st.session_state.get(model_key)
        if model:
            markets = {}
            for market in MARKETS:
                offer = offers.get(market)
                line = offer.get('line') if offer else None
                markets[market] = {'line': line, 'probability': distribution(model, market, line),
                                   'raw_probability': distribution(model, market, line),
                                   'quote': quote_snapshot(offer)}
            policy = apply_policy('basketball', game, markets)
            model = dict(model, recommendation_policy=policy)
            warning = log_forecast(store, st.session_state, snapshot('basketball', game, model, markets, absences, APP_VERSION,
                inputs=st.session_state.get(model_key+':inputs')), model_key)
            if warning and not log_warning:
                st.warning(warning)
            changes = {}
            if easier_lines and LINE_MARKETS.intersection(offers):
                try:
                    alternate_quotes, notes = data.alternative_quotes(game, st.session_state.get(refresh_key, 0))
                    failure = data.alternative_diagnostics.get('failed_request', {})
                    if 'HTTP 410' in failure.get('error', ''):
                        browser_found, browser_notes, diagnostic = browser_quotes(
                            st, store, game, st.session_state.get(refresh_key, 0), all_lines=True)
                        alternate_quotes = browser_found
                        notes.extend(browser_notes)
                        data.alternative_diagnostics = diagnostic
                    data.errors.extend('Εναλλακτικές γραμμές: '+note for note in notes)
                except StorageError as error:
                    alternate_quotes = []
                    st.warning(str(error))
                offers, changes = select_alternatives(game, model, offers, alternate_quotes)
                if changes:
                    for market in changes:
                        quote = offers[market]
                        probability = distribution(model, market, quote['line'])
                        markets[market] = {'line': quote['line'], 'probability': probability,
                                           'raw_probability': probability, 'quote': quote_snapshot(quote)}
                    policy = alternative_policy(game, markets)
                    model = dict(model, recommendation_policy=policy,
                                 alternative_lines={'version': ALTERNATIVE_VERSION, 'changes': changes})
                    warning = log_forecast(store, st.session_state, snapshot('basketball', game, model, markets, absences,
                        APP_VERSION, inputs=st.session_state.get(model_key+':inputs')), model_key+':alternatives')
                    if warning and not log_warning:
                        st.warning(warning)
                    st.subheader('Ευκολότερες γραμμές για αποθήκευση')
                    st.dataframe([{'Αγορά': game_labels[m], 'Αρχικό line': c['original_line'],
                                   'Αρχική απόδοση': c['original_odds'], 'Νέο line': c['selected_line'],
                                   'Νέα απόδοση': c['selected_odds'], 'Εταιρεία': offers[m]['bookmaker'],
                                   'Πιθανότητα': f"{c['selected_probability']['win']:.1%}"}
                                  for m, c in sorted(changes.items())], hide_index=True)
                    st.caption('Οι υπολογισμοί και η αποθήκευση παρακάτω χρησιμοποιούν αυτές τις νέες γραμμές. Κλείσε την επιλογή «Ευκολότερες γραμμές» για τις αρχικές.')
                else:
                    st.caption('Δεν βρέθηκε κατάλληλη ευκολότερη γραμμή κοντά στο 1,70. Οι αρχικές γραμμές παραμένουν ενεργές.')
            counts = model['history_counts']
            st.caption('Ιστορικό που χρησιμοποιήθηκε: '+' · '.join(
                f"{game['teams'][side]['name']}: {counts[side]}/10 αγώνες" for side in ['home', 'away']))
            if min(counts.values()) < 10:
                st.warning('Μικρότερο δείγμα: χρησιμοποιούνται οι διαθέσιμοι αγώνες, με όριο τους 10 πιο πρόσφατους ανά ομάδα.')
            st.metric('Αναμενόμενοι πόντοι μοντέλου', f"{model['mu_home']:.1f} — {model['mu_away']:.1f}")
            st.caption('Κλασική Normal προσέγγιση από πραγματικούς πόντους υπέρ/κατά, με βάρη ημιζωής 90 ημερών. Χωρίς προσαρμογές κατοχών, αντιπάλων ή νεότερη μεταβολή αβεβαιότητας.')
            st.caption('Πηγές ιστορικού: '+', '.join(model['input_sources']))
            recommendation_labels = dict(game_labels)
            recommended = policy['recommended_market']
            if recommended in offers and offers[recommended]['line'] is not None:
                line = offers[recommended]['line']
                recommendation_labels[recommended] += f' {line:+g}' if recommended.startswith('handicap') else f' {line:g}'
            show_recommendation(st, policy, recommendation_labels)
            st.subheader('Όλοι οι υπολογισμοί')
            rows, distributions = [], {}
            for market, q in offers.items():
                p = markets[market]['probability']
                if p is None:
                    continue
                distributions[market] = p
                ev = p['win']*(q['odds']-1)-p['loss']
                rows.append({'Αγορά': game_labels[market], 'Line': q['line'], 'Απόδοση': q['odds'],
                             'Πιθανότητα νίκης': f"{p['win']:.1%}", 'Επιστροφή': f"{p['push']:.1%}", 'Εκτιμώμενο EV': f'{ev:+.1%}'})
            if rows:
                st.dataframe(rows, hide_index=True)
            else:
                st.info('Δεν υπάρχει ακόμη εκτιμήσιμη αβεβαιότητα ή έγκυρη γραμμή για αυτές τις αγορές. Τα διαθέσιμα ιστορικά σκορ δεν συμπληρώνονται με υποθετικές τιμές.')
            eligible = [m for m in distributions if offers[m]['odds'] >= 1.5]
            # A quote/line switch clears selections before saving a different offer.
            selection_key = hashlib.sha256(json.dumps({m: [offers[m].get(k) for k in
                ['line', 'odds', 'bookmaker', 'source', 'source_market_id']] for m in eligible}, sort_keys=True).encode()).hexdigest()[:16]
            chosen = st.multiselect('Επιλογές για αποθήκευση — 1 μονάδα η καθεμία', eligible,
                format_func=lambda m: game_labels[m]+(f" {offers[m]['line']:+g}" if m.startswith('handicap') else f" {offers[m]['line']:g}" if m in {'over', 'under'} else '')
                    +f" · {offers[m]['odds']:.2f}"+(' · εναλλακτική' if m in changes else ''), key='choices:'+game['key']+':'+selection_key)
            st.caption('Αν αλλάξει η γραμμή, η απόδοση ή η εταιρεία, επίλεξε ξανά το σημείο πριν από την αποθήκευση.')
            can_save = game['status'] == 'NS' and instant(game['kickoff']) > datetime.now(timezone.utc) and (not manual or bool(company))
            if st.button('Αποθήκευση επιλογών', disabled=not chosen or not can_save):
                try:
                    count = sum(store.save(game, offers[m], distributions[m], absences, model) for m in chosen)
                    st.success(f'Αποθηκεύτηκαν {count} νέες επιλογές. Οι αρχικές τιμές και γραμμές δεν αλλάζουν σε διπλή αποθήκευση.')
                except (ValueError, StorageError) as error:
                    st.error(str(error))
    if data.errors:
        with st.expander('Κατάσταση πηγών'):
            for error in dict.fromkeys(data.errors):
                st.write(error)
            if league == 'greece' and data.adapters['esake'].diagnostics:
                st.download_button('Λήψη διαγνωστικών ΕΣΑΚΕ',
                                   json.dumps(data.adapters['esake'].diagnostics, ensure_ascii=False, indent=2),
                                   'esake_diagnostics.json', 'application/json')
            if data.paf.diagnostics:
                st.download_button('Λήψη διαγνωστικών Paf',
                                   json.dumps(data.paf.diagnostics, ensure_ascii=False, indent=2),
                                   'paf_diagnostics.json', 'application/json')
            if data.alternative_diagnostics:
                st.download_button('Λήψη διαγνωστικών εναλλακτικών γραμμών',
                                   json.dumps(data.alternative_diagnostics, ensure_ascii=False, indent=2),
                                   'alternative_lines_diagnostics.json', 'application/json')

with history_tab:
    st.subheader('Ιστορικό & αποτελέσματα')
    auto_refresh = st.checkbox('Αυτόματη ενημέρωση αποτελεσμάτων όταν χρησιμοποιώ την εφαρμογή', value=True)
    force = st.button('Ενημέρωση αποτελεσμάτων')
    try:
        records = store.list()
        if auto_refresh or force:
            pending = {r['fixture']['key']: r['fixture'] for r in records if r['status'] == 'pending'
                       and instant(r['fixture']['kickoff']) < datetime.now(timezone.utc)}
            for fixture in pending.values():
                result = store.cached('result:'+fixture['key']+(':'+str(datetime.now(timezone.utc).timestamp()) if force else ''), lambda f=fixture: data.result(f), 120)
                if result:
                    store.settle(result)
            records = store.list()
        all_records = records
        labels = dict(LEAGUES)
        for r in all_records:
            code = r['fixture']['league']
            if code not in labels.values():
                labels[code] = code
        options = ['Σύνολο', *labels]
        selected_league = st.session_state.get('history_league', 'Σύνολο')
        if selected_league not in options:
            st.session_state['history_league'] = 'Σύνολο'
        selected_league = st.selectbox('Προβολή ιστορικού ανά διοργάνωση', options, key='history_league')
        records = all_records if selected_league == 'Σύνολο' else [r for r in all_records if r['fixture']['league'] == labels[selected_league]]
        history_days = [instant(r['fixture']['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date() for r in all_records]
        history_today = datetime.now(ZoneInfo('Europe/Athens')).date()
        date_columns = st.columns(2)
        history_from = date_columns[0].date_input('Από', min(history_days, default=history_today),
                                                 format='DD/MM/YYYY', key='history_from')
        history_to = date_columns[1].date_input('Έως', max(history_days, default=history_today),
                                               format='DD/MM/YYYY', key='history_to')
        st.caption('Το διάστημα περιλαμβάνει και τις δύο ημερομηνίες, βάσει έναρξης αγώνα σε ώρα Ελλάδας. Ο πίνακας και το CSV αφορούν το επιλεγμένο διάστημα· το αντίγραφο JSON περιλαμβάνει ολόκληρο το ιστορικό.')
        if history_from is None or history_to is None:
            st.warning('Επίλεξε και τις δύο ημερομηνίες για να υπολογιστούν τα στατιστικά.')
        elif history_from > history_to:
            st.warning('Η ημερομηνία «Από» πρέπει να είναι πριν ή ίδια με την «Έως».')
        else:
            records = [r for r in records if history_from <= instant(r['fixture']['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date() <= history_to]
            records = sorted(records, key=lambda r: history_order(r['fixture'].get('kickoff'), r.get('probability', {}).get('win')))
            st.caption(f'Στατιστικά και ιστορικό: {selected_league} · {history_from:%d/%m/%Y}–{history_to:%d/%m/%Y}')
            settled = [r for r in records if r['status'] in {'won', 'lost', 'push'}]
            decided = [r for r in settled if r['status'] in {'won', 'lost'}]
            wins = sum(r['status'] == 'won' for r in decided)
            with st.container(key='history_counts'):
                counts = st.columns(3)
                counts[0].metric('Κερδισμένα', wins)
                counts[1].metric('Χαμένα', len(decided)-wins)
                counts[2].metric('Εκκρεμή', sum(r['status'] == 'pending' for r in records))
            st.caption(f'Επιστροφές: {len(settled)-len(decided)} · εξαιρούνται από το ποσοστό επιτυχίας.')
            profit = sum(r['profit'] for r in settled)
            stake = sum(r['stake'] for r in settled)
            cols = st.columns(4)
            cols[0].metric('Επιτυχία (χωρίς επιστροφές)', f'{wins/len(decided):.1%}' if decided else '—')
            cols[1].metric('Καθαρό κέρδος', f'{profit:+.2f} μονάδες')
            cols[2].metric('ROI', f'{profit/stake:+.1%}' if stake else '—')
            cols[3].metric('Δείγμα', f'{len(decided)} κρίθηκαν · {len(settled)-len(decided)} επιστροφές')
            if records:
                display = [{'Ημερομηνία': history_time(r['fixture']['kickoff']),
                            'Αγώνας': r['fixture']['teams']['home']['name']+' — '+r['fixture']['teams']['away']['name'],
                            'Αγορά': market_labels(r['fixture'])[r['market']],
                            'Μοντέλο': r.get('model', {}).get('model_version', '—'),
                            'Αρχική πιθανότητα μοντέλου': f"{r['probability']['win']:.1%}" if r.get('probability', {}).get('win') is not None else '—', 'Line': r['line'],
                            'Απόδοση': r['odds'], 'Μονάδες': r['stake'],
                            'Κατάσταση': {'won': 'Κερδισμένο', 'lost': 'Χαμένο', 'pending': 'Εκκρεμεί', 'push': 'Επιστροφή'}.get(r['status'], r['status']),
                            'Σκορ με παράταση': r['score'],
                            'Κέρδος': r['profit'], 'Πηγή': r['quote']['source'], 'Εταιρεία': r['quote'].get('bookmaker')} for r in records]
                st.dataframe(display, hide_index=True, width='stretch', column_config={
                    'Αρχική πιθανότητα μοντέλου': st.column_config.TextColumn('Ποσοστό', help='Η αρχική πιθανότητα που αποθηκεύτηκε με την επιλογή.'),
                    'Ημερομηνία': st.column_config.TextColumn('Έναρξη (Ελλάδα)')})
                buffer = io.StringIO()
                writer = csv.DictWriter(buffer, fieldnames=list(display[0]))
                writer.writeheader(); writer.writerows(display)
                st.download_button('Εξαγωγή CSV επιλεγμένου διαστήματος', buffer.getvalue().encode('utf-8-sig'), f'basketball_bets_{history_from.isoformat()}_{history_to.isoformat()}.csv', 'text/csv')
            else:
                st.write('Δεν υπάρχουν αποθηκευμένες επιλογές για τη διοργάνωση και το επιλεγμένο διάστημα.')
        if all_records:
            st.download_button('Αντίγραφο όλων των επιλογών JSON', json.dumps(all_records, ensure_ascii=False, indent=2), 'basketball_backup.json', 'application/json')
        analysis_export(st, store, 'basketball')
    except (StorageError, DataError, ValueError) as error:
        st.error(str(error))
    st.caption('Εκκαθάριση μόνο σε επιβεβαιωμένο τελικό σκορ μαζί με παράταση. Ισοπαλία στην ακέραια γραμμή σημαίνει επιστροφή. Άγνωστα αποτελέσματα παραμένουν εκκρεμή. Η ενημέρωση δεν εκτελείται όταν η εφαρμογή είναι κλειστή.')
    if legacy.exists():
        st.info('Το παλιό CSV διατηρείται χωριστά· δεν μετατρέπεται σε επαληθευμένο νέο ιστορικό.')
        st.download_button('Λήψη αρχικού παλιού ιστορικού', legacy.read_bytes(), 'basketball_predictions_history.csv', 'text/csv')
