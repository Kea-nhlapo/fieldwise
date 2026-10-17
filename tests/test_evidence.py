import json
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient
from fieldwise.app import create_app


def weather_payload(rain=(12, 12, 12)):
    today = datetime.now(timezone(timedelta(hours=2))).date()
    return {'latitude':-13.04, 'longitude':33.49, 'timezone':'Africa/Blantyre',
            'utc_offset_seconds':7200, 'generationtime_ms':2.1,
            'daily_units':{'time':'iso8601', 'precipitation_sum':'mm', 'temperature_2m_max':'°C'},
            'daily':{'time':[(today+timedelta(days=i)).isoformat() for i in range(3)],
                     'precipitation_sum':list(rain), 'temperature_2m_max':[30, 31, 32]}}


def soil_payload(value=400):
    return {'type':'Feature', 'geometry':{'type':'Point', 'coordinates':[33.4885,-13.0368]},
            'properties':{'layers':[{'name':'clay',
              'unit_measure':{'d_factor':10, 'mapped_units':'g/kg', 'target_units':'%'},
              'depths':[{'label':'0-5cm', 'values':{'mean':value}}]}]}}


def remote_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    response.encoding = 'utf-8'
    return response


class EvidenceFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def farm(self, fid='F014'):
        return next(f for f in self.client.get('/api/felix/dashboard').json()['farms'] if f['id']==fid)

    def refresh(self, source, payload, fid='F014', status=200):
        with patch('requests.get', return_value=remote_response(payload,status)), patch('requests.post', return_value=remote_response(payload,status)):
            return self.client.post(f'/api/felix/farms/{fid}/evidence/{source}')

    def test_map_uses_identified_post_and_paces_repeat_requests(self):
        payload={'elements':[{'type':'way','tags':{'highway':'primary'},
                             'geometry':[{'lat':-13.04,'lon':33.48},{'lat':-13.03,'lon':33.49}]}]}
        with patch('requests.get', return_value=remote_response({},406)), patch('requests.post', return_value=remote_response(payload)) as remote:
            response=self.client.post('/api/felix/farms/F014/evidence/map')
            self.assertEqual(response.status_code,200)
            self.assertIn('Fieldwise', remote.call_args.kwargs['headers']['User-Agent'])
            self.assertIn('way["highway"]',remote.call_args.kwargs['data']['data'])
            self.assertEqual(response.json()['receipt']['request_method'],'POST')
            self.assertEqual(self.client.post('/api/felix/farms/F014/evidence/map').status_code,429)
            self.assertEqual(remote.call_count,1)

    def test_live_receipt_keeps_time_window_hash_and_exact_provider_response(self):
        payload = weather_payload()
        response = self.refresh('weather', payload)
        self.assertEqual(response.status_code,200)
        receipt = response.json()['receipt']
        self.assertEqual(receipt['http_status'],200)
        self.assertTrue(receipt['success'])
        self.assertIsNotNone(datetime.fromisoformat(receipt['completed_at']).tzinfo)
        self.assertEqual(len(receipt['sha256']),64)
        proof = self.client.get(f"/api/felix/evidence/{receipt['id']}").json()
        self.assertEqual(json.loads(proof['response_text']),payload)
        self.assertEqual(receipt['sha256'],hashlib.sha256(proof['response_text'].encode('utf-8')).hexdigest())
        farm = self.farm()
        self.assertEqual(farm['weather']['mode'],'live_fetch')
        self.assertEqual(farm['weather']['rain_mm'],36)
        self.assertEqual(farm['evidence']['weather']['state'],'current')
        self.assertEqual(farm['risk_profile']['weather_receipt_id'],receipt['id'])
        self.assertFalse(farm['dry_flag'])
        self.assertEqual(self.farm('F043')['weather']['mode'],'bundled_snapshot')

    def test_soil_and_rain_activate_drainage_rule_and_targeted_survey(self):
        self.assertEqual(self.refresh('soil',soil_payload()).status_code,200)
        self.assertEqual(self.refresh('weather',weather_payload()).status_code,200)
        farm=self.farm()
        self.assertEqual(farm['clay_percent'],40)
        self.assertTrue(farm['wet_flag'])
        self.assertEqual(farm['score'],75)
        self.assertEqual(farm['question'],'Is there standing water in your field?')
        self.assertEqual(farm['risk_profile']['environment_points'],75)

    def test_failed_refresh_keeps_last_success_and_shows_failure(self):
        self.assertEqual(self.refresh('weather',weather_payload()).status_code,200)
        before=self.farm()['evidence']['weather']['used_receipt']['id']
        self.assertEqual(self.refresh('weather',{'error':'unavailable'},status=503).status_code,502)
        farm=self.farm()
        self.assertEqual(farm['evidence']['weather']['used_receipt']['id'],before)
        self.assertEqual(farm['evidence']['weather']['last_attempt']['http_status'],503)
        self.assertEqual(farm['weather']['rain_mm'],36)

    def test_invalid_units_and_missing_soil_are_not_zero_or_success(self):
        bad=weather_payload();bad['daily_units']['precipitation_sum']='inch'
        self.assertEqual(self.refresh('weather',bad).status_code,502)
        self.assertEqual(self.refresh('soil',soil_payload(None)).status_code,502)
        farm=self.farm()
        self.assertIsNone(farm['clay_percent'])
        self.assertFalse(farm['wet_flag'])
        self.assertEqual(farm['evidence']['weather']['state'],'bundled')
        self.assertFalse(farm['evidence']['weather']['last_attempt']['success'])

    def test_old_weather_receipt_is_not_relabelled_current(self):
        self.assertEqual(self.refresh('weather',weather_payload()).status_code,200)
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE felix_evidence SET completed_at='2000-01-01T00:00:00+00:00'")
        db.close()
        farm=self.farm()
        self.assertEqual(farm['evidence']['weather']['state'],'stale')
        self.assertIsNone(farm['rain_mm'])
        self.assertIsNone(farm['risk_profile']['weather_receipt_id'])
        self.assertFalse(farm['dry_flag'])

    def test_map_is_context_and_does_not_add_risk_points(self):
        before=self.farm()['score']
        payload={'osm3s':{'timestamp_osm_base':'2026-10-17T00:00:00Z'}, 'elements':[
          {'type':'way','id':1,'tags':{'highway':'primary'},
           'geometry':[{'lat':-13.04,'lon':33.48},{'lat':-13.03,'lon':33.49}]}]}
        response=self.refresh('map',payload)
        self.assertEqual(response.status_code,200)
        data=self.client.get('/api/felix/map').json()
        self.assertEqual(len(data['features']),1)
        self.assertEqual(data['mode'],'live_fetch')
        self.assertEqual(self.farm()['score'],before)
        self.assertFalse(self.farm()['evidence']['map']['used_in_score'])

    def test_partial_map_response_with_timeout_remark_is_not_success(self):
        payload={'remark':'runtime error: Query timed out', 'elements':[
          {'type':'way','tags':{'highway':'primary'},
           'geometry':[{'lat':-13.04,'lon':33.48},{'lat':-13.03,'lon':33.49}]}]}
        self.assertEqual(self.refresh('map',payload).status_code,502)
        self.assertEqual(self.client.get('/api/felix/map').json()['mode'],'bundled_snapshot')

    def test_only_public_coordinates_leave_and_soil_calls_are_paced(self):
        with patch('requests.get', return_value=remote_response(soil_payload())) as remote:
            result=self.client.post('/api/felix/farms/F014/evidence/soil')
            self.assertEqual(result.status_code,200)
            params=remote.call_args.kwargs['params']
            self.assertEqual(set(params),{'lon','lat','property','depth','value'})
            self.assertEqual(self.client.post('/api/felix/farms/F043/evidence/soil').status_code,429)
            self.assertEqual(remote.call_count,1)
        with patch('requests.get',side_effect=AssertionError('Unexpected network call')):
            self.assertEqual(self.client.get('/api/felix/dashboard').status_code,200)

    def test_survey_requires_choice_preserves_trigger_and_shows_before_after(self):
        response=self.client.post('/api/felix/farms/F014/surveys')
        self.assertEqual(response.status_code,200)
        survey=response.json()['survey']
        self.assertEqual(survey['delivery'],'local_draft')
        body={'answers':[1,1],'survey_id':survey['id']}
        self.assertEqual(self.client.post('/api/felix/farms/F014/check-in',json=body).status_code,422)
        body['consent']=True
        result=self.client.post('/api/felix/farms/F014/check-in',json=body)
        self.assertEqual(result.status_code,200)
        saved=self.farm()['surveys'][0]
        self.assertEqual(saved['before']['score'],62)
        self.assertEqual(saved['after']['score'],117)
        self.assertEqual(saved['status'],'answered')
        self.assertTrue(saved['consented_at'])
        self.assertEqual(self.client.post('/api/felix/farms/F014/check-in',json=body).status_code,409)

    def test_export_and_delete_remove_only_selected_farm_reports(self):
        self.client.post('/api/felix/farms/F014/check-in',json={'answers':[1,1],'consent':True})
        self.client.post('/api/felix/farms/F043/check-in',json={'answers':[1,1],'consent':True})
        exported=self.client.get('/api/felix/farms/F014/privacy-export')
        self.assertEqual(exported.status_code,200)
        self.assertEqual(exported.json()['farm']['id'],'F014')
        self.assertEqual(exported.json()['activity'][0]['kind'],'check_in')
        self.assertEqual(self.client.delete('/api/felix/farms/F014/reports').status_code,200)
        self.assertIsNone(self.farm()['report'])
        self.assertEqual(self.farm()['surveys'],[])
        self.assertEqual(self.farm('F043')['report'],'Concern reported')
        self.assertEqual(len(self.client.get('/api/dashboard').json()['farms']),5)
