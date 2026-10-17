"""Simulated 7-day reach: does Fieldwise's ranking help Felix reach new problems sooner?

SIMULATED, NOT FIELD DATA. Every number comes from the assumptions in ASSUMPTIONS below,
which were fixed before the first comparison run. Problems appear on their own timeline,
independent of any scheduling rule, and every rule faces the identical timeline per run.
"""
import math
import random
from functools import lru_cache

ASSUMPTIONS = {
    'farms': 100, 'clusters': 10, 'area': 'Bomet County, Kenya (synthetic layout around -0.78, 35.34)',
    'days': 60, 'visits_per_day': 4, 'working_days_per_week': 5,
    'faw_daily_hazard': '0.002 × (1 + 2 × weather risk), weather risk 0–1 per cluster per week',
    'mln_seeds': 2, 'mln_daily_hazard': '0.0005 + 0.01 per infected farm within 2 km',
    'report_chance': 0.4, 'report_delay_days': '1–5', 'false_reports_per_farm_day': 0.002,
    'weather_noise': '±0.2 on the observed weather risk',
    'reach_window_days': 7, 'runs': 200,
    'fieldwise_knows': 'the hazard formulas above (in a real pilot these would have to be learned)',
    'travel': 'ignored; every visit costs the same',
}
NEIGHBOUR_KM = 2.0


def _km(a, b):
    return 111 * math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0])))


def _world(seed, scramble):
    rng = random.Random(seed)
    centres = [(-0.78 + rng.uniform(-0.12, 0.12), 35.34 + rng.uniform(-0.12, 0.12)) for _ in range(10)]
    farms = [(c[0] + rng.gauss(0, 0.01), c[1] + rng.gauss(0, 0.01)) for c in centres for _ in range(10)]
    near = [[j for j in range(100) if j != i and _km(farms[i], farms[j]) <= NEIGHBOUR_KM] for i in range(100)]
    weeks = 60 // 7 + 1
    weather = [[rng.random() for _ in range(10)] for _ in range(weeks)]          # true FAW risk, per cluster per week
    observed = [[min(1, max(0, w + rng.uniform(-0.2, 0.2))) for w in row] for row in weather]
    onset = {}          # (farm, kind) -> day the problem starts
    mln = set()
    for f in rng.sample(range(100), 2):
        onset[(f, 'mln')] = rng.randrange(0, 20); mln.add(f)
    for day in range(60):
        infected = {f for f in mln if onset[(f, 'mln')] <= day}
        for f in range(100):
            w = weather[day // 7][f // 10]
            if (f, 'faw') not in onset and rng.random() < 0.002 * (1 + 2 * w):
                onset[(f, 'faw')] = day
            if f not in mln and rng.random() < 0.0005 + 0.01 * sum(1 for n in near[f] if n in infected):
                onset[(f, 'mln')] = day; mln.add(f)
    reports = []        # (day, farm, kind or None for false alarm)
    for (f, kind), day in onset.items():
        if rng.random() < 0.4:
            reports.append((day + rng.randint(1, 5), f, kind))
    for day in range(60):
        for f in range(100):
            if rng.random() < 0.002:
                reports.append((day, f, None))
    if scramble:
        # No-signal test: same number and timing of reports and weather values, attached to random farms/clusters.
        reports = [(d, rng.randrange(100), k) for d, _, k in reports]
        observed = [rng.sample(row, len(row)) for row in observed]
    return farms, near, observed, onset, sorted(reports)


def _run(policy, world):
    farms, near, observed, onset, reports = world
    last_visit = [-30] * 100
    open_reports = {}       # farm -> (day reported, kind)
    known_mln = set()       # farms where MLN was reported or found
    found = {}
    r = 0
    order = list(range(100))
    cursor = 0
    for day in range(60):
        while r < len(reports) and reports[r][0] <= day:
            d, f, kind = reports[r]; r += 1
            open_reports.setdefault(f, (d, kind))
            if kind == 'mln': known_mln.add(f)
        if day % 7 >= 5:
            continue
        if policy == 'rotation':
            chosen = [order[(cursor + i) % 100] for i in range(4)]; cursor += 4
        elif policy == 'officer':
            reported = sorted(open_reports, key=lambda f: open_reports[f][0])
            rest = sorted((f for f in range(100) if f not in open_reports), key=lambda f: last_visit[f])
            chosen = (reported + rest)[:4]
        else:
            def score(f):
                since = day - last_visit[f]
                w = observed[day // 7][f // 10]
                h = 0.002 * (1 + 2 * w) + 0.0005 + 0.01 * sum(1 for n in near[f] if n in known_mln)
                p = 1 - math.exp(-h * since)
                return p + (0.6 if f in open_reports else 0)
            chosen = sorted(range(100), key=lambda f: -score(f))[:4]
        for f in chosen:
            last_visit[f] = day
            open_reports.pop(f, None)
            for kind in ('faw', 'mln'):
                start = onset.get((f, kind))
                if start is not None and start <= day and (f, kind) not in found:
                    found[(f, kind)] = day
                    if kind == 'mln': known_mln.add(f)
    eligible = [k for k, d in onset.items() if d <= 60 - 7]
    reached = [k for k in eligible if k in found and found[k] - onset[k] <= 7]
    by_kind = {kind: ([k for k in eligible if k[1] == kind], [k for k in reached if k[1] == kind]) for kind in ('faw', 'mln')}
    return len(eligible), len(reached), {k: (len(e), len(r_)) for k, (e, r_) in by_kind.items()}


POLICIES = {'rotation': 'Basic rotation: visit every farm in turn',
            'officer': 'Experienced officer: reported farms first, then whoever has waited longest',
            'fieldwise': 'Fieldwise: rank by reports, weather risk and nearby MLN'}


def _pct(values, q):
    v = sorted(values); return round(100 * v[min(len(v) - 1, int(q * len(v)))], 1)


@lru_cache(maxsize=4)
def simulate(scramble=False, runs=200):
    totals = {p: [] for p in POLICIES}
    kinds = {p: {'faw': [0, 0], 'mln': [0, 0]} for p in POLICIES}
    wins = {'vs_rotation': 0, 'vs_officer': 0}
    for seed in range(runs):
        world = _world(seed, scramble)
        rates = {}
        for p in POLICIES:
            n, hit, k = _run(p, world)
            rates[p] = hit / n if n else 0
            totals[p].append(rates[p])
            for kind, (e, r) in k.items():
                kinds[p][kind][0] += e; kinds[p][kind][1] += r
        wins['vs_rotation'] += rates['fieldwise'] > rates['rotation']
        wins['vs_officer'] += rates['fieldwise'] > rates['officer']
    return {'simulated': True, 'signal': 'scrambled' if scramble else 'real', 'runs': runs, 'assumptions': ASSUMPTIONS,
            'policies': {p: {'label': POLICIES[p], 'reach_mean': round(100 * sum(v) / len(v), 1),
                             'reach_p5': _pct(v, .05), 'reach_p95': _pct(v, .95),
                             'faw_reach': round(100 * kinds[p]['faw'][1] / max(1, kinds[p]['faw'][0]), 1),
                             'mln_reach': round(100 * kinds[p]['mln'][1] / max(1, kinds[p]['mln'][0]), 1)} for p, v in totals.items()},
            'fieldwise_beats_rotation_runs': wins['vs_rotation'], 'fieldwise_beats_officer_runs': wins['vs_officer']}
