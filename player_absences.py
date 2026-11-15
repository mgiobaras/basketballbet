"""Current player reports and plain team counts; never modify classic predictions."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from basketball_data import DataError, ESPN_BASE, espn_event, matching, name_key
from basketball_model import instant
from basketball_store import StorageError


def unknown(game):
    return {side: {'count': None, 'players': [], 'source': None,
                   'fixture_key': game['key'], 'team_id': game['teams'][side]['id']}
            for side in ['home', 'away']}


def parse_espn(data, game, observed_at, url):
    header = data.get('header')
    native = espn_event(header, 'nba') if isinstance(header, dict) else None
    if (not native or game['league'] != 'nba' or native['key'] != game['key']
            or native['status'] != 'NS' or matching(game, [native], exact_time=True) is None
            or any(native['teams'][s]['id'] != game['teams'][s]['id'] for s in ['home', 'away'])):
        raise DataError('ESPN απουσίες: δεν επιβεβαιώθηκαν ο αγώνας, οι ομάδες και η ώρα έναρξης.')
    reports, notes = unknown(game), []
    injuries = data.get('injuries')
    for side in ['home', 'away']:
        team = game['teams'][side]
        found = [r for r in injuries if isinstance(r, dict) and isinstance(r.get('team'), dict)
                 and 'espn:'+str(r['team'].get('id')) == team['id']] if isinstance(injuries, list) else []
        if (len(found) != 1 or not isinstance(found[0].get('injuries'), list)
                or (found[0]['team'].get('displayName') and name_key(found[0]['team']['displayName']) != name_key(team['name']))):
            notes.append(f"{team['name']}: δεν υπάρχει πλήρης αναφορά απουσιών από την πηγή.")
            continue
        players = {}
        try:
            for entry in found[0]['injuries']:
                athlete = entry.get('athlete') if isinstance(entry, dict) else None
                if (not isinstance(athlete, dict) or not str(athlete.get('id', '')).isdigit()
                        or not isinstance(athlete.get('displayName'), str) or not athlete['displayName'].strip()
                        or not isinstance(entry.get('status'), str) or not entry['status'].strip()):
                    raise ValueError('Incomplete player report')
                player = dict(id=str(athlete['id']), name=athlete['displayName'], status=entry['status'],
                              reported_at=instant(entry['date']).isoformat() if entry.get('date') else None)
                if player['id'] in players and players[player['id']] != player:
                    raise ValueError('Conflicting player reports')
                players[player['id']] = player
        except (KeyError, TypeError, ValueError):
            notes.append(f"{team['name']}: η αναφορά παικτών είναι ελλιπής ή αντικρουόμενη.")
            continue
        values = sorted(players.values(), key=lambda p: p['id'])
        reports[side].update(count=sum(p['status'].casefold() == 'out' for p in values), players=values,
                             source='ESPN', source_url=url, observed_at=observed_at, counting_rule='reported_out_only')
    return reports, notes


def load_absences(data, game, refresh=0):
    if game['league'] != 'nba':
        return unknown(game), ['Δεν έχει συνδεθεί επαληθευμένη αυτόματη πηγή απουσιών για αυτή τη διοργάνωση. Μπορείς να συμπληρώσεις το πλήθος ανά ομάδα.']
    if game['status'] != 'NS' or instant(game['kickoff']) <= datetime.now(timezone.utc):
        return unknown(game), ['Η τρέχουσα αναφορά απουσιών δεν χρησιμοποιείται ως ιστορική αναφορά για αγώνα που έχει ήδη ξεκινήσει.']

    def fetch():
        try:
            native = data.native(game, 'espn')
            if native is None:
                raise DataError('ESPN απουσίες: δεν βρέθηκε μοναδική αντιστοίχιση του αγώνα.')
            url = ESPN_BASE+'/nba/summary'
            response = data.adapters['espn'].http.object(url, {'event': native['id']})
            reports, notes = parse_espn(response, native, datetime.now(timezone.utc).isoformat(), url+'?event='+native['id'])
            for side, report in reports.items():
                report.update(fixture_key=game['key'], team_id=game['teams'][side]['id'], source_team_id=native['teams'][side]['id'])
            return {'absences': reports, 'notes': notes}
        except DataError as error:
            return {'absences': unknown(game), 'notes': [str(error)]}
    # Keep the report tied to fixture identity and do not repeatedly retry a failed source on each UI edit.
    cache_key = f"absences:v1:{game['key']}:{game['kickoff']}:{game['teams']}:{refresh}"
    try:
        result = data.store.cached(cache_key, fetch, 300)
        return result['absences'], result['notes']
    except StorageError as error:
        return unknown(game), [str(error)]


def absence_inputs(st, data, game):
    with st.expander('Απουσίες παικτών', expanded=True):
        refresh_key = 'refresh_absences:'+game['key']
        if st.button('Ανανέωση απουσιών', key=refresh_key+':button'):
            st.session_state[refresh_key] = st.session_state.get(refresh_key, 0)+1
        automatic, notes = load_absences(data, game, st.session_state.get(refresh_key, 0))
        manual = st.checkbox('Χειροκίνητη καταχώριση / διόρθωση απουσιών',
                             value=game['league'] != 'nba', key='manual_absences:'+game['key'])
        selected = {}
        for side, column in zip(['home', 'away'], st.columns(2)):
            with column:
                label = 'Απουσίες — '+game['teams'][side]['name']
                report = automatic[side]
                if manual:
                    count = st.number_input(label, min_value=0, value=report['count'], step=1,
                                            key='absence_count:'+game['key']+':'+side)
                    selected[side] = dict(count=count, source='Χειροκίνητη καταχώριση', players=[],
                                          fixture_key=game['key'], team_id=game['teams'][side]['id'])
                else:
                    st.metric(label, report['count'] if report['count'] is not None else '—')
                    selected[side] = report
                if report['source']:
                    st.caption('ESPN · λήψη '+instant(report['observed_at']).astimezone(ZoneInfo('Europe/Athens')).strftime('%d/%m %H:%M'))
                if report['players']:
                    absent = [p['name'] for p in report['players'] if p['status'].casefold() == 'out']
                    labels = {'day-to-day': 'Αμφίβολος', 'questionable': 'Αμφίβολος',
                              'doubtful': 'Αμφίβολος', 'probable': 'Πιθανή συμμετοχή', 'available': 'Διαθέσιμος'}
                    other = [p['name']+' ('+labels.get(p['status'].casefold(), p['status'])+')'
                             for p in report['players'] if p['status'].casefold() != 'out']
                    if absent:
                        st.caption('Δηλωμένοι εκτός: '+', '.join(absent))
                    if other:
                        st.caption('Άλλες αναφορές — δεν μετρώνται ως απόντες: '+', '.join(other))
        for note in notes:
            st.info(note)
        st.caption('Μετράμε μόνο παίκτες που η πηγή δηλώνει Out. Η αναφορά μπορεί να αλλάξει πριν τον αγώνα. Οι απουσίες καταγράφονται με την ανάλυση· ο κλασικός υπολογισμός παραμένει ίδιος. Κενό πεδίο σημαίνει άγνωστο πλήθος.')
        return selected
