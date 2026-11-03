"""Persistent, immutable unit-stake bets with private optional Supabase storage."""
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlparse
import requests

from basketball_model import MARKETS, instant, number, final_score, outcome


class StorageError(RuntimeError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS basketball_bets(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS basketball_cache(id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS basketball_legacy(id TEXT PRIMARY KEY, payload TEXT NOT NULL);''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, game, quote, probability, absences, model, now=None):
        now = now or datetime.now(timezone.utc)
        market = quote.get('market')
        if game['status'] != 'NS' or instant(game['kickoff']) <= now:
            raise ValueError('Δεν αποθηκεύονται επιλογές μετά την έναρξη ή σε μη προγραμματισμένο αγώνα.')
        if market not in MARKETS or quote.get('fixture_key') != game['key'] or quote.get('scope') != 'including_overtime':
            raise ValueError('Λάθος αγώνας/αγορά ή άγνωστος κανονισμός παράτασης.')
        price = number(quote.get('odds'))
        if price is None or price < 1.5:
            raise ValueError('Ελάχιστη απόδοση 1,50.')
        line = number(quote.get('line'))
        if market not in {'home', 'away'} and (line is None or not (line*2).is_integer() or (market in {'over', 'under'} and line <= 0)):
            raise ValueError('Λείπει η πραγματική γραμμή ή είναι μη έγκυρη.')
        if quote.get('source') not in {'ESPN', 'Sofascore', 'Paf', 'The Odds API', 'Χειροκίνητη καταχώριση'}:
            raise ValueError('Μη έγκυρη πηγή απόδοσης.')
        company = quote.get('bookmaker')
        if not (isinstance(company, str) and company.strip() and len(company) <= 100 and company.isprintable()):
            if quote.get('source') != 'Sofascore' or not str(quote.get('bookmaker_id') or '').isdigit():
                raise ValueError('Χρειάζεται πραγματική εταιρεία ή δημοσιευμένο ID παρόχου.')
        age = (now-instant(quote['observed_at'])).total_seconds()
        if not -5 <= age <= 300:
            raise ValueError('Η λήψη είναι παλιά ή μη έγκυρη. Πάτησε Ανανέωση αποδόσεων.')
        if not isinstance(probability, dict) or any(number(probability.get(k)) is None or not 0 <= probability[k] <= 1 for k in ['win', 'push', 'loss']) or abs(sum(probability.values())-1) > 1e-6:
            raise ValueError('Μη έγκυρες πιθανότητες.')
        key = hashlib.sha256((game['key']+'|'+market).encode()).hexdigest()
        record = {'id': key, 'fixture': game, 'market': market, 'line': line, 'odds': price, 'stake': 1.,
                  'quote': quote, 'probability': probability, 'absences': absences, 'model': model,
                  'created_at': now.isoformat(), 'status': 'pending', 'profit': None, 'score': None}
        return self.insert(record)

    def insert(self, record):
        with self.connect() as db:
            return db.execute('INSERT INTO basketball_bets VALUES (?,?) ON CONFLICT(id) DO NOTHING',
                              (record['id'], json.dumps(record, ensure_ascii=False))).rowcount == 1

    def list(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM basketball_bets ORDER BY id')]

    def update_pending(self, record):
        with self.connect() as db:
            return db.execute("UPDATE basketball_bets SET payload=? WHERE id=? AND json_extract(payload,'$.status')='pending'",
                              (json.dumps(record, ensure_ascii=False), record['id'])).rowcount

    def settle(self, game):
        score = final_score(game)
        if score is None:
            return 0
        changed = 0
        for record in self.list():
            original = record['fixture']
            if original['key'] != game['key'] or record['status'] != 'pending' or original['league'] != game['league']:
                continue
            state = outcome(record['market'], record['line'], score)
            profit = record['odds']-1 if state == 'won' else -1. if state == 'lost' else 0.
            record.update(status=state, profit=profit, score=score, settled_at=datetime.now(timezone.utc).isoformat())
            changed += self.update_pending(record)
        return changed

    def cached(self, key, loader, ttl):
        now = datetime.now(timezone.utc)
        value = self.get_cache(key, now)
        if value is not None:
            return value['value']
        value = loader()
        self.put_cache(key, {'value': value}, now+timedelta(seconds=ttl))
        return value

    def get_cache(self, key, now):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM basketball_cache WHERE id=? AND expires_at>?', (key, now.isoformat())).fetchone()
        return json.loads(row[0]) if row else None

    def put_cache(self, key, value, expiry):
        with self.connect() as db:
            db.execute('INSERT INTO basketball_cache VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,expires_at=excluded.expires_at',
                       (key, json.dumps(value, ensure_ascii=False), expiry.isoformat()))
            db.execute('DELETE FROM basketball_cache WHERE expires_at<?', (datetime.now(timezone.utc).isoformat(),))

    def preserve_legacy(self, path):
        path = Path(path)
        if not path.exists():
            return False
        text = path.read_text(encoding='utf-8-sig')
        key = hashlib.sha256(text.encode()).hexdigest()
        self.put_legacy(key, text)
        return True

    def put_legacy(self, key, text):
        with self.connect() as db:
            db.execute('INSERT INTO basketball_legacy VALUES (?,?) ON CONFLICT(id) DO NOTHING', (key, text))


class SupabaseStore(Store):
    def __init__(self, url, key, transport=None):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.supabase.co') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'}:
            raise StorageError('Μη έγκυρο HTTPS SUPABASE_URL.')
        self.jwt = bool(key and key.startswith('eyJ') and len(key.split('.')) == 3)
        if self.jwt:
            try:
                payload = key.split('.')[1]
                role = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload) % 4))).get('role')
            except (ValueError, TypeError, UnicodeDecodeError):
                role = None
            if role != 'service_role':
                raise StorageError('Χρειάζεται server service_role key, όχι anon/publishable.')
        if not self.jwt and not (key and key.startswith('sb_secret_') and len(key) > 25):
            raise StorageError('Χρειάζεται server secret/service_role key, όχι anon/publishable.')
        self.base, self.key = url.rstrip('/')+'/rest/v1', key
        self.transport = transport or requests.Session()

    def request(self, method, table, params=None, payload=None, prefer=None):
        headers = {'apikey': self.key, 'Content-Type': 'application/json'}
        if self.jwt:
            headers['Authorization'] = 'Bearer '+self.key
        if prefer:
            headers['Prefer'] = prefer
        try:
            r = self.transport.request(method, self.base+'/'+table, params=params, json=payload, headers=headers, timeout=20)
        except requests.RequestException:
            raise StorageError('Η μόνιμη βάση δεν είναι προσβάσιμη. Δεν έγινε προσωρινή τοπική αποθήκευση.') from None
        if r.status_code not in {200, 201, 204}:
            raise StorageError(f'Supabase HTTP {r.status_code}. Έλεγξε το SQL εγκατάστασης και τα Secrets.')
        if r.status_code == 204 or not r.content:
            return None
        try:
            return r.json()
        except ValueError:
            raise StorageError('Μη έγκυρη απάντηση Supabase.') from None

    def insert(self, record):
        rows = self.request('POST', 'basketball_bets', {'on_conflict': 'id'}, {'id': record['id'], 'payload': record}, 'resolution=ignore-duplicates,return=representation')
        if not isinstance(rows, list):
            raise StorageError('Δεν επιβεβαιώθηκε η αποθήκευση.')
        return bool(rows)

    def list(self):
        result, offset = [], 0
        while True:
            rows = self.request('GET', 'basketball_bets', {'select': 'payload', 'order': 'id', 'offset': offset, 'limit': 500})
            if not isinstance(rows, list):
                raise StorageError('Δεν επιβεβαιώθηκε η ανάγνωση ιστορικού.')
            result.extend(r['payload'] for r in rows)
            if len(rows) < 500:
                return result
            offset += 500

    def update_pending(self, record):
        rows = self.request('PATCH', 'basketball_bets', {'id': 'eq.'+record['id'], 'payload->>status': 'eq.pending'}, {'payload': record}, 'return=representation')
        if not isinstance(rows, list):
            raise StorageError('Δεν επιβεβαιώθηκε η εκκαθάριση.')
        return len(rows)

    def get_cache(self, key, now):
        rows = self.request('GET', 'basketball_cache', {'id': 'eq.'+key, 'expires_at': 'gt.'+now.isoformat(), 'limit': 1})
        if not isinstance(rows, list):
            raise StorageError('Δεν επιβεβαιώθηκε η ανάγνωση cache.')
        return rows[0]['payload'] if rows else None

    def put_cache(self, key, value, expiry):
        self.request('POST', 'basketball_cache', {'on_conflict': 'id'}, {'id': key, 'payload': value, 'expires_at': expiry.isoformat()}, 'resolution=merge-duplicates')

    def put_legacy(self, key, text):
        self.request('POST', 'basketball_legacy', {'on_conflict': 'id'}, {'id': key, 'payload': text}, 'resolution=ignore-duplicates')
