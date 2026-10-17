import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from fieldwise.app import create_app


class FelixWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def dashboard(self):
        response = self.client.get('/api/felix/dashboard')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def farm(self, fid='F014'):
        return next(f for f in self.dashboard()['farms'] if f['id'] == fid)

    def post(self, action, body, fid='F014'):
        if action == 'check-in':
            body = dict(body, consent=True)
        return self.client.post(f'/api/felix/farms/{fid}/{action}', json=body)

    def test_imported_snapshot_is_dated_and_separate_from_maize_model(self):
        original = self.client.get('/api/dashboard').json()
        result = self.dashboard()
        self.assertEqual(len(result['farms']), 8)
        self.assertEqual(result['weather']['start'], '2026-10-16')
        self.assertEqual(result['weather']['end'], '2026-10-18')
        self.assertEqual(result['weather']['mode'], 'bundled_snapshot')
        farm = self.farm()
        self.assertAlmostEqual(farm['rain_mm'], .9)
        self.assertAlmostEqual(farm['heat_c'], 30.75)
        self.assertEqual(farm['score'], 62)
        self.assertFalse(farm['wet_flag'])
        self.assertIsNone(farm['clay_percent'])
        self.assertEqual(farm['question'], 'Are plants wilting during the day?')
        self.assertEqual(original['farms'], self.client.get('/api/dashboard').json()['farms'])

    def test_concern_changes_ranking_and_survives_restart(self):
        self.assertEqual(self.post('check-in', {'answers':[1, 2, 2]}, 'F043').status_code, 200)
        result = self.dashboard()
        self.assertEqual(result['farms'][0]['id'], 'F043')
        self.assertEqual(result['farms'][0]['score'], 117)
        self.assertEqual(result['farms'][0]['report'], 'Concern reported')
        self.assertEqual(len(result['alerts']), 1)
        with TestClient(create_app(self.db)) as restarted:
            saved = restarted.get('/api/felix/dashboard').json()
        self.assertEqual(saved['farms'][0]['answers'], [1, 2, 2])
        self.assertEqual(saved['activity'][0]['kind'], 'check_in')

    def test_branching_rejects_partial_or_extra_answers_without_writes(self):
        for answers in ([], [1], [3, 2], [2, 1], [1, 1, 3], [4], [True], ['1']):
            with self.subTest(answers=answers):
                self.assertEqual(self.post('check-in', {'answers':answers}).status_code, 422)
        self.assertEqual(self.dashboard()['activity'], [])
        for answers in ([2], [3, 1], [1, 3, 3]):
            self.assertEqual(self.post('check-in', {'answers':answers}).status_code, 200)
        self.assertEqual(self.farm()['report'], 'Concern reported')

    def test_corrections_plan_and_visit_then_new_concern_reopens(self):
        self.assertEqual(self.post('correction', {'decision':'More urgent'}).status_code, 200)
        self.assertEqual(self.farm()['score'], 92)
        self.assertEqual(self.post('plan', {'planned':True}).status_code, 200)
        self.assertEqual(self.dashboard()['plan'][0]['id'], 'F014')
        self.assertEqual(self.post('visit', {'notes':'Checked water supply.'}).status_code, 200)
        self.assertEqual(self.farm()['score'], 0)
        self.assertEqual(self.farm()['status'], 'Completed')
        self.assertEqual(self.dashboard()['plan'], [])
        self.assertEqual(self.post('check-in', {'answers':[1, 1]}).status_code, 200)
        self.assertFalse(self.farm()['completed'])
        self.assertEqual(self.farm()['score'], 117)

    def test_normal_report_preserves_unresolved_concern_until_visit(self):
        self.post('check-in', {'answers':[1, 1]})
        self.post('check-in', {'answers':[2]})
        self.assertEqual(self.farm()['report'], 'Conditions normal')
        self.assertEqual(self.farm()['score'], 117)
        self.assertEqual(len(self.dashboard()['alerts']), 1)
        self.post('visit', {'notes':'Follow-up completed.'})
        self.assertEqual(self.dashboard()['alerts'], [])

    def test_custom_action_validation_and_unknown_farm(self):
        self.assertEqual(self.post('correction', {'decision':'Different action', 'notes':'  '}).status_code, 422)
        self.assertEqual(self.post('correction', {'decision':'Invalid'}).status_code, 422)
        self.assertEqual(self.post('visit', {'notes':' '}).status_code, 422)
        self.assertEqual(self.post('plan', {'planned':True}, 'ubuntu').status_code, 404)
        self.assertEqual(self.post('correction', {'decision':'Different action', 'notes':'Inspect the pump.'}).status_code, 200)
        self.assertEqual(self.farm()['action'], 'Inspect the pump.')

    def test_felix_mutations_do_not_change_south_african_farms_or_log(self):
        before = self.client.get('/api/dashboard').json()
        self.post('check-in', {'answers':[1, 1]})
        self.post('visit', {'notes':'Demo visit'})
        after = self.client.get('/api/dashboard').json()
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
