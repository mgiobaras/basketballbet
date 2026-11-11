"""Restored classic-only UI, original probabilities, history preservation and stale-mode isolation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from basketball_data import LEAGUES
from basketball_model import MARKETS, analyse, distribution
from basketball_store import Store
from check_basketball import fixture, history, quote


def main():
    now = datetime.now(timezone.utc)
    for title, league in LEAGUES.items():
        target = fixture(kickoff=now+timedelta(days=2))
        target['league'] = league
        games = history(target)
        for game in games:
            game['league'] = league
        if league == 'greece':
            games = games[:10]  # Five actual games per team must remain supported.
        expected = analyse(target, games)
        lines = {'home': None, 'away': None, 'handicap_home': -.5, 'handicap_away': .5,
                 'over': 170.5, 'under': 170.5}
        quotes = [quote(target, market, lines[market], now=now) for market in MARKETS]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
             'BET_DB_PATH': directory+'/db.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
             'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': '', 'ODDS_API_KEY': ''}), \
             patch('basketball_data.BasketballData.fixtures', return_value=[target]), \
             patch('basketball_data.BasketballData.history', return_value=games), \
             patch('basketball_data.BasketballData.quotes', return_value=(quotes, [])), \
             patch('basketball_pace.analyse_pace', side_effect=AssertionError('Pace must be inactive')), \
             patch('basketball_adjustment.adjust_model', side_effect=AssertionError('Adjustment must be inactive')), \
             patch('nba_model.predict', side_effect=AssertionError('NBA candidate must be inactive')):
            store = Store(directory+'/db.sqlite3')
            previous = deepcopy(target)
            previous.update(key='espn:previous', id='previous')
            old_model = dict(expected, model_version='previous-adjusted-model', variance_total=999.)
            assert store.save(previous, quote(previous, now=now), {'win': .7, 'push': 0., 'loss': .3}, {}, old_model, now=now)
            original = store.list()[0]
            app = AppTest.from_file(str(Path(__file__).parent/'app.py'))
            app.session_state['model_mode'] = 'NBA — αντίπαλοι και βαθμονόμηση (παράλληλη δοκιμή)'
            for suffix in [':nba1', ':pace-adjust1', ':classic-adjust1']:
                app.session_state['analysis:'+target['key']+suffix] = old_model
            app.run(timeout=30)
            app.sidebar.selectbox[0].select(title).run(timeout=30)
            assert not app.exception
            assert not any(s.label == 'Μοντέλο υπολογισμού' for s in app.selectbox)
            assert not any(m.label == 'Αναμενόμενοι πόντοι μοντέλου' for m in app.metric)
            next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
            assert not app.exception
            logs = store.list_predictions()
            assert len(logs) == 1
            payload = logs[0]['payload']
            model = payload['model']
            assert model['model_version'] == 'basket-classic-restored-v1'
            assert model['history_counts'] == expected['history_counts']
            assert not any(k in model for k in ['variance_total', 'variance_margin', 'residuals_total', 'residuals_margin', 'probability_adjustment', 'candidate_only'])
            for field in ['mu_home', 'mu_away', 'variance', 'input_games']:
                assert model[field] == expected[field]
            for market, line in lines.items():
                assert payload['markets'][market]['probability'] == distribution(expected, market, line)
            # Restore the normal recommendation policy, rather than the NBA experiment gate.
            assert model['recommendation_policy']['recommended_market'] == 'over'
            app.multiselect[0].select('over').run(timeout=30)
            next(b for b in app.button if b.label == 'Αποθήκευση επιλογών').click().run(timeout=30)
            saved = store.list()
            assert len(saved) == 2 and next(r for r in saved if r['id'] == original['id']) == original
            restored = next(r for r in saved if r['id'] != original['id'])
            assert restored['model']['model_version'] == 'basket-classic-restored-v1'
            assert restored['probability'] == distribution(expected, 'over', 170.5)
            assert len(store.list_predictions()) == 1
    print('PASS classic restore: all three leagues, original scalar-variance probabilities, six markets, five-game Greece, stale experimental state ignored, normal policy, one private log and immutable old selections')


if __name__ == '__main__':
    main()
