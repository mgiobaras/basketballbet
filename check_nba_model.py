"""Independent CDF/forecast leakage checks; historical inputs supplied via CLI."""
import sys,json
from copy import deepcopy
from pathlib import Path
import numpy as np
from nba_model import features,predict
from basketball_model import distribution

def main(root):
 rows=json.loads((root/'replay.json').read_text());r=next(r for r in rows if r['game']['season']==2026);games=json.loads((root/'games.json').read_text());g=r['game'];profile=json.loads((root/'nba_profile.json').read_text())
 a=features(g,games);b=features(g,[x for x in games if x['kickoff']<g['kickoff']])
 assert a==b and a['input_games']==r['x']['input_games']
 altered=deepcopy(g);altered['score']={'home':999,'away':1};assert features(altered,games)==a
 m=predict(g,games,profile);assert m and m['input_games']==a['input_games']
 for market,line in [('home',None),('away',None),('over',220.),('under',220.),('handicap_home',-3.5),('handicap_away',3.5)]:
  p=distribution(m,market,line);assert abs(sum(p.values())-1)<1e-10 and all(0<=v<=1 for v in p.values())
 assert abs(distribution(m,'home')['win']+distribution(m,'away')['win']-1)<1e-10
 assert abs(distribution(m,'handicap_home',-3.5)['win']+distribution(m,'handicap_away',3.5)['win']-1)<1e-10
 assert abs(distribution(m,'over',220.)['win']+distribution(m,'under',220.)['win']+distribution(m,'over',220.)['push']-1)<1e-10
 assert not profile['recommendation_gate_passed']
 print('PASS NBA candidate: only prior days, no target-score leakage, exact ten input IDs, coherent empirical CDF/push/complement markets, failed gate stays experimental')
if __name__=='__main__':main(Path(sys.argv[1]))
