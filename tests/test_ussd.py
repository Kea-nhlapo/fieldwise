import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from fieldwise.app import create_app

PHONE = '+265999123456'


class UssdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def dial(self, text):
        body = urlencode({'sessionId': 'ATUid_test', 'serviceCode': '*384*1#', 'phoneNumber': PHONE, 'networkCode': '65001', 'text': text})
        response = self.client.post('/ussd', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
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
            client = TestClient(create_app(Path(tmp) / 'test.db'), raise_server_exceptions=False)
            samples = ['14*1*1*1*1*1', '14*1*2*1*1', '14*1*1*2*2*2', '14*1' + '*1' * 50, '1' * 500, '*' * 30, '14**', '14*1*', '14*1*abc',
                       '14*1*-1', '14*1*4', '٣*١', '14*1*1\n*2', '%00', 'F014*1*1*1', '0014*1*2', '99999999999999999999*1']
            alphabet = '0123456789**#x '
            samples += [''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 40))) for _ in range(300)]
            for text in samples:
                body = urlencode({'sessionId': 'f', 'serviceCode': '*384#', 'phoneNumber': PHONE, 'text': text})
                r = client.post('/ussd', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                self.assertEqual(r.status_code, 200, text)
                self.assertTrue(r.text.startswith(('CON ', 'END ')), (text, r.text))
                self.assertLessEqual(len(r.text), 182, text)
            client.close()

    def test_answers_past_the_branch_end_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(Path(tmp) / 'test.db'))
            body = urlencode({'sessionId': 'f', 'serviceCode': '*384#', 'phoneNumber': PHONE, 'text': '14*1*1*1*1*1'})
            r = client.post('/ussd', content=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            self.assertTrue(r.text.startswith('END Too many answers'))
            client.close()


if __name__ == '__main__':
    unittest.main()
