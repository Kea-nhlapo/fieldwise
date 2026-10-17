import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


def provider_payload(value=.74, label='3.High'):
    return {'features': [{'station': {'station_id': 7, 'station_name': 'Test Wisconsin station',
              'state': 'WI', 'coordinates': {'latitude': 43.3, 'longitude': -89.5}},
              'timeseries': [{'date': '2026-07-15', 'data': [
                  {'fieldname':'gls_risk', 'value':value},
                  {'fieldname':'gls_risk_class', 'value':label}]}]}]}


class DiseaseAdapterTests(unittest.TestCase):
    def test_provider_classes_missing_values_and_inactive_are_distinct(self):
        from fieldwise.disease import normalize_reference
        for value, label, expected_value, expected_class in [
            (.74, '3.High', .74, 'High'), (-1, 'Inactive', None, 'Inactive'),
            (None, '1.Low', None, 'Unknown'), (float('nan'), 'Low', None, 'Unknown'),
            (3.5, 'High', None, 'Unknown'), (0, '1.Low', 0, 'Low')]:
            with self.subTest(value=value):
                records = normalize_reference(provider_payload(value, label))
                gls = next(r for r in records if r['disease_id'] == 'grey_leaf_spot')
                self.assertEqual(gls['risk'], expected_value)
                self.assertEqual(gls['risk_class'], expected_class)
                tar = next(r for r in records if r['disease_id'] == 'tar_spot')
                self.assertIsNone(tar['risk'])
                self.assertEqual(tar['risk_class'], 'Unknown')

    def test_bad_payload_and_duplicate_days_are_rejected(self):
        from fieldwise.disease import normalize_reference
        duplicate = provider_payload()
        duplicate['features'][0]['timeseries'] *= 2
        for bad in ({'error':'unavailable'}, {'features':[]}, duplicate):
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                normalize_reference(bad)

    def test_live_adapter_shifts_target_date_and_preserves_scope(self):
        from fieldwise.disease import fetch_reference
        def remote(url, params, **kwargs):
            self.assertEqual(params, {'forecasting_date':'2026-07-14', 'risk_days':1})
            class Response:
                def raise_for_status(self): pass
                def json(self): return provider_payload()
            return Response()
        with patch('fieldwise.disease.requests.get', side_effect=remote):
            snapshot = fetch_reference(date(2026,7,15), 1)
        self.assertFalse(snapshot['applicable_to_local_farms'])
        self.assertFalse(snapshot['synthetic'])
        self.assertEqual(snapshot['target_date'], '2026-07-15')
        self.assertEqual(snapshot['records'][0]['date'], '2026-07-15')


class DiseaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from fieldwise.app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def farm(self, fid='ubuntu'):
        return next(f for f in self.client.get('/api/dashboard').json()['farms'] if f['id'] == fid)

    def observe(self, status='symptoms', disease='grey_leaf_spot', fid='ubuntu'):
        return self.client.post(f'/api/farms/{fid}/disease-observations',
             json={'disease_id':disease, 'status':status, 'notes':'Demo observation'})

    def test_old_farms_have_unknown_disease_risk_not_zero(self):
        before = self.farm()
        self.assertEqual(before['priority']['score'], before['water_priority']['score'])
        for item in before['disease']['conditions']:
            self.assertIsNone(item['risk'])
            self.assertEqual(item['assessment'], 'Not assessed')

    def test_observation_creates_persistent_alert_and_increases_priority(self):
        from fieldwise.storage import Store
        before = self.farm()
        self.assertEqual(self.observe().status_code, 200)
        after = self.farm()
        self.assertEqual(after['water_priority'], before['water_priority'])
        self.assertEqual(after['priority']['score'], 80)
        self.assertEqual(after['scenarios'], before['scenarios'])
        self.assertEqual(Store(self.db).get_farm('ubuntu')['disease_observations']['grey_leaf_spot']['status'], 'symptoms')
        alerts = self.client.get('/api/disease/alerts').json()['alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['state'], 'open')
        self.assertIsNone(after['disease']['conditions'][0]['risk'])

    def test_repeat_reports_deduplicate_and_negative_report_does_not_close_alert(self):
        self.observe()
        self.observe()
        self.observe('none')
        alerts = self.client.get('/api/disease/alerts').json()['alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['state'], 'open')
        self.assertEqual(self.farm()['priority']['score'], 80)

    def test_acknowledge_resolve_and_reopen_lifecycle(self):
        self.observe()
        alert = self.client.get('/api/disease/alerts').json()['alerts'][0]
        endpoint = f"/api/disease/alerts/{alert['id']}"
        self.assertEqual(self.client.patch(endpoint, json={'state':'acknowledged'}).status_code, 200)
        self.assertEqual(self.farm()['priority']['score'], 80)
        self.assertEqual(self.client.patch(endpoint, json={'state':'resolved'}).status_code, 200)
        farm = self.farm()
        self.assertEqual(farm['priority']['score'], farm['water_priority']['score'])
        self.observe()
        alerts = self.client.get('/api/disease/alerts').json()['alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['state'], 'open')

    def test_invalid_crop_disease_and_status_do_not_write(self):
        self.assertEqual(self.observe(disease='frogeye_leaf_spot').status_code, 422)
        self.assertEqual(self.observe(status='diagnosed').status_code, 422)
        self.assertEqual(self.observe(fid='absent').status_code, 404)
        self.assertEqual(self.client.get('/api/disease/alerts').json()['alerts'], [])
        self.assertEqual(self.client.get('/api/dashboard').json()['activity'], [])

    def test_uncertain_report_is_watch_and_draft_does_not_send(self):
        self.observe('uncertain')
        self.assertEqual(self.farm()['priority']['score'], 50)
        response = self.client.post('/api/farms/ubuntu/disease-outreach',json={'disease_id':'tar_spot'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['delivery'], 'local_draft')

    def test_reference_fetch_failure_preserves_previous_snapshot(self):
        from fieldwise.disease import normalize_reference
        snapshot = {'target_date':'2026-07-15','risk_days':1,'records':normalize_reference(provider_payload()),
                    'fetched_at':'2026-07-15T00:00:00+00:00','synthetic':False,
                    'applicable_to_local_farms':False,'source':'UW-Madison','region':'Wisconsin, USA'}
        endpoint = '/api/disease/reference?target_date=2026-07-15&risk_days=1'
        with patch('fieldwise.app.fetch_reference', return_value=snapshot):
            self.assertEqual(self.client.post(endpoint).status_code, 200)
        before = self.farm()['priority']
        with patch('fieldwise.app.fetch_reference', side_effect=ValueError('bad upstream data')):
            self.assertEqual(self.client.post(endpoint).status_code, 502)
        cached = self.client.get(endpoint).json()
        self.assertEqual(cached['snapshot']['records'], snapshot['records'])
        self.assertTrue(cached['stale'])
        self.assertEqual(self.farm()['priority'], before)
        self.assertEqual(self.client.get('/api/disease/alerts').json()['alerts'], [])

    def test_offline_sample_is_explicit_and_never_creates_local_alerts(self):
        sample = self.client.get('/api/disease/reference/demo').json()
        self.assertTrue(sample['synthetic'])
        self.assertFalse(sample['applicable_to_local_farms'])
        self.assertGreater(len(sample['records']), 0)
        self.assertEqual(self.client.get('/api/disease/alerts').json()['alerts'], [])

    def test_route_uses_combined_score(self):
        self.observe()
        with patch('fieldwise.app.plan_visits', side_effect=lambda farms, minutes: {'seen':farms}) as solver:
            result = self.client.get('/api/route').json()
        ubuntu = next(f for f in result['seen'] if f['id']=='ubuntu')
        self.assertEqual(ubuntu['score'], 80)


if __name__ == '__main__':
    unittest.main()
