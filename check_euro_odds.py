"""Offline EuroLeague identity and odds checks; prices below are test data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError, matching, name_key
from basketball_store import Store

# Sources checked 2026-11-03: the official 2026/27 team directory at
# hub.euroleague.tech and the 20 team pages linked from
# https://www.sofascore.com/basketball/tournament/international/euroleague/138
TEAMS = [
    ('Anadolu Efes Istanbul', 'Anadolu Efes'),
    ('Armani Olimpia Milan', 'EA7 Emporio Armani Milano'),
    ('Besiktas Istanbul', 'Beşiktaş JK'),
    ('Crvena Zvezda Meridianbet Belgrade', 'KK Crvena zvezda'),
    ('Dubai Basketball', 'BC Dubai'), ('FC Barcelona', 'Barça Basket'),
    ('FC Bayern Munich', 'Bayern München'), ('Fenerbahce Tarfin Istanbul', 'Fenerbahçe Tarfin'),
    ('Hapoel IBI Tel Aviv', 'Hapoel Tel-Aviv'),
    ('Kosner Baskonia Vitoria-Gasteiz', 'Kosner Baskonia'),
    ('LDLC ASVEL Villeurbanne', 'LDLC ASVEL Lyon-Villeurbanne'),
    ('Maccabi Rapyd Tel Aviv', 'Maccabi Tel Aviv'), ('Olympiacos Piraeus', 'Olympiacos BC'),
    ('Panathinaikos AKTOR Athens', 'Panathinaikos BC'), ('Paris Basketball', 'Paris Basketball'),
    ('Partizan Mozzarbet Belgrade', 'KK Partizan Mozzart Bet'), ('Real Madrid', 'Real Madrid'),
    ('Valencia Basket', 'Valencia Basket'), ('Virtus Bologna', 'Virtus Bologna'),
    ('Zalgiris Kaunas', 'Kauno Žalgiris')]

# Same club order as TEAMS. Exact Paf spellings from the owner's Nov4–6
# diagnostics/messages and public listing, including its recorded encoding.
PAF_NAMES = [
    'Anadolu Efes', 'Milano', 'Besiktas', 'KK Crvena Zvezda Belgrade',
    'BC Dubai', 'FC Barcelona', 'FC Bayern München', 'Fenerbahce SK',
    'Hapoel Tel Aviv', 'Saski Baskonia', 'ASVEL Lyon-Villeurbanne',
    'Maccabi Tel Aviv', 'Olympiacos BC', 'Panathinaikos', 'Paris Basket',
    'Partizan Belgrade', 'Real Madrid Baloncesto', 'Valencia Basket Club',
    'Virtus Bologna', 'Å½algiris Kaunas']


def main():
    now = datetime.now(timezone.utc)
    kickoff = now + timedelta(days=2)
    game = {'key': 'euroleague:E2026:91', 'id': '91', 'season': 2026,
            'source': 'euroleague', 'league': 'euroleague', 'status': 'NS', 'kickoff': kickoff.isoformat(),
            'teams': {'home': {'id': 'euroleague:MAD', 'name': 'REAL MADRID'},
                      'away': {'id': 'euroleague:PAO', 'name': 'PANATHINAIKOS AKTOR ATHENS'}},
            'score': {'home': None, 'away': None}}
    native = dict(game, key='sofascore:12345', id='12345', source='sofascore', teams={
        'home': {'id': 'sofascore:3540', 'name': 'Real Madrid'},
        'away': {'id': 'sofascore:3508', 'name': 'Panathinaikos BC'}})
    assert len({name_key(a) for a, _ in TEAMS}) == 20
    # Actual Paf fixture names provided in the user's Thursday diagnostic.
    paf_matches = [
        (('Armani Olimpia Milan', 'Valencia Basket'), ('Milano', 'Valencia Basket Club')),
        (('LDLC ASVEL Villeurbanne', 'FC Bayern Munich'), ('ASVEL Lyon-Villeurbanne', 'FC Bayern München')),
        (('Hapoel IBI Tel Aviv', 'FC Barcelona'), ('Hapoel Tel Aviv', 'FC Barcelona')),
        (('Fenerbahce Tarfin Istanbul', 'Kosner Baskonia Vitoria-Gasteiz'), ('Fenerbahce SK', 'Saski Baskonia')),
        (('Anadolu Efes Istanbul', 'Paris Basketball'), ('Anadolu Efes', 'Paris Basket')),
        # Exact names in the owner's recorded 2026-11-06 Paf listing.
        (('Olympiacos Piraeus', 'Crvena Zvezda Meridianbet Belgrade'),
         ('Olympiacos BC', 'KK Crvena Zvezda Belgrade')),
        (('Partizan Mozzarbet Belgrade', 'Maccabi Rapyd Tel Aviv'),
         ('Partizan Belgrade', 'Maccabi Tel Aviv'))]
    for official, provider_names in paf_matches:
        target, candidate = deepcopy(game), deepcopy(native)
        for index, side in enumerate(['home', 'away']):
            target['teams'][side]['name'] = official[index]
            candidate['teams'][side]['name'] = provider_names[index]
        assert matching(target, [candidate], exact_time=True) is candidate, official
        reversed_game = dict(candidate, teams={'home': candidate['teams']['away'], 'away': candidate['teams']['home']})
        assert matching(target, [reversed_game], exact_time=True) is None
        for other_official, _ in paf_matches:
            if other_official == official:
                continue
            wrong = deepcopy(candidate)
            wrong['teams']['home']['name'] = other_official[0]
            assert matching(target, [wrong], exact_time=True) is None
    assert len(PAF_NAMES) == len(TEAMS) == 20
    for index, (official, sofa) in enumerate(TEAMS):
        assert name_key(official) == name_key(sofa), (official, sofa)
        assert name_key(official) == name_key(PAF_NAMES[index]), (official, PAF_NAMES[index])
        target, candidate = deepcopy(game), deepcopy(native)
        anchor = (index+1) % len(TEAMS)
        target['teams']['home']['name'] = TEAMS[anchor][0]
        candidate['teams']['home']['name'] = PAF_NAMES[anchor]
        target['teams']['away']['name'] = official
        candidate['teams']['away']['name'] = PAF_NAMES[index]
        assert matching(target, [candidate], exact_time=True) is candidate
        assert matching(target, [dict(candidate, teams={'home':candidate['teams']['away'],
                                                       'away':candidate['teams']['home']})], exact_time=True) is None
        assert matching(target, [candidate, deepcopy(candidate)], exact_time=True) is None
        for other, _ in TEAMS:
            if other == official:
                continue
            wrong = deepcopy(candidate)
            wrong['teams']['away']['name'] = other
            assert matching(target, [wrong], exact_time=True) is None
    for changed in [dict(native, league='greece'), dict(native, kickoff=(kickoff+timedelta(minutes=1)).isoformat()),
                    dict(native, teams={'home': native['teams']['away'], 'away': native['teams']['home']})]:
        assert matching(game, [changed], exact_time=True) is None

    raw = {'id': 12345, 'startTimestamp': kickoff.timestamp(), 'status': {'type': 'notstarted'},
           'tournament': {'uniqueTournament': {'slug': 'euroleague'}},
           'homeTeam': {'id': 3540, 'name': 'Real Madrid'}, 'awayTeam': {'id': 3508, 'name': 'Panathinaikos BC'}}
    markets = {'bookmaker': {'name': 'Controlled test company'}, 'markets': [
        {'marketName': 'Winner (incl. overtime)', 'choices': [
            {'name': '1', 'fractionalValue': '4/5'}, {'name': '2', 'fractionalValue': '1/1'}]},
        {'marketName': 'Total (incl. overtime)', 'choiceGroup': '165.5', 'choices': [
            {'name': 'Over', 'fractionalValue': '10/11'}, {'name': 'Under', 'fractionalValue': '10/11'}]},
        {'marketName': 'Handicap (incl. overtime)', 'choices': [
            {'name': '1', 'handicap': '-3.5', 'fractionalValue': '10/11'},
            {'name': '2', 'handicap': '3.5', 'fractionalValue': '10/11'}]}]}
    def response(url, params=None):
        if '/scheduled-events/' in url:
            return {'events': [deepcopy(raw)]}
        if url.endswith('/odds/1/all'):
            return deepcopy(markets)
        raise DataError('controlled source unavailable')

    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/bets.sqlite3')
        http = Mock(); http.object.side_effect = response
        data = BasketballData(store, http)
        offers, errors = data.quotes(game)
        assert not errors and len(offers) == 6
        assert all(q['fixture_key'] == game['key'] and q['source_fixture_key'] == native['key'] for q in offers)
        assert {q['market']: q['line'] for q in offers} == {
            'home': None, 'away': None, 'over': 165.5, 'under': 165.5, 'handicap_home': -3.5, 'handicap_away': 3.5}
        assert all(store.save(game, q, {'win': .5, 'push': 0., 'loss': .5}, {}, {}) for q in offers)
        assert len(store.list()) == 6
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'BET_DB_PATH': directory+'/ui.sqlite3', 'SUPABASE_URL': '',
                                    'SUPABASE_SERVICE_ROLE_KEY': '', 'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': ''}), \
             patch('basketball_data.BasketballData.fixtures', return_value=[game]), \
             patch('basketball_data.BasketballData.quotes', return_value=(offers, errors)):
            app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=30)
            assert not app.exception
            assert any(m.label == 'Over 165.5' and m.value == '1.91' for m in app.metric)
            assert any(m.label == 'Handicap 1 -3.5' for m in app.metric)
        # Failures remain visible, and an unmatched game never requests odds.
        data = BasketballData(Store(directory+'/errors.sqlite3'), http)
        raw['awayTeam']['name'] = 'Unrelated club'
        http.object.reset_mock()
        missing, notes = data.quotes(game)
        assert not missing and any('αντιστοίχιση' in n for n in notes)
        assert not any('/odds/' in call.args[0] for call in http.object.call_args_list)
    print('PASS EuroLeague: official/Sofascore/Paf names for all20 clubs; 380 wrong-team pairs rejected; ambiguous/date/league/home-away guards; Real-Panathinaikos six-market fallback, signed lines, persistence and UI; source diagnostics')


if __name__ == '__main__':
    main()
