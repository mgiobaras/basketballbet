"""Public basketball data adapters and automatic, exact-identity source fallback."""
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import re
import unicodedata
from zoneinfo import ZoneInfo
import requests

from basketball_model import instant, number, final_score, recent_games

LEAGUES = {'NBA': 'nba', 'EuroLeague': 'euroleague', 'Ελλάδα - Basket League': 'greece'}
ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports/basketball'
SOFA_BASE = 'https://api.sofascore.com/api/v1'
EURO_BASE = 'https://api-live.euroleague.net/v2'
ALIASES = {'la clippers': 'los angeles clippers', 'la lakers': 'los angeles lakers',
           'olympiacos piraeus': 'olympiacos', 'olympiacos bc': 'olympiacos',
           'panathinaikos athens': 'panathinaikos', 'panathinaikos aktor athens': 'panathinaikos',
           'panathinaikos bc': 'panathinaikos',
           'real madrid baloncesto': 'real madrid',
           'fenerbahce beko istanbul': 'fenerbahce', 'fc barcelona': 'barcelona',
           # Explicit EuroLeague/Sofascore spellings, checked against the 2026/27
           # official team directory and the linked Sofascore team pages.
           'anadolu efes istanbul': 'anadolu efes',
           'armani olimpia milan': 'olimpia milano',
           'ea7 emporio armani milan': 'olimpia milano',
           'ea7 emporio armani milano': 'olimpia milano',
           'besiktas istanbul': 'besiktas', 'besiktas jk': 'besiktas',
           'besiktas gain istanbul': 'besiktas', 'besiktas emlakjet': 'besiktas',
           'crvena zvezda meridianbet belgrade': 'crvena zvezda',
           'kk crvena zvezda meridianbet': 'crvena zvezda', 'kk crvena zvezda': 'crvena zvezda',
           'bc dubai': 'dubai basketball', 'barca basket': 'barcelona',
           'fc bayern munich': 'bayern munich', 'bayern munchen': 'bayern munich',
           'fenerbahce tarfin istanbul': 'fenerbahce', 'fenerbahce tarfin': 'fenerbahce',
           'fenerbahce istanbul': 'fenerbahce', 'fenerbahce beko': 'fenerbahce',
           'hapoel ibi tel aviv': 'hapoel tel aviv',
           'kosner baskonia vitoria gasteiz': 'baskonia', 'kosner baskonia': 'baskonia',
           'baskonia vitoria gasteiz': 'baskonia', 'saski baskonia': 'baskonia',
           'ldlc asvel villeurbanne': 'asvel', 'ldlc asvel lyon villeurbanne': 'asvel',
           'asvel lyon villeurbanne': 'asvel',
           'maccabi rapyd tel aviv': 'maccabi tel aviv', 'maccabi playtika tel aviv': 'maccabi tel aviv',
           'partizan mozzarbet belgrade': 'partizan', 'partizan mozzart bet belgrade': 'partizan',
           'kk partizan mozzart bet': 'partizan',
           'virtus segafredo bologna': 'virtus bologna', 'zalgiris kaunas': 'zalgiris',
           'kauno zalgiris': 'zalgiris'}


class DataError(RuntimeError):
    pass


