import json,sys,hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from nba_model import features
from basketball_model import analyse,distribution
from basketball_adjustment import adjust_model
ROOT=Path(__file__).resolve().parent.parent/'data/nba_research';ROOT.mkdir(parents=True,exist_ok=True)
PROTOCOL=json.loads((Path(__file__).resolve().parent.parent/'reports/NBA_PROTOCOL.json').read_text());games=json.loads((ROOT/'games.json').read_text());rows=[];history=[]
def day(g):return datetime.fromisoformat(g['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date().isoformat()
for i,g in enumerate(games):
 if g['season']==2023:history.append(g);continue
 prior=[p for p in history if p['season']==g['season'] and day(p)<day(g)]
 counts=[sum(g['teams'][s]['id'] in {t['id'] for t in p['teams'].values()} for p in prior) for s in ['home','away']]
 if min(counts)>=10:
  x=features(g,history);base=adjust_model(g,history,analyse(g,history));h,a=[g['score'][s] for s in ['home','away']]
  if x:rows.append({'game':g,'x':x,'baseline':base,'y':{'margin':h-a,'total':h+a}})
 history.append(g)
 if i%300==0:print('replayed',i,'/',len(games),flush=True)
train=[r for r in rows if r['game']['season']==2024];cal=[r for r in rows if r['game']['season']==2025]
profile={'version':'nba-opponents-residuals-v1','fit_data_before':'2025-07-01T00:00:00+00:00','families':{},'recommendation_gate_passed':False,'historically_checked':False,'protocol':PROTOCOL}
for family in ['margin','total']:
 x=np.array([r['x'][family] for r in train]);y=np.array([r['y'][family] for r in train]);center=x.mean(axis=0);scale=x.std(axis=0);center[0]=0;scale[0]=1;scale[scale==0]=1;z=(x-center)/scale
 beta=np.linalg.solve(z.T@z+np.diag([0.,20.,20.,20.]),z.T@y)
 errors=np.array([r['y'][family]-((np.array(r['x'][family])-center)/scale)@beta for r in cal]);bias=float(errors.mean());residuals=sorted((errors-bias).tolist())
 profile['families'][family]={'center':center.tolist(),'scale':scale.tolist(),'coefficients':beta.tolist(),'bias':bias,'residual_variance':float(np.var(errors,ddof=1)),'residuals':residuals,'fit_n':len(train),'calibration_n':len(cal)}
(ROOT/'profile_frozen_before_test.json').write_text(json.dumps(profile,indent=2));(ROOT/'replay.json').write_text(json.dumps(rows))
print('frozen profile',len(train),len(cal),'test',sum(r['game']['season']==2026 for r in rows),flush=True)
