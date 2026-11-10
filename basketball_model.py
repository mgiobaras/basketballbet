"""Up to ten recent observed basketball scores per team; no fabricated priors."""
from datetime import datetime, timezone
from math import erf, floor, isfinite, sqrt
import numpy as np

MARKETS = {'home': 'Νίκη γηπεδούχου', 'away': 'Νίκη φιλοξενούμενου',
           'over': 'Over', 'under': 'Under',
           'handicap_home': 'Handicap γηπεδούχου', 'handicap_away': 'Handicap φιλοξενούμενου'}


def instant(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Άγνωστη ζώνη ώρας αγώνα.')
    return dt.astimezone(timezone.utc)


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if isfinite(n) else None
    except (ValueError, TypeError):
        return None


def final_score(game):
    hs, aws = (number(game.get('score', {}).get(s)) for s in ['home', 'away'])
    if game.get('status') != 'FT' or hs is None or aws is None:
        return None
    if min(hs, aws) < 0 or not hs.is_integer() or not aws.is_integer() or hs == aws:
        return None
    return int(hs), int(aws)


def recent_games(history, fixture, side):
    tid = fixture['teams'][side]['id']
    cutoff = instant(fixture['kickoff'])
    valid = {g['key']: g for g in history if g['league'] == fixture['league']
             and final_score(g) is not None and instant(g['kickoff']) < cutoff
             and tid in [t['id'] for t in g['teams'].values()]}
    return sorted(valid.values(), key=lambda g: instant(g['kickoff']), reverse=True)[:10]


def analyse(fixture, history):
    groups = [recent_games(history, fixture, s) for s in ['home', 'away']]
    if any(not games for games in groups):
        return None
    profiles = []
    for side, games in zip(['home', 'away'], groups):
        tid = fixture['teams'][side]['id']
        weights = [.5 ** ((instant(fixture['kickoff'])-instant(g['kickoff'])).total_seconds()/86400/90) for g in games]
        scores = [final_score(g) if g['teams']['home']['id'] == tid else final_score(g)[::-1] for g in games]
        means = [float(np.average([s[i] for s in scores], weights=weights)) for i in [0, 1]]
        variances = [float(np.average([(s[i]-means[i])**2 for s in scores], weights=weights)) for i in [0, 1]]
        profiles.append((means, variances))
    (hm, hv), (am, av) = profiles
    mu_home, mu_away = (hm[0]+am[1])/2, (am[0]+hm[1])/2
    variance_home, variance_away = (hv[0]+av[1])/2, (av[0]+hv[1])/2
    # Independent Normal approximation to observed points. No arbitrary variance floor.
    return {'mu_home': mu_home, 'mu_away': mu_away, 'variance': variance_home+variance_away,
            'model_version': 'basket-up-to10-normal-v2',
            'history_counts': {side: len(games) for side, games in zip(['home', 'away'], groups)},
            'input_games': {side: [g['key'] for g in games] for side, games in zip(['home', 'away'], groups)},
            'input_sources': sorted({g['source'] for games in groups for g in games})}


def cdf(value, mean, variance):
    if variance <= 0:
        return float(value >= mean)
    return .5 * (1+erf((value-mean)/sqrt(2*variance)))


def distribution(model, market, line=None):
    if market not in MARKETS:
        raise ValueError('Άγνωστη αγορά.')
    family = 'total' if market in {'over', 'under'} else 'margin'
    variance = model.get('variance_'+family, model['variance'])
    if variance is None:
        return None
    residuals = model.get('residuals_'+family)
    def predicted_cdf(value,mean):
        if residuals:
            samples=np.array(residuals)
            if market=='handicap_away':samples=-samples
            samples=np.sort(samples)
            return float(np.interp(value-mean,samples,np.arange(1,len(samples)+1)/(len(samples)+1),left=1/(len(samples)+1),right=len(samples)/(len(samples)+1)))
        return cdf(value,mean,variance)
    if market in {'home', 'away'}:
        mean = model['mu_home']-model['mu_away']
        h = 1-predicted_cdf(.5, mean)
        a = predicted_cdf(-.5, mean)
        if h+a == 0:
            return None
        p = (h if market == 'home' else a)/(h+a)
        return {'win': p, 'push': 0., 'loss': 1-p}
    if number(line) is None:
        return None
    if not float(line*2).is_integer() or (market in {'over', 'under'} and line <= 0):
        return None
    total = market in {'over', 'under'}
    mean = model['mu_home']+model['mu_away'] if total else model['mu_home']-model['mu_away']
    if market == 'handicap_away':
        mean = -mean
    threshold = line if total else -line
    # Integer-score continuity correction; integer lines have a refund probability.
    low = floor(threshold) + .5 if not float(threshold).is_integer() else threshold-.5
    high = low if not float(threshold).is_integer() else threshold+.5
    below, above = predicted_cdf(low, mean), 1-predicted_cdf(high, mean)
    push = max(0., 1-below-above)
    win = below if market == 'under' else above
    return {'win': win, 'push': push, 'loss': max(0., 1-win-push)}


def outcome(market, line, score):
    hs, aws = score
    if market == 'home':
        delta = hs-aws
    elif market == 'away':
        delta = aws-hs
    elif market == 'over':
        delta = hs+aws-line
    elif market == 'under':
        delta = line-hs-aws
    elif market == 'handicap_home':
        delta = hs+line-aws
    elif market == 'handicap_away':
        delta = aws+line-hs
    else:
        raise ValueError('Άγνωστη αγορά.')
    return 'won' if delta > 0 else 'lost' if delta < 0 else 'push'
