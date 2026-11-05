"""Official ESAKE calendar/results; unknown dates and scores remain unavailable."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

from basketball_data import DataError, name_key
from basketball_model import final_score, instant, recent_games

BASE = 'https://www.esake.gr/el/action/'
ATHENS = ZoneInfo('Europe/Athens')
MONTHS = dict(zip(['ιαν', 'φεβ', 'μαρ', 'απρ', 'μαι', 'ιουν', 'ιουλ', 'αυγ', 'σεπ', 'οκτ', 'νοε', 'δεκ'], range(1, 13)))


def plain(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', value)).split())


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.options, self.blocks = {}, []
        self.select, self.option = None, None
        self.depth, self.start, self.block = 0, None, []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'select':
            self.select = attr.get('id') or attr.get('name')
        if tag == 'option' and self.select:
            self.option = dict(value=attr.get('value', ''), selected='selected' in attr, label='')
        if tag == 'div':
            self.depth += 1
            if 'esake-program-game' in attr.get('class', '').split():
                self.start, self.block = self.depth, []
        if self.start is not None:
            self.block.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.start is not None:
            self.block.append('</'+tag+'>')
        if tag == 'option' and self.option is not None:
            self.options.setdefault(self.select, []).append(self.option)
            self.option = None
        if tag == 'select':
            self.select = None
        if tag == 'div':
            if self.depth == self.start:
                self.blocks.append(''.join(self.block))
                self.start, self.block = None, []
            self.depth -= 1

    def handle_data(self, value):
        if self.option is not None:
            self.option['label'] += value
        if self.start is not None:
            self.block.append(value)

    def handle_entityref(self, name):
        self.handle_data('&'+name+';')

    def handle_charref(self, name):
        self.handle_data('&#'+name+';')


def championships(page):
    values, selected = {}, None
    for option in page.options.get('idchampionship', []):
        label = name_key(plain(option['label']))
        years = re.search(r'(20\d{2})\s*[-/]\s*(20\d{2}|\d{2})', plain(option['label']))
        if (not years or not re.search(r'basket\s*league|\bgbl\b', label)
                or re.search(r'cup|women|γυναικ', label) or not re.fullmatch(r'[\dA-Fa-f]{4,32}', option['value'])):
            continue
        year = int(years[1])
        end = int(years[2]) if len(years[2]) == 4 else year//100*100+int(years[2])
        if end != year+1:
            continue
        if str(year) in values and values[str(year)] != option['value']:
            raise DataError('ΕΣΑΚΕ: αμφίβολη ταυτότητα διοργάνωσης/σεζόν.')
        values[str(year)] = option['value']
        if option['selected']:
            selected = year
    if not values or selected is None:
        raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η επιλεγμένη σεζόν της Basket League.')
    return values, selected


def games_from(page, year, championship, phase, url):
    catalogue, selected = championships(page)
    if selected != year or catalogue.get(str(year)) != championship:
        raise DataError('ΕΣΑΚΕ: η σελίδα επέστρεψε διαφορετική σεζόν.')
    result = {}
    for block in page.blocks:
        ids = set(re.findall(r'EsakegameView\?idgame=([\dA-Fa-f]+)', unescape(block)))
        teams = list(dict.fromkeys(re.findall(r'/dat/esaketeam/([\dA-Fa-f]+)/', block)))
        row = re.search(r'<div\b[^>]*class=["\'][^"\']*\besake-program-game-final-score\b[^"\']*["\'][^>]*>', block)
        text = name_key(plain(block))
        # Keep punctuation for the explicit clock; never invent a time for TBA games.
        date = re.search(r'(\d{1,2})\s+([Α-Ωα-ωΪΫίϊΐύϋΰ]+)\s*[-–]?\s*(\d{1,2}):(\d{2})', plain(block))
        round_number = re.search(r'(\d+)η\s+Αγωνιστική', plain(block), re.I)
        if not date or not row or len(ids) != 1 or len(teams) != 2 or not round_number:
            continue
        spans = [plain(s) for s in re.findall(r'<span\b[^>]*>(.*?)</span>', block[row.end():], re.S)][:3]
        if len(spans) != 3 or not spans[0] or not spans[2]:
            continue
        score = re.fullmatch(r'(?:(\d+)\s*)?[-–](?:\s*(\d+))?', spans[1])
        month_text = name_key(date[2])
        month = next((value for prefix, value in MONTHS.items() if month_text.startswith(prefix)), None)
        if not score or month is None or bool(score[1]) != bool(score[2]):
            continue
        try:
            start = datetime(year if month >= 7 else year+1, month, int(date[1]), int(date[3]), int(date[4]), tzinfo=ATHENS)
        except ValueError:
            continue
        points = {'home': int(score[1]), 'away': int(score[2])} if score[1] else {'home': None, 'away': None}
        state = 'FT' if score[1] else 'NS' if start > datetime.now(ATHENS) else 'PST'
        if re.search(r'αναβολ|ματαιω|postpon|cancel', text):
            state = 'PST'
        gid = ids.pop().upper()
        game = {'key': 'esake:'+gid, 'id': gid, 'source': 'esake', 'league': 'greece',
                'season': year, 'championship': championship, 'phase': phase, 'round': int(round_number[1]),
                'kickoff': start.astimezone(timezone.utc).isoformat(), 'status': state,
                'teams': {s: {'id': 'esake:'+tid.upper(), 'name': name} for s, tid, name in
                          zip(['home', 'away'], teams, [spans[0], spans[2]])},
                'score': points, 'source_url': url}
        if state == 'FT' and (final_score(game) is None or start > datetime.now(ATHENS)):
            continue
        if game['key'] in result and result[game['key']] != game:
            raise DataError('ΕΣΑΚΕ: αντικρουόμενες καταχωρίσεις του ίδιου αγώνα.')
        result[game['key']] = game
    if page.blocks and not result:
        raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκαν ομάδες, ώρα και αναγνωριστικά αγώνων.')
    return list(result.values())


class Esake:
    source = 'esake'
    def __init__(self, store, http):
        self.store, self.http = store, http

    def catalogue(self):
        def load():
            url = BASE+'EsakePrograms'
            page = Page(self.http.text(url))
            seasons, year = championships(page)
            phases = [o['value'] for o in page.options.get('idseason', []) if o['selected']]
            if len(phases) != 1:
                raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η φάση της διοργάνωσης.')
            phase = phases[0]
            return {'seasons': seasons, 'year': year, 'games': games_from(page, year, seasons[str(year)], phase, url)}
        return self.store.cached('esake:catalogue:v1', load, 120)

    def round_page(self, year, championship, phase, series):
        url = BASE+'EsakeResults'
        params = dict(idchampionship=championship, idseason=phase, series=str(series), idteam='')
        page = Page(self.http.text(url, params))
        selected_phases = [o['value'] for o in page.options.get('idseason', []) if o['selected']]
        if selected_phases != [phase]:
            raise DataError('ΕΣΑΚΕ: η πηγή επέστρεψε διαφορετική φάση της διοργάνωσης.')
        games = games_from(page, year, championship, phase, url+'?'+ '&'.join(k+'='+v for k, v in params.items()))
        if any(g['round'] != int(series) for g in games):
            raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η ζητούμενη αγωνιστική.')
        rounds = [o['value'] for o in page.options.get('series', []) if o['value'].isdigit() and 1 <= int(o['value']) <= 40]
        phases = [o['value'] for o in page.options.get('idseason', []) if re.fullmatch(r'[\dA-Fa-f]{8}', o['value'])]
        return games, rounds, phases

    def season(self, year):
        def load():
            championship = self.catalogue()['seasons'].get(str(year))
            if championship is None:
                return []
            first, rounds, phases = self.round_page(year, championship, '00000001', '1')
            values = {g['key']: g for g in first}
            def merge(games):
                for game in games:
                    if game['key'] in values and values[game['key']] != game:
                        raise DataError('ΕΣΑΚΕ: αντικρουόμενη ταυτότητα ή αποτέλεσμα μεταξύ αγωνιστικών.')
                    values[game['key']] = game
            jobs = [('00000001', r) for r in rounds if int(r) != 1]
            for phase in phases:
                if phase == '00000001':
                    continue
                extra, phase_rounds, _ = self.round_page(year, championship, phase, '1')
                merge(extra)
                jobs.extend((phase, r) for r in phase_rounds if int(r) != 1)
            if len(jobs) > 120:
                raise DataError('ΕΣΑΚΕ: μη έγκυρο πλήθος αγωνιστικών.')
            with ThreadPoolExecutor(max_workers=4) as pool:
                for games, _, _ in pool.map(lambda job: self.round_page(year, championship, *job), jobs):
                    merge(games)
            return list(values.values())
        return self.store.cached('esake:season:v1:'+str(year), load, 600)

    def fixtures(self, league, day):
        if league != 'greece':
            return []
        catalogue = self.catalogue()
        games = [g for g in catalogue['games'] if instant(g['kickoff']).astimezone(ATHENS).date() == day]
        if games:
            return games
        year = day.year if day.month >= 7 else day.year-1
        return [g for g in self.season(year) if instant(g['kickoff']).astimezone(ATHENS).date() == day]

    def history(self, game):
        values = {}
        for year in [game['season'], game['season']-1]:
            values.update((g['key'], g) for g in self.season(year) if final_score(g)
                          and 0 < (instant(game['kickoff'])-instant(g['kickoff'])).total_seconds() <= 366*86400)
            if all(len(recent_games(list(values.values()), game, side)) == 10 for side in ['home', 'away']):
                break
        return list(values.values())

    def quotes(self, game):
        return [], []

    def result(self, game):
        games, _, _ = self.round_page(game['season'], game['championship'], game['phase'], game['round'])
        return next((g for g in games if g['key'] == game['key']), None)
