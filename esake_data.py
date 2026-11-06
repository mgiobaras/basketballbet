"""Official ESAKE calendar/results; unknown dates and scores remain unavailable."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from basketball_data import DataError, name_key
from basketball_model import final_score, instant

BASE = 'https://www.esake.gr/el/action/'
ATHENS = ZoneInfo('Europe/Athens')
MONTHS = dict(zip(['ιαν', 'φεβ', 'μαρ', 'απρ', 'μαι', 'ιουν', 'ιουλ', 'αυγ', 'σεπ', 'οκτ', 'νοε', 'δεκ'], range(1, 13)))


def plain(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', value)).split())


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.options, self.blocks, self.rounds = {}, [], set()
        self.select, self.option = None, None
        self.headings, self.heading = [], None
        self.depth, self.start, self.block = 0, None, []
        self.feed(html)

    def handle_startendtag(self, tag, attrs):
        # ESAKE emits <select ... /> followed by options and </select>.
        # Browsers keep non-void select/option elements open despite the slash.
        self.handle_starttag(tag, attrs)
        if tag not in {'select', 'option'}:
            self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'button':
            # Results builds the series options with JavaScript. Read the
            # published navigation values; never execute page scripts.
            series = re.search(r'''\$j\(['"]\#series['"]\)\.val\(['"](\d{1,2})['"]\)''', attr.get('onclick', ''))
            if series and 1 <= int(series[1]) <= 40:
                self.rounds.add(series[1])
        if tag == 'select':
            names = [attr.get(k, '').lower() for k in ['name', 'id']]
            self.select = next((n for n in names if n in {'idchampionship', 'idseason', 'series'}),
                               next((n for n in names if n), 'unnamed:'+str(len(self.options))))
        if tag == 'option' and self.select:
            self.finish_option()
            self.option = dict(value=attr.get('value', ''), selected='selected' in attr, label='')
        if tag in {'h1', 'h2', 'h3', 'h4'} and self.select is None:
            self.heading = {'tag': tag, 'text': ''}
        if tag == 'div':
            self.depth += 1
            if 'esake-program-game' in attr.get('class', '').split():
                self.start, self.block = self.depth, []
        if self.start is not None:
            self.block.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.start is not None:
            self.block.append('</'+tag+'>')
        if tag in {'option', 'select'}:
            self.finish_option()
        if tag == 'select':
            self.select = None
        if self.heading is not None and tag == self.heading['tag']:
            self.headings.append(plain(self.heading['text']))
            self.heading = None
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
        if self.heading is not None:
            self.heading['text'] += value

    def finish_option(self):
        # HTML allows </option> to be omitted before the next option or </select>.
        if self.option is not None:
            self.options.setdefault(self.select, []).append(self.option)
            self.option = None

    def handle_entityref(self, name):
        self.handle_data('&'+name+';')

    def handle_charref(self, name):
        self.handle_data('&#'+name+';')


def season_year(label):
    label = name_key(plain(label))
    if not re.search(r'basket\s*league|\bgbl\b', label) or re.search(r'cup|women|γυναικ', label):
        return None
    # name_key normalizes separators, including the season's dash, to spaces.
    years = re.search(r'\b(20\d{2})\s+(20\d{2}|\d{2})\b', label)
    if not years:
        return None
    year = int(years[1])
    end = int(years[2]) if len(years[2]) == 4 else year//100*100+int(years[2])
    return year if end == year+1 else None


def championships(page):
    catalogues = []
    for options in page.options.values():
        values = {}
        for option in options:
            year = season_year(option['label'])
            if year is None or not re.fullmatch(r'[\dA-Fa-f]{4,32}', option['value']):
                continue
            if str(year) in values and values[str(year)] != option['value']:
                raise DataError('ΕΣΑΚΕ: αμφίβολη ταυτότητα διοργάνωσης/σεζόν.')
            values[str(year)] = option['value']
        if values:
            catalogues.append((values, options))
    if len(catalogues) == 1:
        values, options = catalogues[0]
        active = [o for o in options if o['selected']]
        # In a single-select, no selected attribute means the first option.
        active = active or options[:1]
        selected = season_year(active[0]['label']) if len(active) == 1 else None
        headings = {year for h in page.headings if (year := season_year(h)) is not None}
        if selected is None and not any(o['selected'] for o in options) and len(headings) == 1:
            selected = next(iter(headings))
        if selected is not None and str(selected) in values:
            return values, selected
    fields = ', '.join(f'{name}:{len(opts)}' for name, opts in list(page.options.items())[:5]) or 'κανένα'
    titles = ' / '.join(page.headings[:3])[:160] or 'κανένας'
    selections = ' / '.join(f'{name}={plain(o["label"])[:65]} ({o["value"][:32]})'
        for name, opts in list(page.options.items())[:5]
        for o in ([o for o in opts if o['selected']] or opts[:1])[:2])[:350] or 'καμία'
    raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η επιλεγμένη σεζόν της Basket League. '
                    f'Πεδία: {fields}. Τίτλοι: {titles}. Επιλογές: {selections}.')


def selected_values(page, field):
    options = page.options.get(field, [])
    return [o['value'] for o in options if o['selected']] or [o['value'] for o in options[:1]]


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
        self.diagnostics = {}
        self.errors = []

    def record_failure(self, action, html, error, params=None):
        # Only the public ESAKE response: no app settings, headers or bet history.
        limit = 2_000_000
        key = action+('?' + urlencode(params) if params else '')
        if key not in self.diagnostics and len(self.diagnostics) >= 4:
            return  # Bound downloaded public HTML; all error messages still remain available.
        self.diagnostics[key] = {
            'url': BASE+key, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'error': str(error), 'response_characters': len(html) if html is not None else None,
            'truncated': html is not None and len(html) > limit,
            'html': html[:limit] if html is not None else None}

    def catalogue(self):
        def load():
            errors = []
            for action in ['EsakePrograms', 'EsakeResults']:
                url = BASE+action
                html = None
                try:
                    html = self.http.text(url)
                    page = Page(html)
                    seasons, year = championships(page)
                    phases = selected_values(page, 'idseason')
                    if len(phases) != 1 or not re.fullmatch(r'[\dA-Fa-f]{8}', phases[0]):
                        raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η φάση της διοργάνωσης.')
                    phase = phases[0]
                    return {'seasons': seasons, 'year': year, 'games': games_from(page, year, seasons[str(year)], phase, url)}
                except DataError as error:
                    self.record_failure(action, html, error)
                    errors.append(action+': '+str(error))
            raise DataError(' | '.join(errors))
        return self.store.cached('esake:catalogue:v3', load, 120)

    def round_page(self, year, championship, phase, series):
        url = BASE+'EsakeResults'
        params = dict(idchampionship=championship, idseason=phase, series=f'{int(series):02d}', idteam='')
        def load():
            html = None
            try:
                html = self.http.text(url, params)
                page = Page(html)
                if selected_values(page, 'idseason') != [phase]:
                    raise DataError('ΕΣΑΚΕ: η πηγή επέστρεψε διαφορετική φάση της διοργάνωσης.')
                games = games_from(page, year, championship, phase, url+'?'+urlencode(params))
                if any(g['round'] != int(series) for g in games):
                    raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η ζητούμενη αγωνιστική.')
                rounds = sorted(page.rounds | {o['value'] for o in page.options.get('series', [])
                                if o['value'].isdigit() and 1 <= int(o['value']) <= 40}, key=int)
                phases = [o['value'] for o in page.options.get('idseason', []) if re.fullmatch(r'[\dA-Fa-f]{8}', o['value'])]
                return games, rounds, phases
            except DataError as error:
                self.record_failure('EsakeResults', html, error, params)
                raise
        return self.store.cached(f'esake:round:v1:{year}:{championship}:{phase}:{int(series)}', load, 600)

    def latest_results(self):
        """The normal results page needs no archive query or unplayed phase."""
        def load():
            html = None
            try:
                html = self.http.text(BASE+'EsakeResults')
                page = Page(html)
                seasons, year = championships(page)
                phases = selected_values(page, 'idseason')
                if len(phases) != 1 or not re.fullmatch(r'[\dA-Fa-f]{8}', phases[0]):
                    raise DataError('ΕΣΑΚΕ: δεν επαληθεύτηκε η φάση των αποτελεσμάτων.')
                return {'year': year, 'championship': seasons[str(year)], 'phase': phases[0],
                        'games': games_from(page, year, seasons[str(year)], phases[0], BASE+'EsakeResults')}
            except DataError as error:
                self.record_failure('EsakeResults', html, error)
                raise
        return self.store.cached('esake:latest-results:v1', load, 120)

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
        return self.store.cached('esake:season:v3:'+str(year), load, 600)

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
        """Keep verified current-season results even if an archive page fails."""
        values = {}
        self.errors = []
        def merge(games):
            for g in games:
                if (g.get('season') != game['season'] or g.get('championship') != game['championship']
                        or not final_score(g) or not 0 < (instant(game['kickoff'])-instant(g['kickoff'])).total_seconds() <= 366*86400):
                    continue
                previous = values.get(g['key'])
                if previous and {k:v for k,v in previous.items() if k!='source_url'} != {k:v for k,v in g.items() if k!='source_url'}:
                    raise ValueError('ΕΣΑΚΕ: αντικρουόμενη ταυτότητα ή σκορ ιστορικού αγώνα.')
                values.setdefault(g['key'], g)
        try:
            latest = self.latest_results()
            merge(latest['games'])
        except DataError as error:
            self.errors.append('ΕΣΑΚΕ, πρόσφατα αποτελέσματα: '+str(error))
        phases = [game['phase']]
        if game['phase'] != '00000001':
            phases.append('00000001')  # Include regular-season games before playoffs.
        for phase in phases:
            if phase == game['phase']:
                last = max([game['round']-1]+[g['round'] for g in values.values() if g['phase']==phase])
                if not 0 <= last <= 40:
                    raise DataError('ΕΣΑΚΕ: μη έγκυρο πλήθος προηγούμενων αγωνιστικών.')
                rounds = range(last,0,-1)
            else:
                try:
                    first, rounds, _ = self.round_page(game['season'],game['championship'],phase,1)
                    merge(first)
                    rounds = sorted({int(r) for r in rounds if int(r)!=1},reverse=True)
                except DataError as error:
                    self.errors.append('ΕΣΑΚΕ, κανονική περίοδος: '+str(error))
                    continue
            for series in rounds:
                observed = [g for g in values.values() if g['phase']==phase and g['round']==series]
                if all(any(game['teams'][side]['id'] in [t['id'] for t in g['teams'].values()]
                           for g in observed) for side in ['home','away']):
                    continue
                try:
                    played, _, _ = self.round_page(game['season'],game['championship'],phase,series)
                    merge(played)
                except DataError as error:
                    self.errors.append(f'ΕΣΑΚΕ, αγωνιστική {series}: {error}')
        return list(values.values())

    def quotes(self, game):
        return [], []

    def result(self, game):
        games, _, _ = self.round_page(game['season'], game['championship'], game['phase'], game['round'])
        return next((g for g in games if g['key'] == game['key']), None)
