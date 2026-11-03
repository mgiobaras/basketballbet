"""Recorded Kambi schema and controlled Paf fallback checks, not live price claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import tempfile
from unittest.mock import Mock

from basketball_data import BasketballData, DataError, Paf, paf_event, paf_quotes
from basketball_store import Store

# Faithful reduced fields from a real recorded prematch response, event1007123461:
# https://github.com/EllAchE/nba-tipoff-scraper/blob/
# b1fb92f10d61b94e44bb3d760e9ac269c706a7ab/Data/JSON/sample_sb_json/unibet_all.json
# Historical Unibet/Kambi schema evidence, NOT a current Paf/NBA/EuroLeague quote.
RECORDED = {'event': {'id': 1007123461, 'homeName': 'NO Pelicans', 'awayName': 'POR Trail Blazers',
    'name': 'POR Trail Blazers @ NO Pelicans', 'englishName': 'New Orleans Pelicans - Portland Trail Blazers',
    'start': '2021-02-18T02:10:00Z', 'group': 'NBA', 'path': [{'termKey': 'basketball'}, {'termKey': 'nba'}],
    'sport': 'BASKETBALL', 'state': 'NOT_STARTED'}, 'betOffers': [
    {'id': 2249950592, 'eventId': 1007123461, 'closed': '2021-02-18T02:10:00Z',
     'criterion': {'englishLabel': 'Handicap - Including Overtime', 'lifetime': 'FULL_TIME_OVERTIME'},
     'betOfferType': {'id': 1}, 'tags': ['OFFERED_PREMATCH', 'MAIN_LINE'], 'outcomes': [
         {'type': 'OT_ONE', 'englishLabel': 'New Orleans Pelicans', 'participant': 'NO Pelicans', 'label': 'NO Pelicans', 'odds': 1900, 'line': -4000, 'status': 'OPEN'},
         {'type': 'OT_TWO', 'englishLabel': 'Portland Trail Blazers', 'participant': 'POR Trail Blazers', 'label': 'POR Trail Blazers', 'odds': 1920, 'line': 4000, 'status': 'OPEN'}]},
    {'id': 2249950614, 'eventId': 1007123461, 'closed': '2021-02-18T02:10:00Z',
     'criterion': {'englishLabel': 'Including Overtime', 'lifetime': 'FULL_TIME_OVERTIME'},
     'betOfferType': {'id': 2}, 'tags': ['OFFERED_PREMATCH', 'MAIN'], 'outcomes': [
         {'type': 'OT_ONE', 'englishLabel': 'New Orleans Pelicans', 'participant': 'NO Pelicans', 'label': 'NO Pelicans', 'odds': 1610, 'status': 'OPEN'},
         {'type': 'OT_TWO', 'englishLabel': 'Portland Trail Blazers', 'participant': 'POR Trail Blazers', 'label': 'POR Trail Blazers', 'odds': 2380, 'status': 'OPEN'}]},
    {'id': 2249950534, 'eventId': 1007123461, 'closed': '2021-02-18T02:10:00Z',
     'criterion': {'englishLabel': 'Total Points - Including Overtime', 'lifetime': 'FULL_TIME_OVERTIME'},
     'betOfferType': {'id': 6}, 'tags': ['OFFERED_PREMATCH', 'MAIN_LINE'], 'outcomes': [
         {'type': 'OT_OVER', 'odds': 1900, 'line': 237000, 'status': 'OPEN'},
         {'type': 'OT_UNDER', 'odds': 1920, 'line': 237000, 'status': 'OPEN'}]}]}


def main():
    receipt = datetime.now(timezone.utc).isoformat()
    original = paf_event(RECORDED, 'nba')
    grouped = deepcopy(RECORDED)
    grouped['event'].update(group='Regular Season', path=[{'termKey': 'basketball'},
                           {'termKey': 'competition', 'englishName': 'Euroleague'}])
    assert paf_event(grouped, 'euroleague') is not None
    assert original['teams']['home']['name'] == 'New Orleans Pelicans'
    assert original['teams']['away']['name'] == 'Portland Trail Blazers'
    parsed = paf_quotes(RECORDED, original, receipt, 'recorded-source')
    assert {q['market']: (q['line'], q['odds']) for q in parsed} == {
        'handicap_home': (-4., 1.9), 'handicap_away': (4., 1.92), 'home': (None, 1.61),
        'away': (None, 2.38), 'over': (237., 1.9), 'under': (237., 1.92)}
    contradictory = deepcopy(RECORDED)
    contradictory['event']['homeName'] = 'Unrelated club'
    assert paf_event(contradictory, 'nba') is None
    assert not paf_quotes(contradictory, original, receipt, 'source')
    for occurrence in ['TEAM', 'POINTS_HOME', 'POINTS_AWAY']:
        team_total = deepcopy(RECORDED)
        team_total['betOffers'][2]['criterion']['occurrenceType'] = occurrence
        assert not any(q['market'] in {'over', 'under'} for q in paf_quotes(team_total, original, receipt, 'source'))
    for change in ['state', 'lifetime', 'status', 'eventId', 'wrong_team', 'missing_line']:
        bad = deepcopy(RECORDED)
        if change == 'state':
            bad['event']['state'] = 'STARTED'
        else:
            bad['betOffers'] = [bad['betOffers'][0]]
            offer = bad['betOffers'][0]
            if change == 'lifetime': offer['criterion']['lifetime'] = 'FIRST_HALF'
            if change == 'status': offer['outcomes'][0]['status'] = 'SUSPENDED'
            if change == 'eventId': offer['eventId'] += 1
            if change == 'wrong_team': offer['outcomes'][0]['englishLabel'] = 'Other club'
            if change == 'missing_line': offer['outcomes'][0].pop('line')
        assert not paf_quotes(bad, original, receipt, 'recorded-source'), change
    alternatives = deepcopy(RECORDED)
    extra = deepcopy(alternatives['betOffers'][0]); extra['tags'] = []
    extra['outcomes'][0]['line'], extra['outcomes'][1]['line'] = -5000, 5000
    alternatives['betOffers'].insert(0, extra)
    assert next(q for q in paf_quotes(alternatives, original, receipt, 'source') if q['market'] == 'handicap_home')['line'] == -4

    # Controlled EuroLeague identity uses the recorded schema/price units above.
    row = deepcopy(RECORDED)
    # Names actually returned by Paf in the user's 2026-11-04 diagnostic.
    row['event'].update(homeName='Real Madrid Baloncesto', awayName='Panathinaikos', group='Euroleague',
                        path=[{'termKey': 'basketball'}, {'termKey': 'euroleague'}],
                        start=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
    for offer in row['betOffers']:
        for o in offer['outcomes']:
            if o['type'] == 'OT_ONE': o.update(englishLabel='Real Madrid Baloncesto', participant='Real Madrid Baloncesto', label='Real Madrid Baloncesto')
            if o['type'] == 'OT_TWO': o.update(englishLabel='Panathinaikos', participant='Panathinaikos', label='Panathinaikos')
    game = paf_event(row, 'euroleague')
    game.update(key='euroleague:E2026:91', source='euroleague', season=2026)
    game['teams']['home']['name'] = 'Real Madrid'
    game['teams']['away']['name'] = 'Panathinaikos AKTOR Athens'
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/cache.sqlite3')
        http = Mock(); http.object.return_value = {'events': [row]}
        provider = Paf(store, http)
        offers, notes = provider.quotes(game)
        assert len(offers) == 6 and not notes
        assert len(provider.quotes(game)[0]) == 6 and http.object.call_count == 1
        assert http.object.call_args.args[0] == Paf.BASE+'/listView/basketball/all/all/all/matches.json'
        assert all(q['source'] == q['bookmaker'] == 'Paf' and q['fixture_key'] == game['key'] for q in offers)
        # A list without market rows must use the same native event's full book.
        summary = dict(row, betOffers=[])
        http.object.side_effect = [{'events': [summary]}, {'events': [row['event']], 'betOffers': row['betOffers']}]
        detailed, notes = provider.quotes(game, 3)
        assert len(detailed) == 6 and not notes
        assert http.object.call_args.args[0] == Paf.BASE+f'/betoffer/event/{row["event"]["id"]}.json'
        # A scoped response may repeat only ID/names/start, omitting league/state.
        sparse = {k: row['event'][k] for k in ['id', 'homeName', 'awayName', 'start']}
        http.object.side_effect = [{'events': [summary]}, {'events': [sparse], 'betOffers': row['betOffers']}]
        sparse_quotes, notes = provider.quotes(game, 20)
        assert len(sparse_quotes) == 6 and not notes
        # An empty book is reported as unavailable, never as changed teams.
        http.object.side_effect = [{'events': [summary]}, {'events': [sparse], 'betOffers': []}]
        absent, notes = provider.quotes(game, 21)
        assert not absent and 'δεν υπάρχουν' in notes[0]
        http.object.side_effect = [{'events': [summary]}, DataError('controlled event HTTP403')]
        assert provider.quotes(game, 4) == ([], ['controlled event HTTP403'])
        partial = dict(row, betOffers=[row['betOffers'][1]])
        for index, change in enumerate([{'state': 'STARTED'}, {'start': (datetime.now(timezone.utc)+timedelta(days=3)).isoformat()},
                                        {'homeName': 'Other club'}], 10):
            fresh = dict(row['event'], **change)
            http.object.side_effect = [{'events': [partial]}, {'events': [fresh], 'betOffers': []}]
            stale, notes = provider.quotes(game, index)
            assert not stale and notes  # fresh contradictions invalidate cached partial prices
        http.object.side_effect = None
        # Unmatched/ambiguous fixtures do not request a different game's bet offers.
        http.object.return_value = {'events': [row, deepcopy(row)]}
        try:
            provider.quotes(game, 1)
            raise AssertionError('Ambiguous event accepted')
        except DataError:
            pass
        http.object.side_effect = DataError('controlled HTTP403')
        try:
            provider.quotes(game, 2)
            raise AssertionError('HTTP403 ignored')
        except DataError:
            pass
        data = BasketballData(store, http)
        data.native = Mock(return_value=None)
        data.paf.quotes = Mock(return_value=(offers, []))
        data.odds = Mock(); data.odds.scope = 'controlled'; data.odds.quotes.return_value = []
        found, errors = data.quotes(game)
        assert len(found) == 6 and errors
        data.odds.quotes.assert_not_called()
        assert all(store.save(game, q, {'win': .5, 'push': 0., 'loss': .5}, {}, {}) for q in found)
        assert len(store.list()) == 6
    print('PASS Paf: recorded schema, orientation, six market units, signed/main lines, period/live/suspended/wrong identity guards, no-key fallback, shared cache, persistence and HTTP403 diagnosis')


if __name__ == '__main__':
    main()
