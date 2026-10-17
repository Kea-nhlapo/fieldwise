import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from fieldwise.app import create_app
from fieldwise import learning


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.tmp.name) / 'test.db'))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def dashboard(self):
        return self.client.get('/api/felix/dashboard').json()

    def test_no_visits_means_rules_decide_alone(self):
        data = self.dashboard()
        self.assertTrue(all(f['risk_profile']['learning_points'] == 0 for f in data['farms']))
        self.assertTrue(all(s['visits'] == 0 and s['prior'] == s['posterior'] for s in data['learning'].values()))

    def test_confirmed_visit_raises_signal_rate_and_scores(self):
        before = {f['id']: f['score'] for f in self.dashboard()['farms']}
        response = self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Wilting confirmed.', 'outcomes': ['wilting']})
        self.assertEqual(response.status_code, 200)
        data = self.dashboard()
        dry = data['learning']['dry']
        self.assertEqual((dry['visits'], dry['confirmed']), (1, 1))
        self.assertGreater(dry['posterior'], dry['prior'])
        dry_farms = [f for f in data['farms'] if f['dry_flag'] and not f['completed']]
        self.assertTrue(dry_farms)
        for farm in dry_farms:
            self.assertGreater(farm['risk_profile']['learning_points'], 0)
            self.assertGreater(farm['score'], before[farm['id']])

    def test_advice_only_visit_is_not_a_label(self):
        self.client.post('/api/felix/farms/F014/visit', json={'notes': 'Advised.', 'outcomes': ['advice']})
        self.assertTrue(all(s['visits'] == 0 for s in self.dashboard()['learning'].values()))

    def test_survey_targets_rank_by_decision_change(self):
        targets = self.dashboard()['survey_targets']
        self.assertEqual(len(targets), 8)
        self.assertEqual(targets, sorted(targets, key=lambda t: (-t['decision_change'], -t['expected_movement'], t['rank_now'])))
        for t in targets:
            self.assertLessEqual(t['rank_if_yes'], t['rank_now'])
            self.assertGreaterEqual(t['rank_if_no'], t['rank_now'])
        self.client.post('/api/felix/farms/F014/check-in', json={'answers': [2], 'consent': True})
        self.assertNotIn('F014', [t['id'] for t in self.dashboard()['survey_targets']])

    def test_reset_clears_learning(self):
        self.client.post('/api/felix/farms/F014/visit', json={'notes': 'x', 'outcomes': ['none']})
        self.client.post('/api/demo/reset')
        self.assertTrue(all(s['visits'] == 0 for s in self.dashboard()['learning'].values()))

    def test_adjustment_is_capped(self):
        learned = {s: {'prior': .1, 'posterior': .99, 'visits': 50, 'confirmed': 49, 'label': s} for s in learning.PRIORS}
        self.assertEqual(learning.adjustment(['dry', 'wet', 'concern'], learned)[0], learning.MAX_ADJUST)


if __name__ == '__main__':
    unittest.main()


class RetentionTests(unittest.TestCase):
    def test_old_answers_are_purged_but_open_concerns_kept(self):
        import json, sqlite3, os
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'test.db'
            client = TestClient(create_app(db_path))
            client.post('/api/felix/farms/F014/check-in', json={'answers': [2], 'consent': True})
            client.post('/api/felix/farms/F027/check-in', json={'answers': [1, 2, 2], 'consent': True})
            db = sqlite3.connect(db_path)
            try:
                old = '2020-01-01T00:00:00+00:00'
                for sid, payload in db.execute('SELECT id, payload FROM felix_surveys').fetchall():
                    db.execute('UPDATE felix_surveys SET payload=? WHERE id=?', (json.dumps(dict(json.loads(payload), created_at=old)), sid))
                for fid, payload in db.execute('SELECT id, payload FROM felix_farms').fetchall():
                    farm = json.loads(payload)
                    if farm.get('reported_at'):
                        db.execute('UPDATE felix_farms SET payload=? WHERE id=?', (json.dumps(dict(farm, reported_at=old)), fid))
                db.execute('UPDATE felix_activity SET created_at=?', (old,))
                db.commit()
            finally:
                db.close()
            result = client.post('/api/felix/retention/run').json()
            self.assertEqual((result['retention_days'], result['surveys_deleted']), (180, 2))
            farms = {f['id']: f for f in client.get('/api/felix/dashboard').json()['farms']}
            self.assertIsNone(farms['F014']['report'])
            self.assertEqual(farms['F027']['report'], 'Concern reported', 'open concern stays until reviewed')
            self.assertEqual(client.get('/api/felix/dashboard').json()['activity'], [])
            client.close()
