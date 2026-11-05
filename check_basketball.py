"""Controlled model/data/storage/UI checks; not a strategy backtest."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError, ESPN, HTTP, espn_event, espn_quotes, sofa_quotes
from basketball_model import analyse, distribution, final_score, outcome
from basketball_store import Store, SupabaseStore, StorageError

NOW = datetime(2030, 1, 20, 10, tzinfo=timezone.utc)


def fixture(gid='1000', kickoff=None, home=1, away=2, score=None):
    return {'key': 'espn:'+str(gid), 'id': str(gid), 'source': 'espn', 'league': 'nba',
            'kickoff': (kickoff or NOW+timedelta(days=1)).isoformat(), 'status': 'FT' if score else 'NS',
            'teams': {s: {'id': 'espn:'+str(t), 'name': 'Team '+str(t)} for s, t in [('home', home), ('away', away)]},
            'score': dict(zip(['home', 'away'], score)) if score else {'home': None, 'away': None}}


def history(f):
    cutoff = datetime.fromisoformat(f['kickoff'])
    return [fixture(d*2+s, cutoff-timedelta(days=d), 1 if s == 0 else 2, 3+s,
                    (100+d, 90+d%3)) for d in range(1, 11) for s in range(2)]


def quote(f, market='over', line=200., now=NOW):
    return {'fixture_key': f['key'], 'market': market, 'line': line, 'odds': 1.9,
            'bookmaker': 'Controlled company', 'source': 'ESPN', 'source_url': 'https://site.api.espn.com/controlled',
            'observed_at': now.isoformat(), 'scope': 'including_overtime', 'price_kind': 'published_current'}


def event(f):
    return {'id': f['id'], 'date': f['kickoff'], 'competitions': [{'status': {'type': {'state': 'pre', 'completed': False}},
            'competitors': [{'homeAway': s, 'team': {'id': t['id'].split(':')[1], 'displayName': t['name']}}
                            for s, t in f['teams'].items()]}]}


def main():
    f = fixture()
    h = history(f)
    model = analyse(f, h)
    assert model and len(model['input_games']['home']) == len(model['input_games']['away']) == 10
    assert analyse(f, h[:9]) is None
    newer = fixture('999', datetime.fromisoformat(f['kickoff'])+timedelta(days=1), score=(150, 50))
    older = fixture('998', NOW-timedelta(days=100), score=(150, 50))
    other = deepcopy(h[0]); other['league'] = 'euroleague'
    assert analyse(f, h+[newer, older, other]) == model
    p = distribution(model, 'over', 200.)
    assert p['push'] > 0 and abs(sum(p.values())-1) < 1e-10
    assert distribution(model, 'over', 200.5)['push'] == 0
    assert outcome('over', 200, (102, 98)) == 'push'
    assert outcome('handicap_home', -4, (102, 98)) == 'push'
    assert outcome('handicap_away', 4, (102, 98)) == 'push'
    assert outcome('handicap_home', -3.5, (102, 98)) == 'won'
    assert outcome('under', 200.5, (102, 98)) == 'won'
    raw = event(f)
    prices = {'provider': {'name': 'Controlled company'}, 'pointSpread': {
        'home': {'current': {'line': '-4.5', 'odds': '-110'}, 'open': {'line': '+9.5', 'odds': '+200'}},
        'away': {'current': {'line': '+4.5', 'odds': '-110'}}},
        'total': {'over': {'current': {'line': 'o200.5', 'odds': '-110'}}}}
    raw['competitions'][0]['odds'] = [prices]
    qs = espn_quotes({'header': raw}, f, NOW.isoformat(), 'controlled')
    assert {q['market']: q['line'] for q in qs} == {'handicap_home': -4.5, 'handicap_away': 4.5, 'over': 200.5}
    raw['id'] = 'wrong'
    assert not espn_quotes({'header': raw}, f, NOW.isoformat(), 'controlled')
    raw['id'] = f['id']; raw['competitions'][0]['competitors'][0]['team']['id'] = '999'
    assert not espn_quotes({'header': raw}, f, NOW.isoformat(), 'controlled')
    raw = event(f); raw['competitions'][0]['odds'] = [{'provider': {'name': 'Controlled'}, 'pointSpread': {'home': {'current': {'line': '-4.5'}}}}]
    assert not espn_quotes({'header': raw}, f, NOW.isoformat(), 'controlled')
    sofa = {'markets': [{'marketName': 'Total (incl. overtime)', 'bookmakerId': 1, 'choiceGroup': '200.5',
                         'choices': [{'name': 'Over', 'fractionalValue': '10/11'}]}]}
    assert sofa_quotes(sofa, f, NOW.isoformat(), 'controlled')[0]['line'] == 200.5
    sofa['markets'][0]['marketName'] = 'First half total'
    assert not sofa_quotes(sofa, f, NOW.isoformat(), 'controlled')
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/basket.sqlite3')
        assert store.save(f, quote(f), p, {'home': None, 'away': {'starters': 0}}, model, now=NOW)
        assert not store.save(f, dict(quote(f), odds=2.1, line=210), p, {}, model, now=NOW)
        assert Store(directory+'/basket.sqlite3').list()[0]['line'] == 200
        for invalid in [dict(quote(f), odds=1.49), dict(quote(f), line=None), dict(quote(f), fixture_key='wrong'),
                        dict(quote(f), observed_at=(NOW-timedelta(minutes=6)).isoformat()), dict(quote(f), scope='first_half')]:
            try:
                store.save(f, invalid, p, {}, model, now=NOW)
                raise AssertionError('invalid bet accepted')
            except ValueError:
                pass
        try:
            store.save(dict(f, kickoff=(NOW-timedelta(seconds=1)).isoformat()), quote(f), p, {}, model, now=NOW)
            raise AssertionError('late bet accepted')
        except ValueError:
            pass
        calls = []
        assert store.cached('missing_result', lambda: calls.append(1), 60) is None
        assert store.cached('missing_result', lambda: calls.append(2), 60) is None
        assert calls == [1]
        done = dict(f, status='FT', score={'home': 102, 'away': 98})
        assert store.settle(done) == 1 and store.list()[0]['status'] == 'push' and store.list()[0]['profit'] == 0
        assert store.settle(done) == 0
        legacy = Path(directory)/'legacy.csv';legacy.write_text('old,unverified\n1,2\n')
        assert store.preserve_legacy(legacy) and legacy.read_text() == 'old,unverified\n1,2\n'
        data = BasketballData(store)
        primary, secondary = Mock(), Mock()
        primary.history.side_effect = DataError('controlled primary failure')
        primary.fixtures.return_value = [f]
        secondary.history.return_value = h
        secondary.fixtures.return_value = [dict(f, key='sofascore:1000', source='sofascore')]
        data.adapters = {'espn': primary, 'sofascore': secondary}
        assert len(data.history(f)) == 20
        assert data.errors == ['controlled primary failure']
        # Different source keys referring to exactly the same fixture are deduped.
        primary.history.side_effect = None;primary.history.return_value = h[:2]
        store = Store(directory+'/merge.sqlite3'); data.store = store; data.errors = []
        assert len(data.history(f)) == 20
        data.store = Store(directory+'/conflict.sqlite3')
        bad = deepcopy(h); bad[0]['score']['home'] += 1
        secondary.history.return_value = bad
        try:
            data.history(f); raise AssertionError('conflicting scores accepted')
        except ValueError:
            pass
        secondary.history.return_value = h
        # Line and receipt remain attached to their source when a market falls back.
        primary.quotes.return_value = ([quote(f, 'home', None)], [])
        secondary.quotes.return_value = ([quote(f)], [])
        with patch('basketball_data.datetime') as clock:
            clock.now.return_value = NOW
            offers, _ = data.quotes(f)
        assert {q['market'] for q in offers} == {'home', 'over'}
        assert next(q for q in offers if q['market'] == 'over')['line'] == 200
    # Remote errors never create a local store or expose the server key.
    transport = Mock(); transport.request.side_effect = __import__('requests').ConnectionError('do not leak this')
    remote = SupabaseStore('https://test.supabase.co', 'sb_secret_'+'x'*30, transport)
    try:
        remote.list(); raise AssertionError('unavailable remote accepted')
    except StorageError as error:
        assert 'do not leak' not in str(error) and 'sb_secret' not in str(error)
    print('PASS data/model/storage: last10, future exclusion, exact fixture identity, signed lines, no synthetic defaults, source fallback, immutable quotes, unit stake, refunds, legacy isolation, remote failures')


def ui_check():
    from streamlit.testing.v1 import AppTest
    now = datetime.now(timezone.utc)
    f = fixture(kickoff=now+timedelta(days=2)); h = history(f)
    q = quote(f, now=now)
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'BET_DB_PATH': directory+'/bets.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '', 'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': ''}), \
         patch('basketball_data.BasketballData.fixtures', return_value=[f]), \
         patch('basketball_data.BasketballData.history', return_value=h), \
         patch('basketball_data.BasketballData.quotes', return_value=([q], [])):
        app = AppTest.from_file(str(root/'app.py')).run(timeout=30)
        assert not app.exception
        assert len(app.sidebar.selectbox[0].options) == 3
        assert not app.radio and not any('πηγή' in s.label.lower() for s in app.selectbox)
        assert any(m.label == 'Over 200' and m.value == '1.90' for m in app.metric)
        assert any(m.label == 'Νίκη Team 1' for m in app.metric)
        assert any(m.label == 'Νίκη Team 2' for m in app.metric)
        assert any(m.label == 'Handicap Team 1' for m in app.metric)
        assert any(m.label == 'Handicap Team 2' for m in app.metric)
        assert all(n.value is None for n in app.number_input)
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception and app.multiselect[0].options
        log = Store(directory+'/bets.sqlite3').list_predictions()
        assert len(log) == 1 and len(log[0]['payload']['markets']) == 6
        assert Store(directory+'/bets.sqlite3').list() == []
        assert log[0]['payload']['markets']['over']['line'] == 200
        assert log[0]['payload']['markets']['under']['line'] is None
        assert log[0]['payload']['markets']['under']['probability'] is None
        assert log[0]['payload']['markets']['home']['probability'] is not None
        assert len(log[0]['payload']['inputs']['home']) == 10
        app.multiselect[0].select('over').run(timeout=30)
        next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run(timeout=30)
        assert not app.exception
        records = Store(directory+'/bets.sqlite3').list()
        assert len(records) == 1 and records[0]['line'] == 200 and records[0]['stake'] == 1
        next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run(timeout=30)
        assert len(Store(directory+'/bets.sqlite3').list()) == 1
        assert Store(directory+'/bets.sqlite3').list_predictions() == log
        next(c for c in app.checkbox if c.label.startswith('Χειροκίνητη')).check().run(timeout=30)
        assert not app.exception
        assert all(n.value is None for n in app.number_input)
        assert any(n.label == 'Απόδοση Νίκη Team 1' for n in app.number_input)
        assert any(n.label == 'Απόδοση Νίκη Team 2' for n in app.number_input)
    print('PASS UI: all3 competitions, automatic total line/odds, no source selector, manual absences, prediction, immutable save, empty manual fields')


if __name__ == '__main__':
    main()
    ui_check()
