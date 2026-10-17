import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from fieldwise.app import create_app

PHONE = '+265999123456'
KEY = 'test-gateway-key'


class UssdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db, ussd_key_value=KEY))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def dial(self, text):
        body = urlencode({'sessionId': 'ATUid_test', 'serviceCode': '*384*1#', 'phoneNumber': PHONE, 'networkCode': '65001', 'text': text})
        response = self.client.post(f'/ussd?key={KEY}', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.startswith(('CON ', 'END ')), response.text)
        self.assertLessEqual(len(response.text), 182, 'USSD screens must fit 182 characters')
        return response.text

    def farm(self, fid='F014'):
        return next(f for f in self.client.get('/api/felix/dashboard').json()['farms'] if f['id'] == fid)

    def test_full_check_in_updates_score_and_answers_queued_survey(self):
        survey = self.client.post('/api/felix/farms/F014/surveys').json()['survey']
        self.assertIn(survey['question'], self.dial('14*1'))
        self.dial('14*1*1'); self.dial('14*1*1*2')
        self.assertTrue(self.dial('14*1*1*2*2').startswith('END Thank you'))
        farm = self.farm()
        self.assertEqual(farm['report'], 'Concern reported')
        self.assertEqual([s['status'] for s in farm['surveys']], ['answered'])
        self.assertEqual(farm['surveys'][0]['id'], survey['id'])

    def test_no_answer_ends_after_one_question(self):
        self.assertTrue(self.dial('27*1*2').startswith('END'))
        self.assertEqual(self.farm('F027')['report'], 'Conditions normal')

    def test_declining_saves_nothing(self):
        self.assertIn('Nothing was saved', self.dial('14*2'))
        self.assertIsNone(self.farm()['report'])

    def test_bad_input(self):
        self.assertIn('not found', self.dial('99'))
        self.assertIn('not found', self.dial('abc'))
        self.assertIn('1, 2 or 3', self.dial('14*1*7'))

    def test_phone_number_is_never_stored(self):
        self.dial('14*1*1*1')
        db = sqlite3.connect(self.db)
        try:
            for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                for row in db.execute(f'SELECT * FROM {table}'):
                    self.assertNotIn('999123456', ' '.join(map(str, row)), table)
        finally:
            db.close()

    def test_simulator_page_served(self):
        self.assertIn('Africa’s Talking', self.client.get('/ussd-simulator').text)



class UssdFuzzTests(unittest.TestCase):
    """The gateway shows whatever /ussd returns, so it must always be a CON or END screen."""

    def test_malformed_input_never_errors(self):
        import random
        rng = random.Random(42)
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=KEY), raise_server_exceptions=False)
            samples = ['14*1*1*1*1*1', '14*1*2*1*1', '14*1*1*2*2*2', '14*1' + '*1' * 50, '1' * 500, '*' * 30, '14**', '14*1*', '14*1*abc',
                       '14*1*-1', '14*1*4', '٣*١', '14*1*1\n*2', '%00', 'F014*1*1*1', '0014*1*2', '99999999999999999999*1']
            alphabet = '0123456789**#x '
            samples += [''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 40))) for _ in range(300)]
            for text in samples:
                body = urlencode({'sessionId': 'f', 'serviceCode': '*384#', 'phoneNumber': PHONE, 'text': text})
                r = client.post(f'/ussd?key={KEY}', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                self.assertEqual(r.status_code, 200, text)
                self.assertTrue(r.text.startswith(('CON ', 'END ')), (text, r.text))
                self.assertLessEqual(len(r.text), 182, text)
            client.close()

    def test_answers_past_the_branch_end_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=KEY))
            body = urlencode({'sessionId': 'f', 'serviceCode': '*384#', 'phoneNumber': PHONE, 'text': '14*1*1*1*1*1'})
            r = client.post(f'/ussd?key={KEY}', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertTrue(r.text.startswith('END Too many answers'))
            client.close()



class UssdGatewayTests(unittest.TestCase):
    """Only the registered gateway may submit answers, and the simulator needs an officer."""

    def post(self, client, url, text='', service='*384#'):
        body = urlencode({'sessionId': 'g', 'serviceCode': service, 'phoneNumber': PHONE, 'text': text})
        return client.post(url, content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})

    def test_callback_is_off_without_a_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=''))
            self.assertEqual(self.post(client, '/ussd').status_code, 404)
            client.close()

    def test_wrong_or_missing_key_is_refused_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=KEY))
            self.assertEqual(self.post(client, '/ussd', '14*1*2').status_code, 403)
            self.assertEqual(self.post(client, '/ussd?key=guess', '14*1*2').status_code, 403)
            farm = next(f for f in client.get('/api/felix/dashboard').json()['farms'] if f['id'] == 'F014')
            self.assertIsNone(farm['report'])
            client.close()

    def test_unregistered_service_code_is_refused(self):
        import os
        os.environ['FIELDWISE_USSD_CODE'] = '*384*7#'
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=KEY))
                self.assertIn('not registered', self.post(client, f'/ussd?key={KEY}', '', '*999#').text)
                self.assertTrue(self.post(client, f'/ussd?key={KEY}', '', '*384*7#').text.startswith('CON'))
                client.close()
        finally:
            del os.environ['FIELDWISE_USSD_CODE']

    def test_simulator_route_needs_an_officer_when_a_pin_is_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', officer_pin_value='4821', ussd_key_value=''))
            self.assertEqual(self.post(client, '/api/ussd/simulate').status_code, 401)
            client.headers['X-Officer-Token'] = client.post('/api/session', json={'pin': '4821'}).json()['officer_token']
            self.assertTrue(self.post(client, '/api/ussd/simulate').text.startswith('CON'))
            client.close()


    def test_key_in_a_header_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', ussd_key_value=KEY))
            body = urlencode({'sessionId': 'h', 'serviceCode': '*384#', 'phoneNumber': PHONE, 'text': ''})
            r = client.post('/ussd', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded', 'X-Fieldwise-Ussd-Key': KEY})
            self.assertTrue(r.text.startswith('CON'))
            client.close()


class AccessLogRedactionTests(unittest.TestCase):
    def test_uvicorn_access_lines_never_contain_the_key(self):
        import logging
        from fieldwise.ussd import RedactUssdKey
        with tempfile.TemporaryDirectory() as tmp:
            create_app(Path(tmp) / 'test.db', ussd_key_value=KEY)
        self.assertTrue(any(isinstance(f, RedactUssdKey) for f in logging.getLogger('uvicorn.access').filters))
        # Same shape as uvicorn's access log record.
        record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s - "%s %s HTTP/%s" %d',
                                   ('127.0.0.1:5000', 'POST', f'/ussd?key={KEY}&x=1', '1.1', 200), None)
        RedactUssdKey().filter(record)
        line = record.getMessage()
        self.assertNotIn(KEY, line)
        self.assertIn('/ussd?key=[REDACTED]&x=1', line)


if __name__ == '__main__':
    unittest.main()
