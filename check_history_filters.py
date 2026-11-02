"""Controlled UI check for basketball league filters and refund-aware totals."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from check_basketball import fixture


def main():
    rows = []
    for league, status, profit in [('nba', 'won', 1.), ('nba', 'lost', -1.), ('nba', 'push', 0.),
                                   ('nba', 'pending', None), ('euroleague', 'won', 2.)]:
        game = fixture();game['league'] = league
        rows.append(dict(fixture=game, status=status, profit=profit, probability={'win': .64, 'push': 0., 'loss': .36}, stake=1., market='over', line=200., odds=3. if profit == 2 else 2.,
                         score=None if status == 'pending' else [102, 98], quote={'source': 'Controlled', 'bookmaker': 'Controlled'}, absences={}))
    original = deepcopy(rows)
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'BET_DB_PATH': d+'/test.sqlite3', 'SUPABASE_URL': '',
         'SUPABASE_SERVICE_ROLE_KEY': '', 'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': ''}), \
         patch('basketball_store.Store.list', return_value=rows), \
         patch('basketball_data.BasketballData.fixtures', return_value=[]):
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        def metrics():
            assert not app.exception
            return {m.label: m.value for m in app.metric}
        assert metrics()['Κερδισμένα'] == '2' and metrics()['Χαμένα'] == '1'
        assert set(app.dataframe[0].value['Αρχική πιθανότητα μοντέλου']) == {'64.0%'}
        assert metrics()['Επιστροφές'] == '1' and metrics()['Εκκρεμή'] == '1' and metrics()['ROI'] == '+50.0%'
        next(w for w in app.selectbox if w.label == 'Προβολή ιστορικού ανά διοργάνωση').select('NBA').run()
        assert metrics()['Επιτυχία (χωρίς επιστροφές)'] == '50.0%' and metrics()['ROI'] == '+0.0%'
        assert len(app.dataframe[0].value) == 4 and next(w for w in app.selectbox if w.label == 'Προβολή ιστορικού ανά διοργάνωση').value == 'NBA'
        next(w for w in app.selectbox if w.label == 'Προβολή ιστορικού ανά διοργάνωση').select('EuroLeague').run()
        assert metrics()['ROI'] == '+200.0%' and len(app.dataframe[0].value) == 1
        next(w for w in app.selectbox if w.label == 'Προβολή ιστορικού ανά διοργάνωση').select('Ελλάδα - Basket League').run()
        assert metrics()['Κερδισμένα'] == '0' and metrics()['ROI'] == '—' and not app.dataframe
        next(w for w in app.selectbox if w.label == 'Προβολή ιστορικού ανά διοργάνωση').select('Σύνολο').run()
        assert metrics()['Κερδισμένα'] == '2' and len(app.dataframe[0].value) == 5
    assert rows == original
    print('PASS basketball history: league dropdown, win/loss/pending/refund counts, ROI, empty league, restore totals, no record changes')


if __name__ == '__main__':
    main()
