"""BasketballBet: automatic real data, observed last-ten model and persistent bets."""
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

from basketball_data import BasketballData, DataError, LEAGUES
from basketball_model import MARKETS, analyse, distribution, instant, recent_games
from basketball_pace import analyse_pace, boxscores
from basketball_store import Store, SupabaseStore, StorageError
from personal_access import require_personal_access
from sports_ui import apply_theme, history_order, history_time

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='BasketballBet', page_icon='🏀', layout='wide')
apply_theme('basketball')
st.title('🏀 BasketballBet')
st.caption('Έκδοση BASKET-2026-11-06-GREECE1 · app.py')
st.caption('Τελευταίοι 10 πραγματικοί αγώνες · 1 μονάδα ανά επιλογή · αποδόσεις ≥1,50. Ο στόχος 70% και η κερδοφορία δεν έχουν επιβεβαιωθεί.')


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

data = BasketballData(store, odds_key=setting('ODDS_API_KEY'))
match_tab, history_tab = st.tabs(['Αγώνας & επιλογές', 'Ιστορικό & αποτελέσματα'])
with match_tab:
    league_name = st.sidebar.selectbox('Διοργάνωση', list(LEAGUES))
    league = LEAGUES[league_name]
    day = st.sidebar.date_input('Ημερομηνία αγώνα', datetime.now(ZoneInfo('Europe/Athens')).date())
    st.info('Αυτόματη αναζήτηση σε επόμενη διαθέσιμη πηγή όταν λείπουν στοιχεία. Δεν επιλέγεις πηγή. Οι απουσίες παραμένουν χειροκίνητες.')
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
        except StorageError as error:
            quotes = []
            st.error(str(error))
        by_market = {q['market']: q for q in quotes}
        st.subheader('Αυτόματες αποδόσεις, Over/Under και handicap')
        st.caption('Οι αγορές αφορούν τελικό σκορ μαζί με παράταση. Κάθε τιμή κρατά το δικό της line, εταιρεία και πηγή. Τα δημοσιευμένα snapshots μπορεί να έχουν αλλάξει στη στοιχηματική.')
        manual = st.checkbox('Χειροκίνητη καταχώριση / διόρθωση', key='manual:'+game['key'])
        company = st.text_input('Εταιρεία χειροκίνητων αποδόσεων', max_chars=100, key='company:'+game['key']).strip() if manual else ''
        offers = {}
        columns = st.columns(3)
        for index, (market, label) in enumerate(game_labels.items()):
            with columns[index % 3]:
                q = by_market.get(market)
                if manual:
                    st.write(label)
                    line = st.number_input('Line '+label, value=None, step=.5, key=f'line:{game["key"]}:{market}') if market not in {'home', 'away'} else None
                    price = st.number_input('Απόδοση '+label, min_value=1.01, value=None, step=.01, key=f'price:{game["key"]}:{market}')
                    if price is not None and (market in {'home', 'away'} or line is not None):
                        offers[market] = {'fixture_key': game['key'], 'market': market, 'line': line, 'odds': price,
                                          'source': 'Χειροκίνητη καταχώριση', 'bookmaker': company, 'price_kind': 'manual',
                                          'scope': 'including_overtime', 'observed_at': datetime.now(timezone.utc).isoformat()}
                else:
                    line_label = '' if not q or q['line'] is None else f" {q['line']:+g}" if market.startswith('handicap') else f" {q['line']:g}"
                    st.metric(label+line_label, f"{q['odds']:.2f}" if q else '—')
                    if q:
                        offers[market] = q
                        company_label = q.get('bookmaker') or f"πάροχος ID {q.get('bookmaker_id')} (δεν δηλώθηκε εταιρεία)"
                        st.caption(f"{q['source']} / {company_label} · {q['price_kind']} · λήψη {q['observed_at']}")
        if not offers:
            st.info('Δεν βρέθηκαν επιβεβαιωμένες τιμές με τις αντίστοιχες γραμμές. Τα κενά δεν αντικαθίστανται με 1,90 ή υποθετικά lines.')
            if league in {'euroleague', 'nba'} and not setting('ODDS_API_KEY'):
                st.info('Εναλλακτική αυτόματη πηγή: ενεργοποίησε το The Odds API προσθέτοντας ODDS_API_KEY στα Secrets του Streamlit. Διαθέτει δωρεάν πρόγραμμα με όριο χρήσης.')
        st.subheader('Χειροκίνητες απουσίες')
        absences = {}
        for column, side in zip(st.columns(2), ['home', 'away']):
            with column:
                st.write(game['teams'][side]['name'])
                starters = st.number_input('Βασικοί που λείπουν', min_value=0, value=None, step=1, key=f'abs:starters:{game["key"]}:{side}')
                reserves = st.number_input('Αναπληρωματικοί που λείπουν', min_value=0, value=None, step=1, key=f'abs:reserves:{game["key"]}:{side}')
                score = None if starters is None or reserves is None else -starters-.5*reserves
                absences[side] = {'starters': starters, 'reserves': reserves, 'index': score}
        st.caption('Δείκτης: βασικός −1, αναπληρωματικός −0,5. Αποθηκεύεται χωρίς αυθαίρετη αλλαγή πιθανοτήτων. Κενή καταχώριση σημαίνει άγνωστο.')
        model_mode = st.selectbox('Μοντέλο υπολογισμού', ['Κλασικό — τελευταίοι 10 αγώνες', 'Ρυθμός & αποτελεσματικότητα — πειραματικό'],
                                  key='model_mode')
        pace_mode = model_mode.startswith('Ρυθμός')
        if pace_mode:
            st.caption('Εκτιμώμενες κατοχές και επίθεση/άμυνα ανά 100 κατοχές από αναλυτικά στατιστικά. Απαιτεί πλήρη στοιχεία για τους τελευταίους 10 αγώνες κάθε ομάδας σε NBA/Ευρωλίγκα. Δεν έχει επιβεβαιωθεί βελτίωση ακρίβειας.')
        model_key = 'analysis:'+game['key']+(':pace-v1' if pace_mode else ':classic-v1')
        if st.button('Υπολογισμός με πραγματικά δεδομένα', type='primary'):
            st.session_state.pop(model_key, None)
            try:
                with st.spinner('Αναζήτηση των τελευταίων 10 πραγματικών αγώνων ανά ομάδα…'):
                    history = data.history(game)
                    model = analyse(game, history)
                    if model and pace_mode:
                        model = analyse_pace(game, history, boxscores(data, game, history))
                if model:
                    st.session_state[model_key] = model
                else:
                    counts = {game['teams'][s]['name']: len(recent_games(history, game, s)) for s in ['home', 'away']}
                    if pace_mode and all(n == 10 for n in counts.values()):
                        st.warning('Δεν υπάρχουν επαληθευμένα αναλυτικά στατιστικά για όλους τους τελευταίους 10 αγώνες κάθε ομάδας. Δες την «Κατάσταση πηγών» ή επίλεξε το κλασικό μοντέλο.')
                    else:
                        st.warning(f'Αποχή: χρειάζονται 10 αγώνες ανά ομάδα πριν από τον επιλεγμένο αγώνα. Διαθέσιμοι: {counts}.')
            except (DataError, StorageError, ValueError) as error:
                st.error(str(error))
        model = st.session_state.get(model_key)
        if model:
            st.metric('Αναμενόμενοι πόντοι μοντέλου', f"{model['mu_home']:.1f} — {model['mu_away']:.1f}")
            if pace_mode:
                st.caption('Πειραματική Normal προσέγγιση με προσαρμογή αναμενόμενων πόντων στις εκτιμώμενες κατοχές και την αποτελεσματικότητα. Βάρη ημιζωής 90 ημερών. Η διακύμανση παραμένει αυτή του κλασικού μοντέλου και δεν έχει βαθμονομηθεί για αυτή την προσαρμογή.')
                st.dataframe([{'Ομάδα': game['teams'][side]['name'],
                               f'Κατοχές / {model["regulation_minutes"]} λεπτά': round(profile['pace'], 1),
                               'Πόντοι υπέρ / 100 κατοχές': round(profile['offensive_rating'], 1),
                               'Πόντοι κατά / 100 κατοχές': round(profile['defensive_rating'], 1)}
                              for side, profile in model['profiles'].items()], hide_index=True)
                st.caption('Οι κατοχές εκτιμώνται από σουτ, επιθετικά ριμπάουντ, λάθη και βολές. Ο ρυθμός προσαρμόζεται στη διάρκεια· οι αναμενόμενοι πόντοι περιλαμβάνουν την ιστορική συμμετοχή παρατάσεων. Πηγές αναλυτικών στατιστικών: '+', '.join(sorted({b['source'] for b in model['boxscore_inputs'].values()})))
            else:
                st.caption('Πειραματική Normal προσέγγιση από πραγματικούς πόντους υπέρ/κατά, βάρη παλαιότητας90 ημερών. Χωρίς σταθερό πλεονέκτημα έδρας, συντελεστές ξεκούρασης ή επινοημένους μέσους όρους.')
            st.caption('Πηγές ιστορικού: '+', '.join(model['input_sources']))
            rows, distributions = [], {}
            for market, q in offers.items():
                p = distribution(model, market, q['line'])
                if p is None:
                    continue
                distributions[market] = p
                ev = p['win']*(q['odds']-1)-p['loss']
                rows.append({'Αγορά': game_labels[market], 'Line': q['line'], 'Απόδοση': q['odds'],
                             'Πιθανότητα νίκης': f"{p['win']:.1%}", 'Επιστροφή': f"{p['push']:.1%}", 'Εκτιμώμενο EV': f'{ev:+.1%}'})
            if rows:
                st.dataframe(rows, hide_index=True)
            eligible = [m for m in distributions if offers[m]['odds'] >= 1.5]
            chosen = st.multiselect('Επιλογές για αποθήκευση — 1 μονάδα η καθεμία', eligible, format_func=lambda m: game_labels[m], key='choices:'+game['key'])
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
            if data.paf.diagnostics:
                st.download_button('Λήψη διαγνωστικών Paf',
                                   json.dumps(data.paf.diagnostics, ensure_ascii=False, indent=2),
                                   'paf_diagnostics.json', 'application/json')

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
        records = sorted(records, key=lambda r: history_order(r['fixture'].get('kickoff'), r.get('probability', {}).get('win')))
        st.caption('Στατιστικά και ιστορικό: '+selected_league)
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
                        'Κέρδος': r['profit'], 'Πηγή': r['quote']['source'], 'Εταιρεία': r['quote'].get('bookmaker'),
                        'Απουσίες': json.dumps(r['absences'], ensure_ascii=False)} for r in records]
            st.dataframe(display, hide_index=True, width='stretch', column_config={
                'Αρχική πιθανότητα μοντέλου': st.column_config.TextColumn('Ποσοστό', help='Η αρχική πιθανότητα που αποθηκεύτηκε με την επιλογή.'),
                'Ημερομηνία': st.column_config.TextColumn('Έναρξη (Ελλάδα)')})
            st.download_button('Αντίγραφο όλων των επιλογών JSON', json.dumps(all_records, ensure_ascii=False, indent=2), 'basketball_backup.json', 'application/json')
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(display[0]))
            writer.writeheader(); writer.writerows(display)
            st.download_button('Εξαγωγή CSV', buffer.getvalue().encode('utf-8-sig'), 'basketball_bets.csv', 'text/csv')
        else:
            st.write('Δεν υπάρχουν αποθηκευμένες επιλογές για: '+selected_league)
    except (StorageError, DataError, ValueError) as error:
        st.error(str(error))
    st.caption('Εκκαθάριση μόνο σε επιβεβαιωμένο τελικό σκορ μαζί με παράταση. Ισοπαλία στην ακέραια γραμμή σημαίνει επιστροφή. Άγνωστα αποτελέσματα παραμένουν εκκρεμή. Η ενημέρωση δεν εκτελείται όταν η εφαρμογή είναι κλειστή.')
    if legacy.exists():
        st.info('Το παλιό CSV διατηρείται χωριστά· δεν μετατρέπεται σε επαληθευμένο νέο ιστορικό.')
        st.download_button('Λήψη αρχικού παλιού ιστορικού', legacy.read_bytes(), 'basketball_predictions_history.csv', 'text/csv')
