"""Replay an owner-provided ESAKE diagnostics JSON; uploads stay outside Git.

Usage: python check_esake_capture.py /path/to/esake_diagnostics.json
Expected capture: official programme/results received on 2026-11-06.
No live network calls, credentials or personal betting database are used.
"""
from datetime import date, datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from basketball_data import BasketballData, DataError
from basketball_store import Store
from check_greek_basket import MATCHES
from esake_data import BASE, Page, championships, games_from, selected_values


def main(path):
    records = json.loads(Path(path).read_text(encoding='utf-8'))
    received = datetime.fromisoformat(records['EsakePrograms']['captured_at'])

    class CaptureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return received.astimezone(tz) if tz else received.replace(tzinfo=None)

    expected_scores = [(95,84),(81,65),(59,73),(87,76),(53,63),(91,62),(101,91)]
    with patch('esake_data.datetime', CaptureClock), tempfile.TemporaryDirectory() as directory:
        for action in ['EsakePrograms', 'EsakeResults']:
            record = records[action]
            assert not record['truncated'] and record['url'] == BASE+action
            page = Page(record['html'])
            catalogue, year = championships(page)
            assert year == 2026 and catalogue['2026'] == '184645B9'
            assert selected_values(page, 'idseason') == ['00000001']
            games = games_from(page, year, catalogue[str(year)], '00000001', record['url'])
            assert len(games) == 7 and len({g['key'] for g in games}) == 7
            if action == 'EsakePrograms':
                assert [(g['teams']['home']['name'], g['teams']['away']['name']) for g in games] == [m[:2] for m in MATCHES]
                assert all(g['status'] == 'NS' and g['score'] == {'home':None,'away':None} for g in games)
                assert [datetime.fromisoformat(g['kickoff']).astimezone(ZoneInfo('Europe/Athens')).strftime('%d/%m %H:%M')
                        for g in games] == ['07/11 15:00','07/11 16:00','07/11 17:00','07/11 17:00','07/11 17:30','08/11 13:00','08/11 17:30']
            else:
                assert all(g['status'] == 'FT' for g in games)
                assert [(g['score']['home'], g['score']['away']) for g in games] == expected_scores
                assert page.rounds == {f'{n:02d}' for n in range(1,27)}
        http = Mock()
        http.text.side_effect = lambda url, params=None: records[url.rsplit('/',1)[1]]['html']
        http.object.side_effect = DataError('No network allowed in replay')
        store = Store(directory+'/source.sqlite3'); data = BasketballData(store, http=http)
        sat = data.fixtures('greece', date(2026,11,7)); sun = data.fixtures('greece', date(2026,11,8))
        assert len(sat) == 5 and len(sun) == 2 and not data.errors
        assert http.text.call_count == 1 and not http.object.called and not data.adapters['esake'].diagnostics
        adapter = data.adapters['esake']
        results, rounds, _ = adapter.round_page(2026, '184645B9', '00000001', '05')
        assert len(results) == 7 and len(rounds) == 26
        assert http.text.call_args.args[1]['series'] == '05'
        try:
            adapter.round_page(2026, '184645B9', '00000001', '01')
            raise AssertionError('Default round 5 accepted as requested round 1')
        except DataError as error:
            assert 'αγωνιστική' in str(error)
        assert store.list() == []
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'BET_DB_PATH': directory+'/ui.sqlite3', 'SUPABASE_URL':'',
            'SUPABASE_SERVICE_ROLE_KEY':'', 'REQUIRE_REMOTE_DB':'false', 'APP_PASSWORD':'', 'ODDS_API_KEY':''}), \
             patch('basketball_data.HTTP.text', side_effect=http.text.side_effect), \
             patch('basketball_data.HTTP.object', side_effect=DataError('No network allowed in replay')), \
             patch('basketball_data.BasketballData.quotes', return_value=([],[])):
            app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
            app.sidebar.selectbox[0].select('Ελλάδα - Basket League')
            app.sidebar.date_input[0].set_value(date(2026,11,7)).run(timeout=30)
            assert not app.exception
            assert next(s for s in app.selectbox if s.label == 'Αγώνας').options == [m[0]+' — '+m[1] for m in MATCHES[:5]]
            app.sidebar.date_input[0].set_value(date(2026,11,8)).run(timeout=30)
            assert not app.exception
            assert next(s for s in app.selectbox if s.label == 'Αγώνας').options == [m[0]+' — '+m[1] for m in MATCHES[5:]]
            assert Store(directory+'/ui.sqlite3').list() == []
    print('PASS actual ESAKE capture: season/phase, 5+2 programme games, Athens times, seven final scores, 26 JS round choices, wrong-round rejection, no Sofascore request, Streamlit lists and isolated history')


if __name__ == '__main__':
    main(sys.argv[1])
