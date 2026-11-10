import requests,json,sys,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from basketball_data import espn_event
from basketball_model import final_score
ROOT=Path(__file__).resolve().parent.parent/'data/nba_research';ROOT.mkdir(parents=True,exist_ok=True);CACHE=ROOT/'public';CACHE.mkdir(exist_ok=True)
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
def get(url,params,path):
 if path.exists():return json.loads(path.read_text())
 r=requests.get(url,params=params,timeout=(5,35));r.raise_for_status();d=r.json();path.write_text(json.dumps(d));return d
d=get(BASE+'/teams',{'limit':100},CACHE/'teams.json');teams=[x['team']['id'] for x in d['sports'][0]['leagues'][0]['teams']]
def schedule(year,tid):
 d=get(BASE+f'/teams/{tid}/schedule',{'season':year,'seasontype':2},CACHE/f'schedule_{year}_{tid}.json')
 return year,[g for e in d.get('events',[]) if e.get('competitions',[{}])[0].get('type',{}).get('type')!='commissioners-cup' and (g:=espn_event(e,'nba')) and final_score(g) is not None]
allgames={}
with ThreadPoolExecutor(max_workers=5) as p:
 fs=[p.submit(schedule,y,t) for y in [2023,2024,2025,2026] for t in teams]
 for i,f in enumerate(as_completed(fs),1):
  y,gs=f.result()
  for g in gs:g['season']=y;allgames[g['key']]=g
  if i%20==0:print('schedules',i,'/',len(fs),flush=True)
(ROOT/'games.json').write_text(json.dumps(sorted(allgames.values(),key=lambda g:g['kickoff'])))
print('games',len(allgames),flush=True)
