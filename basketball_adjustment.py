"""Competition-specific total/margin uncertainty from the same recent games.

The input games and predicted means are unchanged. Unlike the independent-score
baseline, total and margin variances include the observed within-game covariance
and uncertainty in the two estimated means. No fixed league score offsets.
"""
from copy import deepcopy
import math

import numpy as np

from basketball_model import final_score, instant, recent_games


def adjust_model(fixture, history, model):
    if model is None:
        return None
    result = deepcopy(model)
    profiles = []
    for side in ['home', 'away']:
        games = recent_games(history, fixture, side)
        weights = np.array([.5**((instant(fixture['kickoff'])-instant(g['kickoff'])).total_seconds()/86400/90) for g in games])
        weights /= weights.sum()
        scores = [final_score(g) if g['teams']['home']['id'] == fixture['teams'][side]['id'] else final_score(g)[::-1] for g in games]
        points = np.array(scores, dtype=float)
        observations = {'total': points[:, 0]+points[:, 1], 'margin': points[:, 0]-points[:, 1]}
        effective = 1/float(np.sum(weights**2))
        # Center first: identical integer scores must have exactly zero variance,
        # rather than rounding noise that could produce artificial certainty.
        centered = {name: values-values[0] for name, values in observations.items()}
        variances = {name: float(np.sum(weights*(values-np.sum(weights*values))**2)/(1-1/effective))
                     if effective > 1+1e-8 else None for name, values in centered.items()}
        profiles.append({'effective_games': effective, 'variances': variances})
    for family in ['total', 'margin']:
        available = [p['variances'][family] for p in profiles if p['variances'][family] is not None]
        pooled = float(np.mean(available)) if available else None
        if pooled is None or not math.isfinite(pooled) or pooled <= 0:
            result['variance_'+family] = None
            continue
        mean_uncertainty = sum((p['variances'][family] if p['variances'][family] is not None else pooled)/p['effective_games'] for p in profiles)/4
        result['variance_'+family] = pooled+mean_uncertainty
    result['base_model_version'] = model['model_version']
    result['model_version'] = model['model_version']+'-uncertainty1'
    result['probability_adjustment'] = {
        'version': 'basketball-total-margin-2026-11-08-v1', 'league': fixture['league'],
        'method': 'observed_total_margin_variance_with_mean_uncertainty',
        'profiles': profiles, 'fresh_accuracy_verified': False,
    }
    return result
