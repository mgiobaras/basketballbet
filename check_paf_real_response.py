"""Replay the user's real Paf response; no network or current-price claims."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from basketball_data import Paf, paf_event, paf_quotes
from basketball_model import instant
from basketball_store import Store


def main():
    data = json.loads(Path(__file__).with_name('testdata').joinpath('paf_real_panathinaikos.json').read_text())
    game, receipt = data['requested'], data['recorded_at']
    game['status'] = 'NS'
    full = dict(event=data['detail_response']['events'][0], betOffers=data['detail_response']['betOffers'])
    assert paf_event(full, 'euroleague') is not None
    quotes = paf_quotes(full, game, receipt, 'recorded-public-response')
    expected = {'home': (None, 1.91), 'away': (None, 1.89), 'over': (170.5, 1.91),
                'under': (170.5, 1.89), 'handicap_home': (.5, 1.91), 'handicap_away': (-.5, 1.89)}
    assert {q['market']: (q['line'], q['odds']) for q in quotes} == expected
    assert all(q['source_market_id'] not in {2711833881, 2711833899, 2711833902} for q in quotes)
    wrong = deepcopy(full)
    wrong['event']['homeName'] = 'Different team'
    assert not paf_quotes(wrong, game, receipt, 'recorded-public-response')
    with tempfile.TemporaryDirectory() as directory:
        store = Store(directory+'/cache.sqlite3')
        http = Mock()
        http.object.side_effect = [{'events': [data['matched']]}, data['detail_response']]
        with patch('basketball_data.datetime') as clock:
            clock.now.return_value = instant(receipt)
            found, notes = Paf(store, http).quotes(game)
        assert not notes
        assert {q['market']: (q['line'], q['odds']) for q in found} == expected
        for q in found:
            assert store.save(game, q, {'win': .5, 'push': 0., 'loss': .5}, {}, {}, now=instant(receipt))
        assert len(store.list()) == 6
    print('PASS real Paf response: race/period markets do not change team identity; six main prices/lines, two-stage retrieval and persistence')


if __name__ == '__main__':
    main()
