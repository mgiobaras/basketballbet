import sys,json,re,hashlib,requests
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent.parent/'data/nba_research';ROOT.mkdir(parents=True,exist_ok=True);C=ROOT/'odds';C.mkdir(exist_ok=True)
games=json.loads((ROOT/'games.json').read_text());history=[];targets=[]
for g in games:
 if g['season']==2026:
  prior=[p for p in history if p['season']==2026 and p['kickoff'][:10]<g['kickoff'][:10]]
  counts=[sum(g['teams'][s]['id'] in {t['id'] for t in p['teams'].values()} for p in prior) for s in ['home','away']]
  if min(counts)>=10:targets.append(g)
 history.append(g)
def load(g):
 path=C/(g['id']+'.json')
 if path.exists():return
 url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary'
 r=requests.get(url,params={'event':g['id']},timeout=(5,30));r.raise_for_status();d=r.json()
 packet={'source_url':url+'?event='+g['id'],'retrieved_at':datetime.now(timezone.utc).isoformat(),'response_sha256':hashlib.sha256(r.content).hexdigest(),'header':d.get('header'),'pickcenter':d.get('pickcenter',[])}
 path.write_text(json.dumps(packet))
errors=[]
with ThreadPoolExecutor(max_workers=5) as pool:
 fs={pool.submit(load,g):g for g in targets}
 for i,f in enumerate(as_completed(fs),1):
  try:f.result()
  except Exception as e:errors.append({'id':fs[f]['id'],'error':str(e)})
  if i%100==0:print('historical quotes',i,'/',len(fs),'errors',len(errors),flush=True)
(ROOT/'odds_download_errors.json').write_text(json.dumps(errors));print('done',len(targets),len(errors),flush=True)
