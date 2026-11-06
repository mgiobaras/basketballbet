"""Available 1..10 real games, independent team counts and rolling latest-ten."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from basketball_model import analyse, distribution
from basketball_pace import analyse_pace
from basketball_store import Store
from check_basketball import fixture, history, quote
from check_pace import controlled


def main():
    f = fixture()
    games = history(f)
    few = games[:10]  # Five completed games per team.
    model = analyse(f,few)
    assert model['history_counts'] == {'home':5,'away':5}
    assert set(model['input_games']['home']) == {g['key'] for g in few[::2]}
    # With 5 home observations and 3 away observations, means stay 105/85;
    # no missing games are padded and no ten-game denominator is used.
    unequal = deepcopy(games[:6]+games[6:10:2])
    for g in unequal:
        g['score'] = {'home':100,'away':90} if g['teams']['home']['id']=='espn:1' else {'home':80,'away':110}
    independent = analyse(f,unequal)
    assert independent['history_counts'] == {'home':5,'away':3}
    assert math.isclose(independent['mu_home'],105) and math.isclose(independent['mu_away'],85)
    assert analyse(f,games[:2])['history_counts'] == {'home':1,'away':1}
    assert analyse(f,games[::2]) is None and analyse(f,[]) is None
    future = fixture('future',datetime.fromisoformat(f['kickoff'])+timedelta(days=1),score=(999,1))
    wrong = deepcopy(games[0]);wrong.update(key='other-league',league='euroleague')
    incomplete = deepcopy(games[0]);incomplete.update(key='unfinished',status='LIVE')
    assert analyse(f,few+[future,wrong,incomplete]+few) == model
    old = [fixture(900+s,datetime.fromisoformat(f['kickoff'])-timedelta(days=11),1+s,3+s,(999,1)) for s in range(2)]
    full = analyse(f,list(reversed(games+old)))
    assert full == analyse(f,games) and full['history_counts'] == {'home':10,'away':10}
    newest = fixture('newest',datetime.fromisoformat(f['kickoff'])-timedelta(hours=12),1,2,(120,110))
    rolled = analyse(f,games+old+[newest])
    for side,index in [('home',0),('away',1)]:
        ids = rolled['input_games'][side]
        assert len(ids)==10 and ids[0]==newest['key']
        assert games[18+index]['key'] not in ids and old[index]['key'] not in ids
    for market,line in [('home',None),('away',None),('over',200.5),('under',200.5),('handicap_home',-3.5),('handicap_away',3.5)]:
        p = distribution(model,market,line)
        assert p and all(math.isfinite(v) and 0<=v<=1 for v in p.values()) and math.isclose(sum(p.values()),1)
    pace_games,boxes = controlled(f)
    pace_games = pace_games[:10]
    pace = analyse_pace(f,pace_games,boxes)
    assert pace['history_counts'] == {'home':5,'away':5} and len(pace['boxscore_inputs'])==10
    missing = dict(boxes);missing.pop(pace_games[0]['key'])
    assert analyse_pace(f,pace_games,missing) is None
    ui_check()
    print('PASS available history: 5/5 and 5/3, hand-calculated means, minimum1, zero/future/unfinished/wrong-league rejection, dedupe, rolling latest10, valid probabilities, pace completeness and Greek UI/history isolation')


def ui_check():
    from streamlit.testing.v1 import AppTest
    now = datetime.now(timezone.utc)
    f = fixture(kickoff=now+timedelta(days=2)); games = history(f)[:10]
    for g in [f]+games:
        g.update(league='greece',source='esake',key=g['key'].replace('espn:','esake:'))
        for team in g['teams'].values():team['id']=team['id'].replace('espn:','esake:')
    q = quote(f,now=now);q.update(source='Paf',bookmaker='Paf')
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH':directory+'/bets.sqlite3','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'',
        'REQUIRE_REMOTE_DB':'false','APP_PASSWORD':'','ODDS_API_KEY':''}), \
         patch('basketball_data.BasketballData.fixtures',return_value=[f]), \
         patch('basketball_data.BasketballData.history',return_value=games), \
         patch('basketball_data.BasketballData.quotes',return_value=([q],[])):
        store = Store(directory+'/bets.sqlite3')
        old = dict(f,key='esake:old-selection')
        old_quote = dict(q,fixture_key=old['key'])
        assert store.save(old,old_quote,{'win':.6,'push':0.,'loss':.4},{},{'model_version':'basket-last10-normal-v1'})
        original = store.list()[0]
        app = AppTest.from_file(str(Path(__file__).parent/'app.py'))
        app.session_state['model_mode'] = 'Κλασικό — τελευταίοι 10 αγώνες'
        app.run(timeout=30)
        app.sidebar.selectbox[0].select('Ελλάδα - Basket League').run(timeout=30)
        next(b for b in app.button if b.label.startswith('Υπολογισμός')).click().run(timeout=30)
        assert not app.exception and any(m.label=='Αναμενόμενοι πόντοι μοντέλου' for m in app.metric)
        assert any('Team 1: 5/10' in c.value and 'Team 2: 5/10' in c.value for c in app.caption)
        assert app.multiselect[0].options
        log = store.list_predictions()
        assert len(log)==1 and log[0]['payload']['model']['history_counts']=={'home':5,'away':5}
        app.multiselect[0].select('over').run(timeout=30)
        next(b for b in app.button if b.label=='Αποθήκευση επιλογών').click().run(timeout=30)
        rows = store.list()
        assert len(rows)==2 and next(r for r in rows if r['id']==original['id'])==original
        saved = next(r for r in rows if r['id']!=original['id'])
        assert saved['model']['history_counts']=={'home':5,'away':5} and saved['odds']==q['odds']


if __name__ == '__main__':
    main()
