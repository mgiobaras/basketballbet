"""Select actual easier quotes, without changing the classic scoring model."""
from basketball_model import distribution
from recommendations import MIN_EV, apply_policy, assess, finite

VERSION = 'basket-easier-lines-2026-11-16-v1'
TARGET_ODDS = 1.70
MIN_PRICE, MAX_PRICE = 1.60, 1.80
MIN_POINTS, MAX_POINTS = 2., 5.
LINE_MARKETS = {'over', 'under', 'handicap_home', 'handicap_away'}


def select_alternatives(game, model, original, quotes, now=None):
    """Nearest price to 1.70, then nearest improvement to 3 points; no hindsight.

    Keep the original if no verified, easier quote has positive model EV >=3%.
    The existing recommendation policy separately decides whether to recommend it.
    """
    selected, changes = dict(original), {}
    for market in LINE_MARKETS.intersection(original):
        base = original[market]
        base_line = base.get('line')
        if not finite(base_line):
            continue
        base_p = distribution(model, market, base_line)
        if base_p is None:
            continue
        candidates = []
        for quote in quotes:
            line, price = quote.get('line'), quote.get('odds')
            if (quote.get('market') != market or not finite(line) or not finite(price)
                    or not MIN_PRICE <= price <= MAX_PRICE
                    or quote.get('source') not in {'Paf', 'ESPN', 'Sofascore', 'The Odds API', 'Χειροκίνητη καταχώριση'}):
                continue
            improvement = base_line-line if market == 'over' else line-base_line
            if not MIN_POINTS <= improvement <= MAX_POINTS:
                continue
            probability = distribution(model, market, line)
            values = {market: {'line': line, 'probability': probability, 'quote': quote}}
            decision = assess('basketball', game, values, now)['decisions'][market]
            if (decision['reason'] not in {'main_recommendation', 'another_main_recommendation', 'probability_below_threshold', 'insufficient_expected_value'}
                    or decision['expected_value'] < MIN_EV or probability['win'] <= base_p['win']):
                continue
            candidates.append((quote, probability, improvement))
        if candidates:
            quote, probability, improvement = min(candidates, key=lambda item: (
                round(abs(item[0]['odds']-TARGET_ODDS), 8), abs(item[2]-3),
                -item[1]['win'], item[0]['line'], str(item[0].get('bookmaker')), str(item[0].get('source_market_id'))))
            selected[market] = dict(quote)
            changes[market] = {'original_line': base_line, 'original_odds': base['odds'],
                               'original_probability': base_p, 'original_bookmaker': base.get('bookmaker'),
                               'selected_line': quote['line'], 'selected_odds': quote['odds'],
                               'selected_probability': probability, 'points_easier': improvement}
    return selected, changes


def alternative_policy(game, markets, now=None):
    policy = apply_policy('basketball', game, markets, now)
    policy['policy_version'] = VERSION
    policy['criteria'].update(target_odds=TARGET_ODDS, alternate_odds_range=[MIN_PRICE, MAX_PRICE],
                              easier_points_range=[MIN_POINTS, MAX_POINTS])
    for value in markets.values():
        value['recommendation']['policy_version'] = VERSION
    return policy
