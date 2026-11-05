"""History order, original probabilities, push accounting and stable fixture selection."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from check_basketball import fixture


def main():
    now = datetime.now(timezone.utc)
    game = fixture(kickoff=now+timedelta(days=2))
    other = fixture('other', kickoff=now+timedelta(days=2, hours=1), home=3, away=4)
    rows = []
    for label, kickoff, chance, state in [
        ('Later', '2030-01-02T12:00:00Z', .99, 'pending'),
        ('Lower', '2030-01-01T12:00:00Z', .61, 'lost'),
        ('Unknown', '2030-01-01T12:00:00Z', None, 'push'),
        ('Higher', '2030-01-01T14:00:00+02:00', .81, 'won')]:
        f = deepcopy(game); f['kickoff'] = kickoff; f['teams']['home']['name'] = label
        rows.append(dict(fixture=f, market='over', line=200, odds=1.9, stake=1., status=state,
                         probability={'win': chance}, profit=.9 if state == 'won' else -1. if state == 'lost' else 0.,
                         score=None, absences={}, quote={'source': 'controlled'}, model={}))
    before = deepcopy(rows)
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'BET_DB_PATH': d+'/bets.sqlite3', 'SUPABASE_URL': '',
         'SUPABASE_SERVICE_ROLE_KEY': '', 'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': '', 'ODDS_API_KEY': ''}), \
         patch('basketball_store.Store.list', return_value=rows), \
         patch('basketball_data.BasketballData.fixtures', return_value=[game, other]) as games, \
         patch('basketball_data.BasketballData.quotes', return_value=([], [])):
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        assert not app.exception
        table = app.dataframe[0].value
        assert list(table['Αγώνας']) == ['Higher — Team 2', 'Lower — Team 2', 'Unknown — Team 2', 'Later — Team 2']
        assert table.iloc[0]['Ημερομηνία'] == '01/01/2030 14:00'
        metrics = {m.label: m.value for m in app.metric}
        assert metrics['Κερδισμένα'] == metrics['Χαμένα'] == metrics['Εκκρεμή'] == '1'
        assert metrics['Επιτυχία (χωρίς επιστροφές)'] == '50.0%'
        assert any(c.value.startswith('Επιστροφές: 1') for c in app.caption)
        games.return_value = [other, game]
        next(c for c in app.checkbox if c.label.startswith('Χειροκίνητη καταχώριση')).check().run()
        assert not app.exception
        assert next(s for s in app.selectbox if s.label == 'Αγώνας').value == game['key']
        assert all(n.value is None for n in app.number_input)
    assert rows == before
    print('PASS basketball history: kickoff/timezone order, descending original probability, missing probability last, unchanged records, three counts, push excluded, stable fixture')


if __name__ == '__main__':
    main()
