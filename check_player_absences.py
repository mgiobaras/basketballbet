"""Replay real ESPN reports, reject unsafe identity, and preserve classic maths/old selections."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError, espn_event
from basketball_model import analyse, distribution
from basketball_store import Store
from check_basketball import history, quote
from player_absences import load_absences, parse_espn, unknown

ROOT = Path(__file__).parent


def main():
    recorded = json.loads((ROOT/'testdata/espn_absences_recorded.json').read_text())
    game, data = recorded['fixture'], recorded['data']
    reports, notes = parse_espn(data, game, recorded['observed_at'], recorded['source_url'])
    assert not notes and [reports[s]['count'] for s in ['home','away']]==[4,2]
    assert len(reports['away']['players'])==5  # Three day-to-day reports are not counted as absences.
    duplicate = deepcopy(data); duplicate['injuries'][0]['injuries'].append(deepcopy(duplicate['injuries'][0]['injuries'][0]))
    assert parse_espn(duplicate,game,recorded['observed_at'],'controlled')[0]['home']['count']==4
    conflict = deepcopy(duplicate); conflict['injuries'][0]['injuries'][-1]['status']='Day-To-Day'
    assert parse_espn(conflict,game,recorded['observed_at'],'controlled')[0]['home']['count'] is None
    empty = deepcopy(data);empty['injuries'][0]['injuries']=[]
    assert parse_espn(empty,game,recorded['observed_at'],'controlled')[0]['home']['count']==0
    missing = deepcopy(data);missing.pop('injuries')
    assert all(r['count'] is None for r in parse_espn(missing,game,recorded['observed_at'],'controlled')[0].values())
    for change in ['id','time','teams','league']:
        wrong=deepcopy(game)
        if change=='id':wrong['key']='espn:other'
        if change=='time':wrong['kickoff']=(datetime.fromisoformat(game['kickoff'])+timedelta(hours=1)).isoformat()
        if change=='teams':wrong['teams']['home']['id']='espn:other'
        if change=='league':wrong['league']='euroleague'
        try:parse_espn(data,wrong,recorded['observed_at'],'controlled');raise AssertionError(change)
        except DataError:pass
    now=datetime.now(timezone.utc)
    target=deepcopy(game);target['kickoff']=(now+timedelta(days=2)).isoformat()
    shifted=deepcopy(data);shifted['header']['date']=target['kickoff']
    shifted['header']['competitions'][0]['date']=target['kickoff']
    with tempfile.TemporaryDirectory() as d:
        http=Mock();http.object.return_value=shifted
        provider=BasketballData(Store(d+'/data.sqlite3'),http)
        found,notes=load_absences(provider,target)
        assert not notes and found['home']['count']==4 and found['away']['count']==2
        load_absences(provider,target);http.object.assert_called_once()
        provider.native=Mock(side_effect=AssertionError('Historical/unsupported games must not fetch current reports'))
        historical=dict(target,kickoff=(now-timedelta(days=1)).isoformat())
        assert load_absences(provider,historical)[0]['home']['count'] is None
        assert load_absences(provider,dict(target,league='greece'))[0]['home']['count'] is None
        provider.native=Mock(return_value=target);http.object.side_effect=DataError('controlled HTTP403')
        assert load_absences(provider,target,1)[0]['home']['count'] is None
        calls=http.object.call_count;load_absences(provider,target,1);assert http.object.call_count==calls
    ui_check(target,found)
    print('PASS absences: real ESPN 4/2 plus three uncertain, exact identity/time, explicit zero vs unknown, duplicates/conflicts, no historical current-data leakage, cached source failures and UI/manual persistence')


def ui_check(target, reports):
    from streamlit.testing.v1 import AppTest
    now=datetime.now(timezone.utc)
    games=history(target)
    for g in games:
        for team in g['teams'].values():
            if team['id']=='espn:1':team['id']=target['teams']['home']['id']
            elif team['id']=='espn:2':team['id']=target['teams']['away']['id']
    baseline=analyse(target,games);q=quote(target,now=now)
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'BET_DB_PATH':d+'/db.sqlite3',
         'SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'','REQUIRE_REMOTE_DB':'false','APP_PASSWORD':'','ODDS_API_KEY':''}), \
         patch('basketball_data.BasketballData.fixtures',return_value=[target]), \
         patch('basketball_data.BasketballData.history',return_value=games), \
         patch('basketball_data.BasketballData.quotes',return_value=([q],[])), \
         patch('player_absences.load_absences',return_value=(reports,[])) as source:
        store=Store(d+'/db.sqlite3')
        old=dict(target,key='espn:previous')
        legacy_absences={'home':{'starters':1,'reserves':2},'away':None}
        assert store.save(old,quote(old,now=now),{'win':.6,'push':0.,'loss':.4},legacy_absences,{},now=now)
        original=store.list()[0]
        app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
        assert not app.exception
        assert not any('Βασικοί' in n.label or 'Αναπληρωματικοί' in n.label for n in app.number_input)
        assert next(m.value for m in app.metric if m.label=='Απουσίες — '+target['teams']['home']['name'])=='4'
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception
        logs=store.list_predictions();assert len(logs)==1
        assert logs[0]['payload']['absences']['home']['count']==4
        assert logs[0]['payload']['model']['mu_home']==baseline['mu_home']
        fresh=deepcopy(reports)
        for r in fresh.values():r['observed_at']=(now+timedelta(seconds=1)).isoformat()
        source.return_value=(fresh,[])
        app.run(timeout=30)
        assert len(store.list_predictions())==1  # A receipt refresh alone is not another forecast.
        next(c for c in app.checkbox if c.key=='manual_absences:'+target['key']).check().run(timeout=30)
        for side,count in [('home',3),('away',0)]:
            next(n for n in app.number_input if n.key=='absence_count:'+target['key']+':'+side).set_value(count)
        app.run(timeout=30)
        app.multiselect[0].select('over').run(timeout=30)
        next(b for b in app.button if b.label=='Αποθήκευση επιλογών').click().run(timeout=30)
        assert not app.exception
        rows=store.list();assert len(rows)==2 and next(r for r in rows if r['id']==original['id'])==original
        saved=next(r for r in rows if r['id']!=original['id'])
        assert [saved['absences'][s]['count'] for s in ['home','away']]==[3,0]
        assert all(saved['absences'][s]['source']=='Χειροκίνητη καταχώριση' for s in ['home','away'])
        assert saved['probability']==distribution(baseline,'over',200.)
        assert store.list_predictions()[0]==logs[0]
        # A different fixture never inherits manually entered numbers from the previous one.
        other=deepcopy(target);other.update(key='espn:another',id='another')
        source.return_value=(unknown(other),['controlled missing report'])
        with patch('basketball_data.BasketballData.fixtures',return_value=[other]):
            app.run(timeout=30)
            assert not app.exception
            next(c for c in app.checkbox if c.key=='manual_absences:'+other['key']).check().run(timeout=30)
            inputs=[n for n in app.number_input if n.key.startswith('absence_count:')]
            assert len(inputs)==2 and all(n.value is None for n in inputs)


if __name__=='__main__':main()
