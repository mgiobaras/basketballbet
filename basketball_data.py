"""Public basketball data adapters and automatic, exact-identity source fallback."""
from datetime import datetime, timedelta, timezone
from fractions import Fraction
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
           'fenerbahce beko istanbul': 'fenerbahce', 'fc barcelona': 'barcelona'}


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
    def __init__(self, store, http=None):
        self.store = store
        http = http or HTTP()
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
                        continue
                    found, notes = self.adapters[source].quotes(native)
                    for q in found:
                        q = dict(q, fixture_key=game['key'], source_fixture_key=native['key'])
                        if not any(existing['market'] == q['market'] for existing in quotes):
                            quotes.append(q)
                    errors.extend(notes)
                    if len({q['market'] for q in quotes}) == 6:
                        break
                except DataError as error:
                    errors.append(str(error))
            return quotes, errors
        return self.store.cached(f'quotes:{game["key"]}:{refresh}', load, 90)

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
