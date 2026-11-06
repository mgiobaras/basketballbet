"""Controlled Greek routing/identity using recorded Kambi market structure.

These are functional checks, not evidence of current Paf Greek prices/coverage.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError, GREEK_TEAMS, Paf, name_key, paf_event, paf_quotes
from basketball_store import Store
from check_paf_odds import RECORDED
from check_greek_basket import MATCHES


def row_for(home, away, kickoff):
    row = deepcopy(RECORDED)
    row['event'].update(homeName=home, awayName=away, start=kickoff,
        group='GBL', path=[{'termKey':'basketball'}, {'termKey':'greece'}, {'termKey':'gbl'}])
    for offer in row['betOffers']:
        for item in offer['outcomes']:
            if item['type'] in {'OT_ONE', 'OT_TWO'}:
                name = home if item['type'] == 'OT_ONE' else away
                item.update(englishLabel=name, participant=name, label=name)
    return row


def main():
    now = datetime.now(timezone.utc)
    kickoff = (now+timedelta(days=1)).isoformat()
    assert len(GREEK_TEAMS) == 14
    assert len({name_key(name) for match in MATCHES for name in match[:2]}) == 14
    expected = {'handicap_home':(-4.,1.9), 'handicap_away':(4.,1.92), 'home':(None,1.61),
                'away':(None,2.38), 'over':(237.,1.9), 'under':(237.,1.92)}
    english_pairs = [('Doxa Lefkadas','Aris'), ('Kolossos Rhodes','Peristeri'),
                     ('Iraklis','Mykonos'), ('Promitheas Patras','AS Karditsas'),
                     ('PAOK Thessaloniki','Vikos BC'), ('AEK Athens','Panathinaikos AKTOR Athens'),
                     ('Maroussi BC','Olympiacos Piraeus')]
    for (home, away, _), (english_home, english_away) in zip(MATCHES, english_pairs, strict=True):
        row = row_for(english_home, english_away, kickoff)
        native = paf_event(row, 'greece'); assert native
        game = dict(native, key='esake:controlled', source='esake')
        game['teams'] = {'home':{'id':'esake:1','name':home}, 'away':{'id':'esake:2','name':away}}
        offers = paf_quotes(row, game, now.isoformat(), 'controlled-recorded-schema')
        assert {q['market']:(q['line'],q['odds']) for q in offers} == expected
        for other_home, other_away, _ in MATCHES:
            if (other_home,other_away) != (home,away):
                wrong = deepcopy(game)
                wrong['teams']['home']['name'], wrong['teams']['away']['name'] = other_home, other_away
                assert not paf_quotes(row,wrong,now.isoformat(),'controlled')
    row = row_for('Doxa Lefkadas', 'Aris', kickoff)
    game = paf_event(row, 'greece')
    game.update(key='esake:controlled', source='esake')
    game['teams'] = {'home':{'id':'esake:1','name':MATCHES[0][0]}, 'away':{'id':'esake:2','name':MATCHES[0][1]}}
    for group, path in [('A1',[{'name':'Greece'}]), ('Basket League',[{'termKey':'greece'}]),
                        ('Greece - GBL',[]), ('Greek Basket League',[])]:
        valid = deepcopy(row); valid['event'].update(group=group,path=path)
        assert paf_event(valid, 'greece')
    for group, path in [('GBL',[]), ('GBL',[{'name':'Other country'}]),
                        ('A2',[{'name':'Greece'}]), ('Cup',[{'name':'Greece'}]),
                        ('A1 (W)',[{'name':'Greece'},{'name':'A1'}]),
                        ('U20',[{'name':'Greece'},{'name':'A1'}]),
                        ('Women',[{'name':'Greece'},{'name':'GBL'}])]:
        bad = deepcopy(row); bad['event'].update(group=group,path=path)
        assert paf_event(bad, 'greece') is None, (group,path)
    assert paf_event(row, 'euroleague') is None
    for change in [{'homeName':'Other club'}, {'start':(now+timedelta(days=2)).isoformat()},
                   {'homeName':'Aris','awayName':'Doxa Lefkadas'}, {'state':'STARTED'}]:
        bad = deepcopy(row); bad['event'].update(change)
        assert not paf_quotes(bad,game,now.isoformat(),'controlled')
    missing = deepcopy(row)
    missing['betOffers'][2]['outcomes'][0].pop('line')
    assert not any(q['market'] in {'over','under'} for q in paf_quotes(missing,game,now.isoformat(),'controlled'))
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/source.sqlite3'); http = Mock()
        http.object.return_value = {'events':[row]}
        data = BasketballData(store,http)
        data.native = Mock(side_effect=DataError('Sofascore controlled HTTP 403'))
        qs, errors = data.quotes(game)
        assert len(qs) == 6 and any('403' in e for e in errors)
        data.native.assert_called_once_with(game,'sofascore')  # ESAKE is not an odds source.
        assert http.object.call_count == 1 and data.paf.diagnostics['matched']['event']['group'] == 'GBL'
        assert all(q['fixture_key'] == game['key'] and q['source'] == q['bookmaker'] == 'Paf' for q in qs)
        again = BasketballData(store,http)
        assert len(again.quotes(game)[0]) == 6 and again.paf.diagnostics['listing_count'] == 1
        assert http.object.call_count == 1
        assert all(store.save(game,q,{'win':.5,'push':0.,'loss':.5},{},{}) for q in qs)
        # A listing without prices requests the same identified event's details.
        provider = Paf(store,http)
        http.object.side_effect = [{'events':[dict(row,betOffers=[])]},
                                   {'events':[row['event']], 'betOffers':row['betOffers']}]
        assert len(provider.quotes(game,4)[0]) == 6
        assert http.object.call_args.args[0].endswith('/event/'+str(row['event']['id'])+'.json')
        http.object.side_effect = None; http.object.return_value = {'events':[row,row]}
        try:
            provider.quotes(game,5)
            raise AssertionError('Ambiguous Greek event accepted')
        except DataError:
            pass
        http.object.side_effect = [{'events':[dict(row,betOffers=[])]},
                                   {'events':[row['event']], 'betOffers':[]}]
        absent, notes = provider.quotes(game,6)
        assert not absent and notes and len(store.list()) == 6
    ui_check(game,row)
    print('PASS Greek odds: all14 club identities, league/country guards, no invented lines, six-market Paf fallback after403, cache, details, ambiguity, persistence and UI')


def ui_check(game,row):
    from streamlit.testing.v1 import AppTest
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH':directory+'/ui.sqlite3','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'',
        'REQUIRE_REMOTE_DB':'false','APP_PASSWORD':'','ODDS_API_KEY':''}), \
         patch('basketball_data.BasketballData.fixtures',side_effect=lambda self_league,day: [game] if self_league == 'greece' else []), \
         patch('basketball_data.BasketballData.native',side_effect=DataError('Sofascore controlled HTTP 403')), \
         patch('basketball_data.HTTP.object',return_value={'events':[row]}):
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        app.sidebar.selectbox[0].select('Ελλάδα - Basket League').run(timeout=30)
        assert not app.exception
        assert any(m.label == 'Over 237' and m.value == '1.90' for m in app.metric)
        assert any(m.label == 'Under 237' and m.value == '1.92' for m in app.metric)
        assert any(m.label == 'Handicap '+game['teams']['home']['name']+' -4' and m.value == '1.90' for m in app.metric)
        assert any(m.label == 'Νίκη '+game['teams']['away']['name'] and m.value == '2.38' for m in app.metric)
        assert Store(directory+'/ui.sqlite3').list() == []


if __name__ == '__main__':
    main()
