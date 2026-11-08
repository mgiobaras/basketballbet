"""An explicit, versioned recommendation policy; all other calculations stay visible."""
from datetime import datetime, timezone
import math

POLICY_VERSION = 'recommendations-2026-11-08-v1'
MIN_PROBABILITY = .70
MIN_ODDS = 1.50
MIN_EV = .03


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('A timezone is required')
    return result.astimezone(timezone.utc)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def assess(sport, fixture, markets, now=None):
    """At most one main recommendation per fixture, fixed before the outcome.

    This policy is a candidate for future evaluation, never proof of 70% accuracy.
    It does not limit the user's ability to save another supported market.
    """
    now = now or datetime.now(timezone.utc)
    kickoff = instant(fixture['fixture']['date'] if sport == 'football' else fixture['kickoff'])
    status = fixture['fixture']['status']['short'] if sport == 'football' else fixture['status']
    decisions = {}
    for market, values in markets.items():
        value = values.get('probability')
        win = value.get('win') if isinstance(value, dict) else value
        push = value.get('push', 0.) if isinstance(value, dict) else 0.
        loss = value.get('loss') if isinstance(value, dict) else 1-win if finite(win) else None
        quote = values.get('quote') or {}
        price = quote.get('odds')
        if isinstance(price, dict):
            price = price.get(market)
        conditional = win/(1-push) if finite(win) and finite(push) and 0 <= push < 1 else None
        ev = win*(price-1)-loss if all(finite(v) for v in [win, loss, price]) else None
        reason = None
        if status != 'NS' or now >= kickoff:
            reason = 'match_closed'
        elif not all(finite(v) and 0 <= v <= 1 for v in [win, push, loss]) or abs(win+push+loss-1) > 1e-8:
            reason = 'missing_probability'
        elif not finite(price) or price < MIN_ODDS:
            reason = 'missing_or_low_odds'
        elif not (str(quote.get('bookmaker') or '').strip() or (quote.get('source') == 'Sofascore' and str(quote.get('bookmaker_id') or '').isdigit())):
            reason = 'missing_bookmaker'
        elif sport == 'football' and quote.get('fixture_id') != fixture['fixture']['id']:
            reason = 'quote_fixture_mismatch'
        elif sport == 'basketball' and (quote.get('fixture_key') != fixture['key'] or quote.get('market') != market or quote.get('line') != values.get('line') or quote.get('scope') != 'including_overtime'):
            reason = 'quote_market_mismatch'
        elif sport == 'basketball' and market not in {'home', 'away'} and (not finite(values.get('line')) or not float(values['line']*2).is_integer() or (market in {'over','under'} and values['line'] <= 0)):
            reason = 'invalid_line'
        else:
            try:
                age = (now-instant(quote['observed_at'])).total_seconds()
                if not 0 <= age <= 300 or instant(quote['observed_at']) >= kickoff:
                    reason = 'stale_quote'
            except (KeyError, TypeError, ValueError):
                reason = 'missing_quote_time'
        if reason is None and (conditional is None or conditional < MIN_PROBABILITY):
            reason = 'probability_below_threshold'
        if reason is None and (ev is None or ev < MIN_EV):
            reason = 'insufficient_expected_value'
        decisions[market] = {'candidate': reason is None, 'recommended': False,
                             'reason': reason, 'conditional_probability': conditional,
                             'push_probability': push, 'expected_value': ev,
                             'odds': price, 'line': values.get('line')}
    candidates = [m for m, d in decisions.items() if d['candidate']]
    selected = max(candidates, key=lambda m: (decisions[m]['conditional_probability'], decisions[m]['expected_value'], m)) if candidates else None
    for market, decision in decisions.items():
        decision['recommended'] = market == selected
        if decision['candidate']:
            decision['reason'] = 'main_recommendation' if market == selected else 'another_main_recommendation'
    return {'policy_version': POLICY_VERSION, 'recommended_market': selected, 'decisions': decisions,
            'criteria': {'minimum_probability': MIN_PROBABILITY, 'minimum_odds': MIN_ODDS,
                         'minimum_expected_value': MIN_EV, 'maximum_recommendations_per_match': 1},
            'status': 'under_evaluation', 'verified_hit_rate': None}


def apply_policy(sport, fixture, markets, now=None):
    policy = assess(sport, fixture, markets, now)
    for market, decision in policy['decisions'].items():
        markets[market]['recommendation'] = dict(decision, policy_version=POLICY_VERSION)
    return policy


def show_recommendation(st, policy, labels):
    st.subheader('Προτάσεις μοντέλου — υπό αξιολόγηση')
    market = policy['recommended_market']
    if market is not None:
        value = policy['decisions'][market]
        label = 'πιθανότητα χωρίς επιστροφή' if value['push_probability'] else 'πιθανότητα'
        st.info(f"Κύρια πρόταση: {labels[market]} · απόδοση {value['odds']:.2f} · {label} {value['conditional_probability']:.1%}")
    else:
        st.caption('Δεν προκύπτει κύρια πρόταση με τα τρέχοντα κριτήρια. Μπορείς να αποθηκεύσεις δική σου επιλογή από τους υπολογισμούς.')
    st.caption('Κριτήρια: πιθανότητα ≥70%, απόδοση ≥1,50 και εκτιμώμενο EV ≥3%. Έως μία κύρια πρόταση ανά αγώνα. Το φίλτρο δεν αποτελεί επιβεβαίωση πραγματικής επιτυχίας 70%.')


def first_recommendations(records):
    """A fixed first-valid rule; never reinterpret legacy calculations as tips."""
    selected, seen = [], set()
    for record in sorted(records, key=lambda r: (instant(r['captured_at']), r['id'])):
        payload = record.get('payload', {})
        policy = payload.get('model', {}).get('recommendation_policy') or {}
        market = policy.get('recommended_market')
        if not payload.get('eligible_for_evaluation') or not market or not policy.get('policy_version'):
            continue
        if not policy.get('decisions', {}).get(market, {}).get('recommended'):
            continue
        sport, fixture = record['sport'], payload['fixture']
        kickoff = fixture['fixture']['date'] if sport == 'football' else fixture['kickoff']
        fixture_id = (fixture.get('_provider', 'api_sports')+':'+str(fixture['fixture']['id'])) if sport == 'football' else fixture['key']
        if instant(record['captured_at']) >= instant(kickoff):
            continue
        key = (sport, fixture_id, policy['policy_version'])
        if key not in seen:
            seen.add(key)
            selected.append(record)
    return selected
