"""Simulated 7-day reach: does Fieldwise's ranking help Felix reach new crop problems sooner?

SIMULATED, NOT FIELD DATA. Every number comes from the assumptions below.

Design rules, fixed before the first comparison run:
  * Problems (fall armyworm, maize lethal necrosis) appear on their own timeline. No scheduling
    rule changes when or where a problem starts, so we never claim avoided crop loss.
  * Every scheduling rule faces the identical timeline in each run (paired comparison).
  * Fieldwise does not know the simulation's true rates. It ranks with its own rule-of-thumb
    weights (FieldwisePrior), and we rerun it with those weights halved and doubled.
  * A no-signal run scrambles reports and weather across farms. If Fieldwise still won there,
    the win would come from the set-up rather than the data.
"""
import math
import random
from dataclasses import asdict, dataclass, replace

KINDS = ('faw', 'mln')


@dataclass(frozen=True)
class Assumptions:
    farms: int = 100
    farms_per_cluster: int = 10          # farms grouped in villages
    days: int = 60
    visits_per_day: int = 4
    working_days_per_week: int = 5
    centre: tuple = (-0.78, 35.34)       # Bomet County, Kenya
    area_half_width_deg: float = 0.12    # cluster centres within ±0.12° (about ±13 km) for 100 farms
    cluster_sd_deg: float = 0.01         # farms within a village spread about 1 km
    faw_daily_risk: float = 0.002        # fall armyworm: chance per farm per day in a neutral week
    faw_weather_gain: float = 2.0        # a warm, dry week (risk 1.0) triples the chance
    mln_first_cases: int = 2
    mln_background_risk: float = 0.0005
    mln_risk_per_infected_neighbour: float = 0.005
    neighbour_km: float = 2.0
    report_chance: float = 0.4           # share of real problems a farmer reports
    report_delay_days: tuple = (1, 5)
    false_reports_per_farm_day: float = 0.002
    weather_noise: float = 0.2           # observed weather risk = true ± this
    reach_window_days: int = 7


@dataclass(frozen=True)
class FieldwisePrior:
    """Fieldwise's own ranking weights. Set from rules of thumb, not fitted to the simulation."""
    daily_risk: float = 0.003            # rough chance a farm develops a problem worth a visit
    weather_gain: float = 1.0            # a warm, dry week roughly doubles fall armyworm risk
    neighbour_gain: float = 5.0          # each farm with known MLN within 2 km multiplies MLN risk
    report_weight: float = 0.5           # chance a farmer report turns out to be real

    def scaled(self, factor):
        return replace(self, weather_gain=self.weather_gain * factor, neighbour_gain=self.neighbour_gain * factor)


POLICIES = {
    'rotation': 'Basic rotation: every farm in turn, village by village',
    'officer': 'Experienced officer: reported farms first, oldest report first, then whoever has waited longest',
    'fieldwise': 'Fieldwise: rank by farmer reports, weather risk and nearby MLN',
}


def _km(a, b):
    return 111.0 * math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0])))


