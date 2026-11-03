"""Opt-in possession estimates from completed games' public team box scores."""
import re

import numpy as np

from basketball_data import DataError, ESPN_BASE, EURO_BASE, espn_event, identity, name_key
from basketball_model import analyse, final_score, instant, number, recent_games

SIDES = ('home', 'away')


def count(value):
    n = number(value)
    if n is None or n < 0 or not n.is_integer():
        raise DataError('Box score: λείπει έγκυρο ομαδικό στατιστικό.')
    return n


def attempts(value):
    match = re.fullmatch(r'(\d+)\s*-\s*(\d+)', str(value))
    if match is None or int(match[1]) > int(match[2]):
        raise DataError('Box score: μη έγκυρες προσπάθειες σουτ.')
    return int(match[2])


def espn_box(data, game):
    header = data.get('header') or {}
    native = espn_event(header, game['league'])
    if (native is None or native['key'] != game['key'] or identity(native) != identity(game)
            or instant(native['kickoff']) != instant(game['kickoff'])
            or final_score(native) != final_score(game)):
        raise DataError('ESPN box score: διαφέρει η ταυτότητα, η ώρα ή το τελικό σκορ.')
    competitors = header['competitions'][0]['competitors']
    periods = [len(t.get('linescores') or []) for t in competitors]
    if len(periods) != 2 or periods[0] != periods[1] or periods[0] < 4:
        raise DataError('ESPN box score: άγνωστη διάρκεια αγώνα/παρατάσεων.')
    for t in competitors:
        if sum(count(p.get('displayValue')) for p in t['linescores']) != native['score'][t['homeAway']]:
            raise DataError('ESPN box score: οι περίοδοι διαφέρουν από το τελικό σκορ.')
    rows = data.get('boxscore', {}).get('teams', [])
    stats = {}
    for side in SIDES:
        found = [r for r in rows if r.get('homeAway') == side
                 and 'espn:'+str(r.get('team', {}).get('id')) == native['teams'][side]['id']]
        if len(found) != 1:
            raise DataError('ESPN box score: αμφίβολη αντιστοίχιση ομάδας.')
        values = {s['name']: s.get('displayValue') for s in found[0].get('statistics', [])}
        turnovers = values.get('totalTurnovers')
        if turnovers is None:
            # Individual turnovers alone omit team turnovers.
            turnovers = count(values.get('turnovers')) + count(values.get('teamTurnovers'))
        stats[side] = {'fga': attempts(values.get('fieldGoalsMade-fieldGoalsAttempted')),
                       'fta': attempts(values.get('freeThrowsMade-freeThrowsAttempted')),
                       'orb': count(values.get('offensiveRebounds')), 'tov': count(turnovers)}
    return stats, 48 + (periods[0]-4)*5


def euro_box(data, game):
    if game['key'] != f'euroleague:E{game["season"]}:{game["id"]}':
        raise DataError('EuroLeague box score: μη έγκυρο αναγνωριστικό αγώνα.')
    stats, durations = {}, []
    for side, key in zip(SIDES, ('local', 'road')):
        row = data.get(key) or {}
        clubs = {(str(p.get('player', {}).get('club', {}).get('code', '')),
                  name_key(p.get('player', {}).get('club', {}).get('name', '')))
                 for p in row.get('players', [])}
        if len(clubs) != 1 or not next(iter(clubs))[0] or next(iter(clubs))[1] != name_key(game['teams'][side]['name']):
            raise DataError('EuroLeague box score: αμφίβολη αντιστοίχιση ομάδας.')
        total = row.get('total') or {}
        if count(total.get('points')) != game['score'][side]:
            raise DataError('EuroLeague box score: διαφέρει το τελικό σκορ.')
        duration = number(total.get('timePlayed'))
        if duration is None or duration < 2400 or (duration-2400) % 300 != 0:
            raise DataError('EuroLeague box score: άγνωστη διάρκεια αγώνα/παρατάσεων.')
        durations.append(duration/60)
        # `total` already includes team rebounds/turnovers; do not add `team` again.
        stats[side] = {'fga': count(total.get('fieldGoalsAttemptedTotal')),
                       'fta': count(total.get('freeThrowsAttempted')),
                       'orb': count(total.get('offensiveRebounds')), 'tov': count(total.get('turnovers'))}
    if durations[0] != durations[1]:
        raise DataError('EuroLeague box score: αντικρουόμενη διάρκεια αγώνα.')
    return stats, durations[0]


