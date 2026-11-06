"""Recover verified history across archive outages; no fabricated production data.

Optional argument replays the owner's real esake_diagnostics.json default pages.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError
from basketball_model import analyse, recent_games
from basketball_store import Store
from check_greek_basket import header, block
from esake_data import BASE, Page, games_from


def page_for(round_number, home_id='3CA10C07', away_id='00000005'):
    day = round_number+3
    a = block(f'F00000{round_number:02d}','ΔΟΞΑ ΛΕΥΚΑΔΑΣ ELABET','Opponent A',f'Σαβ {day} Οκτ - 15:00','85 - 75',round_number)
    b = block(f'E00000{round_number:02d}','ΑΡΗΣ','Opponent B',f'Σαβ {day} Οκτ - 17:00','90 - 80',round_number)
    a = a.replace('A0000001',home_id).replace('A0000002','A0000007')
    b = b.replace('A0000001',away_id).replace('A0000002','A0000008')
    return header(rounds=tuple(str(n) for n in range(1,27)))+a+b


def main(capture=None):
    target_page = header()+block('7E44FE22','ΔΟΞΑ ΛΕΥΚΑΔΑΣ ELABET','ΑΡΗΣ','Σαβ 7 Νοε - 15:00')
    target_page = target_page.replace('A0000001','3CA10C07').replace('A0000002','00000005')
    target = games_from(Page(target_page),2026,'184645B9','00000001','controlled-programme')[0]
    latest = page_for(5)
    if capture:
        raw = json.loads(Path(capture).read_text(encoding='utf-8'))
        latest = raw['EsakeResults']['html']
        actual = games_from(Page(raw['EsakePrograms']['html']),2026,'184645B9','00000001',BASE+'EsakePrograms')
        target = next(g for g in actual if g['id']=='7E44FE22')
    with tempfile.TemporaryDirectory() as directory:
        http = Mock()
        def response(url, params=None):
            if url.endswith('EsakePrograms'):
                return target_page
            if params is None:
                return latest
            raise DataError('Αποτυχία ασφαλούς σύνδεσης με www.esake.gr.')
        http.text.side_effect = response
        data = BasketballData(Store(directory+'/partial.sqlite3'),http=http)
        data.adapters['sofascore'].fixtures = Mock(side_effect=DataError('controlled Sofascore403'))
        # Prove a previously cached empty six-hour history cannot suppress recovery.
        data.store.cached('history:'+target['key'],lambda:[],6*3600)
        partial = data.history(target)
        model = analyse(target,partial)
        assert model and model['history_counts']=={'home':1,'away':1}
        if capture:
            # Actual round5: Doxa won away73-59; Aris won home101-91.
            assert math.isclose(model['mu_home'],82) and math.isclose(model['mu_away'],80)
        assert any('σύνδεσης' in e for e in data.errors)
        assert len(data.adapters['esake'].diagnostics) <= 4
        assert all(call.args[1]['idseason']=='00000001' and call.args[1]['idchampionship']=='184645B9'
                   for call in http.text.call_args_list if len(call.args)>1 and call.args[1])
        # Archive recovers without discarding the verified latest round. Older
        # round numbers can have later kickoff dates, so selection stays by time.
        def recovered(url,params=None):
            if params is None:
                return latest
            number = int(params['series'])
            assert 1 <= number <= 4 and params['idseason']=='00000001'
            return page_for(number)
        http.text.side_effect = recovered
        data.errors=[]
        full = data.history(target)
        assert analyse(target,full)['history_counts']=={'home':5,'away':5}
        for side in ['home','away']:
            picked = recent_games(full,target,side)
            assert len({g['key'] for g in picked})==5 and {g['round'] for g in picked}=={1,2,3,4,5}
        assert data.store.list()==[]
        requests_before=http.text.call_count
        data.history(target)
        assert http.text.call_count==requests_before  # Valid per-round cache, no repeated archive storm.
        # No valid data means abstention; history is never invented to satisfy min1.
        down = Mock();down.text.side_effect=DataError('controlled offline')
        empty = BasketballData(Store(directory+'/empty.sqlite3'),http=down)
        empty.adapters['sofascore'].fixtures = Mock(side_effect=DataError('controlled403'))
        assert analyse(target,empty.history(target)) is None
        # The same official record on a default and scoped URL is one observation.
        adapter=data.adapters['esake']
        adapter.latest_results = Mock(return_value={'games':[dict(g,source_url='different-url') for g in full]})
        assert len(adapter.history(target))==len(full)
        # Genuine conflicting scores remain fatal rather than silently skipped.
        conflict=deepcopy(full[0]);conflict['score']['home']+=1
        adapter.latest_results.return_value={'games':[full[0],conflict]}
        try:
            adapter.history(target);raise AssertionError('Conflicting source scores accepted')
        except ValueError:
            pass
        # A postponed round1 game played late must enter the latest10 even
        # after ten games were found in numerically newer rounds.
        late_target=dict(target,round=13)
        later_http=Mock()
        def rescheduled(url,params=None):
            number=int(params['series']) if params else 12
            html=page_for(number)
            return html.replace('Σαβ 4 Οκτ','Πεμ 5 Νοε') if number==1 else html
        later_http.text.side_effect=rescheduled
        later=BasketballData(Store(directory+'/rolling.sqlite3'),http=later_http).adapters['esake']
        observations=later.history(late_target)
        assert analyse(late_target,observations)['history_counts']=={'home':10,'away':10}
        for side in ['home','away']:
            picked=recent_games(observations,late_target,side)
            assert picked[0]['round']==1 and {g['round'] for g in picked}=={1,*range(4,13)}
    ui_check(target,latest)
    print('PASS ESAKE history: verified latest results survive archive timeouts, 1/1 -> 5/5 after recovery, old empty cache bypassed, no future-phase/previous-season requests, per-round cache, duplicate URL isolation, conflict/zero guards and real Greek calculation UI')


def ui_check(target,latest):
    from streamlit.testing.v1 import AppTest
    now=datetime.now(timezone.utc)
    q={'fixture_key':target['key'],'market':'over','line':160.5,'odds':1.9,'source':'Paf','bookmaker':'Paf',
       'observed_at':now.isoformat(),'scope':'including_overtime','price_kind':'controlled'}
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH':directory+'/ui.sqlite3','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'',
        'REQUIRE_REMOTE_DB':'false','APP_PASSWORD':'','ODDS_API_KEY':''}), \
         patch('basketball_data.BasketballData.fixtures',return_value=[target]), \
         patch('basketball_data.BasketballData.quotes',return_value=([q],[])), \
         patch('basketball_data.Sofa.fixtures',side_effect=DataError('controlled403')), \
         patch('basketball_data.HTTP.text') as text:
        text.side_effect=lambda url,params=None: latest if params is None else page_for(int(params['series']))
        app=AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        app.sidebar.selectbox[0].select('Ελλάδα - Basket League').run(timeout=30)
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception and any(m.label=='Αναμενόμενοι πόντοι μοντέλου' for m in app.metric)
        assert any('5/10' in c.value for c in app.caption)
        log=Store(directory+'/ui.sqlite3').list_predictions()
        assert len(log)==1 and log[0]['payload']['model']['history_counts']=={'home':5,'away':5}


if __name__=='__main__':
    main(sys.argv[1] if len(sys.argv)>1 else None)