def name_key(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', str(value)).casefold() if not unicodedata.combining(c))
    value = ' '.join(re.sub(r'[^\w]+', ' ', value).split())
    return ALIASES.get(value, value)


def identity(game):
    return (game['league'], instant(game['kickoff']).date(), *(name_key(game['teams'][s]['name']) for s in ['home', 'away']))


def matching(game, values, exact_time=False):
    found = [g for g in values if identity(g) == identity(game)
             and (not exact_time or instant(g['kickoff']) == instant(game['kickoff']))]
    return found[0] if len(found) == 1 else None


def american(value):
    if str(value).strip().upper() in {'EVEN', 'EVS'}:
        return 2.
    value = number(value)
    return 1+(value/100 if value > 0 else 100/-value) if value is not None and abs(value) >= 100 else None


def line_number(value, total=False):
    if isinstance(value, str):
        value = value.strip()
        if total and value[:1].lower() in {'o', 'u'}:
            value = value[1:]
    n = number(value)
    if n is None or (total and n <= 0) or not (n*2).is_integer():
        return None
    return n


def make_quote(game, market, odds, line, company, source, url, receipt, kind='published_pre_match', company_id=None):
    if number(odds) is None or odds <= 1 or (market not in {'home', 'away'} and line is None):
        return None
    if not company and not company_id:
        return None
    return {'fixture_key': game['key'], 'market': market, 'odds': odds, 'line': line,
            'bookmaker': company, 'bookmaker_id': company_id, 'source': source,
            'source_url': url, 'observed_at': receipt, 'price_kind': kind, 'scope': 'including_overtime'}


def espn_event(event, league):
    if not isinstance(event, dict):
        return None
    comps = event.get('competitions') or []
    if len(comps) != 1:
        return None
    comp = comps[0]
    sides = {t.get('homeAway'): t for t in comp.get('competitors', [])}
    if not all(s in sides and sides[s].get('team', {}).get('id') and sides[s]['team'].get('displayName') for s in ['home', 'away']):
        return None
    if sides['home']['team']['id'] == sides['away']['team']['id']:
        return None
    try:
        kickoff = instant(event.get('date') or comp['date']).isoformat()
    except (ValueError, KeyError, TypeError):
        return None
    status = comp.get('status', event.get('status', {})).get('type', {})
    state = 'FT' if status.get('completed') else 'NS' if status.get('state') == 'pre' else 'LIVE'
    if any(w in str(status).lower() for w in ['postpon', 'cancel', 'suspend', 'abandon']):
        state = 'PST'
    def score(side):
        value = sides[side].get('score')
        return number(value.get('value')) if isinstance(value, dict) else number(value)
    return {'key': 'espn:'+str(event['id']), 'id': str(event['id']), 'source': 'espn', 'league': league,
            'kickoff': kickoff, 'status': state,
            'teams': {s: {'id': 'espn:'+str(sides[s]['team']['id']), 'name': sides[s]['team']['displayName']} for s in ['home', 'away']},
            'score': {s: score(s) for s in ['home', 'away']},
            'source_url': f'{ESPN_BASE}/{league}/summary?event={event["id"]}'}


def espn_quotes(data, game, receipt, url):
    header = data.get('header') or {}
    native = espn_event(header, game['league']) if header.get('competitions') else None
    if native is None or native['key'] != game['key'] or identity(native) != identity(game) or native['status'] != 'NS' or any(native['teams'][s]['id'] != game['teams'][s]['id'] for s in ['home', 'away']):
        return []
    comp = header['competitions'][0]
    values = data.get('pickcenter') or comp.get('odds') or []
    quotes = []
    for value in values:
        if not isinstance(value, dict):
            continue
        company = (value.get('provider') or {}).get('name')
        if not isinstance(company, str) or not company.strip():
            continue
        def add(market, price, line=None, kind='published_pre_match'):
            q = make_quote(game, market, price, line, company.strip(), 'ESPN', url, receipt, kind)
            if q:
                quotes.append(q)
        # Published snapshots remain labeled as such; line and odds always come
        # from the same current/close object. Never use opening prices as current.
        for group, side, market in [('moneyline', 'home', 'home'), ('moneyline', 'away', 'away'),
                                    ('total', 'over', 'over'), ('total', 'under', 'under'),
                                    ('pointSpread', 'home', 'handicap_home'), ('pointSpread', 'away', 'handicap_away')]:
            item = (value.get(group) or {}).get(side) or {}
            phase = 'current' if 'current' in item else 'close'
            point = item.get(phase) or {}
            price = american(point.get('odds'))
            line = None if group == 'moneyline' else line_number(point.get('line'), group == 'total')
            add(market, price, line, 'published_'+phase)
        # Legacy summary fields are accepted only with the matching team IDs.
        for side in ['home', 'away']:
            item = value.get(side+'TeamOdds') or {}
            tid = item.get('teamId', (item.get('team') or {}).get('id'))
            if tid is not None and 'espn:'+str(tid) == game['teams'][side]['id']:
                add(side, american(item.get('moneyLine')))
                spread = line_number(value.get('spread'))
                if spread is not None and isinstance(item.get('favorite'), bool):
                    signed = -abs(spread) if item['favorite'] else abs(spread)
                    add('handicap_'+side, american(item.get('spreadOdds')), signed)
        total = line_number(value.get('overUnder'), True)
        for side in ['over', 'under']:
            add(side, american(value.get(side+'Odds')), total)
    return quotes


class HTTP:
    def __init__(self, transport=None):
        self.transport = transport or requests.Session()

    def get(self, url, params=None):
        try:
            r = self.transport.get(url, params=params, timeout=(5, 20), headers={'Accept': 'application/json', 'User-Agent': 'BasketballBet/2'})
        except requests.RequestException:
            raise DataError('Αποτυχία ασφαλούς σύνδεσης με '+url.split('/')[2]+'.') from None
        if r.status_code != 200:
            raise DataError(url.split('/')[2]+f': HTTP {r.status_code}.')
        try:
            result = r.json()
        except ValueError:
            raise DataError('Μη έγκυρο JSON από '+url.split('/')[2]+'.') from None
        if not isinstance(result, (dict, list)):
            raise DataError('Μη έγκυρη μορφή δεδομένων.')
        return result

    def object(self, url, params=None):
        data = self.get(url, params)
        if not isinstance(data, dict):
            raise DataError('Η πηγή δεν επέστρεψε έγκυρο αντικείμενο δεδομένων.')
        return data


class TheOddsAPI:
    BASE = 'https://api.the-odds-api.com/v4/sports'
    SPORTS = {'euroleague': 'basketball_euroleague', 'nba': 'basketball_nba'}

    def __init__(self, key, store, transport=None):
        self.key, self.store = key, store
        self.scope = hashlib.sha256(key.encode()).hexdigest()
        self.transport = transport or requests.Session()

    def quotes(self, game, refresh=0):
        sport = self.SPORTS.get(game['league'])
        if not sport:
            return []
        url = f'{self.BASE}/{sport}/odds'
        def load():
            try:
                response = self.transport.get(url, params={'apiKey': self.key, 'regions': 'eu',
                    'markets': 'h2h,spreads,totals', 'oddsFormat': 'decimal', 'dateFormat': 'iso'}, timeout=(5, 20))
            except requests.RequestException:
                raise DataError('The Odds API: αποτυχία σύνδεσης με την πηγή αποδόσεων.') from None
            if response.status_code != 200:
                reason = {401: 'μη έγκυρο κλειδί ή εξαντλημένα credits', 403: 'δεν επιτρέπεται πρόσβαση',
                          429: 'όριο αιτημάτων ή credits'}.get(response.status_code, 'αποτυχία ανάκτησης')
                raise DataError(f'The Odds API: HTTP {response.status_code} — {reason}.')
            try:
                events = response.json()
            except ValueError:
                raise DataError('The Odds API: μη έγκυρο JSON.') from None
            if not isinstance(events, list):
                raise DataError('The Odds API: μη έγκυρη λίστα αγώνων.')
            return {'events': events, 'receipt': datetime.now(timezone.utc).isoformat()}
        # Share one league feed across fixtures. The key never enters cache payloads.
        feed = self.store.cached(f'odds_api:v1:{self.scope}:{sport}:{refresh}', load, 120)
        matches = []
        for event in feed['events']:
            if not isinstance(event, dict) or event.get('sport_key') != sport or not event.get('id'):
                continue
            try:
                same = instant(event['commence_time']) == instant(game['kickoff']) and all(
                    name_key(event[side+'_team']) == name_key(game['teams'][side]['name']) for side in ['home', 'away'])
            except (KeyError, TypeError, ValueError):
                continue
            if same:
                matches.append(event)
        if len(matches) != 1:
            raise DataError('The Odds API: δεν βρέθηκε μοναδική αντιστοίχιση του αγώνα με ίδια διοργάνωση, ομάδες και ώρα.')
        event, quotes = matches[0], []
        for book in event.get('bookmakers', []):
            if not isinstance(book, dict):
                continue
            company = book.get('title')
            if not isinstance(company, str) or not company.strip():
                continue
            for market in book.get('markets', []):
                if not isinstance(market, dict):
                    continue
                kind = market.get('key')
                if kind not in {'h2h', 'spreads', 'totals'}:
                    continue
                outcomes = market.get('outcomes', [])
                # Full-game two-way markets only; never substitute a draw or a period.
                if not isinstance(outcomes, list) or len(outcomes) != 2 or not all(isinstance(o, dict) for o in outcomes):
                    continue
                labels = {name_key(o.get('name', '')) for o in outcomes}
                expected = {'over', 'under'} if kind == 'totals' else {name_key(event[s+'_team']) for s in ['home', 'away']}
                if labels != expected:
                    continue
                for outcome in outcomes:
                    label = name_key(outcome['name'])
                    side = label if kind == 'totals' else 'home' if label == name_key(event['home_team']) else 'away'
                    code = side if kind != 'spreads' else 'handicap_'+side
                    price = number(outcome.get('price'))
                    line = None if kind == 'h2h' else line_number(outcome.get('point'), kind == 'totals')
                    q = make_quote(game, code, price, line, company.strip(), 'The Odds API', url, feed['receipt'])
                    if q:
                        q.update(source_fixture_key='the_odds_api:'+event['id'],
                                 published_at=market.get('last_update', book.get('last_update')))
                        quotes.append(q)
        return quotes


def paf_event(row, league):
    """Read Kambi's own home/away orientation, never the displayed @ ordering."""
    event = row.get('event') or {} if isinstance(row, dict) else {}
    if not isinstance(event, dict):
        return None
    groups = {name_key(event.get('group', ''))}
    groups.update(name_key(p.get(k, '')) for p in event.get('path') or [] if isinstance(p, dict)
                  for k in ['termKey', 'englishName', 'name'])
    allowed = {'euroleague': {'euroleague', 'euroleague men'}, 'nba': {'nba'}}
    if (event.get('sport') != 'BASKETBALL' or not groups.intersection(allowed.get(league, set()))
            or event.get('state') != 'NOT_STARTED' or not str(event.get('id', '')).isdigit()):
        return None
    names = {side: event.get(side+'Name') for side in ['home', 'away']}
    if not all(isinstance(n, str) and n.strip() for n in names.values()):
        return None
    # Recorded Kambi feeds carry full English labels on typed winner outcomes,
    # even when homeName/awayName are abbreviations such as NO Pelicans.
    pairs = set()
    for offer in row.get('betOffers') or []:
        if (not isinstance(offer, dict) or (offer.get('betOfferType') or {}).get('id') != 2
                or str(offer.get('eventId')) != str(event['id'])):
            continue
        outcomes = offer.get('outcomes') or []
        if not isinstance(outcomes, list):
            continue
        pair = {o.get('type'): o.get('englishLabel') for o in outcomes if isinstance(o, dict)}
        if all(isinstance(pair.get(t), str) and pair[t].strip() for t in ['OT_ONE', 'OT_TWO']):
            for side, code in [('home', 'OT_ONE'), ('away', 'OT_TWO')]:
                entries = [o for o in outcomes if isinstance(o, dict) and o.get('type') == code]
                if len(entries) != 1 or not any(isinstance(entries[0].get(k), str)
                        and name_key(entries[0][k]) == name_key(names[side])
                        for k in ['participant', 'label', 'englishLabel']):
                    return None
            pairs.add((pair['OT_ONE'], pair['OT_TWO']))
    if len(pairs) > 1:
        return None
    if len(pairs) == 1:
        names = dict(zip(['home', 'away'], pairs.pop()))
    if not all(isinstance(n, str) and n.strip() for n in names.values()) or name_key(names['home']) == name_key(names['away']):
        return None
    try:
        kickoff = instant(event['start']).isoformat()
    except (KeyError, TypeError, ValueError):
        return None
    return {'key': 'paf:'+str(event['id']), 'id': str(event['id']), 'source': 'paf', 'league': league,
            'kickoff': kickoff, 'status': 'NS', 'teams': {s: {'id': 'paf:'+s, 'name': names[s]} for s in names}}


def paf_quotes(row, game, receipt, url):
    """Kambi recorded schema: full-time overtime, open two-way main markets."""
    native = paf_event(row, game['league'])
    if native is None or matching(game, [native], exact_time=True) is None:
        return []
    candidates = {}
    labels = {'including overtime': 'winner', 'moneyline including overtime': 'winner',
              'handicap including overtime': 'spread', 'point spread including overtime': 'spread',
              'total points including overtime': 'total'}
    for offer in row.get('betOffers') or []:
        if not isinstance(offer, dict) or str(offer.get('eventId')) != native['id'] or offer.get('suspended'):
            continue
        criterion = offer.get('criterion') or {}
        if criterion.get('occurrenceType') not in {None, 'POINTS'}:
            continue
        label = name_key(criterion.get('englishLabel') or criterion.get('label', ''))
        kind = labels.get(label)
        lifetime = criterion.get('lifetime')
        if lifetime == 'FULL_TIME_OVERTIME':
            kind = kind or {'moneyline': 'winner', 'match odds': 'winner', 'match': 'winner',
                            'handicap': 'spread', 'point spread': 'spread', 'total points': 'total'}.get(label)
        if kind is None or (lifetime is not None and lifetime != 'FULL_TIME_OVERTIME'):
            continue
        outcomes = offer.get('outcomes') or []
        if not isinstance(outcomes, list) or len(outcomes) != 2 or not all(isinstance(o, dict) and o.get('status') == 'OPEN' for o in outcomes):
            continue
        types = {o.get('type') for o in outcomes}
        if types != ({'OT_OVER', 'OT_UNDER'} if kind == 'total' else {'OT_ONE', 'OT_TWO'}):
            continue
        pair = []
        for outcome in outcomes:
            side = {'OT_ONE': 'home', 'OT_TWO': 'away', 'OT_OVER': 'over', 'OT_UNDER': 'under'}[outcome['type']]
            if kind != 'total':
                names = [outcome.get(k) for k in ['englishLabel', 'participant', 'label']]
                if not any(isinstance(n, str) and name_key(n) == name_key(native['teams'][side]['name']) for n in names):
                    break
            raw_odds, raw_line = number(outcome.get('odds')), number(outcome.get('line'))
            if raw_odds is None or not raw_odds.is_integer():
                break
            line = None if kind == 'winner' else line_number(raw_line/1000, kind == 'total') if raw_line is not None else None
            code = 'handicap_'+side if kind == 'spread' else side
            quote = make_quote(game, code, raw_odds/1000, line, 'Paf', 'Paf', url, receipt)
            if quote is None:
                break
            quote.update(source_fixture_key=native['key'], published_at=outcome.get('changedDate'),
                         source_market_id=offer.get('id'))
            pair.append(quote)
        if len(pair) != 2:
            continue
        if kind == 'spread' and pair[0]['line'] != -pair[1]['line']:
            continue
        if kind == 'total' and pair[0]['line'] != pair[1]['line']:
            continue
        priority = bool({'MAIN', 'MAIN_LINE'}.intersection(offer.get('tags') or []))
        candidates.setdefault(kind, []).append((priority, pair))
    quotes = []
    for values in candidates.values():
        main = [pair for priority, pair in values if priority]
        eligible = main or [pair for _, pair in values]
        # Several distinct lines without a single marked main line are ambiguous.
        if len(eligible) == 1:
            quotes.extend(eligible[0])
    return quotes


class Paf:
    BASE = 'https://eu-offering-api.kambicdn.com/offering/v2018/paf'
    PARAMS = {'lang': 'en_GB', 'market': 'GB', 'client_id': 2, 'channel_id': 1}

    def __init__(self, store, http):
        self.store, self.http = store, http
        self.diagnostics = {}

    def quotes(self, game, refresh=0):
        if game['league'] != 'euroleague' or game['status'] != 'NS' or instant(game['kickoff']) <= datetime.now(timezone.utc):
            return [], []
        self.diagnostics = {'requested': {k: game[k] for k in ['key', 'league', 'kickoff', 'teams']},
                            'recorded_at': datetime.now(timezone.utc).isoformat()}
        def fetch(url):
            try:
                value = self.http.object(url, self.PARAMS)
            except DataError as error:
                self.diagnostics['failed_request'] = {'url': url, 'error': str(error)}
                raise DataError(f'Paf: {str(error)} Αίτημα: {url}') from None
            return {'value': value, 'receipt': datetime.now(timezone.utc).isoformat()}
        listing = self.store.cached(f'paf:list:v1:{refresh}', lambda: fetch(
            self.BASE+'/listView/basketball/all/all/all/matches.json'), 120)
        rows = listing['value'].get('events')
        if not isinstance(rows, list):
            raise DataError('Paf: δεν επιστράφηκε έγκυρη λίστα αγώνων.')
        self.diagnostics['listing_count'] = len(rows)
        found = [row for row in rows if (native := paf_event(row, 'euroleague')) is not None
                 and matching(game, [native], exact_time=True) is not None]
        if len(found) != 1:
            requested = instant(game['kickoff'])
            candidates = []
            for row in rows:
                event = row.get('event') if isinstance(row, dict) else None
                if not isinstance(event, dict):
                    continue
                try:
                    start = instant(event['start'])
                except (KeyError, TypeError, ValueError):
                    continue
                if start.astimezone(ZoneInfo('Europe/Athens')).date() != requested.astimezone(ZoneInfo('Europe/Athens')).date():
                    continue
                score = sum(name_key(event.get(s+'Name', '')) == name_key(game['teams'][s]['name']) for s in ['home', 'away'])
                native = paf_event(row, 'euroleague')
                summary = (f"{event.get('homeName', '?')} — {event.get('awayName', '?')} | "
                           f"{start.astimezone(ZoneInfo('Europe/Athens')):%d/%m %H:%M} | "
                           f"{event.get('group', '?')} | {event.get('state', '?')} | "
                           f"{'αναγνωρίστηκε' if native else 'δεν αναγνωρίστηκε'}")
                candidates.append((-score, abs((start-requested).total_seconds()), summary))
            samples = '; '.join(v[2] for v in sorted(candidates)[:5]) or 'κανένας αγώνας στην επιλεγμένη ημερομηνία'
            raise DataError(f"Paf: δεν βρέθηκε μοναδική αντιστοίχιση. Ζητήθηκε: "
                            f"{game['teams']['home']['name']} — {game['teams']['away']['name']} | "
                            f"{requested.astimezone(ZoneInfo('Europe/Athens')):%d/%m %H:%M}. "
                            f"Η πηγή επέστρεψε {len(rows)} αγώνες. Κοντινές καταχωρίσεις: {samples}.")
        row = found[0]
        self.diagnostics['matched'] = {'event': row['event'], 'betOffers': (row.get('betOffers') or [])[:50]}
        event_id = row['event']['id']
        url = self.BASE+f'/betoffer/event/{event_id}.json'
        quotes = paf_quotes(row, game, listing['receipt'], self.BASE+'/listView/basketball/all/all/all/matches.json')
        notes = []
        if len(quotes) < 6:
            try:
                details = self.store.cached(f'paf:event:v1:{event_id}:{refresh}', lambda: fetch(url), 90)
                value = details['value']
                self.diagnostics['detail_response'] = {'events': value.get('events'),
                                                      'betOffers': (value.get('betOffers') or [])[:50]}
                # If returned, the fresh event metadata must still be the same fixture.
                fresh_events = value.get('events')
                if fresh_events is not None:
                    valid = [e for e in fresh_events if isinstance(e, dict) and str(e.get('id')) == str(event_id)] if isinstance(fresh_events, list) else []
                    if len(valid) != 1:
                        quotes = []
                        raise DataError('Paf: αμφίβολη ταυτότητα αγώνα στην απάντηση αποδόσεων.')
                    # The event endpoint can return a partial event. Missing keys
                    # retain the listing context; explicit new values still win.
                    previous_event = row['event']
                    fresh_event = dict(previous_event, **valid[0])
                    row = dict(row, event=fresh_event, betOffers=value.get('betOffers') or [])
                    fresh_native = paf_event(row, game['league'])
                    if fresh_native is None or matching(game, [fresh_native], exact_time=True) is None:
                        quotes = []
                        summary = (f"{fresh_event.get('homeName', '?')} — {fresh_event.get('awayName', '?')} | "
                                   f"{fresh_event.get('start', '?')} | {fresh_event.get('state', '?')}")
                        names = sorted({str(o.get('englishLabel') or o.get('participant') or o.get('label'))
                                        for offer in row['betOffers'] if isinstance(offer, dict)
                                        for o in offer.get('outcomes') or [] if isinstance(o, dict)
                                        and o.get('type') in {'OT_ONE', 'OT_TWO'}})
                        raise DataError('Paf: δεν επιβεβαιώθηκε η ταυτότητα στη δεύτερη απάντηση. '
                                        f'Στοιχεία πηγής: {summary}. Ομάδες στις αγορές: {", ".join(names[:6]) or "δεν δόθηκαν"}.')
                detailed = paf_quotes(dict(row, betOffers=value.get('betOffers') or []), game, details['receipt'], url)
                quotes.extend(q for q in detailed if not any(old['market'] == q['market'] for old in quotes))
            except DataError as error:
                notes.append(str(error))
        if not quotes and not notes:
            notes.append('Paf: δεν υπάρχουν επιβεβαιωμένες ανοικτές αγορές πλήρους αγώνα με παράταση και τις αντίστοιχες γραμμές.')
        return quotes, notes


class ESPN:
    source = 'espn'
    def __init__(self, http):
        self.http = http

    def fixtures(self, league, day):
        if league == 'greece':
            return []
        data = self.http.object(f'{ESPN_BASE}/{league}/scoreboard', {'dates': day.strftime('%Y%m%d'), 'limit': 200})
        return [g for e in data.get('events', []) if (g := espn_event(e, league))]

    def history(self, game):
        if game['league'] == 'greece':
            return []
        cutoff = instant(game['kickoff'])
        season = cutoff.year + (cutoff.month >= 7)
        values = {}
        for side in ['home', 'away']:
            tid = game['teams'][side]['id'].split(':', 1)[1]
            for year in [season, season-1]:
                data = self.http.object(f'{ESPN_BASE}/{game["league"]}/teams/{tid}/schedule', {'season': year})
                for e in data.get('events', []):
                    g = espn_event(e, game['league'])
                    if g and final_score(g) and 0 < (cutoff-instant(g['kickoff'])).total_seconds() <= 366*86400:
                        values[g['key']] = g
                if len(recent_games(list(values.values()), game, side)) >= 10:
                    break
        return list(values.values())

    def quotes(self, game):
        path = f'{ESPN_BASE}/{game["league"]}'
        results, errors = [], []
        try:
            data = self.http.object(path+'/summary', {'event': game['id']})
            results.extend(espn_quotes(data, game, datetime.now(timezone.utc).isoformat(), path+'/summary?event='+game['id']))
        except DataError as error:
            errors.append(str(error))
        try:
            day = instant(game['kickoff']).strftime('%Y%m%d')
            data = self.http.object(path+'/scoreboard', {'dates': day})
            events = [e for e in data.get('events', []) if str(e.get('id')) == game['id']]
            if len(events) == 1:
                results.extend(espn_quotes({'header': events[0]}, game, datetime.now(timezone.utc).isoformat(), path+'/scoreboard?dates='+day))
        except DataError as error:
            errors.append(str(error))
        return results, errors

    def result(self, game):
        data = self.http.object(f'{ESPN_BASE}/{game["league"]}/summary', {'event': game['id']})
        header = data.get('header') or {}
        return espn_event(header, game['league']) if header.get('competitions') else None


def sofa_event(event, league):
    if not isinstance(event, dict):
        return None
    tournament = (event.get('tournament') or {})
    unique = tournament.get('uniqueTournament') or tournament
    slug = unique.get('slug', '').lower()
    category = (tournament.get('category') or {}).get('name', '').lower()
    allowed = {'nba': {'nba'}, 'euroleague': {'euroleague'}, 'greece': {'basket-league', 'greek-basket-league', 'a1'}}
    if slug not in allowed[league] or (league == 'greece' and category != 'greece'):
        return None
    if not event.get('id') or number(event.get('startTimestamp')) is None:
        return None
    sides = {s: event.get(s+'Team') or {} for s in ['home', 'away']}
    if not all(t.get('id') and t.get('name') for t in sides.values()):
        return None
    if sides['home']['id'] == sides['away']['id']:
        return None
    try:
        kickoff = datetime.fromtimestamp(event['startTimestamp'], timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None
    state = (event.get('status') or {}).get('type')
    state = {'finished': 'FT', 'notstarted': 'NS', 'inprogress': 'LIVE'}.get(state, 'PST')
    return {'key': 'sofascore:'+str(event['id']), 'id': str(event['id']), 'source': 'sofascore', 'league': league,
            'kickoff': kickoff, 'status': state,
            'teams': {s: {'id': 'sofascore:'+str(t['id']), 'name': t['name']} for s, t in sides.items()},
            'score': {s: number((event.get(s+'Score') or {}).get('current')) for s in ['home', 'away']},
            'source_url': f'{SOFA_BASE}/event/{event["id"]}'}


def sofa_quotes(data, game, receipt, url):
    results = []
    for market in data.get('markets', []):
        if market.get('suspended') or market.get('isLive'):
            continue
        name = market.get('marketName', '').casefold()
        # Only explicitly documented full-game markets incl. overtime can settle
        # against final basketball scores. Unclear periods remain unavailable.
        if not ('incl. overtime' in name or market.get('includesOvertime') is True):
            continue
        base = name.split(' (')[0]
        kind = 'winner' if base in {'winner', 'full time'} else 'total' if base in {'total', 'total points'} else 'handicap' if base in {'handicap', 'asian handicap'} else None
        if kind is None:
            continue
        company = (market.get('bookmaker') or data.get('bookmaker') or {}).get('name')
        company_id = str(market.get('bookmakerId', data.get('bookmakerId', '1')))
        group = line_number(market.get('choiceGroup'), kind == 'total')
        for choice in market.get('choices', []):
            if choice.get('suspended'):
                continue
            label = str(choice.get('name', '')).casefold()
            code = ({'1': 'home', '2': 'away'} if kind == 'winner' else
                    {'over': 'over', 'under': 'under'} if kind == 'total' else {'1': 'handicap_home', '2': 'handicap_away'}).get(label)
            if code is None:
                continue
            try:
                price = 1+float(Fraction(str(choice['fractionalValue'])))
            except (ValueError, KeyError, ZeroDivisionError, OverflowError):
                continue
            line = None if kind == 'winner' else line_number(choice.get('handicap', group), kind == 'total')
            # A shared handicap belongs to the home side; away needs its own
            # explicit handicap, never copy a signed line to the other team.
            if code == 'handicap_away' and 'handicap' not in choice:
                continue
            q = make_quote(game, code, price, line, company, 'Sofascore', url, receipt, company_id=company_id)
            if q:
                results.append(q)
    return results


class Sofa:
    source = 'sofascore'
    def __init__(self, http):
        self.http = http

    def fixtures(self, league, day):
        data = self.http.object(f'{SOFA_BASE}/sport/basketball/scheduled-events/{day.isoformat()}')
        return [g for e in data.get('events', []) if (g := sofa_event(e, league))]

    def history(self, game):
        values = {}
        cutoff = instant(game['kickoff'])
        for side in ['home', 'away']:
            tid = game['teams'][side]['id'].split(':', 1)[1]
            for page in range(40):
                data = self.http.object(f'{SOFA_BASE}/team/{tid}/events/last/{page}')
                raw = data.get('events', [])
                for e in raw:
                    g = sofa_event(e, game['league'])
                    if g and final_score(g) and 0 < (cutoff-instant(g['kickoff'])).total_seconds() <= 366*86400:
                        values[g['key']] = g
                if len(recent_games(list(values.values()), game, side)) >= 10 or not data.get('hasNextPage'):
                    break
                if raw and max(e.get('startTimestamp', 0) for e in raw) < cutoff.timestamp()-366*86400:
                    break
        return list(values.values())

    def quotes(self, game):
        url = f'{SOFA_BASE}/event/{game["id"]}/odds/1/all'
        data = self.http.object(url)
        return sofa_quotes(data, game, datetime.now(timezone.utc).isoformat(), url), []

    def result(self, game):
        data = self.http.object(f'{SOFA_BASE}/event/{game["id"]}')
        return sofa_event(data.get('event') or {}, game['league'])


class Euro:
    source = 'euroleague'
    def __init__(self, http):
        self.http = http

    def season(self, year):
        url = f'{EURO_BASE}/competitions/E/seasons/E{year}/games'
        data = self.http.get(url, {'limit': 500})
        rows = data.get('data', []) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise DataError('EuroLeague: μη έγκυρη λίστα αγώνων.')
        values = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                kickoff = instant(row.get('utcDate') or row['date']).isoformat()
                teams = {s: row[k] for s, k in [('home', 'local'), ('away', 'road')]}
                if not all(t.get('club', {}).get('code') and t['club'].get('name') for t in teams.values()):
                    continue
                if teams['home']['club']['code'] == teams['away']['club']['code']:
                    continue
                gid = str(row['gameCode'])
                values.append({'key': f'euroleague:E{year}:{gid}', 'id': gid, 'season': year,
                    'source': 'euroleague', 'league': 'euroleague', 'kickoff': kickoff,
                    'status': 'FT' if row.get('played') is True else 'NS' if row.get('played') is False else 'PST',
                    'teams': {s: {'id': 'euroleague:'+str(t['club']['code']), 'name': t['club']['name']} for s, t in teams.items()},
                    'score': {s: number(t.get('score')) for s, t in teams.items()}, 'source_url': url})
            except (ValueError, KeyError, TypeError):
                continue
        if rows and not values:
            raise DataError('EuroLeague: μη ασφαλής ώρα ή ταυτότητα αγώνων στην απάντηση.')
        return values

    def fixtures(self, league, day):
        if league != 'euroleague':
            return []
        year = day.year if day.month >= 7 else day.year-1
        return [g for g in self.season(year) if instant(g['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date() == day]

    def history(self, game):
        year = game['season']
        values = []
        for y in [year, year-1]:
            values.extend(g for g in self.season(y) if final_score(g) and 0 < (instant(game['kickoff'])-instant(g['kickoff'])).total_seconds() <= 366*86400)
            if all(len(recent_games(values, game, s)) >= 10 for s in ['home', 'away']):
                break
        return values

    def quotes(self, game):
        return [], []  # Official scores API does not publish bookmaker odds.

    def result(self, game):
        return next((g for g in self.season(game['season']) if g['key'] == game['key']), None)


class BasketballData:
    def __init__(self, store, http=None, odds_key=''):
        self.store = store
        self.odds = TheOddsAPI(odds_key, store) if odds_key else None
        http = http or HTTP()
        self.paf = Paf(store, http)
        self.adapters = {'espn': ESPN(http), 'sofascore': Sofa(http), 'euroleague': Euro(http)}
        self.errors = []

    def order(self, league):
        return ['espn', 'sofascore'] if league == 'nba' else ['euroleague', 'sofascore', 'espn'] if league == 'euroleague' else ['sofascore']

    def fixtures_from(self, source, league, day):
        key = f'fixtures:{source}:{league}:{day}'
        def load():
            days = [day] if source == 'euroleague' else [day-timedelta(days=1), day]
            values = {}
            for requested_day in days:
                for game in self.adapters[source].fixtures(league, requested_day):
                    if instant(game['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date() == day:
                        values[game['key']] = game
            return sorted(values.values(), key=lambda g: (g['status'] != 'NS', instant(g['kickoff'])))
        return self.store.cached(key, load, 120)

    def fixtures(self, league, day):
        for source in self.order(league):
            try:
                values = self.fixtures_from(source, league, day)
                if values:
                    return values
            except DataError as error:
                self.errors.append(str(error))
        return []

    def native(self, game, source):
        if game['source'] == source:
            return game
        day = instant(game['kickoff']).astimezone(ZoneInfo('Europe/Athens')).date()
        return matching(game, self.fixtures_from(source, game['league'], day), exact_time=True)

    def history(self, game):
        combined = {}
        for source in [game['source']]+[s for s in self.order(game['league']) if s != game['source']]:
            try:
                native = self.native(game, source)
                if native is None:
                    continue
                values = self.store.cached('history:'+native['key'], lambda: self.adapters[source].history(native), 6*3600)
                for g in values:
                    if g['league'] != game['league'] or final_score(g) is None or not 0 < (instant(game['kickoff'])-instant(g['kickoff'])).total_seconds() <= 366*86400:
                        continue
                    teams = {s: dict(t) for s, t in g['teams'].items()}
                    for team in teams.values():
                        for side in ['home', 'away']:
                            if team['id'] == native['teams'][side]['id']:
                                team['id'] = game['teams'][side]['id']
                    g = dict(g, teams=teams)
                    key = identity(g)
                    if key in combined:
                        if instant(combined[key]['kickoff']) != instant(g['kickoff']):
                            raise ValueError('Αμφίβολη ταυτότητα ιστορικού αγώνα μεταξύ πηγών· ο υπολογισμός σταμάτησε.')
                        if final_score(combined[key]) != final_score(g):
                            raise ValueError('Αντικρουόμενα σκορ μεταξύ πηγών· ο υπολογισμός σταμάτησε.')
                    combined.setdefault(key, g)
                if all(len(recent_games(list(combined.values()), game, s)) >= 10 for s in ['home', 'away']):
                    break
            except DataError as error:
                self.errors.append(str(error))
        return list(combined.values())

    def quotes(self, game, refresh=0):
        def load():
            quotes, errors = [], []
            if game['status'] != 'NS' or instant(game['kickoff']) <= datetime.now(timezone.utc):
                return quotes, errors
            for source in self.order(game['league']):
                try:
                    native = self.native(game, source)
                    if native is None:
                        errors.append(f'{source}: δεν βρέθηκε μοναδική αντιστοίχιση του αγώνα με ίδια διοργάνωση, ομάδες και ώρα έναρξης για αναζήτηση αποδόσεων.')
                        continue
                    found, notes = self.adapters[source].quotes(native)
                    for q in found:
                        q = dict(q, fixture_key=game['key'], source_fixture_key=native['key'])
                        if not any(existing['market'] == q['market'] for existing in quotes):
                            quotes.append(q)
                    errors.extend(notes)
                    if not found and source != 'euroleague' and not notes:
                        errors.append(f'{source}: δεν επιστράφηκαν επιβεβαιωμένες αποδόσεις πλήρους αγώνα με τις αντίστοιχες γραμμές.')
                    if len({q['market'] for q in quotes}) == 6:
                        break
                except DataError as error:
                    errors.append(str(error))
            if len({q['market'] for q in quotes}) < 6 and game['league'] == 'euroleague':
                try:
                    found, notes = self.paf.quotes(game, refresh)
                    quotes.extend(q for q in found if not any(old['market'] == q['market'] for old in quotes))
                    errors.extend(notes)
                except DataError as error:
                    errors.append(str(error))
            if len({q['market'] for q in quotes}) < 6 and self.odds and game['league'] in TheOddsAPI.SPORTS:
                try:
                    found = self.odds.quotes(game, refresh)
                    quotes.extend(q for q in found if not any(old['market'] == q['market'] for old in quotes))
                    if not found:
                        errors.append('The Odds API: δεν υπάρχουν δημοσιευμένες αποδόσεις για τον αγώνα.')
                except DataError as error:
                    errors.append(str(error))
            return quotes, errors
        scope = self.odds.scope if self.odds else 'public'
        def snapshot():
            quotes, errors = load()
            return {'quotes': quotes, 'errors': errors, 'paf_diagnostics': self.paf.diagnostics}
        result = self.store.cached(f'quotes:v8:{scope}:{game["key"]}:{refresh}', snapshot, 90)
        self.paf.diagnostics = result['paf_diagnostics']
        return result['quotes'], result['errors']

    def result(self, game):
        for source in [game['source']]+[s for s in self.order(game['league']) if s != game['source']]:
            try:
                native = self.native(game, source)
                if native is None:
                    continue
                result = self.adapters[source].result(native)
                if result and result['key'] == native['key'] and identity(result) == identity(game) and final_score(result) and all(result['teams'][s]['id'] == native['teams'][s]['id'] for s in ['home', 'away']):
                    return dict(result, key=game['key'])
            except DataError as error:
                self.errors.append(str(error))
        return None
