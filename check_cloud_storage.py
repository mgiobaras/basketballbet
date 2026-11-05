"""Real local PostgreSQL/PostgREST readiness; uses isolated test-only credentials."""
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from basketball_store import SupabaseStore
from basketball_model import analyse, distribution
from check_basketball import fixture, history, quote, NOW
from check_prediction_log import cloud_check

DOCKER = ['env', '-u', 'DOCKER_HOST', '-u', 'DOCKER_CONTEXT', '-u', 'DOCKER_TLS', '-u', 'DOCKER_TLS_VERIFY', '-u', 'DOCKER_CERT_PATH', 'docker', '--host=unix:///var/run/docker.sock']
SECRET = 'basketball-local-test-only-postgrest-secret'


def docker(*args, text=None, check=True):
    r = subprocess.run(DOCKER+list(args), input=text, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(r.stderr[:1500])
    return r


def jwt(role):
    enc = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).rstrip(b'=')
    msg = enc({'alg': 'HS256', 'typ': 'JWT'})+b'.'+enc({'role': role, 'exp': int(time.time())+3600})
    return (msg+b'.'+base64.urlsafe_b64encode(hmac.new(SECRET.encode(), msg, hashlib.sha256).digest()).rstrip(b'=')).decode()


class LocalTransport:
    def __init__(self, base):
        self.base = base

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        target = self.base+url.split('/rest/v1', 1)[1]+('?' + urllib.parse.urlencode(params) if params else '')
        req = urllib.request.Request(target, method=method, headers=headers or {}, data=__import__('json').dumps(json).encode() if json is not None else None)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            response = opener.open(req, timeout=timeout or 5)
        except urllib.error.HTTPError as e:
            response = e
        body = response.read()
        class Reply:
            status_code = response.code
            content = body
            def json(self):
                return __import__('json').loads(body)
        return Reply()


def main():
    suffix = uuid.uuid4().hex[:8]
    network, pg, rest = ('basket-net-'+suffix, 'basket-pg-'+suffix, 'basket-rest-'+suffix)
    docker('network', 'create', network)
    try:
        docker('run', '-d', '--rm', '--name', pg, '--network', network, '--network-alias', 'pg', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:17-alpine')
        for _ in range(60):
            if docker('exec', pg, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', check=False).returncode == 0:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('PostgreSQL did not become ready')
        docker('exec', '-i', pg, 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', text='CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS; CREATE ROLE authenticator LOGIN NOINHERIT; GRANT anon,authenticated,service_role TO authenticator;')
        sql = (Path(__file__).parent/'database/supabase_setup.sql').read_text()
        for _ in range(2):
            docker('exec', '-i', pg, 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', text=sql)
        docker('run', '-d', '--rm', '--name', rest, '--network', network, '-p', '127.0.0.1::3000', '-e', 'PGRST_DB_URI=postgres://authenticator@pg:5432/postgres', '-e', 'PGRST_DB_ANON_ROLE=anon', '-e', 'PGRST_DB_SCHEMAS=public', '-e', 'PGRST_JWT_SECRET='+SECRET, 'postgrest/postgrest:v12.2.3')
        address = docker('port', rest, '3000').stdout.strip().splitlines()[0]
        transport = LocalTransport('http://'+address)
        store = SupabaseStore('https://test.supabase.co', jwt('service_role'), transport)
        for _ in range(80):
            try:
                assert store.list() == []
                break
            except Exception:
                time.sleep(.25)
        else:
            raise RuntimeError('PostgREST did not become ready')
        f = fixture(); m = analyse(f, history(f)); q = quote(f)
        assert store.save(f, q, distribution(m, 'over', 200), {'home': None}, m, now=NOW)
        assert not store.save(f, dict(q, line=210, odds=2.2), distribution(m, 'over', 210), {}, m, now=NOW)
        assert store.list()[0]['line'] == 200
        done = dict(f, status='FT', score={'home': 102, 'away': 98})
        assert store.settle(done) == 1 and store.settle(done) == 0
        assert store.list()[0]['status'] == 'push' and store.list()[0]['profit'] == 0
        migration = (Path(__file__).parent/'database/enable_prediction_logging.sql').read_text()
        cloud_check(store, transport, jwt, lambda: docker('exec', '-i', pg, 'psql', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-q', text=migration))
        assert store.cached('stat', lambda: {'actual': 0}, 60) == {'actual': 0}
        assert store.cached('stat', lambda: None, 60) == {'actual': 0}
        for role in ['anon', 'authenticated']:
            reply = transport.request('GET', 'https://test.supabase.co/rest/v1/basketball_bets', headers={'Authorization': 'Bearer '+jwt(role)})
            assert reply.status_code in {401, 403}
        docker('restart', rest)
        transport.base = 'http://'+docker('port', rest, '3000').stdout.strip().splitlines()[0]
        for _ in range(40):
            try:
                assert store.list()[0]['status'] == 'push'
                break
            except Exception:
                time.sleep(.25)
        else:
            raise RuntimeError('Stored history did not survive restart')
        assert len(store.list_predictions()) == 1003
        print('PASS real PostgreSQL/PostgREST: idempotent schema, private tables, unit-stake persistence, immutable lines/odds, push settlement, cache, server restart')
    finally:
        docker('rm', '-f', rest, pg, check=False)
        docker('network', 'rm', network, check=False)


if __name__ == '__main__':
    main()
