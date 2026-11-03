"""Possession arithmetic, real response parsing, cache identity and opt-in UI checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError
from basketball_model import analyse, distribution
from basketball_pace import analyse_pace, boxscores, espn_box, euro_box
from basketball_store import Store
from check_basketball import fixture, history, quote

ROOT = Path(__file__).resolve().parent


def controlled(f):
    games, boxes = history(f), {}
    for g in games:
        first = g['teams']['home']['id'] == f['teams']['home']['id']
        g['score'] = dict(home=100 if first else 120, away=80 if first else 90)
        boxes[g['key']] = {'kickoff': g['kickoff'], 'score': dict(g['score']),
                           'team_names': {s: g['teams'][s]['name'] for s in ['home', 'away']},
                           'possessions': 80 if first else 100, 'minutes': 48, 'source': 'controlled'}
    return games, boxes


def rejected(call):
    try:
        call()
        raise AssertionError('invalid box score accepted')
    except DataError:
        pass


def main():
    recorded = json.loads((ROOT/'testdata/pace_boxscores.json').read_text())
    nba, euro = recorded['nba'], recorded['euroleague']
    ns, minutes = espn_box(nba['response'], nba['fixture'])
    assert minutes == 48 and ns['home'] == dict(fga=81, fta=19, orb=13, tov=18)
    assert ns['away']['tov'] == 13  # Includes the team turnover, not only player turnovers.
    es, minutes = euro_box(euro['response'], euro['fixture'])
    assert minutes == 40 and es['home'] == dict(fga=73, fta=19, orb=15, tov=14)
    bad = deepcopy(nba['response']); bad['header']['id'] = 'wrong'
    rejected(lambda: espn_box(bad, nba['fixture']))
    bad = deepcopy(nba['response']); bad['header']['competitions'][0]['date'] = '2026-11-01T21:30Z'
    rejected(lambda: espn_box(bad, nba['fixture']))
    bad = deepcopy(nba['response']); bad['header']['competitions'][0]['competitors'][0]['linescores'] = []
    rejected(lambda: espn_box(bad, nba['fixture']))
    bad = deepcopy(nba['response'])
    bad['boxscore']['teams'][0]['statistics'] = [s for s in bad['boxscore']['teams'][0]['statistics'] if s['name'] not in {'totalTurnovers', 'teamTurnovers'}]
    rejected(lambda: espn_box(bad, nba['fixture']))
    bad = deepcopy(euro['response']); bad['road']['players'][0]['player']['club']['name'] = 'Wrong team'
    rejected(lambda: euro_box(bad, euro['fixture']))
    bad = deepcopy(euro['response']); bad['road']['total']['points'] += 1
    rejected(lambda: euro_box(bad, euro['fixture']))
    bad = deepcopy(euro['response']); bad['local']['total'].pop('offensiveRebounds')
    rejected(lambda: euro_box(bad, euro['fixture']))
    ot = deepcopy(euro['response'])
    for side in ['local', 'road']:
        ot[side]['total']['timePlayed'] = 2700
    assert euro_box(ot, euro['fixture'])[1] == 45
    ot = deepcopy(nba['response'])
    for row in ot['header']['competitions'][0]['competitors']:
        row['linescores'].append({'displayValue': '0'})
    assert espn_box(ot, nba['fixture'])[1] == 53
    # Real-response possession arithmetic and a shared fixture fetched only once.
    with tempfile.TemporaryDirectory() as directory:
        http = Mock(); http.object.return_value = nba['response']
        data = BasketballData(Store(directory+'/cache.sqlite3'), http=http)
        f = deepcopy(nba['fixture']); f['key'] = 'future'; f['kickoff'] = '2026-11-03T20:30Z'
        f['status'] = 'NS'; f['score'] = dict(home=None, away=None)
        result = boxscores(data, f, [nba['fixture']])
        b = result[nba['fixture']['key']]
        expected = ((81-13+18+.44*19)+(84-14+13+.44*26))/2
        assert abs(b['possessions']-expected) < 1e-10 and b['source_fixture_key'] == nba['fixture']['key']
        assert boxscores(data, f, [nba['fixture']]) == result and http.object.call_count == 1
        http.object.side_effect = DataError('controlled outage')
        changed = deepcopy(nba['fixture']); changed['score']['home'] += 1
        assert not boxscores(data, f, [changed]) and http.object.call_count == 2
    f = fixture(); games, boxes = controlled(f)
    classic = analyse(f, games)
    model = analyse_pace(f, games, boxes)
    assert abs(model['mu_home']-96.75) < 1e-10 and abs(model['mu_away']-99) < 1e-10
    assert model['profiles']['home']['pace'] == 80 and model['profiles']['home']['offensive_rating'] == 125
    assert model['expected_possessions'] == 90 and model['variance'] == classic['variance']
    assert analyse(f, games) == classic and model['model_version'] != classic['model_version']
    assert len(model['boxscore_inputs']) == 20 and len(model['input_games']['home']) == 10
    incomplete = dict(boxes); incomplete.pop(games[0]['key'])
    assert analyse_pace(f, games, incomplete) is None  # Do not replace missing recent games with older ones.
    future = deepcopy(games[0]); future['key'] = 'future'; future['kickoff'] = f['kickoff']
    older = deepcopy(games[0]); older['key'] = 'old'; older['kickoff'] = '2028-01-01T00:00:00Z'
    assert analyse_pace(f, games+[future, older], boxes) == model
    reversed_games, reversed_boxes = deepcopy(games), deepcopy(boxes)
    for g in reversed_games[:4]:
        g['teams'] = dict(home=g['teams']['away'], away=g['teams']['home'])
        g['score'] = dict(home=g['score']['away'], away=g['score']['home'])
        reversed_boxes[g['key']]['score'] = dict(g['score'])
        reversed_boxes[g['key']]['team_names'] = {s: g['teams'][s]['name'] for s in ['home', 'away']}
    reversed_model = analyse_pace(f, reversed_games, reversed_boxes)
    assert reversed_model['mu_home'] == model['mu_home'] and reversed_model['profiles'] == model['profiles']
    euro_fixture, euro_games, euro_boxes = deepcopy(f), deepcopy(games), deepcopy(boxes)
    euro_fixture['league'] = 'euroleague'
    for g in euro_games:
        g['league'] = 'euroleague'; euro_boxes[g['key']]['minutes'] = 40
    euro_model = analyse_pace(euro_fixture, euro_games, euro_boxes)
    assert euro_model['regulation_minutes'] == 40 and euro_model['profiles']['home']['pace'] == 80
    assert euro_model['mu_home'] == model['mu_home']
    ot_boxes = deepcopy(boxes)
    for b in ot_boxes.values():
        b['minutes'] = 53; b['possessions'] *= 53/48
    ot_model = analyse_pace(f, games, ot_boxes)
    assert abs(ot_model['profiles']['home']['pace']-80) < 1e-10
    assert abs(ot_model['expected_possessions']-90*53/48) < 1e-10
    bad = deepcopy(boxes); bad[games[0]['key']]['team_names']['away'] = 'Wrong team'
    assert analyse_pace(f, games, bad) is None
    for market, line in [('home', None), ('over', 190.5), ('under', 190), ('handicap_home', -2.5)]:
        assert abs(sum(distribution(model, market, line).values())-1) < 1e-10
    print('PASS pace: real NBA/Euro parsing, missing stats rejected, exact identity, shared-game cache, corrected-score invalidation, hand-calculated ratings/means, overtime pace, last10/future exclusion, classic unchanged')


def ui_check():
    from streamlit.testing.v1 import AppTest
    now = datetime.now(timezone.utc)
    f = fixture(kickoff=now+timedelta(days=2)); games, boxes = controlled(f)
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'BET_DB_PATH': directory+'/bets.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '', 'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': ''}), \
         patch('basketball_data.BasketballData.fixtures', return_value=[f]), \
         patch('basketball_data.BasketballData.history', return_value=games), \
         patch('basketball_pace.boxscores', return_value=boxes), \
         patch('basketball_data.BasketballData.quotes', return_value=([quote(f, now=now)], [])):
        app = AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
        mode = next(s for s in app.selectbox if s.label == 'Μοντέλο υπολογισμού')
        assert mode.value.startswith('Κλασικό')
        mode.select_index(1).run()
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception and any(m.value == '96.8 — 99.0' for m in app.metric)
        assert any('Κατοχές / 48 λεπτά' in d.value.columns for d in app.dataframe)
        app.multiselect[0].select('over').run()
        next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run()
        record = Store(directory+'/bets.sqlite3').list()[0]
        assert record['model']['model_version'] == 'basket-last10-possessions-v1'
        assert len(record['model']['boxscore_inputs']) == 20 and record['odds'] == 1.9
        next(s for s in app.selectbox if s.label == 'Μοντέλο υπολογισμού').select_index(0).run()
        assert not app.exception and not any(m.label == 'Αναμενόμενοι πόντοι μοντέλου' for m in app.metric)
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run()
        assert not app.exception and any(m.value == '95.0 — 100.0' for m in app.metric)
        with patch('basketball_pace.boxscores', return_value={}):
            next(s for s in app.selectbox if s.label == 'Μοντέλο υπολογισμού').select_index(1).run()
            next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run()
            assert not app.exception and any('Δεν υπάρχουν επαληθευμένα αναλυτικά' in w.value for w in app.warning)
            assert not any(m.label == 'Αναμενόμενοι πόντοι μοντέλου' for m in app.metric)
    print('PASS pace UI: classic default, explicit experiment, computed metrics, saved model provenance, isolated mode state')


if __name__ == '__main__':
    main()
    ui_check()
