"""Public Paf browser fetch when the hosting server receives HTTP 410.

No cookies, application secrets or betting history are sent to the component.
The existing Paf parser still validates every fixture and quote on the server.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

import streamlit.components.v1 as components

from basketball_data import DataError, Paf


component = components.declare_component('paf_browser', path=str(Path(__file__).with_name('paf_browser_frontend')))


class PendingFetch(Exception):
    def __init__(self, url, params):
        self.url, self.params = url, params


class BrowserHTTP:
    def __init__(self, state):
        self.state = state
        self.received_at = None

    def object(self, url, params=None):
        allowed = (url in {Paf.BASE+'/listView/basketball/all/all/all/matches.json',
                          Paf.BASE+'/listView/basketball/greece/all/all/matches.json'}
                   or re.fullmatch(re.escape(Paf.BASE)+r'/betoffer/event/\d+\.json', url))
        if not allowed or params != Paf.PARAMS:
            raise DataError('Μη επιτρεπόμενο αίτημα δημόσιων αποδόσεων.')
        reply = self.state['responses'].get(url)
        now = datetime.now(timezone.utc)
        if reply is None or (now-datetime.fromisoformat(reply['received_at'])).total_seconds() >= 120:
            raise PendingFetch(url, params)
        if reply.get('error'):
            raise DataError(reply['error'])
        self.received_at = reply['received_at']
        return reply['data']


def browser_quotes(st, store, game, refresh=0):
    identity = [game['key'], game['league'], game['kickoff'], game['teams'], refresh]
    scope = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    state = st.session_state.get('paf_browser_state')
    if not state or state['scope'] != scope:
        state = {'scope': scope, 'responses': {}, 'pending': None}
        st.session_state['paf_browser_state'] = state
    provider = Paf(store, BrowserHTTP(state), cache_namespace='browser:'+scope+':')
    try:
        quotes, notes = provider.quotes(game, refresh)
    except PendingFetch as pending:
        request = state['pending']
        if not request or request['url'] != pending.url:
            request = {'id': uuid4().hex, 'url': pending.url, 'params': pending.params}
            state['pending'] = request
        reply = component(request=request, key='paf_browser:'+scope, default=None)
        if isinstance(reply, dict) and reply.get('id') == request['id']:
            record = {'received_at': datetime.now(timezone.utc).isoformat()}
            if reply.get('ok') is True and isinstance(reply.get('data'), dict) and len(json.dumps(reply['data'])) <= 4_000_000:
                record['data'] = reply['data']
            else:
                message = reply.get('error')
                record['error'] = ('Λήψη Paf από browser: '+message[:500]) if isinstance(message, str) else 'Αποτυχία λήψης Paf από browser.'
            state['responses'][request['url']] = record
            state['pending'] = None
            st.rerun()
        return [], ['Αναμονή αυτόματης λήψης Paf από τον browser…'], provider.diagnostics
    except DataError as error:
        return [], [str(error)], provider.diagnostics
    for quote in quotes:
        quote['price_kind'] = 'published_pre_match_browser'
    provider.diagnostics['transport'] = 'browser_public_fetch'
    return quotes, notes, provider.diagnostics
