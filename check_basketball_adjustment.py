"""Hand-check total/margin covariance, small samples and unchanged input history."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math

from basketball_adjustment import adjust_model
from basketball_model import analyse, distribution
from check_basketball import fixture, history


def main():
    target=fixture(kickoff=datetime(2030,1,1,tzinfo=timezone.utc))
    games=[fixture(10+d*2+s,datetime.fromisoformat(target['kickoff'])-timedelta(days=d+1),1+s,3+s,points)
           for d,pair in enumerate([[(100,90),(80,75)],[(110,80),(100,85)]]) for s,points in enumerate(pair)]
    original=deepcopy(games)
    raw=analyse(target,games)
    adjusted=adjust_model(target,games,raw)
    assert games==original and adjusted['input_games']==raw['input_games'] and adjusted['history_counts']==raw['history_counts']
    assert adjusted['mu_home']==raw['mu_home'] and adjusted['mu_away']==raw['mu_away']
    assert adjusted['variance_total'] != adjusted['variance_margin']
    # Two-observation unbiased variances: total 0 and 450, margin 200 and 50.
    effective=adjusted['probability_adjustment']['profiles'][0]['effective_games']
    assert math.isclose(adjusted['variance_total'],225+450/effective/4)
    assert math.isclose(adjusted['variance_margin'],125+250/effective/4)
    for market,line in [('home',None),('away',None),('over',190.),('under',190.),('handicap_home',-3.5),('handicap_away',3.5)]:
        p=distribution(adjusted,market,line)
        assert p and math.isclose(sum(p.values()),1) and all(0<=v<=1 for v in p.values())
    assert math.isclose(distribution(adjusted,'over',190.)['push'],distribution(adjusted,'under',190.)['push'])
    assert distribution(adjusted,'over',1.665) is None
    assert distribution(adjusted,'over',-1.5) is None
    few=games[:2]
    one=adjust_model(target,few,analyse(target,few))
    assert one['history_counts']=={'home':1,'away':1}
    assert one['variance_margin'] is None and distribution(one,'home') is None
    full_history=history(target)
    raw_full=analyse(target,full_history)
    new=adjust_model(target,full_history,raw_full)
    assert new['input_games']==raw_full['input_games'] and new['history_counts']=={'home':10,'away':10}
    constant=deepcopy(full_history)
    for g in constant:g['score']={'home':100,'away':90}
    no_variance=adjust_model(target,constant,analyse(target,constant))
    assert no_variance['variance_total'] is None and no_variance['variance_margin'] is None
    assert distribution(no_variance,'over',200.5) is None
    for league in ['nba','euroleague','greece']:
        local=deepcopy(target);local['league']=league
        local_history=deepcopy(full_history)
        for g in local_history:g['league']=league
        model=adjust_model(local,local_history,analyse(local,local_history))
        assert model['probability_adjustment']['league']==league
    print('PASS basketball adjustment: independent hand-calculated total/margin uncertainty, unchanged means/last-ten/history, all three leagues, pushes, no false certainty from one game, invalid-line rejection')


if __name__=='__main__':main()
