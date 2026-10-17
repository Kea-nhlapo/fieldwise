import math
import tempfile
import unittest
from pathlib import Path


class WaterBalanceTests(unittest.TestCase):
    def test_irrigation_interruption_increases_depletion_and_priority(self):
        from fieldwise.engine import compare, prioritize
        from fieldwise.storage import DEMO_FARMS
        from fieldwise.weather import demo_weather
        farm = DEMO_FARMS[0]
        result = compare(farm, demo_weather())
        wet, dry = result['working'], result['interrupted']
        self.assertGreater(dry[-1]['depletion_mm'], wet[-1]['depletion_mm'] + 15)
        self.assertGreater(prioritize(dry, '2')['score'], prioritize(wet, '1')['score'])
        for series in (wet, dry):
            for day in series:
                self.assertTrue(math.isfinite(day['depletion_mm']))
                self.assertGreaterEqual(day['ks'], 0)
                self.assertLessEqual(day['ks'], 1)
                self.assertLessEqual(day['depletion_mm'], day['taw_mm'] + 0.01)

    def test_invalid_soil_is_rejected(self):
        from fieldwise.engine import compare
        from fieldwise.storage import DEMO_FARMS
        from fieldwise.weather import demo_weather
        farm = dict(DEMO_FARMS[0], theta_wp=0.4)
        with self.assertRaises(ValueError):
            compare(farm, demo_weather())

    def test_weather_rejects_gaps_missing_and_negative_values(self):
        from fieldwise.weather import validate_weather, demo_weather
        for mutation in ('missing', 'negative', 'gap', 'nan'):
            rows = demo_weather()
            if mutation == 'missing': rows[0]['et0_mm'] = None
            if mutation == 'negative': rows[0]['rain_mm'] = -1
            if mutation == 'gap': rows.pop(2)
            if mutation == 'nan': rows[0]['et0_mm'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_weather(rows)


class RoutingTests(unittest.TestCase):
    def test_route_respects_shift_including_service_and_return(self):
        from fieldwise.planning import plan_visits
        farms = [{'id': str(i), 'name': str(i), 'score': score, 'visit_minutes': 30}
                 for i, score in enumerate([100, 30, 5])]
        matrix = [[0, 10, 10, 10], [10, 0, 10, 10], [10, 10, 0, 10], [10, 10, 10, 0]]
        route = plan_visits(farms, 55, matrix)
        self.assertEqual([x['id'] for x in route['visits']], ['0'])
        self.assertEqual(route['total_minutes'], 50)
        self.assertEqual(set(route['deferred']), {'1', '2'})

    def test_impossible_day_defers_everyone(self):
        from fieldwise.planning import plan_visits
        route = plan_visits([{'id':'a','name':'A','score':90,'visit_minutes':40}], 20, [[0,10],[10,0]])
        self.assertEqual(route['visits'], [])
        self.assertEqual(route['deferred'], ['a'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from fieldwise.app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_reply_changes_priority_and_persists(self):
        from fieldwise.storage import Store
        before = self.client.get('/api/dashboard').json()
        farm = next(f for f in before['farms'] if f['id'] == 'makhaya')
        response = self.client.post('/api/farms/makhaya/reply', json={'reply':'2'})
        self.assertEqual(response.status_code, 200)
        after = self.client.get('/api/dashboard').json()
        changed = next(f for f in after['farms'] if f['id'] == 'makhaya')
        self.assertGreater(changed['priority']['score'], farm['priority']['score'])
        self.assertEqual(Store(self.db).get_farm('makhaya')['reply'], '2')
        self.assertEqual(len(after['activity']), 1)

    def test_invalid_reply_and_unknown_farm_do_not_mutate(self):
        self.assertEqual(self.client.post('/api/farms/makhaya/reply', json={'reply':'9'}).status_code, 422)
        self.assertEqual(self.client.post('/api/farms/absent/reply', json={'reply':'2'}).status_code, 404)
        self.assertEqual(self.client.get('/api/dashboard').json()['activity'], [])

    def test_outreach_only_records_a_local_draft(self):
        response = self.client.post('/api/farms/makhaya/outreach')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['delivery'], 'local_draft')
        self.assertIn('Reply 1', response.json()['text'])

    def test_dashboard_and_route_are_usable(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        result = self.client.get('/api/dashboard').json()
        self.assertEqual(len(result['farms']), 5)
        self.assertTrue(result['demo'])
        route = self.client.get('/api/route?minutes=120').json()
        self.assertLessEqual(route['total_minutes'], 120)
        self.assertEqual(self.client.get('/api/route?minutes=-1').status_code, 422)


if __name__ == '__main__':
    unittest.main()