def boxscores(data, fixture, history):
    """Fetch only the selected last ten per team. Cache compact, validated snapshots."""
    selected = {g['key']: g for side in SIDES for g in recent_games(history, fixture, side)}
    source = {'nba': 'espn', 'euroleague': 'euroleague'}.get(fixture['league'])
    if source is None:
        data.errors.append('Ρυθμός/αποτελεσματικότητα: δεν υπάρχει επαληθευμένη πηγή αναλυτικών στατιστικών για αυτή τη διοργάνωση.')
        return {}
    values = {}
    for game in selected.values():
        try:
            native = data.native(game, source)
            if native is None or final_score(native) != final_score(game):
                raise DataError('Box score: δεν αντιστοιχίστηκε με ασφάλεια ο ολοκληρωμένος αγώνας.')
            if source == 'espn':
                url = f'{ESPN_BASE}/nba/summary?event={native["id"]}'
                parser = espn_box
            else:
                url = f'{EURO_BASE}/competitions/E/seasons/E{native["season"]}/games/{native["id"]}/stats'
                parser = euro_box

            def load():
                raw = data.adapters[source].http.object(url)
                try:
                    stats, minutes = parser(raw, native)
                except (KeyError, TypeError, AttributeError, ValueError) as error:
                    raise DataError('Box score: μη έγκυρη μορφή ομαδικών στατιστικών.') from error
                estimates = [s['fga']-s['orb']+s['tov']+.44*s['fta'] for s in stats.values()]
                if any(s['orb'] > s['fga'] for s in stats.values()) or min(estimates) <= 0:
                    raise DataError('Box score: μη έγκυρη εκτίμηση κατοχών.')
                return {'stats': stats, 'minutes': minutes, 'possessions': sum(estimates)/2,
                        'source': source, 'source_url': url, 'source_fixture_key': native['key'],
                        'kickoff': native['kickoff'], 'score': native['score'],
                        'team_names': {s: native['teams'][s]['name'] for s in SIDES}}

            # Include score/time/names so corrected source records cannot reuse an old snapshot.
            cache_key = f'boxscore:v1:{native["key"]}:{native["kickoff"]}:{final_score(native)}:{identity(native)}'
            values[game['key']] = data.store.cached(cache_key, load, 7*86400)
        except DataError as error:
            data.errors.append(f'{game["teams"]["home"]["name"]} — {game["teams"]["away"]["name"]}: {error}')
    return values


def analyse_pace(fixture, history, boxes):
    """Experimental adjusted means; retain the classic observed score variance."""
    model = analyse(fixture, history)
    if model is None or fixture['league'] not in {'nba', 'euroleague'}:
        return None
    regulation = 48 if fixture['league'] == 'nba' else 40
    profiles = {}
    for side in SIDES:
        games = recent_games(history, fixture, side)
        observations, weights = [], []
        for game in games:
            box = boxes.get(game['key'])
            if (not box or instant(box['kickoff']) != instant(game['kickoff']) or box['score'] != game['score']
                    or any(name_key(box['team_names'][s]) != name_key(game['teams'][s]['name']) for s in SIDES)
                    or number(box.get('possessions')) is None or box['possessions'] <= 0
                    or number(box.get('minutes')) is None or box['minutes'] < regulation):
                return None
            points = final_score(game)
            if game['teams']['home']['id'] != fixture['teams'][side]['id']:
                points = points[::-1]
            possessions = box['possessions']
            observations.append([possessions*regulation/box['minutes'], possessions,
                                 100*points[0]/possessions, 100*points[1]/possessions])
            weights.append(.5 ** ((instant(fixture['kickoff'])-instant(game['kickoff'])).total_seconds()/86400/90))
        means = np.average(observations, axis=0, weights=weights)
        profiles[side] = dict(zip(('pace', 'possessions', 'offensive_rating', 'defensive_rating'), map(float, means)))
    home, away = profiles['home'], profiles['away']
    # Total game possessions retain observed overtime exposure; displayed pace is per 40/48 minutes.
    possessions = (home['possessions']+away['possessions'])/2
    model.update(mu_home=possessions*(home['offensive_rating']+away['defensive_rating'])/200,
                 mu_away=possessions*(away['offensive_rating']+home['defensive_rating'])/200,
                 model_version='basket-last10-possessions-v1', profiles=profiles,
                 expected_possessions=possessions, regulation_minutes=regulation,
                 possession_formula='average(home,away) of FGA - ORB + TOV + 0.44 * FTA',
                 variance_method='classic_observed_scores',
                 boxscore_inputs={key: boxes[key] for key in {k for keys in model['input_games'].values() for k in keys}})
    return model
