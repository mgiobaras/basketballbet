"""Browser transport contract; vendor CORS/live hosting are not simulated as proof.

Optional: python check_paf_browser.py /path/to/owner-pasted-listing.json
"""
from copy import deepcopy
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import DataError, Paf, paf_event, paf_quotes
from basketball_store import Store
from check_greek_odds import row_for
from paf_browser import BrowserHTTP, browser_quotes


class Rerun(Exception):
    pass


class UI:
    def __init__(self):
        self.session_state = {}

    def rerun(self):
        raise Rerun()


def main(capture=None):
    now = datetime.now(timezone.utc)
    row = row_for('Doxa Lefkadas','Aris',(now+timedelta(days=1)).isoformat())
    game = paf_event(row,'greece'); game.update(source='esake',key='esake:controlled')
    game['teams']['home']['name'] = 'ΔΟΞΑ ΛΕΥΚΑΔΑΣ ELABET'
    game['teams']['away']['name'] = 'ΑΡΗΣ'
    requests = []

    def answer(*, request, **kwargs):
        requests.append(request)
        value = {'events':[dict(row,betOffers=[])]} if '/listView/' in request['url'] else {
            'events':[row['event']], 'betOffers':row['betOffers']}
        return {'id':request['id'], 'ok':True, 'data':value}

    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/source.sqlite3'); ui = UI()
        with patch('paf_browser.component',side_effect=answer):
            for _ in range(5):
                try:
                    quotes, notes, diagnostic = browser_quotes(ui,store,game)
                    break
                except Rerun:
                    pass
            else:
                raise AssertionError('Browser stages did not finish')
        assert len(quotes) == 6 and not notes and len(requests) == 2
        assert requests[0]['url'].endswith('/basketball/greece/all/all/matches.json')
        assert requests[1]['url'].endswith('/event/'+str(row['event']['id'])+'.json')
        assert all(r['params'] == Paf.PARAMS for r in requests)
        assert all(q['price_kind'] == 'published_pre_match_browser' and q['fixture_key'] == game['key'] for q in quotes)
        assert diagnostic['transport'] == 'browser_public_fetch'
        before = deepcopy(quotes)
        with patch('paf_browser.component',side_effect=AssertionError('Unnecessary refetch')):
            assert browser_quotes(ui,store,game)[0] == before  # Receipt never refreshed on a UI rerun.
        assert store.list() == []
        for q in quotes:
            assert store.save(game,q,{'win':.5,'push':0.,'loss':.5},{},{})
        assert len(store.list()) == 6
        # A delayed component response from a different game/refresh cannot enter.
        ui = UI()
        with patch('paf_browser.component',return_value={'id':'wrong-request','ok':True,'data':{'events':[row]}}):
            found, notes, _ = browser_quotes(ui,store,game,99)
        assert not found and notes and ui.session_state['paf_browser_state']['responses'] == {}
        old_request = ui.session_state['paf_browser_state']['pending']['id']
        changed = dict(game,kickoff=(now+timedelta(days=2)).isoformat())
        with patch('paf_browser.component',return_value=None):
            browser_quotes(ui,store,changed,99)
        assert ui.session_state['paf_browser_state']['pending']['id'] != old_request
        # CORS/network/HTTP errors are surfaced; no proxies, other hosts or invented odds.
        ui = UI()
        def denied(*,request,**kwargs):
            return {'id':request['id'],'ok':False,'error':'HTTP 403'}
        with patch('paf_browser.component',side_effect=denied):
            try:
                browser_quotes(ui,store,game,100)
                raise AssertionError('Missing rerun')
            except Rerun:
                pass
            found, notes, _ = browser_quotes(ui,store,game,100)
        assert not found and '403' in notes[0]
        http = BrowserHTTP({'responses':{}})
        try:
            http.object('https://other.invalid/private',Paf.PARAMS)
            raise AssertionError('Arbitrary client URL accepted')
        except DataError:
            pass
    ui_check(game,row)
    if capture:
        data = json.loads(Path(capture).read_text(encoding='utf-8'))
        assert len(data['events']) == 103 and data['soonMode'] == 'HOURLY'
        assert not any(paf_event(r,'greece') for r in data['events'])
        euro = [r for r in data['events'] if paf_event(r,'euroleague')]
        assert len(euro) == 4
        assert all(len(paf_quotes(r,paf_event(r,'euroleague'),now.isoformat(),'owner-browser-capture')) == 2 for r in euro)
        print('PASS owner browser capture: 103 actual events, four EuroLeague moneylines, no Greek events; never treated as live app odds')
    print('PASS browser adapter: source allowlist, staged listing/details, exact existing parser, immutable receipts, scoped cache, stale response rejection, errors and Streamlit metrics after server410')


