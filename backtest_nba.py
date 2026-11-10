"""Frozen chronological NBA experiment; actual ESPN closing prices, no price defaults."""
import argparse,csv,json,math
from pathlib import Path
import numpy as np
from basketball_model import distribution,outcome
from basketball_data import espn_event


def decimal(value):
 try:
  v=float(str(value).replace('−','-'))
  return 1+v/100 if v>0 else 1+100/abs(v) if v<0 else None
 except (ValueError,TypeError):return None


def closing_quotes(packet,game):
 native=espn_event(packet.get('header',{}),'nba')
 if not native or native['key']!=game['key'] or native['teams']!=game['teams'] or native['score']!=game['score'] or native['kickoff']!=game['kickoff']:return {}
 providers=packet.get('pickcenter',[])
 if len(providers)!=1 or not providers[0].get('provider',{}).get('name'):return {}
 row=providers[0];quotes={}
 for market,group,side in [('home','moneyline','home'),('away','moneyline','away'),('handicap_home','pointSpread','home'),('handicap_away','pointSpread','away'),('over','total','over'),('under','total','under')]:
  close=row.get(group,{}).get(side,{}).get('close',{});odd=decimal(close.get('odds'));line=None
  if odd is None:continue
  if group!='moneyline':
   try:line=float(str(close['line']).lstrip('ouOU'))
   except (KeyError,ValueError):continue
   if not (2*line).is_integer():continue
  quotes[market]={'odds':odd,'line':line,'bookmaker':row['provider']['name'],'source_url':packet['source_url'],'snapshot':'close','receipt_before_kickoff':None}
 return quotes


def candidate(row,profile):
 values={}
 for f in ['margin','total']:
  s=profile['families'][f];values[f]=float(((np.array(row['x'][f])-s['center'])/s['scale'])@s['coefficients']+s['bias'])
 return {'mu_home':(values['total']+values['margin'])/2,'mu_away':(values['total']-values['margin'])/2,'variance':profile['families']['margin']['residual_variance'],
         **{'variance_'+f:profile['families'][f]['residual_variance'] for f in ['margin','total']},
         **{'residuals_'+f:profile['families'][f]['residuals'] for f in ['margin','total']}}


def run(root):
 profile=json.loads((root/'profile_frozen_before_test.json').read_text());rows=[r for r in json.loads((root/'replay.json').read_text()) if r['game']['season']==2026]
 results={};allbets=[];missing=[];paired=[];pool={v['key']:v for v in json.loads((root/'games.json').read_text())}
 for name in ['original','candidate','pace']:
  bets=[];briers=[];market_briers=[];seen_quotes=0
  for row in rows:
   g=row['game'];model=row['baseline'] if name=='original' else candidate(row,profile)
   if name=='pace':
    from basketball_pace import analyse_pace
    from basketball_adjustment import adjust_model
    ids={i for arr in row['baseline']['input_games'].values() for i in arr}
    hist=[pool[i] for i in ids];boxes={}
    for i in ids:
     path=root/'boxes'/(pool[i]['id']+'.json')
     if path.exists():boxes[i]=json.loads(path.read_text())
    raw=analyse_pace(g,hist,boxes)
    if raw is None:continue
    model=adjust_model(g,hist,raw)
   score=[g['score'][s] for s in ['home','away']]
   p=distribution(model,'home');briers.append((p['win']-int(score[0]>score[1]))**2)
   path=root/'odds'/(g['id']+'.json');q=closing_quotes(json.loads(path.read_text()),g) if path.exists() else {}
   if not q:
    if name=='candidate':missing.append(g['key'])
    continue
   seen_quotes+=1;choices=[]
   for market,quote in q.items():
    p=distribution(model,market,quote['line'])
    if not p:continue
    status=outcome(market,quote['line'],score);pc=p['win']/(1-p['push']);ev=p['win']*(quote['odds']-1)-p['loss']
    market_briers.append((pc-int(status=='won'))**2) if status!='push' else None
    if pc>=.70 and quote['odds']>=1.5 and ev>=.03:
     choices.append({'model':name,'fixture_key':g['key'],'kickoff':g['kickoff'],'market':market,**quote,'probability':pc,'EV':ev,'status':status,'score':score,'profit':quote['odds']-1 if status=='won' else -1 if status=='lost' else 0})
   if choices:bets.append(max(choices,key=lambda v:(v['probability'],v['EV'],v['market'])))
  wins=sum(b['status']=='won' for b in bets);loss=sum(b['status']=='lost' for b in bets);profit=sum(b['profit'] for b in bets)
  results[name]={'eligible_games':len(briers),'games_with_quotes':seen_quotes,'bets':len(bets),'wins':wins,'losses':loss,'pushes':len(bets)-wins-loss,'hit_rate':wins/(wins+loss) if wins+loss else None,'profit':profit,'roi':profit/len(bets) if bets else None,'home_brier':float(np.mean(briers)),'priced_market_brier':float(np.mean(market_briers))}
  allbets.extend(bets)
 c=results['candidate'];o=results['original'];gate=c['bets']>=50 and (c['hit_rate'] or 0)>=.70 and c['profit']>0 and c['home_brier']<o['home_brier']
 profile.update(historically_checked=True,recommendation_gate_passed=gate)
 (root/'nba_profile.json').write_text(json.dumps(profile,indent=2))
 report={'season':'2025-2026','criterion':'both teams >=10 completed regular-season games before Athens match day','results':results,'recommendation_gate_passed':gate,'missing_quotes':missing,'closing_prices_with_no_capture_timestamp':True,'protocol':profile['protocol']}
 (root/'results.json').write_text(json.dumps(report,indent=2));(root/'bets.json').write_text(json.dumps(allbets,indent=2))
 with (root/'bets.csv').open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(allbets[0]) if allbets else ['model']);w.writeheader();w.writerows(allbets)
 print(json.dumps(report,indent=2))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);run(parser.parse_args().directory)
