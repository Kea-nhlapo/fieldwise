"""Learning from Felix's visit outcomes, and choosing which farmer to survey next.

Each recorded visit with a tapped outcome is a label: did the signals that were active
at the visit turn out to be a real problem? A Beta-Bernoulli model per signal keeps a
running estimate of that rate. Priors encode the hand-written rules' intent, so with no
visits the learned adjustment is zero and the original rules decide alone.
"""
from datetime import datetime, timezone

PROBLEM_OUTCOMES = {'wilting', 'water', 'pests'}
CLEAR_OUTCOMES = {'none'}
# Beta(problem, no problem) pseudo-counts.
PRIORS = {'dry': (2, 2), 'wet': (2, 2), 'concern': (3, 1), 'none': (1, 3)}
LABELS = {'dry': 'Hot, dry forecast', 'wet': 'Heavy rain on clay soil', 'concern': 'Farmer reported a concern', 'none': 'No signal active'}
POINTS_PER_UNIT = 60   # learned points per unit change in problem probability
MAX_ADJUST = 25
TOP_K = 3              # visits Felix can make in a day


def ensure_table(db):
    db.execute('CREATE TABLE IF NOT EXISTS felix_outcomes (id INTEGER PRIMARY KEY, signal TEXT NOT NULL, problem INTEGER NOT NULL, created_at TEXT NOT NULL)')


def active_signals(assessed):
    signals = [s for s, on in (('dry', assessed['dry_flag']), ('wet', assessed['wet_flag']),
                               ('concern', assessed.get('concern_open'))) if on]
    return signals or ['none']


def label_from_outcomes(outcomes):
    codes = set(outcomes or ())
    if codes & PROBLEM_OUTCOMES: return 1
    if codes & CLEAR_OUTCOMES: return 0
    return None   # advice or follow-up only: not a label


def record(db, signals, problem):
    now = datetime.now(timezone.utc).isoformat()
    for signal in signals:
        db.execute('INSERT INTO felix_outcomes (signal,problem,created_at) VALUES (?,?,?)', (signal, problem, now))


def stats(db):
    counts = {s: [0, 0] for s in PRIORS}
    for signal, problem, n in db.execute('SELECT signal, problem, COUNT(*) FROM felix_outcomes GROUP BY signal, problem'):
        if signal in counts: counts[signal][0 if problem else 1] += n
    result = {}
    for s, (a, b) in PRIORS.items():
        yes, no = counts[s]
        result[s] = {'label': LABELS[s], 'prior': round(a / (a + b), 2), 'posterior': round((a + yes) / (a + b + yes + no), 2),
                     'visits': yes + no, 'confirmed': yes}
    return result


def adjustment(signals, learned):
    raw = sum(POINTS_PER_UNIT * (learned[s]['posterior'] - learned[s]['prior']) for s in signals)
    points = max(-MAX_ADJUST, min(MAX_ADJUST, round(raw)))
    parts = [f"{learned[s]['label']}: confirmed {learned[s]['confirmed']} of {learned[s]['visits']} visits"
             for s in signals if learned[s]['visits']]
    return points, parts


def problem_probability(signals, learned):
    """Chance the farmer will report a concern, from the strongest active environmental signal."""
    env = [s for s in signals if s != 'concern'] or ['none']
    return max(learned[s]['posterior'] for s in env)


def survey_targets(ranked, rescore, learned):
    """Rank unanswered farms by the chance that asking changes today's top-K visit list.

    `rescore(farm, answer)` returns the farm's score if the farmer answers 'yes' (concern) or 'no'.
    """
    scores = {f['id']: f['score'] for f in ranked}
    targets = []
    for farm in ranked:
        if farm['completed'] or farm.get('concern_open') or farm.get('report'):
            continue
        others = sorted(v for k, v in scores.items() if k != farm['id'])

        def rank_for(score):
            return 1 + sum(1 for v in others if v > score)
        now, yes, no = farm['rank'], rank_for(rescore(farm, 'yes')), rank_for(rescore(farm, 'no'))
        p = problem_probability(active_signals(farm), learned)
        in_now = now <= TOP_K
        change = p * ((yes <= TOP_K) != in_now) + (1 - p) * ((no <= TOP_K) != in_now)
        movement = p * abs(now - yes) + (1 - p) * abs(now - no)
        targets.append({'id': farm['id'], 'name': farm['name'], 'crop': farm['crop'], 'rank_now': now,
                        'rank_if_yes': yes, 'rank_if_no': no, 'p_concern': round(p, 2),
                        'decision_change': round(change, 2), 'expected_movement': round(movement, 1)})
    return sorted(targets, key=lambda t: (-t['decision_change'], -t['expected_movement'], t['rank_now']))
