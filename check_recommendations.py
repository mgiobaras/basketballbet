"""Policy/log checks with explicit pregame receipts; no sporting accuracy claims."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from prediction_log import log_forecast, snapshot
from recommendations import apply_policy, first_recommendations

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def main():
    for sport in ['football', 'basketball']:
        fixture = {'fixture': {'id': 1, 'date': (NOW+timedelta(days=1)).isoformat(), 'status': {'short': 'NS'}}} if sport=='football' else {'key':'espn:1','kickoff':(NOW+timedelta(days=1)).isoformat(),'status':'NS'}
        names = ['over25', 'gg'] if sport=='football' else ['over','handicap_away']
        markets={}
        for name,p,line in zip(names,[.72,.74],[2.5 if sport=='football' else 200.5, None if sport=='football' else 3.5]):
            quote={'bookmaker':'Observed company','source':'ESPN', 'observed_at':NOW.isoformat()}
            if sport=='football':quote.update(fixture_id=1,odds={name:1.8})
            else:quote.update(fixture_key='espn:1',market=name,line=line,scope='including_overtime',odds=1.8)
            markets[name]={'probability':p if sport=='football' else {'win':p,'push':0.,'loss':1-p},'line':line,'quote':quote}
        original=deepcopy(markets)
        policy=apply_policy(sport,fixture,markets,NOW)
        assert policy['recommended_market']==names[1] and sum(v['recommendation']['recommended'] for v in markets.values())==1
        assert policy['verified_hit_rate'] is None
        model={'model_version':'controlled','created_at':NOW.isoformat(),'recommendation_policy':policy}
        packet=snapshot(sport,fixture,model,markets,{},'controlled',now=NOW)
        store=Mock();state={}
        assert log_forecast(store,state,packet,'controlled') is None
        rerun=deepcopy(packet);rerun['id']='rerun';rerun['captured_at']=(NOW+timedelta(seconds=1)).isoformat()
        for v in rerun['payload']['markets'].values():v['quote']['observed_at']=rerun['captured_at']
        log_forecast(store,state,rerun,'controlled')
        assert store.record_prediction.call_count==1
        changed=deepcopy(rerun);changed['id']='changed'
        q=changed['payload']['markets'][names[0]]['quote']
        q['odds']={names[0]:1.9} if sport=='football' else 1.9
        log_forecast(store,state,changed,'controlled')
        assert store.record_prediction.call_count==2
        assert first_recommendations([rerun,packet,changed])==[packet]
        legacy=deepcopy(packet);legacy['id']='legacy';legacy['payload']['model'].pop('recommendation_policy')
        assert first_recommendations([legacy])==[]
        bad=deepcopy(original)
        for v in bad.values():v['quote']['bookmaker']=''
        assert apply_policy(sport,fixture,bad,NOW)['recommended_market'] is None
        assert apply_policy(sport,fixture,deepcopy(original),NOW+timedelta(minutes=6))['recommended_market'] is None
        assert apply_policy(sport,fixture,deepcopy(original),NOW+timedelta(days=2))['recommended_market'] is None
        for v in bad.values():v['probability']=None
        assert apply_policy(sport,fixture,bad,NOW)['recommended_market'] is None
        if sport=='basketball':
            bad=deepcopy(original)
            for v in bad.values():v['line']=v['quote']['line']=1.665
            assert apply_policy(sport,fixture,bad,NOW)['recommended_market'] is None
        assert original[names[0]]['quote']['observed_at']==NOW.isoformat()
    print('PASS recommendations: one main tip, explicit policy, timestamp/line/company gates, no 70% claim, immutable first-valid selection, semantic rerun dedupe and no legacy reclassification')


if __name__=='__main__':main()
