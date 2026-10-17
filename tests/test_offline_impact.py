import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from fieldwise.app import create_app


class OfflineAndImpactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def metrics(self):
        response = self.client.get('/api/impact')
        self.assertEqual(response.status_code, 200)
        return {m['id']: m for m in response.json()['metrics']}, response.json()

    def test_empty_log_reports_no_data_rather_than_zero_rates(self):
        metrics, body = self.metrics()
        self.assertIsNone(body['tracking_since'])
        self.assertEqual(metrics['farmer_signals']['value'], 0)
        self.assertIsNone(metrics['survey_response']['value'])
        self.assertIsNone(metrics['time_to_action']['value'])

    def test_kasungu_flow_feeds_every_officer_metric(self):
        survey = self.client.post('/api/felix/farms/F014/surveys').json()['survey']
        self.assertEqual(self.client.post('/api/felix/farms/F014/check-in',
                         json={'answers': [1, 2, 2], 'consent': True, 'survey_id': survey['id']}).status_code, 200)
        self.client.post('/api/felix/farms/F014/correction', json={'decision': 'More urgent', 'notes': ''})
        self.assertEqual(self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Checked wilting'}).status_code, 200)
        metrics, body = self.metrics()
        self.assertEqual(metrics['farmer_signals']['value'], 1)
        self.assertEqual((metrics['survey_response']['numerator'], metrics['survey_response']['denominator']), (1, 1))
        self.assertEqual(metrics['decisions_changed']['value'], 100)
        self.assertGreater(metrics['mean_shift']['value'], 0)
        self.assertEqual(metrics['officer_overrides']['value'], 1)
        self.assertEqual(metrics['targeted_visits']['value'], 100)
        self.assertIsNotNone(metrics['time_to_action']['value'])
        self.assertEqual(body['daily'][0]['visits'], 1)

    def test_impact_log_holds_no_farm_identifiers_and_survives_erasure(self):
        self.client.post('/api/felix/farms/F014/check-in', json={'answers': [1, 2, 2], 'consent': True})
        self.client.delete('/api/felix/farms/F014/reports')
        metrics, body = self.metrics()
        self.assertEqual(metrics['erasures']['value'], 1)
        self.assertEqual(metrics['farmer_signals']['value'], 1)
        for event in body['recent']:
            self.assertNotIn('farm_id', event)
            self.assertNotIn('F014', str(event['detail']))

    def test_south_africa_reply_logs_signal_and_priority_shift(self):
        self.client.post('/api/farms/makhaya/reply', json={'reply': '2'})
        metrics, _ = self.metrics()
        self.assertEqual(metrics['farmer_signals']['value'], 1)
        self.assertEqual(metrics['decisions_changed']['denominator'], 1)

    def test_replayed_offline_write_is_saved_once_and_logs_sync_delay(self):
        queued = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        headers = {'Idempotency-Key': 'outbox-123', 'X-Fieldwise-Queued-At': queued}
        first = self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Captured offline'}, headers=headers)
        second = self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Captured offline'}, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(second.headers['X-Fieldwise-Replay'], 'duplicate-ignored')
        log = self.client.get('/api/felix/farms/F014/privacy-export').json()['activity']
        self.assertEqual(sum(a['kind'] == 'visit' for a in log), 1)
        metrics, _ = self.metrics()
        self.assertEqual(metrics['offline_synced']['value'], 1)
        self.assertAlmostEqual(metrics['offline_delay']['value'], 30, delta=1)

    def test_rejected_offline_write_is_not_counted_as_synced(self):
        response = self.client.post('/api/felix/farms/F014/visit', json={'notes': ''},
                                    headers={'Idempotency-Key': 'bad-1', 'X-Fieldwise-Queued-At': datetime.now(timezone.utc).isoformat()})
        self.assertEqual(response.status_code, 422)
        metrics, _ = self.metrics()
        self.assertEqual(metrics['offline_synced']['value'], 0)

    def test_offline_shell_assets_are_served(self):
        sw = self.client.get('/sw.js')
        self.assertEqual(sw.status_code, 200)
        self.assertEqual(sw.headers['service-worker-allowed'], '/')
        shell = [line.strip(" ',") for line in sw.text.split('const SHELL = [')[1].split('];')[0].replace('\n', ' ').split(',')]
        paths = [p.strip().strip("'") for p in shell if p.strip().strip("'")]
        self.assertEqual(len(paths), len(set(paths)), 'cache.addAll rejects duplicate requests, which breaks offline install')
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(self.client.get('/static/manifest.webmanifest').status_code, 200)
        csv = self.client.get('/api/impact/export.csv')
        self.assertTrue(csv.text.startswith('id,kind,workspace,detail,value,created_at'))

    def test_pages_have_accessibility_landmarks(self):
        for page in ('/', '/felix', '/impact'):
            html = self.client.get(page).text
            self.assertIn('class="skip-link" href="#main-content"', html, page)
            self.assertIn('id="main-content"', html, page)
            self.assertIn('/static/offline.js', html, page)
            self.assertIn('rel="manifest"', html, page)
            self.assertIn('<nav aria-label=', html, page)



class DemoResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_reset_clears_demo_state_and_restarts_metrics_without_deleting_log(self):
        self.client.post('/api/farms/makhaya/reply', json={'reply': '2'})
        self.client.post('/api/felix/farms/F014/check-in', json={'answers': [1, 2, 2], 'consent': True})
        self.assertEqual(self.client.post('/api/demo/reset').status_code, 200)
        felix = self.client.get('/api/felix/dashboard').json()
        self.assertEqual(felix['activity'], [])
        self.assertFalse(any(f['concern_open'] or f['surveys'] for f in felix['farms']))
        makhaya = next(f for f in self.client.get('/api/dashboard').json()['farms'] if f['id'] == 'makhaya')
        self.assertEqual(makhaya['reply'], 'unknown')
        impact = self.client.get('/api/impact').json()
        self.assertEqual(next(m for m in impact['metrics'] if m['id'] == 'farmer_signals')['value'], 0)
        self.assertIsNotNone(impact['reset_at'])
        csv = self.client.get('/api/impact/export.csv').text
        self.assertIn('farmer_signal', csv)
        self.assertIn('demo_reset', csv)


if __name__ == '__main__':
    unittest.main()


class YieldEstimateTests(unittest.TestCase):
    def test_fao33_loss_formula_and_at_risk_metric(self):
        from fieldwise.engine import yield_loss
        series = [{'ks': 0.5}, {'ks': 1.0}]
        rows = [{'et0_mm': 6.0}, {'et0_mm': 6.0}]
        # deficit = (1-0.5)*1.1*6 = 3.3 mm; loss = 1.25*3.3/600 = 0.6875%; 6000 kg/ha -> 41 kg
        self.assertEqual(yield_loss({}, series, rows), {'deficit_mm': 3.3, 'loss_pct': 0.7, 'loss_kg': 41})
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db'))
            farm = next(f for f in client.get('/api/dashboard').json()['farms'] if f['id'] == 'makhaya')
            y = farm['yield_estimate']
            self.assertEqual(y['at_stake_kg'], y['interrupted']['loss_kg'] - y['working']['loss_kg'])
            client.post('/api/farms/makhaya/reply', json={'reply': '1'})
            client.post('/api/farms/makhaya/reply', json={'reply': '2'})
            metric = next(m for m in client.get('/api/impact').json()['metrics'] if m['id'] == 'maize_at_risk')
            self.assertEqual(metric['numerator'], 1, 'only replies that reveal stopped irrigation count')
            self.assertGreater(metric['value'], 0)
            client.close()


class MaizeAtRiskCountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def at_risk(self):
        m = next(m for m in self.client.get('/api/impact').json()['metrics'] if m['id'] == 'maize_at_risk')
        return m['numerator'], m['value']

    def test_repeat_report_counts_once_and_new_episode_counts_again(self):
        self.client.post('/api/farms/siyakhula/reply', json={'reply': '2'})
        first = self.at_risk()
        self.client.post('/api/farms/siyakhula/reply', json={'reply': '2'})
        self.client.post('/api/farms/siyakhula/reply', json={'reply': '3'})
        self.assertEqual(self.at_risk(), first, 'repeat reports must not add the same field again')
        self.client.post('/api/farms/siyakhula/reply', json={'reply': '1'})
        self.client.post('/api/farms/siyakhula/reply', json={'reply': '2'})
        self.assertEqual(self.at_risk()[0], 2, 'a new interruption after irrigation worked again counts')


class ConcurrencyTests(unittest.TestCase):
    def test_reset_commits_while_another_request_is_reading(self):
        # Regression: a dashboard read held open while scoring farms made the demo reset fail with
        # 'database is locked' after a 10 s wait. WAL lets the write commit alongside the read.
        import sqlite3
        import time
        from fieldwise.storage import Store
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.db'
            store = Store(path)
            reader = sqlite3.connect(path)
            try:
                reader.execute('BEGIN')
                reader.execute('SELECT * FROM farms').fetchall()   # read transaction stays open
                started = time.time()
                store.reset_demo()
                self.assertLess(time.time() - started, 2)
            finally:
                reader.close()
