"""Controlled alternative odds feed, quota cache, provenance and secret checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import tempfile
from unittest.mock import Mock

import requests

from basketball_data import BasketballData, DataError, TheOddsAPI
from basketball_store import Store
from check_basketball import fixture


def main():
    now = datetime.now(timezone.utc)
    game = fixture(kickoff=now+timedelta(days=2))
    game.update(league='euroleague', source='euroleague', key='euroleague:E2026:91', season=2026)
    game['teams']['home']['name'] = 'REAL MADRID'
    game['teams']['away']['name'] = 'PANATHINAIKOS AKTOR ATHENS'
    event = {'id': 'test-event', 'sport_key': 'basketball_euroleague', 'commence_time': game['kickoff'],
             'home_team': 'Real Madrid', 'away_team': 'Panathinaikos', 'bookmakers': [
                 {'title': 'Controlled book', 'last_update': now.isoformat(), 'markets': [
                     {'key': 'h2h', 'outcomes': [{'name': 'Real Madrid', 'price': 1.8}, {'name': 'Panathinaikos', 'price': 2.1}]},
                     {'key': 'totals', 'outcomes': [{'name': 'Over', 'point': 165.5, 'price': 1.9}, {'name': 'Under', 'point': 165.5, 'price': 1.9}]},
                     {'key': 'spreads', 'outcomes': [{'name': 'Real Madrid', 'point': -3.5, 'price': 1.9}, {'name': 'Panathinaikos', 'point': 3.5, 'price': 1.9}]}]}]}
    secret = 'controlled-key-never-use'
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/odds.sqlite3')
        transport = Mock()
        transport.get.return_value.status_code = 200
        transport.get.return_value.json.return_value = [event]
        source = TheOddsAPI(secret, store, transport)
        qs = source.quotes(game)
        assert len(qs) == 6 and len(source.quotes(game)) == 6 and transport.get.call_count == 1
        assert transport.get.call_args.kwargs['params']['regions'] == 'eu'
        assert transport.get.call_args.kwargs['params']['markets'] == 'h2h,spreads,totals'
        assert all(secret not in json.dumps(q) for q in qs)
        assert all(q['source'] == 'The Odds API' and q['bookmaker'] == 'Controlled book' for q in qs)
        assert {q['market']: q['line'] for q in qs} == {'home': None, 'away': None, 'over': 165.5,
            'under': 165.5, 'handicap_home': -3.5, 'handicap_away': 3.5}
        assert all(store.save(game, q, {'win': .5, 'push': 0., 'loss': .5}, {}, {}) for q in qs)
        with store.connect() as db:
            assert all(secret not in row[0] for row in db.execute('SELECT payload FROM basketball_cache'))

        # All public sources fail; the optional feed still fills all six markets.
        data = BasketballData(store, odds_key=secret)
        data.odds = source
        data.paf.quotes = Mock(return_value=([], []))
        for adapter in data.adapters.values():
            adapter.fixtures = Mock(side_effect=DataError('controlled HTTP 403'))
            adapter.quotes = Mock(return_value=([], []))
        found, notes = data.quotes(game)
        assert len(found) == 6 and notes and transport.get.call_count == 1

        cases = [dict(event, home_team='Other team'), dict(event, sport_key='basketball_nba'),
                 dict(event, commence_time=(now+timedelta(days=3)).isoformat())]
        for index, bad in enumerate(cases, 1):
            transport.get.return_value.json.return_value = [bad]
            try:
                source.quotes(game, index)
                raise AssertionError('wrong event accepted')
            except DataError:
                pass
        transport.get.return_value.json.return_value = [event, event]
        try:
            source.quotes(game, 10)
            raise AssertionError('ambiguous event accepted')
        except DataError:
            pass
        incomplete = deepcopy(event)
        markets = incomplete['bookmakers'][0]['markets']
        markets[0]['outcomes'].append({'name': 'Draw', 'price': 12.})
        markets[1]['key'] = 'totals_h1'
        markets[2]['outcomes'][1].pop('point')
        transport.get.return_value.json.return_value = [incomplete]
        assert [q['market'] for q in source.quotes(game, 11)] == ['handicap_home']
        for status in [401, 403, 429]:
            transport.get.return_value.status_code = status
            try:
                source.quotes(game, status)
                raise AssertionError('HTTP failure ignored')
            except DataError as error:
                assert str(status) in str(error) and secret not in str(error)
        transport.get.side_effect = requests.ConnectionError('sensitive URL '+secret)
        try:
            source.quotes(game, 1000)
            raise AssertionError('connection failure ignored')
        except DataError as error:
            assert secret not in str(error)
    print('PASS odds API: six markets, public-source failure fallback, cache reuse, exact identity, ambiguity/draw/period exclusion, missing lines, saved provenance, key redaction and HTTP errors')


if __name__ == '__main__':
    main()