class World:
    """One random season: farm layout, weather, problem onsets and farmer reports."""

    def __init__(self, seed, a=Assumptions(), scramble=False):
        rng = random.Random(seed)
        self.a = a
        n, per = a.farms, a.farms_per_cluster
        clusters = math.ceil(n / per)
        half = a.area_half_width_deg * math.sqrt(n / 100)   # keep village density constant as farms grow
        centres = [(a.centre[0] + rng.uniform(-half, half), a.centre[1] + rng.uniform(-half, half)) for _ in range(clusters)]
        self.cluster = [i // per for i in range(n)]
        self.farms = [(centres[c][0] + rng.gauss(0, a.cluster_sd_deg), centres[c][1] + rng.gauss(0, a.cluster_sd_deg)) for c in self.cluster]
        self.near = self._neighbours()
        weeks = a.days // 7 + 1
        self.weather = [[rng.random() for _ in range(clusters)] for _ in range(weeks)]
        observed = [[min(1.0, max(0.0, w + rng.uniform(-a.weather_noise, a.weather_noise))) for w in row] for row in self.weather]
        self.onset = {}
        infected = {}
        for f in rng.sample(range(n), a.mln_first_cases):
            infected[f] = rng.randrange(0, 20)
        for day in range(a.days):
            active = {f for f, d in infected.items() if d <= day}
            for f in range(n):
                w = self.weather[day // 7][self.cluster[f]]
                if (f, 'faw') not in self.onset and rng.random() < a.faw_daily_risk * (1 + a.faw_weather_gain * w):
                    self.onset[(f, 'faw')] = day
                if f not in infected:
                    k = sum(1 for g in self.near[f] if g in active)
                    if rng.random() < a.mln_background_risk + a.mln_risk_per_infected_neighbour * k:
                        infected[f] = day
        for f, d in infected.items():
            self.onset[(f, 'mln')] = d
        reports = []   # (day, farm, kind, real)
        for (f, kind), d in sorted(self.onset.items()):
            if rng.random() < a.report_chance:
                reports.append((d + rng.randint(*a.report_delay_days), f, kind, True))
        for day in range(a.days):
            for f in range(n):
                if rng.random() < a.false_reports_per_farm_day:
                    reports.append((day, f, rng.choice(KINDS), False))
        if scramble:
            # Same number, timing and type of reports, and the same weather values, attached to random farms
            # and villages. The problems themselves do not move.
            reports = [(d, rng.randrange(n), kind, real) for d, _, kind, real in reports]
            observed = [rng.sample(row, len(row)) for row in observed]
        self.observed = observed
        self.reports = sorted(reports, key=lambda r: (r[0], r[1]))

    def _neighbours(self):
        cell = self.a.neighbour_km / 111.0
        grid = {}
        for i, (lat, lon) in enumerate(self.farms):
            grid.setdefault((int(lat // cell), int(lon // cell)), []).append(i)
        near = []
        for i, (lat, lon) in enumerate(self.farms):
            gx, gy = int(lat // cell), int(lon // cell)
            cand = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid.get((gx + dx, gy + dy), ())]
            near.append([j for j in cand if j != i and _km(self.farms[i], self.farms[j]) <= self.a.neighbour_km])
        return near


class Officer:
    """Runs one scheduling rule through a season and records when each problem was first visited."""

    def __init__(self, world, policy, prior=FieldwisePrior()):
        self.w, self.policy, self.prior = world, policy, prior
        n = world.a.farms
        self.last_visit = [-30] * n
        self.open_reports = {}       # farm -> (day, kind)
        self.known_mln = set()       # farms with MLN reported or confirmed
        self.found = {}              # (farm, kind) -> day first visited while present
        self.order = sorted(range(n), key=lambda f: (world.cluster[f], f))
        self.cursor = 0
        self.next_report = 0
        self.log = {}                # day -> chosen farms

    def score(self, f, day):
        """Fieldwise priority: chance of an undetected problem since the last visit, plus open reports."""
        p = self.prior
        since = day - self.last_visit[f]
        weather = self.w.observed[day // 7][self.w.cluster[f]]
        known = sum(1 for g in self.w.near[f] if g in self.known_mln)
        rate = p.daily_risk * (1 + p.weather_gain * weather) + p.daily_risk * p.neighbour_gain * known
        return 1 - math.exp(-rate * since) + (p.report_weight if f in self.open_reports else 0)

    def step(self, day):
        a, w = self.w.a, self.w
        while self.next_report < len(w.reports) and w.reports[self.next_report][0] <= day:
            d, f, kind, _ = w.reports[self.next_report]
            self.next_report += 1
            if (f, kind) not in self.found:
                self.open_reports.setdefault(f, (d, kind))
                if kind == 'mln':
                    self.known_mln.add(f)
        if day % 7 >= a.working_days_per_week:
            return []
        k = a.visits_per_day
        if self.policy == 'rotation':
            chosen = [self.order[(self.cursor + i) % a.farms] for i in range(k)]
            self.cursor += k
        elif self.policy == 'officer':
            reported = sorted(self.open_reports, key=lambda f: self.open_reports[f][0])
            rest = sorted((f for f in range(a.farms) if f not in self.open_reports), key=lambda f: (self.last_visit[f], f))
            chosen = (reported + rest)[:k]
        else:
            chosen = sorted(range(a.farms), key=lambda f: (-self.score(f, day), f))[:k]
        for f in chosen:
            self.last_visit[f] = day
            self.open_reports.pop(f, None)
            for kind in KINDS:
                start = w.onset.get((f, kind))
                if start is not None and start <= day and (f, kind) not in self.found:
                    self.found[(f, kind)] = day
                    if kind == 'mln':
                        self.known_mln.add(f)
        self.log[day] = chosen
        return chosen

    def run(self, until=None):
        for day in range(self.w.a.days if until is None else until):
            self.step(day)
        return self

    def reach(self):
        a = self.w.a
        eligible = [key for key, d in self.w.onset.items() if d <= a.days - 1 - a.reach_window_days]
        hit = {key for key in eligible if key in self.found and self.found[key] - self.w.onset[key] <= a.reach_window_days}
        by_kind = {kind: (sum(1 for key in eligible if key[1] == kind), sum(1 for key in hit if key[1] == kind)) for kind in KINDS}
        return len(eligible), len(hit), by_kind


def _summary(values):
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]
    return {'mean': round(100 * sum(v) / len(v), 1), 'p5': round(100 * q(.05), 1), 'p95': round(100 * q(.95), 1)}


def compare(runs=200, a=Assumptions(), prior=FieldwisePrior(), scramble=False, first_seed=0):
    """Paired comparison of all scheduling rules over `runs` seasons."""
    rates = {p: [] for p in POLICIES}
    kinds = {p: {k: [0, 0] for k in KINDS} for p in POLICIES}
    problems = []
    for seed in range(first_seed, first_seed + runs):
        world = World(seed, a, scramble)
        for p in POLICIES:
            n, hit, by_kind = Officer(world, p, prior).run().reach()
            rates[p].append(hit / n if n else 0.0)
            for k, (e, h) in by_kind.items():
                kinds[p][k][0] += e
                kinds[p][k][1] += h
        problems.append(n)
    diff = lambda x, y: [i - j for i, j in zip(rates[x], rates[y])]
    return {
        'runs': runs, 'signal': 'scrambled' if scramble else 'real',
        'problems_per_run': round(sum(problems) / len(problems), 1),
        'policies': {p: dict(_summary(rates[p]), label=POLICIES[p],
                             **{f'{k}_reach': round(100 * kinds[p][k][1] / max(1, kinds[p][k][0]), 1) for k in KINDS})
                     for p in POLICIES},
        'fieldwise_minus_rotation': dict(_summary(diff('fieldwise', 'rotation')), wins=sum(d > 0 for d in diff('fieldwise', 'rotation'))),
        'fieldwise_minus_officer': dict(_summary(diff('fieldwise', 'officer')), wins=sum(d > 0 for d in diff('fieldwise', 'officer'))),
    }


def describe():
    return {'assumptions': asdict(Assumptions()), 'fieldwise_prior': asdict(FieldwisePrior()), 'policies': POLICIES}
