"""Date and league filters agree with metrics/CSV, preserve full backups and never alter history."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import csv
import io
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from check_basketball import fixture


def main():
    target = fixture(kickoff=datetime.now(timezone.utc)+timedelta(days=2))
    rows = []
    for name, kickoff, league, state, profit in [
        ('Before', '2030-07-05T20:59:59Z', 'nba', 'won', 1.),
        ('First', '2030-07-05T21:00:00Z', 'nba', 'won', 1.),
        ('Loss', '2030-07-06T12:00:00Z', 'nba', 'lost', -1.),
        ('Refund', '2030-07-06T13:00:00Z', 'nba', 'push', 0.),
        ('Pending', '2030-07-07T12:00:00Z', 'nba', 'pending', 0.),
        ('Last', '2030-07-07T20:59:59Z', 'euroleague', 'won', .8),
        ('After', '2030-07-07T21:00:00Z', 'nba', 'lost', -1.),
    ]:
        game = deepcopy(target)
        game.update(key='controlled:'+name, kickoff=kickoff, league=league)
        game['teams']['home']['name'] = name
        rows.append(dict(fixture=game, market='over', line=200.5, odds=1.8 if name=='Last' else 2.,
                         stake=1., status=state, probability={'win': .7}, profit=profit,
                         score=None, absences={}, quote={'source': 'controlled'}, model={}))
    original = deepcopy(rows)
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
         'BET_DB_PATH': directory+'/db.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
         'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': '', 'ODDS_API_KEY': ''}), \
         patch('basketball_store.Store.list', return_value=rows), \
         patch('basketball_data.BasketballData.fixtures', return_value=[target]), \
         patch('basketball_data.BasketballData.quotes', return_value=([], [])), \
         patch('streamlit.download_button', wraps=st.download_button) as downloads:
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        assert not app.exception and len(app.dataframe[0].value)==7

        def dates(start, end):
            next(d for d in app.date_input if d.key=='history_from').set_value(start)
            next(d for d in app.date_input if d.key=='history_to').set_value(end)
            app.run(timeout=30)
            assert not app.exception

        def metrics():
            return {m.label: m.value for m in app.metric}

        dates(date(2030,7,6), date(2030,7,7))
        values = metrics()
        assert [values[k] for k in ['Κερδισμένα','Χαμένα','Εκκρεμή']]==['2','1','1']
        assert values['Επιτυχία (χωρίς επιστροφές)']=='66.7%'
        assert values['Καθαρό κέρδος']=='+0.80 μονάδες' and values['ROI']=='+20.0%'
        assert values['Δείγμα']=='3 κρίθηκαν · 1 επιστροφές'
        table = app.dataframe[0].value
        assert [v.split(' — ')[0] for v in table['Αγώνας']]==['First','Loss','Refund','Pending','Last']
        exported = next(c.args[1] for c in reversed(downloads.call_args_list) if c.args[0]=='Εξαγωγή CSV επιλεγμένου διαστήματος')
        assert len(list(csv.DictReader(io.StringIO(exported.decode('utf-8-sig')))))==5

        next(s for s in app.selectbox if s.label=='Προβολή ιστορικού ανά διοργάνωση').select('NBA').run(timeout=30)
        assert metrics()['Επιτυχία (χωρίς επιστροφές)']=='50.0%' and metrics()['ROI']=='+0.0%'
        assert len(app.dataframe[0].value)==4
        dates(date(2030,7,7), date(2030,7,7))
        assert metrics()['Εκκρεμή']=='1' and metrics()['Επιτυχία (χωρίς επιστροφές)']=='—' and metrics()['ROI']=='—'
        dates(date(2030,7,9), date(2030,7,10))
        assert not app.dataframe and metrics()['Δείγμα']=='0 κρίθηκαν · 0 επιστροφές'
        assert metrics()['Επιτυχία (χωρίς επιστροφές)']=='—' and metrics()['ROI']=='—'
        dates(date(2030,7,8), date(2030,7,6))
        assert any('πριν ή ίδια' in w.value for w in app.warning)
        assert 'Κερδισμένα' not in metrics() and not app.dataframe
        dates(None, date(2030,7,7))
        assert any('και τις δύο' in w.value for w in app.warning)
        assert 'Κερδισμένα' not in metrics()
        backup = next(c.args[1] for c in reversed(downloads.call_args_list) if c.args[0]=='Αντίγραφο όλων των επιλογών JSON')
        assert json.loads(backup)==original
    assert rows==original
    print('PASS history dates: Athens summer-midnight boundaries, inclusive/single-day ranges, league intersection, win/loss/push/pending, ROI, empty/invalid/incomplete ranges, filtered CSV and full immutable JSON')


if __name__=='__main__':
    main()
