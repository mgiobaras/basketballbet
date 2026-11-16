"""Controlled real-quote contract and UI/persistence checks, not a hit-rate backtest."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from alternative_lines import VERSION, select_alternatives
from basketball_data import BasketballData, DataError, Paf, paf_event, paf_quotes
from basketball_model import analyse, distribution, outcome
from basketball_store import Store
from check_basketball import fixture, history, quote
from check_paf_odds import RECORDED
from check_paf_browser import UI, Rerun
from paf_browser import browser_quotes
from player_absences import unknown
from recommendations import POLICY_VERSION, first_recommendations


def full_book():
    row = deepcopy(RECORDED)
    row['event']['start'] = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    for index, line in [(0, -1000), (2, 234000)]:
        extra = deepcopy(row['betOffers'][index])
        extra.update(id=extra['id']+100, tags=['OFFERED_PREMATCH'])
        for i, o in enumerate(extra['outcomes']):
            o.update(line=-line if index == 0 and i == 1 else line, odds=1700 if i == 0 else 2200)
        row['betOffers'].append(extra)
    return row


def main():
    now = datetime.now(timezone.utc)
    game = fixture(kickoff=now+timedelta(days=2))
    for market, line, shifted, home, away in [
        ('over', 237.5, 234.5, 125., 115.), ('under', 247.5, 250.5, 125., 115.),
        ('handicap_home', -5.5, -2.5, 125., 115.), ('handicap_away', -5.5, -2.5, 115., 125.),
        ('handicap_home', 5.5, 8.5, 122., 118.), ('handicap_away', 5.5, 8.5, 118., 122.)]:
        model = {'mu_home': home, 'mu_away': away, 'variance': 100.}
        base = quote(game, market, line, now)
        alt = dict(quote(game, market, shifted, now), odds=1.7, source='Paf', bookmaker='Paf', source_market_id=42)
        original, candidates = deepcopy(base), deepcopy(alt)
        selected, changes = select_alternatives(game, model, {market: base}, [alt], now)
        assert selected[market] == alt and changes[market]['points_easier'] == 3
        p = distribution(model, market, shifted)
        assert p['win'] > distribution(model, market, line)['win']
        assert changes[market]['selected_probability'] == p and base == original and alt == candidates
        # Reject stale/future receipts, identity/scope errors, missing companies, hard lines and invented prices.
        hard = line+3 if market == 'over' else line-3
        for change in [{'odds': 1.9}, {'odds': 1.59}, {'line': hard}, {'line': line},
                       {'line': shifted+.1}, {'odds': float('nan')}, {'line': True},
                       {'fixture_key': 'other'}, {'market': 'home'}, {'scope': 'first_half'},
                       {'bookmaker': ''}, {'source': 'Invented'},
                       {'observed_at': (now-timedelta(minutes=6)).isoformat()},
                       {'observed_at': (now+timedelta(seconds=1)).isoformat()}]:
            assert not select_alternatives(game, model, {market: base}, [dict(alt, **change)], now)[1], change
        assert not select_alternatives(dict(game, status='LIVE'), model, {market: base}, [alt], now)[1]
    model = {'mu_home': 125., 'mu_away': 115., 'variance': 100.}
    base = quote(game, 'over', 237.5, now)
    alt = dict(base, line=234.5, odds=1.7)
    near = dict(alt, line=235., odds=1.71)
    assert select_alternatives(game, model, {'over': base}, [near, alt], now)[0]['over'] == alt
    assert select_alternatives(game, model, {'over': base}, [near], now)[1]['over']['selected_probability']['push'] > 0
    assert outcome('over', 235., (117, 118)) == 'push'
    negative_ev = dict(model, mu_home=110., mu_away=100.)
    assert not select_alternatives(game, negative_ev, {'over': base}, [alt], now)[1]
    assert select_alternatives(game, model, {'over': base}, [], now) == ({'over': base}, {})
    assert not select_alternatives(game, model, {'home': quote(game, 'home', None, now)}, [alt], now)[1]
    provider_check(now)
    ui_check(now)
    print('PASS alternatives: six signed directions, actual price/line pairing, fixed selection, freshness/identity/period/EV guards, full-book refresh/closure, browser coexistence, classic math, parallel logs, saved line, duplicate protection and selection reset')


def provider_check(now):
    # The owner's recorded public Paf book already contains a second spread pair.
    captured = json.loads((Path(__file__).parent/'testdata/paf_real_panathinaikos.json').read_text())
    recorded = dict(captured['matched'], betOffers=captured['detail_response']['betOffers'])
    actual = paf_quotes(recorded, captured['requested'], captured['recorded_at'], 'recorded-source', all_lines=True)
    assert len(actual) == 8
    assert any(q['market'] == 'handicap_home' and q['line'] == 5.5 and q['odds'] == 1.43 for q in actual)
    row = full_book()
    game = paf_event(row, 'nba')
    receipt = now.isoformat()
    assert len(paf_quotes(row, game, receipt, 'source')) == 6
    parsed = paf_quotes(row, game, receipt, 'source', all_lines=True)
    assert len(parsed) == 10
    assert any(q['line'] == 234 and q['odds'] == 1.7 and q['source_market_id'] == row['betOffers'][-1]['id'] for q in parsed)
    for edit in ['event', 'period', 'closed']:
        bad = deepcopy(row)
        if edit == 'event': bad['event']['state'] = 'STARTED'
        if edit == 'period': bad['betOffers'][-1]['criterion']['lifetime'] = 'FIRST_HALF'
        if edit == 'closed': bad['betOffers'][-1]['outcomes'][0]['status'] = 'SUSPENDED'
        assert not any(q['market'] == 'over' and q['line'] == 234 for q in paf_quotes(bad, game, receipt, 'source', True))
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/cache.sqlite3')
        http = Mock()
        http.object.side_effect = [{'events': [dict(row, betOffers=row['betOffers'][:3])]},
                                  {'events': [row['event']], 'betOffers': row['betOffers']}]
        data = BasketballData(store, http)
        found, notes = data.alternative_quotes(game)
        assert len(found) == 10 and not notes and http.object.call_count == 2
        assert data.alternative_quotes(game)[0] == found and http.object.call_count == 2
        # A fresh empty/closed book removes listing quotes; changed metadata invalidates all of them.
        http.object.side_effect = [{'events': [row]}, {'events': [row['event']], 'betOffers': []}]
        assert not data.alternative_quotes(game, 1)[0]
        http.object.side_effect = [{'events': [row]}, {'events': [dict(row['event'], state='STARTED')], 'betOffers': row['betOffers']}]
        assert not data.alternative_quotes(game, 2)[0]
        http.object.side_effect = DataError('HTTP 410')
        assert not data.alternative_quotes(game, 3)[0]
        assert '410' in data.alternative_diagnostics['failed_request']['error']
        # Independent browser stages must not repeatedly discard one another's cached replies.
        ui = UI()
        def reply(*, request, **kwargs):
            payload = {'events': [row]} if '/listView/' in request['url'] else {'events': [row['event']], 'betOffers': row['betOffers']}
            return {'id': request['id'], 'ok': True, 'data': payload}
        with patch('paf_browser.component', side_effect=reply) as component:
            for _ in range(7):
                try:
                    main, _, _ = browser_quotes(ui, store, game, 30)
                    alternatives, _, _ = browser_quotes(ui, store, game, 30, all_lines=True)
                    break
                except Rerun:
                    pass
            else: raise AssertionError('Browser scopes kept replacing each other')
            assert len(main) == 6 and len(alternatives) == 10
            calls = component.call_count
            assert browser_quotes(ui, store, game, 30, all_lines=True)[0] == alternatives
            assert component.call_count == calls


def ui_check(now):
    from streamlit.testing.v1 import AppTest
    game = fixture(kickoff=now+timedelta(days=2))
    games = history(game)
    expected = analyse(game, games)
    line = int(expected['mu_home']+expected['mu_away']-3)+.5
    base = quote(game, 'over', line, now)
    alternate = dict(base, line=line-3, odds=1.7, source='Paf', bookmaker='Paf', source_market_id=987)
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH': directory+'/db.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
        'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': '', 'ODDS_API_KEY': ''}), \
         patch('basketball_data.BasketballData.fixtures', return_value=[game]), \
         patch('basketball_data.BasketballData.history', return_value=games), \
         patch('basketball_data.BasketballData.quotes', return_value=([base], [])), \
         patch('basketball_data.BasketballData.alternative_quotes', return_value=([alternate], [])) as source, \
         patch('player_absences.load_absences', return_value=(unknown(game), [])):
        store = Store(directory+'/db.sqlite3')
        old = dict(game, key='espn:previous')
        store.save(old, quote(old, now=now), distribution(expected, 'over', 200.), {}, expected)
        original = store.list()[0]
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception
        logs = store.list_predictions()
        assert len(logs) == 2
        baseline, variant = [r['payload'] for r in logs]
        assert baseline['model']['recommendation_policy']['policy_version'] == POLICY_VERSION
        assert variant['model']['recommendation_policy']['policy_version'] == VERSION
        assert baseline['markets']['over']['line'] == line and variant['markets']['over']['line'] == line-3
        assert variant['markets']['over']['quote']['source_market_id'] == 987
        for payload in [baseline, variant]:
            for key in ['mu_home', 'mu_away', 'variance', 'input_games', 'history_counts']:
                assert payload['model'][key] == expected[key]
        assert len(first_recommendations(logs)) == 2
        app.multiselect[0].select('over').run(timeout=30)
        assert len(store.list_predictions()) == 2
        next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run(timeout=30)
        assert not app.exception
        saved = next(r for r in store.list() if r['id'] != original['id'])
        assert saved['line'] == line-3 and saved['odds'] == 1.7
        assert saved['probability'] == distribution(expected, 'over', line-3)
        assert saved['model']['alternative_lines']['changes']['over']['original_line'] == line
        # Loss of alternate coverage clears the selection; no silent save of the original.
        source.return_value = ([], [])
        app.run(timeout=30)
        assert not app.exception and app.multiselect[0].value == []
        assert next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').disabled
        source.return_value = ([alternate], [])
        next(c for c in app.checkbox if c.label == 'Ευκολότερες γραμμές κοντά στο 1,70').uncheck().run(timeout=30)
        app.multiselect[0].select('over').run(timeout=30)
        next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run(timeout=30)
        assert store.list() == sorted([original, saved], key=lambda r: r['id'])


if __name__ == '__main__':
    main()
