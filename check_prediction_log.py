"""Private snapshots: isolation, immutable retry, timestamps and missing inputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from unittest.mock import Mock

from prediction_log import snapshot, quote_snapshot, queue_prediction, flush_predictions


def cloud_check(store, transport, jwt, reapply):
    """Exercise the actual REST/SQL boundary, including export beyond 1000 rows."""
    sport = 'football' if (Path(__file__).parent/'bet_store.py').exists() else 'basketball'
    baseline = store.list()
    now = datetime.now(timezone.utc)
    kickoff = (now+timedelta(days=1)).isoformat()
    fixture = {'fixture': {'id': 123, 'date': kickoff, 'status': {'short': 'NS'}}} if sport == 'football' else {
        'key': 'espn:123', 'kickoff': kickoff, 'status': 'NS'}
    packet = snapshot(sport, fixture, {'model_version': 'cloud-controlled'}, {}, {}, 'controlled', now=now)
    store.record_prediction(packet)
    changed = deepcopy(packet); changed['payload']['app_version'] = 'overwrite-attempt'
    store.record_prediction(changed)
    assert len(store.list_predictions()) == 1
    assert store.list_predictions()[0]['payload'] == packet['payload']
    extra = [dict(packet, id=packet['id']+'-'+str(i)) for i in range(1002)]
    endpoint = '/app_prediction_log' if sport == 'football' else 'app_prediction_log'
    store.request('POST', endpoint, payload=extra, prefer='return=minimal')
    other = dict(packet, id=packet['id']+'-other', sport='basketball' if sport == 'football' else 'football')
    store.record_prediction(other)
    before = store.list_predictions()
    assert len(before) == 1003
    reapply(); reapply()
    assert store.list_predictions() == before and store.list() == baseline
    url = store.base+'/app_prediction_log'
    for role in ['anon', 'authenticated']:
        headers = {'Authorization': 'Bearer '+jwt(role), 'Content-Type': 'application/json'}
        for method, target, payload in [('GET', url, None), ('POST', url, packet),
                ('POST', store.base+'/rpc/app_list_prediction_logs', {'p_sport': sport})]:
            reply = transport.request(method, target, headers=headers, json=payload)
            assert reply.status_code in {401, 403, 404}, (role, method, reply.status_code, reply.json())
    headers = {'Authorization': 'Bearer '+jwt('service_role'), 'Content-Type': 'application/json'}
    for method in ['PATCH', 'DELETE']:
        reply = transport.request(method, url, headers=headers, params={'id': 'eq.'+packet['id']},
                                  json={'payload': {}} if method == 'PATCH' else None)
        assert reply.status_code in {401, 403}, (method, reply.status_code)
    assert store.list_predictions() == before
    print('PASS private '+sport+' REST log: >1000 export, sport isolation, duplicate immutability, migration twice preserves all history, anon/auth denied, service update/delete denied')


def main():
    football = (Path(__file__).parent/'bet_store.py').exists()
    if football:
        from bet_store import BetStore as Store
        from supabase_store import SupabaseBetStore as RemoteStore
    else:
        from basketball_store import Store, SupabaseStore as RemoteStore
    sport = 'football' if football else 'basketball'
    now = datetime.now(timezone.utc)
    kickoff = (now+timedelta(days=1)).isoformat()
    fixture = {'fixture': {'id': 123, 'date': kickoff, 'status': {'short': 'NS'}}} if football else {
        'key': 'espn:123', 'kickoff': kickoff, 'status': 'NS'}
    model = {'model_version': 'controlled-v1', 'probabilities': {'home': .6}}
    quote = dict(odds=1.9, line=200.5, source='Controlled', observed_at=now.isoformat(), api_key='MUST_NOT_LOG')
    markets = {'home': {'probability': .6, 'quote': quote_snapshot(quote)},
               'under': {'probability': None, 'quote': None, 'line': None}}
    packet = snapshot(sport, fixture, model, markets, {}, 'controlled-app', now=now, inputs={'scores': [100, 90]})
    assert packet['payload']['eligible_for_evaluation']
    assert 'api_key' not in packet['payload']['markets']['home']['quote']
    model['probabilities']['home'] = .99
    markets['home']['probability'] = .99
    assert packet['payload']['model']['probabilities']['home'] == .6
    assert packet['payload']['markets']['home']['probability'] == .6
    late = snapshot(sport, fixture, model, markets, {}, 'controlled-app', now=now+timedelta(days=2))
    assert not late['payload']['eligible_for_evaluation']
    non_ns = deepcopy(fixture)
    if football:
        non_ns['fixture']['status']['short'] = 'FT'
    else:
        non_ns['status'] = 'FT'
    assert not snapshot(sport, non_ns, model, markets, {}, 'controlled-app', now=now)['payload']['eligible_for_evaluation']
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/log.sqlite3')
        selected_before = store.list()
        store.record_prediction(packet)
        changed = deepcopy(packet); changed['payload']['app_version'] = 'overwrite-attempt'
        store.record_prediction(changed)
        assert store.list_predictions() == [packet]
        assert store.list() == selected_before
        assert store.list_predictions('basketball' if football else 'football') == []
        assert Store(directory+'/log.sqlite3').list_predictions() == [packet]
        state = {}; queue_prediction(state, late)
        failed = Mock(); failed.record_prediction.side_effect = RuntimeError('private database error')
        message = flush_predictions(failed, state, sport)
        assert message and 'enable_prediction_logging.sql' in message and 'private database error' not in message
        assert list(state['pending_prediction_log:'+sport]) == [late['id']]
        assert flush_predictions(store, state, sport) is None
        assert len(store.list_predictions()) == 2
        assert state['pending_prediction_log:'+sport] == {}
    transport = Mock(); reply = transport.request.return_value
    reply.status_code = 201; reply.content = b'[]'; reply.json.return_value = []
    remote = RemoteStore('https://test.supabase.co', 'sb_secret_'+'x'*30, transport)
    remote.record_prediction(packet)
    assert transport.request.call_args.args[1].endswith('/rest/v1/app_prediction_log')
    assert transport.request.call_args.kwargs['json'] == packet
    reply.status_code = 200; reply.json.return_value = [packet]
    assert remote.list_predictions() == [packet]
    assert transport.request.call_args.kwargs['json'] == {'p_sport': sport}
    reply.status_code = 503
    state = {}; queue_prediction(state, packet)
    assert flush_predictions(remote, state, sport) and state['pending_prediction_log:'+sport]
    print('PASS '+sport+' log: separate persistence, frozen snapshots, safe quote fields, no invented missing values, pregame eligibility, immutable retry and remote failures')


if __name__ == '__main__':
    main()
