"""Opponent-adjusted NBA candidate. Frozen historical fit; no owner bets used."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
from zoneinfo import ZoneInfo
from basketball_model import instant, final_score, recent_games

VERSION='nba-opponents-residuals-v1'


def features(game, history):
    cutoff=instant(game['kickoff'])
    pool={g['key']:g for g in history if g['league']=='nba' and final_score(g) is not None
          and 0<(cutoff-instant(g['kickoff'])).total_seconds()<=366*86400
          and instant(g['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date()<cutoff.astimezone(ZoneInfo('Europe/Athens')).date()}
    groups=[recent_games(list(pool.values()),game,s) for s in ['home','away']]
    if any(len(g)<10 for g in groups):return None
    teams=sorted({t['id'] for g in pool.values() for t in g['teams'].values()})
    index={t:i+1 for i,t in enumerate(teams)};size=len(teams)+1
    xm=[];xt=[];ym=[];yt=[];weights=[]
    for g in pool.values():
        h,a=final_score(g);i,j=[index[g['teams'][s]['id']] for s in ['home','away']]
        m=np.zeros(size);t=np.zeros(size);m[0]=t[0]=1;m[i]=1;m[j]=-1;t[i]=t[j]=1
        xm.append(m);xt.append(t);ym.append(h-a);yt.append(h+a)
        weights.append(.5**((cutoff-instant(g['kickoff'])).total_seconds()/86400/90))
    w=np.array(weights);penalty=np.diag([0.]+[20.]*(size-1))
    def fit(x,y):
        x=np.array(x);return np.linalg.solve(x.T@(w[:,None]*x)+penalty,x.T@(w*np.array(y)))
    margin,total=fit(xm,ym),fit(xt,yt)
    profiles=[]
    for side,games in zip(['home','away'],groups):
        tid=game['teams'][side]['id'];observed=[];ws=[]
        for g in games:
            own='home' if g['teams']['home']['id']==tid else 'away';other='away' if own=='home' else 'home'
            h,a=final_score(g);gf,ga=(h,a) if own=='home' else (a,h)
            opponent=index[g['teams'][other]['id']]
            observed.append([gf-ga,gf+ga,gf-ga-(margin[0] if own=='home' else -margin[0])+margin[opponent],gf+ga-total[0]-total[opponent]])
            ws.append(.5**((cutoff-instant(g['kickoff'])).total_seconds()/86400/90))
        profiles.append(np.average(observed,axis=0,weights=ws))
    h,a=profiles;i,j=[index[game['teams'][s]['id']] for s in ['home','away']]
    return {'margin':[1.,float((h[0]-a[0])/2),float(h[2]-a[2]+margin[0]),float(margin[i]-margin[j]+margin[0])],
            'total':[1.,float((h[1]+a[1])/2),float(h[3]+a[3]+total[0]),float(total[0]+total[i]+total[j])],
            'input_games':{s:[g['key'] for g in gs] for s,gs in zip(['home','away'],groups)}}


def predict(game,history,profile=None):
    if profile is None:
        path=Path(__file__).with_name('nba_profile.json')
        if not path.exists():return None
        profile=json.loads(path.read_text())
    if instant(game['kickoff'])<=instant(profile['fit_data_before']):return None
    cutoff=instant(game['kickoff']);start=cutoff.replace(year=cutoff.year-(cutoff.month<7),month=7,day=1,hour=0,minute=0,second=0,microsecond=0)
    if any(sum(start<=instant(g['kickoff'])<cutoff and final_score(g) is not None and
           game['teams'][s]['id'] in {t['id'] for t in g['teams'].values()} for g in history)<10 for s in ['home','away']):return None
    values=features(game,history)
    if values is None:return None
    means={};variances={}
    for family in ['margin','total']:
        spec=profile['families'][family];x=np.array(values[family]);scale=np.array(spec['scale']);center=np.array(spec['center'])
        means[family]=float(((x-center)/scale)@np.array(spec['coefficients'])+spec['bias'])
        variances[family]=spec['residual_variance']
    return {'model_version':VERSION,'mu_home':(means['total']+means['margin'])/2,
            'mu_away':(means['total']-means['margin'])/2,'variance':variances['margin'],
            'variance_margin':variances['margin'],'variance_total':variances['total'],
            'residuals_margin':profile['families']['margin']['residuals'],
            'residuals_total':profile['families']['total']['residuals'],
            'history_counts':{'home':10,'away':10},'input_games':values['input_games'],
            'input_sources':['espn'],'probability_adjustment':{'version':profile['version'],
            'fresh_accuracy_verified':False,'historically_checked':profile.get('historically_checked',False)},
            'candidate_only':True,'validated_for_recommendations':profile.get('recommendation_gate_passed',False)}


def league_history(data,game):
    """Cache the public league pool, excluding results unavailable at calculation."""
    from basketball_data import ESPN_BASE, espn_event
    now=datetime.now(timezone.utc);season=instant(game['kickoff']).year+(instant(game['kickoff']).month>=7)
    http=data.adapters['espn'].http
    def load():
        directory=http.object(ESPN_BASE+'/nba/teams',{'limit':100})
        teams=directory['sports'][0]['leagues'][0]['teams'];games={}
        for entry in teams:
            for year in [season-1,season]:
                raw=http.object(ESPN_BASE+'/nba/teams/'+str(entry['team']['id'])+'/schedule',{'season':year,'seasontype':2})
                for event in raw.get('events',[]):
                    if event.get('competitions',[{}])[0].get('type',{}).get('type')=='commissioners-cup':continue
                    native=espn_event(event,'nba')
                    if native and final_score(native) is not None:games[native['key']]=native
        return list(games.values())
    pool=data.store.cached('nba-league-history-v1:'+str(season),load,6*3600)
    return [g for g in pool if instant(g['kickoff'])<min(now,instant(game['kickoff']))]
