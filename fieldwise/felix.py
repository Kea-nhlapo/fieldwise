"""Browser adaptation of Tshego's Felix workflow. See TSHEGO-INTEGRATION.md.

Rules and farm data originate in the supplied Flutter felix_app.dart.
Kasungu scenario scores are illustrative and never enter the maize model.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints, model_validator
from .evidence import Evidence
from . import learning
from .ussd import register_ussd


Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Choice = Annotated[int, Field(strict=True, ge=1, le=3)]


class CheckIn(BaseModel):
    answers: list[Choice] = Field(min_length=1, max_length=3)
    consent: bool = Field(default=False, strict=True)
    survey_id: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def complete_branch(self):
        if not self.consent:
            raise ValueError('Choose to participate after reading the demo privacy notice.')
        expected = 1 if self.answers[0] == 2 else (2 if len(self.answers) > 1 and self.answers[1] == 1 else 3)
        if len(self.answers) != expected:
            raise ValueError('Complete the check-in branch without extra answers.')
        return self


class Correction(BaseModel):
    decision: Literal['More urgent', 'Call instead', 'Already checked', 'Different action', 'Reset']
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ''

    @model_validator(mode='after')
    def custom_action_requires_note(self):
        if self.decision == 'Different action' and not self.notes:
            raise ValueError('Describe the different action.')
        return self


class PlanChoice(BaseModel):
    planned: bool = Field(strict=True)


class Visit(BaseModel):
    notes: Note
    outcomes: list[Literal['wilting', 'water', 'pests', 'none', 'advice', 'followup']] = Field(default=[], max_length=6)


def assess(farm, weather, soil=None, learned=None):
    """Port of _Farm score/action/why/success, with persistent concern review."""
    available = weather['rain_mm'] is not None and weather['heat_c'] is not None
    dry = available and weather['rain_mm'] < 3 and weather['heat_c'] >= 30
    clay = soil['clay_percent'] if soil else None
    wet = available and weather['mode'] == 'live_fetch' and clay is not None and clay >= 35 and weather['rain_mm'] >= 25
    concern = farm.get('concern_open', False)
    normal = farm.get('report') == 'Conditions normal'
    override = farm.get('override')
    completed = farm.get('completed', False)
    base = 75 if wet else 62 if dry else 25
    report_points = 55 if concern else -15 if normal else 0
    officer_points = 30 if override == 'More urgent' else -20 if override == 'Call instead' else 0
    signals = learning.active_signals({'dry_flag': dry, 'wet_flag': wet, 'concern_open': concern})
    learning_points, learning_basis = learning.adjustment(signals, learned) if learned else (0, [])
    score = base + report_points + officer_points + learning_points
    if completed:
        score = 0
    status = ('Completed' if completed else 'Call today' if override == 'Call instead'
              else 'Visit today' if score >= 75 else 'Watch' if score >= 55 else 'Routine')
    action = ('Call farmer' if override == 'Call instead' else farm.get('note')
              if override == 'Different action' else 'Check drainage' if wet else 'Check water stress' if dry
              else 'Follow up report' if concern else 'Routine follow-up')
    basis = 'Fetched forecast' if weather['mode'] == 'live_fetch' else 'Bundled demonstration outlook'
    why = ('An unreviewed farmer concern needs Felix to confirm the conditions.' if concern else
           'Forecast rain and mapped clay suggest checking drainage; neither proves waterlogging.' if wet else
           f'{basis}: hot weather and little rain suggest checking for water stress.' if dry else
           'Current weather evidence is missing or stale. Routine points are a scheduling baseline, not low risk.' if not available else
           'No weather threshold crossed; this does not confirm healthy crops.')
    success = ('Record drainage and standing water before and after the forecast rain.' if wet else
               'Record visible stress and available water, then check again after action.' if dry else
               'Record the crop condition and date of the next follow-up.')
    return dict(farm, score=score, status=status, action=action, why=why, success=success,
                dry_flag=dry, wet_flag=wet, clay_percent=clay, weather=weather,
                rain_mm=weather['rain_mm'], heat_c=weather['heat_c'],
                question='Is there standing water in your field?' if wet else 'Are plants wilting during the day?' if dry else 'Have you noticed a new crop problem?',
                risk_profile={'rule_version':'felix-v2', 'evaluated_at':datetime.now(timezone.utc).isoformat(),
                  'basis':weather['mode'], 'environment_points':base, 'report_points':report_points,
                  'officer_points':officer_points, 'learning_points':learning_points, 'learning_basis':learning_basis,
                  'completion_adjustment':-(base+report_points+officer_points+learning_points) if completed else 0,
                  'water_stress':'Flagged for checking' if dry else 'Threshold not crossed' if available else 'Unknown',
                  'drainage':'Flagged for checking' if wet else 'Threshold not crossed' if clay is not None and weather['mode']=='live_fetch' else 'Unknown',
                  'confidence':'Illustrative rules; uncalibrated, requires officer review'})


def register_felix(app, store, root):
    assets = root / 'static' / 'tshego'
    snapshot = json.loads((assets / 'kasungu_weather.json').read_text(encoding='utf-8-sig'))
    days = snapshot['daily'][:3]
    weather = {'mode':'bundled_snapshot', 'start':days[0]['date'][:10], 'end':days[-1]['date'][:10],
               'rain_mm':sum(d['precipitation_sum'] for d in days),
               'heat_c':max(d['temperature_2m_max'] for d in days),
               'location':snapshot['location'], 'timezone':'UTC (source snapshot)',
               'source':'Tshego’s bundled Open-Meteo snapshot; not a current forecast',
               'soil_source':'Unknown until a successful soil retrieval'}
    farms = json.loads((assets / 'farms.json').read_text(encoding='utf-8-sig'))
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS felix_farms (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS felix_activity
                   (id INTEGER PRIMARY KEY, farm_id TEXT, kind TEXT, text TEXT, created_at TEXT)''')
        db.execute('CREATE TABLE IF NOT EXISTS felix_surveys (id INTEGER PRIMARY KEY, farm_id TEXT, payload TEXT NOT NULL)')
        learning.ensure_table(db)
        for farm in farms:
            farm.update(report=None, answers=[], completed=False, planned=False, concern_open=False,
                        override=None, note='', visit_notes='', reported_at=None)
            db.execute('INSERT OR IGNORE INTO felix_farms VALUES (?,?)', (farm['id'], json.dumps(farm)))

    def reset():
        """Clear Kasungu reports, surveys and visits. Live evidence receipts are kept as the offline cache."""
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for farm in json.loads((assets / 'farms.json').read_text(encoding='utf-8-sig')):
                farm.update(report=None, answers=[], completed=False, planned=False, concern_open=False,
                            override=None, note='', visit_notes='', reported_at=None)
                db.execute('INSERT OR REPLACE INTO felix_farms VALUES (?,?)', (farm['id'], json.dumps(farm)))
            db.execute('DELETE FROM felix_surveys')
            db.execute('DELETE FROM felix_activity')
            db.execute('DELETE FROM felix_outcomes')
    app.state.felix_reset = reset

    router = APIRouter(prefix='/api/felix', tags=['Tshego / Kasungu demo'])
    evidence = Evidence(store, assets)

    def learned_now():
        with store.connect() as db:
            return learning.stats(db)

    def evaluate(farm, learned=None):
        contexts = {source:evidence.context(farm['id'], source) for source in ('weather','soil','map')}
        weather_context = contexts['weather']
        selected_weather = weather_context['normalized'] or (dict(weather, mode='unavailable', rain_mm=None, heat_c=None)
                            if weather_context['state']=='stale' else weather)
        result = assess(farm, selected_weather, contexts['soil']['normalized'], learned or learned_now())
        result['evidence'] = {source:{k:v for k,v in context.items() if k!='normalized'} for source,context in contexts.items()}
        result['risk_profile']['weather_receipt_id'] = weather_context['used_receipt']['id'] if weather_context['used_receipt'] else None
        result['risk_profile']['soil_receipt_id'] = contexts['soil']['used_receipt']['id'] if contexts['soil']['used_receipt'] else None
        result['evidence']['soil']['used_in_score'] = contexts['soil']['state']=='current' and weather_context['state']=='current'
        return result

    def raw_farm(fid, db):
        row = db.execute('SELECT payload FROM felix_farms WHERE id=?', (fid,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Kasungu farm not found')
        return json.loads(row[0])

    def summary(farm, db):
        evaluated = evaluate(farm)
        ranked = sorted([evaluate(json.loads(r[0])) for r in db.execute('SELECT payload FROM felix_farms')
                         if json.loads(r[0])['id'] != farm['id']] + [evaluated], key=lambda f:(-f['score'],f['id']))
        return {k:evaluated[k] for k in ('score','status','action','risk_profile')} | {'rank':next(i+1 for i,f in enumerate(ranked) if f['id']==farm['id'])}

    def new_survey(farm, db):
        evaluated = evaluate(farm)
        survey = {'farm_id':farm['id'], 'created_at':datetime.now(timezone.utc).isoformat(),
                  'delivery':'local_draft', 'status':'queued', 'notice_version':'fieldwise-demo-v1',
                  'question':evaluated['question'], 'trigger':evaluated['why'], 'before':summary(farm,db),
                  'consented_at':None, 'responded_at':None, 'answers':None, 'after':None}
        cursor = db.execute('INSERT INTO felix_surveys (farm_id,payload) VALUES (?,?)', (farm['id'],json.dumps(survey)))
        survey['id'] = cursor.lastrowid
        db.execute('UPDATE felix_surveys SET payload=? WHERE id=?', (json.dumps(survey),survey['id']))
        store.record_impact('survey_queued', 'kasungu', 'ussd_invitation', 1, db=db)
        return survey

    def mutate(fid, kind, change):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            farm = raw_farm(fid, db)
            text = change(farm, db)
            now = datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE felix_farms SET payload=? WHERE id=?', (json.dumps(farm), fid))
            db.execute('INSERT INTO felix_activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                       (fid, kind, text, now))
        return {'status':'saved', 'delivery':'local_only', 'farm':evaluate(farm)}

    def purge_expired():
        """Delete farmer answers and activity older than FIELDWISE_RETENTION_DAYS (default 180)."""
        days = int(os.environ.get('FIELDWISE_RETENTION_DAYS', '180'))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            expired = [(r[0], r[1]) for r in db.execute('SELECT id, payload FROM felix_surveys')
                       if json.loads(r[1])['created_at'] < cutoff]
            for sid, _ in expired:
                db.execute('DELETE FROM felix_surveys WHERE id=?', (sid,))
            db.execute('DELETE FROM felix_activity WHERE created_at < ?', (cutoff,))
            for (fid, payload) in db.execute('SELECT id, payload FROM felix_farms').fetchall():
                farm = json.loads(payload)
                if farm.get('reported_at') and farm['reported_at'] < cutoff and not farm.get('concern_open'):
                    farm.update(report=None, answers=[], answer_summary='', reported_at=None)
                    db.execute('UPDATE felix_farms SET payload=? WHERE id=?', (json.dumps(farm), fid))
        return {'retention_days': days, 'surveys_deleted': len(expired)}
    app.state.felix_purge = purge_expired
    purge_expired()

    @router.post('/retention/run')
    def run_retention():
        return purge_expired()

    @router.get('/dashboard')
    def dashboard():
        with store.connect() as db:
            current = [evaluate(json.loads(r[0])) for r in db.execute('SELECT payload FROM felix_farms')]
            for farm in current:
                farm['surveys'] = [json.loads(row[0]) for row in db.execute('SELECT payload FROM felix_surveys WHERE farm_id=? ORDER BY id DESC', (farm['id'],))]
            activity = [dict(zip(('id','farm_id','kind','text','created_at'), row)) for row in
                        db.execute('SELECT * FROM felix_activity ORDER BY id DESC LIMIT 50')]
        ranked = sorted(current, key=lambda f: (-f['score'], f['id']))
        for rank, farm in enumerate(ranked, 1):
            farm['rank'] = rank
        learned = learned_now()

        def rescore(farm, answer):
            changed = dict(farm, concern_open=True, report='Concern reported') if answer == 'yes' else dict(farm, report='Conditions normal')
            soil = {'clay_percent': farm['clay_percent']} if farm['clay_percent'] is not None else None
            return assess(changed, farm['weather'], soil, learned)['score']
        targets = learning.survey_targets(ranked, rescore, learned)
        return {'farms':ranked, 'weather':weather, 'activity':activity, 'learning':learned, 'survey_targets':targets,
                'visits_per_day':learning.TOP_K,
                'alerts':[f for f in ranked if f['concern_open']],
                'plan':[f for f in ranked if f['planned'] and not f['completed']],
                'demo':True, 'author':'Tshego, supplied ZIP',
                'score_label':'Illustrative triage points, not a percentage or disease probability'}

    @router.post('/farms/{fid}/check-in')
    def check_in(fid: str, body: CheckIn):
        def change(farm, db):
            if body.survey_id:
                row = db.execute('SELECT payload FROM felix_surveys WHERE id=? AND farm_id=?', (body.survey_id,fid)).fetchone()
                if row is None:
                    raise HTTPException(404, 'Survey not found for this farm')
                survey = json.loads(row[0])
                if survey['status'] != 'queued':
                    raise HTTPException(409, 'This survey has already been answered. Queue another survey for a correction.')
            else:
                survey = new_survey(farm, db)
            survey['response_before'] = summary(farm, db)
            concern = body.answers[0] != 2
            farm.update(answers=body.answers, report='Concern reported' if concern else 'Conditions normal',
                        reported_at=datetime.now(timezone.utc).isoformat())
            if concern:
                if farm['completed']:
                    farm.update(completed=False, override=None, note='')
                farm['concern_open'] = True
            labels = [['Yes', 'No', 'Not sure'], ['One area', 'Several areas', 'Not sure'],
                      ['Today', 'More than one day', 'Not sure']]
            farm['answer_summary'] = ' · '.join(labels[i][a-1] for i, a in enumerate(body.answers))
            survey.update(status='answered', consented_at=farm['reported_at'], responded_at=farm['reported_at'],
                          answers=body.answers, after=summary(farm,db))
            db.execute('UPDATE felix_surveys SET payload=? WHERE id=?', (json.dumps(survey),survey['id']))
            store.record_impact('farmer_signal', 'kasungu', 'ussd_check_in', 1, db=db)
            store.record_impact('survey_answered', 'kasungu', 'ussd_check_in', 1, db=db)
            store.record_impact('priority_shift', 'kasungu', 'ussd_check_in',
                                survey['after']['score'] - survey['response_before']['score'], db=db)
            return f"Simulated check-in: {farm['report']}. {farm['answer_summary']}"
        return mutate(fid, 'check_in', change)

    @router.post('/farms/{fid}/correction')
    def correction(fid: str, body: Correction):
        def change(farm, db):
            farm.update(override=None if body.decision == 'Reset' else body.decision, note=body.notes,
                        completed=body.decision == 'Already checked')
            if farm['completed']:
                farm.update(planned=False, concern_open=False)
            store.record_impact('officer_override', 'kasungu', body.decision, 1, db=db)
            return f"Felix changed the recommendation: {body.decision}. {body.notes}"
        return mutate(fid, 'correction', change)

    @router.post('/farms/{fid}/plan')
    def plan(fid: str, body: PlanChoice):
        def change(farm, db):
            if farm['completed'] and body.planned:
                raise HTTPException(409, 'Reopen the completed farm before adding a visit.')
            farm['planned'] = body.planned
            return 'Added to visit shortlist.' if body.planned else 'Removed from visit shortlist.'
        return mutate(fid, 'plan', change)

    @router.post('/farms/{fid}/visit')
    def visit(fid: str, body: Visit):
        def change(farm, db):
            assessed = evaluate(farm)
            status = assessed['status']
            label = learning.label_from_outcomes(body.outcomes)
            if label is not None:
                learning.record(db, learning.active_signals(assessed), label)
            hours = None
            if farm.get('concern_open') and farm.get('reported_at'):
                hours = (datetime.now(timezone.utc) - datetime.fromisoformat(farm['reported_at'])).total_seconds() / 3600
            store.record_impact('visit_recorded', 'kasungu',
                                'targeted' if status in ('Visit today', 'Watch', 'Call today') else 'routine', hours, db=db)
            farm.update(completed=True, concern_open=False, planned=False, visit_notes=body.notes)
            return 'Felix recorded a visit: ' + body.notes
        return mutate(fid, 'visit', change)

    @router.post('/farms/{fid}/evidence/{source}')
    def refresh_evidence(fid: str, source: Literal['weather','soil','map']):
        with store.connect() as db:
            farm = raw_farm(fid, db)
        receipt = evidence.refresh(farm, source)
        store.record_impact('evidence_fetch', 'kasungu', f"{source}:{'ok' if receipt['success'] else 'failed'}", 1)
        return JSONResponse({'receipt':receipt}, status_code=200 if receipt['success'] else 502)

    @router.get('/evidence/{identifier}')
    def receipt(identifier: int):
        return evidence.get_receipt(identifier)

    @router.get('/map')
    def map_data():
        return evidence.map()

    @router.post('/farms/{fid}/surveys')
    def queue_survey(fid: str):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            farm = raw_farm(fid, db)
            survey = new_survey(farm, db)
            db.execute('INSERT INTO felix_activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                       (fid,'survey_draft','Survey invitation queued locally; no telecom delivery.',survey['created_at']))
        return {'survey':survey}

    @router.get('/farms/{fid}/privacy-export')
    def privacy_export(fid: str):
        with store.connect() as db:
            farm = raw_farm(fid, db)
            surveys = [json.loads(row[0]) for row in db.execute('SELECT payload FROM felix_surveys WHERE farm_id=? ORDER BY id', (fid,))]
            activity = [dict(zip(('id','farm_id','kind','text','created_at'), row)) for row in
                        db.execute('SELECT * FROM felix_activity WHERE farm_id=? ORDER BY id', (fid,))]
        return {'farm':farm, 'surveys':surveys, 'activity':activity, 'exported_at':datetime.now(timezone.utc).isoformat(),
                'scope':'Local demo reports only; no phone numbers collected'}

    @router.delete('/farms/{fid}/reports')
    def erase_reports(fid: str):
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            farm = raw_farm(fid, db)
            farm.update(report=None, answers=[], completed=False, planned=False, concern_open=False,
                        override=None, note='', visit_notes='', reported_at=None, answer_summary='')
            db.execute('UPDATE felix_farms SET payload=? WHERE id=?', (json.dumps(farm),fid))
            db.execute('DELETE FROM felix_surveys WHERE farm_id=?', (fid,))
            db.execute('DELETE FROM felix_activity WHERE farm_id=?', (fid,))
            store.record_impact('erasure', 'kasungu', 'farm_reports', 1, db=db)
        return {'status':'deleted', 'scope':'Selected farm reports, surveys, corrections and visit notes; public evidence retained'}

    def ussd_lookup(fid):
        with store.connect() as db:
            row = db.execute('SELECT payload FROM felix_farms WHERE id=?', (fid,)).fetchone()
            if row is None:
                return None
            farm = json.loads(row[0])
            queued = next((json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM felix_surveys WHERE farm_id=? ORDER BY id DESC', (fid,))
                if json.loads(r[0])['status'] == 'queued'), None)
        question = queued['question'] if queued else evaluate(farm)['question']
        return farm, question, queued['id'] if queued else None

    def ussd_submit(fid, answers, survey_id):
        check_in(fid, CheckIn(answers=answers, consent=True, survey_id=survey_id))
        with store.connect() as db:
            db.execute('INSERT INTO felix_activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                       (fid, 'ussd', 'Answers arrived over USSD after the farmer agreed on the phone. No phone number stored.',
                        datetime.now(timezone.utc).isoformat()))

    register_ussd(app, ussd_lookup, ussd_submit)
    app.include_router(router)
