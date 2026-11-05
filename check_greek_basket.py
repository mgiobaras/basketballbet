"""Controlled ESAKE markup contract and Greek league identity/UI regression checks.

Markup follows the published esake-program-game / final-score structure. The
fixture IDs and HTML below are controlled examples, not downloaded live prices.
The 7/8 November fixture names/times were checked on ESAKE's public programme.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import BasketballData, DataError, sofa_event
from basketball_store import Store
from esake_data import BASE, Page, championships, games_from


def header(year=2026, phase='00000001', rounds=('1', '6')):
    return (f'<select id="idchampionship"><option value="184645B9" selected>Stoiximan GBL {year}-{year+1}</option>'
            f'<option value="44B80BEB">Stoiximan GBL {year-1}-{year}</option></select>'
            f'<select id="idseason"><option value="{phase}" selected>Regular</option></select>'
            '<select id="series">'+''.join(f'<option value="{r}">{r}</option>' for r in rounds)+'</select>')


def block(gid, home, away, when, score='&nbsp;-&nbsp;', round_number=6):
    return (f'<div class="esake-program-game"><h5>{round_number:02}η Αγωνιστική</h5>'
            f'<div class="esake-program-game-info">{when}</div>'
            f'<a href="/el/action/EsakegameView?idgame={gid}&amp;mode=3">Στατιστικά</a>'
            '<div class="esake-program-game-final-score row equal">'
            f'<img src="/dat/esaketeam/A0000001/logo.png"><span>{home}</span>'
            f'<span>{score}</span><span>{away}</span><img src="/dat/esaketeam/A0000002/logo.png">'
            '</div></div>')


MATCHES = [('ΔΟΞΑ ΛΕΥΚΑΔΑΣ ELABET', 'ΑΡΗΣ', 'Σαβ 7 Νοε - 15:00'),
           ('ΚΟΛΟΣΣΟΣ H HOTELS COLLECTION', 'ΠΕΡΙΣΤΕΡΙ Betsson', 'Σαβ 7 Νοε - 16:00'),
           ('ΗΡΑΚΛΗΣ', 'ΜΥΚΟΝΟΣ Betsson BC', 'Σαβ 7 Νοε - 17:00'),
           ('ΠΡΟΜΗΘΕΑΣ ΠΑΤΡΑΣ ΒΙΚΟΣ COLA', 'ΚΑΡΔΙΤΣΑ ΙΑΠΩΝΙΚΗ', 'Σαβ 7 Νοε - 17:00'),
           ('ΠΑΟΚ', 'VIKOS ΦALCONS', 'Σαβ 7 Νοε - 17:30'),
           ('ΑΕΚ', 'ΠΑΝΑΘΗΝΑΪΚΟΣ AKTOR', 'Κυρ 8 Νοε - 13:00'),
           ('ΜΑΡΟΥΣΙ', 'ΟΛΥΜΠΙΑΚΟΣ', 'Κυρ 8 Νοε - 17:30')]


def main():
    html = header()+''.join(block(f'B000000{i}', *m) for i, m in enumerate(MATCHES))
    page = Page(html)
    assert len(page.blocks) == 7 and championships(page)[1] == 2026
    games = games_from(page, 2026, '184645B9', '00000001', BASE+'EsakePrograms')
    assert len(games) == 7 and all(g['status'] == 'NS' for g in games)
    assert games[0]['kickoff'] == '2026-11-07T13:00:00+00:00'
    assert games[5]['kickoff'] == '2026-11-08T11:00:00+00:00'
    for h in [html.replace('Stoiximan GBL', 'Greek Cup'), html.replace('selected>', '>'), html.replace('2026-2027', '2025-2026')]:
        try:
            games_from(Page(h), 2026, '184645B9', '00000001', 'controlled')
            raise AssertionError('Unverified competition/season accepted')
        except DataError:
            pass
    missing_time = header()+block('C0000001', 'Home', 'Away', 'Κυρ 8 Νοε - TBA')
    try:
        games_from(Page(missing_time), 2026, '184645B9', '00000001', 'controlled')
        raise AssertionError('Unknown time invented')
    except DataError:
        pass
    old = header(2025)+block('C0000001', 'Home', 'Away', 'Σαβ 10 Ιαν - 17:00', '90&nbsp;-&nbsp;80', 1)
    played = games_from(Page(old), 2025, '184645B9', '00000001', 'controlled')[0]
    assert played['status'] == 'FT' and played['kickoff'].startswith('2026-01-10T15:00')
    assert played['score'] == dict(home=90, away=80)
    # Stable men's league ID 304 accepts rebranding; a similarly named cup does not.
    raw = dict(id=1, startTimestamp=1794056400, status={'type': 'notstarted'},
               tournament={'uniqueTournament': {'id': 304, 'slug': 'stoiximan-basket-league'}, 'category': {'name': 'Greece'}},
               homeTeam={'id': 1, 'name': 'Home'}, awayTeam={'id': 2, 'name': 'Away'})
    assert sofa_event(raw, 'greece')
    raw['tournament']['uniqueTournament']['slug'] = 'a-new-sponsor-name'
    assert sofa_event(raw, 'greece')
    raw['tournament']['uniqueTournament']['id'] = 608
    assert sofa_event(raw, 'greece') is None
    raw['tournament']['uniqueTournament'] = {'slug': 'stoiximan-basket-league'}
    assert sofa_event(raw, 'greece')
    raw['tournament']['category']['name'] = 'Spain'
    assert sofa_event(raw, 'greece') is None
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/test.sqlite3'); http = Mock(); http.text.return_value = html
        data = BasketballData(store, http=http)
        saturday = data.fixtures('greece', date(2026, 11, 7))
        sunday = data.fixtures('greece', date(2026, 11, 8))
        assert len(saturday) == 5 and len(sunday) == 2 and http.text.call_count == 1
        assert all(g['source'] == 'esake' for g in saturday+sunday)
        assert not http.object.called  # Official fixtures need no blocked Sofascore request.
        archive = BasketballData(Store(directory+'/archive.sqlite3'), http=http).adapters['esake']
        def archived_page(url, params=None):
            if url.endswith('EsakePrograms'):
                return html
            series = int(params['series'])
            return header(rounds=('1', '2'))+block(f'D000000{series}', 'Home', 'Away',
                       f'Σαβ {series+3} Οκτ - 17:00', '90&nbsp;-&nbsp;80', series)
        http.text.side_effect = archived_page
        archived = archive.season(2026)
        assert len(archived) == 2 and all(g['status'] == 'FT' for g in archived)
        assert archive.result(archived[0])['score'] == {'home': 90, 'away': 80}
        from check_basketball import fixture, history
        target = fixture(); target.update(league='greece', source='esake', season=2026)
        observed = history(target)
        for g in observed:
            g.update(league='greece', source='esake')
        archive.season = Mock(side_effect=lambda year: observed[:4] if year == 2026 else observed[4:])
        assert len(archive.history(target)) == 20
        assert archive.season.call_count == 2
        http.text.side_effect = None
        # Preserve automatic fallback when the official source is unavailable.
        other = BasketballData(Store(directory+'/fallback.sqlite3'), http=http)
        other.adapters['esake'].fixtures = Mock(side_effect=DataError('controlled official outage'))
        other.adapters['sofascore'].fixtures = Mock(return_value=saturday)
        assert len(other.fixtures('greece', date(2026, 11, 7))) == 5
    print('PASS Greece: 5 Saturday/2 Sunday fixtures, Athens time, official cache, source fallback, season/identity/TBA guards and stable tournament ID')
    ui_check(html)


def ui_check(html):
    from streamlit.testing.v1 import AppTest
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH': directory+'/ui.sqlite3', 'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
        'REQUIRE_REMOTE_DB': 'false', 'APP_PASSWORD': '', 'ODDS_API_KEY': ''}), \
         patch('basketball_data.HTTP.text', return_value=html), \
         patch('basketball_data.BasketballData.quotes', return_value=([], [])), \
         patch('basketball_data.BasketballData.fixtures') as fixtures:
        # Start with no NBA games, then exercise the real Greek source/selector.
        fixtures.return_value = []
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        fixtures.side_effect = lambda league, day: original(BasketballData(Store(directory+'/source.sqlite3')), league, day)
        app.sidebar.selectbox[0].select('Ελλάδα - Basket League')
        app.sidebar.date_input[0].set_value(date(2026, 11, 7)).run(timeout=30)
        assert not app.exception
        assert len(next(s for s in app.selectbox if s.label == 'Αγώνας').options) == 5
        app.sidebar.date_input[0].set_value(date(2026, 11, 8)).run(timeout=30)
        assert not app.exception
        assert len(next(s for s in app.selectbox if s.label == 'Αγώνας').options) == 2
    print('PASS Greek UI: automatic official lookup and correct date-specific fixture lists')


original = BasketballData.fixtures
if __name__ == '__main__':
    main()