def ui_check(game,row):
    from streamlit.testing.v1 import AppTest
    with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
        'BET_DB_PATH':directory+'/ui.sqlite3','SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'',
        'REQUIRE_REMOTE_DB':'false','APP_PASSWORD':'','ODDS_API_KEY':''}), \
         patch('basketball_data.BasketballData.fixtures',side_effect=lambda league,day:[game] if league=='greece' else []), \
         patch('basketball_data.BasketballData.native',side_effect=DataError('Sofascore controlled HTTP403')), \
         patch('basketball_data.HTTP.object',side_effect=DataError('eu-offering-api.kambicdn.com: HTTP 410.')), \
         patch('paf_browser.component') as widget:
        def reply(*,request,**kwargs):
            data = {'events':[dict(row,betOffers=[])]} if '/listView/' in request['url'] else {
                'events':[row['event']],'betOffers':row['betOffers']}
            return {'id':request['id'],'ok':True,'data':data}
        widget.side_effect = reply
        app = AppTest.from_file(str(Path(__file__).parent/'app.py')).run(timeout=30)
        app.sidebar.selectbox[0].select('Ελλάδα - Basket League').run(timeout=30)
        assert not app.exception
        assert any(m.label=='Over 237' and m.value=='1.90' for m in app.metric)
        assert any(m.label=='Under 237' and m.value=='1.92' for m in app.metric)
        assert widget.call_count == 2 and Store(directory+'/ui.sqlite3').list() == []


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', nargs='?')
    parser.add_argument('--frontend', action='store_true')
    args = parser.parse_args()
    main(args.capture)
    if args.frontend:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            try:
                page = browser.new_page()
                # Execute our own frontend with an offline fetch stub. Do not
                # change browser policies or try to reach a blocked vendor host.
                page.set_content(Path(__file__).with_name('paf_browser_frontend').joinpath('index.html').read_text())
                page.evaluate('''()=>{
                    window.results=[]; window.requests=[];
                    addEventListener("message", e=>{if(e.data.type==="streamlit:setComponentValue")window.results.push(e.data.value);});
                    window.fetch=async(url,options)=>{
                        window.requests.push({url,options:{credentials:options.credentials,headers:options.headers,mode:options.mode}});
                        return new Response('{"events":[]}',{status:url.includes("betoffer")?410:200});
                    };
                }''')
                def dispatch(request):
                    page.evaluate('(request)=>window.dispatchEvent(new MessageEvent("message",{source:window,data:{type:"streamlit:render",args:{request}}}))', request)
                first = {'id':'listing','url':Paf.BASE+'/listView/basketball/greece/all/all/matches.json','params':Paf.PARAMS}
                dispatch(first)
                page.wait_for_function('results.length===1', timeout=5000)
                assert page.evaluate('results[0]') == {'id':'listing','ok':True,'data':{'events':[]}}
                dispatch(first)
                assert page.evaluate('requests.length') == 1
                dispatch(dict(first,id='details',url=Paf.BASE+'/betoffer/event/123.json'))
                page.wait_for_function('results.length===2', timeout=5000)
                assert page.evaluate('results[1].ok') is False and '410' in page.evaluate('results[1].error')
                dispatch(dict(first,id='invalid',url='https://other.invalid/private'))
                page.wait_for_function('results.length===3', timeout=5000)
                assert page.evaluate('results[2].ok') is False and page.evaluate('requests.length') == 2
                observed = page.evaluate('requests')
                assert all(r['options']['credentials']=='omit' and r['options']['mode']=='cors'
                           and not any(k.lower() in {'cookie','authorization'} for k in r['options']['headers']) for r in observed)
            finally:
                browser.close()
        print('PASS Chromium frontend: offline fetch/postMessage pipeline, deduplication, public URL allowlist, errors and no cookies/auth; no live vendor/CORS claim')
