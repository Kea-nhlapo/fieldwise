import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from fieldwise.app import create_app

PIN = '4821'


class OfficerPinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db', officer_pin_value=PIN, ussd_key_value='gw'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def sign_in(self, pin=PIN):
        return self.client.post('/api/session', json={'pin': pin})

    def test_writes_and_farmer_records_need_a_session(self):
        for method, path, body in [('post', '/api/felix/farms/F014/visit', {'notes': 'x'}), ('post', '/api/farms/makhaya/reply', {'reply': '2'}),
                                   ('post', '/api/demo/reset', None), ('delete', '/api/felix/farms/F014/reports', None)]:
            r = getattr(self.client, method)(path, **({'json': body} if body else {}))
            self.assertEqual(r.status_code, 401, path)
            self.assertEqual(r.json()['auth'], 'required')
        for path in ['/api/felix/dashboard', '/api/dashboard', '/api/felix/farms/F014/privacy-export']:
            self.assertEqual(self.client.get(path).status_code, 401, path)

    def test_public_and_aggregate_reads_stay_open(self):
        for path in ['/api/health', '/api/impact', '/api/simulation', '/api/felix/map', '/api/session', '/felix', '/static/app.js']:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_ussd_callback_stays_open(self):
        body = urlencode({'sessionId': 's', 'serviceCode': '*384#', 'phoneNumber': '+254700000000', 'text': ''})
        r = self.client.post('/ussd?key=gw', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.text.startswith('CON'))

    def test_wrong_pin_is_refused_and_right_pin_signs_in(self):
        self.assertEqual(self.sign_in('0000').status_code, 401)
        r = self.sign_in()
        self.assertEqual(r.status_code, 200)
        self.assertIn('httponly', r.headers['set-cookie'].lower())
        self.assertTrue(self.client.get('/api/session').json()['signed_in'])
        self.assertEqual(self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Checked'}).status_code, 200)
        self.client.delete('/api/session')
        self.assertEqual(self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Again'}).status_code, 401)

    def test_repeated_wrong_pins_lock_sign_in(self):
        for _ in range(5):
            self.sign_in('1111')
        self.assertEqual(self.sign_in().status_code, 429, 'even the right PIN waits during lockout')

    def test_refused_offline_replay_can_succeed_after_sign_in(self):
        headers = {'Idempotency-Key': 'outbox-auth-1'}
        self.assertEqual(self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Offline'}, headers=headers).status_code, 401)
        self.sign_in()
        r = self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Offline'}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('X-Fieldwise-Replay', r.headers)


class NoPinTests(unittest.TestCase):
    def test_without_a_pin_the_app_is_open_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', officer_pin_value=''))
            self.assertEqual(client.get('/api/session').json(), {'auth_enabled': False, 'signed_in': False})
            self.assertEqual(client.post('/api/farms/makhaya/reply', json={'reply': '1'}).status_code, 200)
            client.close()



class RecordCachingTests(unittest.TestCase):
    def test_farmer_records_are_not_stored_by_the_browser_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db', officer_pin_value=PIN))
            client.post('/api/session', json={'pin': PIN})
            self.assertEqual(client.get('/api/felix/dashboard').headers.get('cache-control'), 'no-store')
            self.assertNotEqual(client.get('/api/impact').headers.get('cache-control'), 'no-store')
            client.close()

    def test_service_worker_and_server_agree_on_which_reads_are_open(self):
        import re
        from fieldwise.auth import OPEN_READS
        root = Path(__file__).resolve().parents[1] / 'static'
        for name in ('sw.js', 'offline.js'):
            listed = re.search(r"const OPEN_READS = \[([^\]]+)\]", (root / name).read_text(encoding='utf-8')).group(1)
            self.assertEqual(tuple(re.findall(r"'([^']+)'", listed)), OPEN_READS, name)


if __name__ == '__main__':
    unittest.main()
