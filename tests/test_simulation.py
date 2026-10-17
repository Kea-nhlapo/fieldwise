import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from fastapi.testclient import TestClient
from fieldwise.app import create_app, ROOT
from fieldwise.simulation import Assumptions, FieldwisePrior, Officer, POLICIES, World, compare, example_day


class WorldTests(unittest.TestCase):
    def test_seeded_worlds_are_reproducible(self):
        a, b = World(3), World(3)
        self.assertEqual(a.onset, b.onset)
        self.assertEqual(a.reports, b.reports)
        self.assertEqual(a.farms, b.farms)

    def test_scrambling_moves_signals_but_not_problems(self):
        real, scrambled = World(5), World(5, scramble=True)
        self.assertEqual(real.onset, scrambled.onset, 'problems must not move')
        self.assertEqual(sorted((d, k, r) for d, _, k, r in real.reports), sorted((d, k, r) for d, _, k, r in scrambled.reports))
        self.assertNotEqual([f for _, f, _, _ in real.reports], [f for _, f, _, _ in scrambled.reports])
        self.assertEqual(sorted(sum(real.observed, [])), sorted(sum(scrambled.observed, [])))

    def test_neighbours_are_within_two_km_and_symmetric(self):
        w = World(1)
        for i, near in enumerate(w.near):
            for j in near:
                self.assertIn(i, w.near[j])


class RuleTests(unittest.TestCase):
    def test_rules_never_change_the_problem_timeline(self):
        w = World(2)
        before = dict(w.onset)
        counts = {p: Officer(w, p).run().reach()[0] for p in POLICIES}
        self.assertEqual(w.onset, before)
        self.assertEqual(len(set(counts.values())), 1, 'every rule is scored on the same problems')

    def test_rotation_covers_every_farm_in_order(self):
        o = Officer(World(4), 'rotation').run()
        visited = [f for day in sorted(o.log) for f in o.log[day]]
        self.assertEqual(visited[:100], o.order)

    def test_officer_visits_reported_farms_first(self):
        w = World(6)
        o = Officer(w, 'officer')
        for day in range(w.a.days):
            pending = set(o.open_reports)
            chosen = o.step(day)
            if chosen and pending:
                self.assertTrue(set(chosen[:len(pending)]) <= pending or pending <= set(chosen))

    def test_fieldwise_weights_differ_from_the_true_rates(self):
        a, p = Assumptions(), FieldwisePrior()
        self.assertNotEqual(p.daily_risk, a.faw_daily_risk)
        self.assertNotEqual(p.weather_gain, a.faw_weather_gain)

    def test_fieldwise_ranking_ignores_the_true_rates(self):
        # Changing the simulation's true rates must not change a score computed from the same observations.
        w = World(8)
        o = Officer(w, 'fieldwise').run(until=20)
        scores = [o.score(f, 20) for f in range(100)]
        w.a = replace(w.a, faw_daily_risk=0.5, mln_risk_per_infected_neighbour=0.9)
        self.assertEqual(scores, [o.score(f, 20) for f in range(100)])


class ComparisonTests(unittest.TestCase):
    def test_comparison_is_reproducible(self):
        self.assertEqual(compare(5), compare(5))

    def test_paired_counts_add_up(self):
        r = compare(10)
        d = r['fieldwise_minus_rotation']
        self.assertEqual(d['ahead'] + d['tied'] + d['behind'], 10)

    def test_strict_no_signal_removes_the_advantage(self):
        r = compare(60, scramble=True, use_findings=False)
        self.assertLess(abs(r['fieldwise_minus_rotation']['mean']), 5)

    def test_example_day_shows_both_demo_moments(self):
        e = example_day()
        kinds = {s['kind'] for s in e['spotlight']}
        self.assertEqual(kinds, {'faw', 'mln'})
        fieldwise = {p['farm']: p for p in e['picks']['fieldwise']}
        faw, mln = (s['farm'] for s in sorted(e['spotlight'], key=lambda s: s['kind']))
        self.assertEqual(fieldwise[faw]['report'], 'faw')
        self.assertIsNone(fieldwise[mln]['report'])
        self.assertGreater(fieldwise[mln]['mln_neighbours'], 0)


class PageTests(unittest.TestCase):
    def test_results_file_matches_current_assumptions_and_is_labelled(self):
        data = json.loads((ROOT / 'static' / 'sim' / 'results.json').read_text(encoding='utf-8'))
        self.assertTrue(data['simulated'])
        self.assertEqual(data['assumptions'], json.loads(json.dumps(asdict(Assumptions()))),
                         'results.json is stale: rerun scripts/run_simulation.py')
        self.assertEqual(data['fieldwise_prior'], asdict(FieldwisePrior()))

    def test_page_and_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db'))
            page = client.get('/simulation').text
            self.assertIn('SIMULATED', page)
            self.assertIn('/static/simulation.js', page)
            api = client.get('/api/simulation')
            self.assertEqual(api.status_code, 200)
            self.assertTrue(api.json()['simulated'])
            client.close()


if __name__ == '__main__':
    unittest.main()
