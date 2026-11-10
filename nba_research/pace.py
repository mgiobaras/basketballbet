import json,requests,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from basketball_pace import espn_box
ROOT=Path(__file__).resolve().parent.parent/'data/nba_research';ROOT.mkdir(parents=True,exist_ok=True);C=ROOT/'boxes';C.mkdir(exist_ok=True);games=[g for g in json.loads((ROOT/'games.json').read_text()) if g['season']==2026]
def load(g):
 path=C/(g['id']+'.json')
 if path.exists():return
 u='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+g['id'];r=requests.get(u,timeout=(5,30));r.raise_for_status();d=r.json();stats,minutes=espn_box(d,g)
 poss=sum(s['fga']-s['orb']+s['tov']+.44*s['fta'] for s in stats.values())/2
 b={'kickoff':g['kickoff'],'score':g['score'],'team_names':{s:g['teams'][s]['name'] for s in ['home','away']},'possessions':poss,'minutes':minutes,'source':'espn','source_url':u}
 path.write_text(json.dumps(b))
errors=[]
with ThreadPoolExecutor(max_workers=5) as p:
 fs={p.submit(load,g):g for g in games}
 for i,f in enumerate(as_completed(fs),1):
  try:f.result()
  except Exception as e:errors.append({'id':fs[f]['id'],'error':str(e)})
  if i%100==0:print('boxscores',i,'/',len(fs),'missing',len(errors),flush=True)
(ROOT/'box_errors.json').write_text(json.dumps(errors));print('pace source complete',len(games)-len(errors),flush=True)
