from pathlib import Path
from datetime import date, datetime, timezone
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import compare, prioritize, yield_at_stake
from .storage import Store
from .weather import demo_weather, fetch_forecast
from .planning import plan_visits
from .felix import register_felix
from .impact import summarize
from .auth import officer_pin, register_auth
from .disease import CATALOG, condition_for_crop, local_monitoring, combined_priority, fetch_reference, demo_reference

ROOT = Path(__file__).resolve().parents[1]


class Reply(BaseModel):
    reply: Literal['1', '2', '3']


class DiseaseChoice(BaseModel):
    disease_id: Literal['grey_leaf_spot', 'tar_spot', 'frogeye_leaf_spot', 'white_mould']


class DiseaseObservation(DiseaseChoice):
    status: Literal['symptoms', 'none', 'uncertain']
    notes: str = Field(default='', max_length=500)


class AlertReview(BaseModel):
    state: Literal['acknowledged', 'resolved']


def create_app(db_path=None, officer_pin_value=None, ussd_key_value=None):
    app = FastAPI(title='Fieldwise local prototype')
    store = Store(db_path or ROOT / 'data' / 'fieldwise.db')
    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    app.state.ussd_key = ussd_key_value   # None: read FIELDWISE_USSD_KEY
    register_felix(app, store, ROOT)

    @app.middleware('http')
    async def offline_replay(request: Request, call_next):
        """Outbox writes carry an Idempotency-Key, so a replay after a lost response is not saved twice."""
        key = request.headers.get('idempotency-key')
        if request.method not in ('POST', 'PATCH', 'DELETE') or not key:
            return await call_next(request)
        key = key[:100]
        if (previous := store.replayed(key)):
            return Response(previous[1], status_code=previous[0], media_type='application/json',
                            headers={'X-Fieldwise-Replay': 'duplicate-ignored'})
        response = await call_next(request)
        body = b''.join([chunk async for chunk in response.body_iterator])
        # Refusals (no session, rate limited) are not results; the replay must be allowed to succeed later.
        if response.status_code < 500 and response.status_code not in (401, 403, 429):
            store.remember(key, response.status_code, body)
        queued_at = request.headers.get('x-fieldwise-queued-at')
        if queued_at and response.status_code < 400:
            try: delay = (datetime.now(timezone.utc) - datetime.fromisoformat(queued_at.replace('Z', '+00:00'))).total_seconds()
            except ValueError: delay = None
            store.record_impact('offline_sync', 'kasungu' if request.url.path.startswith('/api/felix') else 'sa',
                                request.url.path.rsplit('/', 1)[-1], max(delay, 0) if delay is not None else None)
        return Response(body, status_code=response.status_code, media_type=response.media_type,
                        headers={k: v for k, v in response.headers.items() if k.lower() != 'content-length'})

    @app.get('/simulation')
    def simulation_page(): return FileResponse(ROOT / 'static' / 'simulation.html')

    @app.get('/api/simulation')
    def simulation_results():
        # Precomputed by scripts/run_simulation.py (seeded, about a minute) so the page loads instantly and offline.
        path = ROOT / 'static' / 'sim' / 'results.json'
        if not path.exists():
            raise HTTPException(404, 'No simulation results yet. Run scripts/run_simulation.py.')
        return FileResponse(path, media_type='application/json')

    @app.get('/pilot')
    def pilot(): return FileResponse(ROOT / 'static' / 'pilot.html')

    @app.get('/ussd-simulator')
    def ussd_simulator(): return FileResponse(ROOT / 'static' / 'phone.html')

    register_auth(app, officer_pin(officer_pin_value))

    @app.get('/impact')
    def impact_index(): return FileResponse(ROOT / 'static' / 'impact.html')

    @app.get('/sw.js')
    def service_worker():
        # Served from the root so its scope covers every page, not just /static/.
        return FileResponse(ROOT / 'static' / 'sw.js', media_type='text/javascript',
                            headers={'Cache-Control': 'no-cache', 'Service-Worker-Allowed': '/'})

    @app.post('/api/demo/reset')
    def demo_reset():
        store.reset_demo()
        app.state.felix_reset()
        # The impact log stays append-only; metrics count from the newest reset marker.
        store.record_impact('demo_reset', 'all', 'demo_reset', None)
        return {'status': 'reset', 'kept': 'Live evidence receipts, disease reference cache and the impact log history'}

    @app.get('/api/impact')
    def impact(): return summarize(store.impact_events())

    @app.get('/api/impact/export.csv')
    def impact_export():
        rows = ['id,kind,workspace,detail,value,created_at'] + [
            ','.join('' if e[k] is None else str(e[k]).replace(',', ';') for k in ('id','kind','workspace','detail','value','created_at'))
            for e in store.impact_events()]
        return PlainTextResponse('\n'.join(rows) + '\n', media_type='text/csv',
                                 headers={'Content-Disposition': 'attachment; filename="fieldwise-impact.csv"'})

    @app.get('/felix')
    def felix_index(): return FileResponse(ROOT / 'static' / 'felix.html')

    def get_farm(fid):
        try: return store.get_farm(fid)
        except KeyError: raise HTTPException(404, 'Farm not found')

    def evaluate(farm):
        weather = farm.get('weather')
        rows = weather['rows'] if weather else demo_weather()
        scenarios = compare(farm, rows)
        selected = 'interrupted' if farm['reply'] in ('2', '3') else 'working'
        water_priority = prioritize(scenarios[selected], farm['reply'])
        alerts = store.disease_alerts(farm['id'])
        return dict(farm, scenarios=scenarios, selected_scenario=selected, yield_estimate=yield_at_stake(farm, scenarios, rows),
                    water_priority=water_priority, priority=combined_priority(water_priority, alerts),
                    disease=local_monitoring(farm, alerts),
                    weather_source=weather['source'] if weather else 'Synthetic dry-spell demo',
                    weather_fetched_at=weather['fetched_at'] if weather else None,
                    window={'start': rows[0]['date'], 'end': rows[-1]['date'], 'days': len(rows)})

    @app.get('/')
    def index(): return FileResponse(ROOT / 'static' / 'index.html')

    @app.get('/api/health')
    def health(): return {'status':'ok', 'mode':'local', 'sms_delivery':'disabled'}

    @app.get('/api/dashboard')
    def dashboard():
        farms = sorted([evaluate(f) for f in store.farms()], key=lambda f: -f['priority']['score'])
        return {'demo':True, 'farms':farms, 'activity':store.activity(),
                'disease_catalog':CATALOG, 'disease_alerts':store.disease_alerts(),
                'assumptions':['Fictional farms; uncalibrated soil and starting moisture.',
                    'Mature maize held at fixed crop coefficient 1.1 and root depth over the scenario window.',
                    'Working irrigation: 30 mm every 4 days, 85% efficiency; interruption starts on window day 1.',
                    'Wind defaults to 2 m/s; minimum humidity estimated from temperature by pyfao56.',
                    'Forecasts and synthetic weather are not measured farm conditions.'],
                'engine':'pyfao56', 'authorship':'Local prototype — no shared-account authentication required'}

    @app.post('/api/farms/{fid}/reply')
    def reply(fid: str, body: Reply):
        before = evaluate(get_farm(fid))['priority']['score']
        label = {'1':'Irrigation working', '2':'Irrigation interrupted', '3':'No irrigation / rainfed'}[body.reply]
        stopped = body.reply in ('2', '3')
        # Count maize at risk once per interruption: a repeat report adds nothing until irrigation works again.
        newly_at_risk = stopped and not get_farm(fid).get('maize_risk_logged')
        farm = store.update(fid, {'reply':body.reply, 'maize_risk_logged':stopped}, 'reply', 'Simulated farmer reply: ' + label)
        store.record_impact('farmer_signal', 'sa', 'sms_reply', 1)
        after = evaluate(farm)
        store.record_impact('priority_shift', 'sa', 'sms_reply', after['priority']['score'] - before)
        if newly_at_risk:
            # A farmer reporting no working irrigation reveals the interrupted-scenario loss as maize at risk.
            store.record_impact('maize_at_risk', 'sa', 'sms_reply', after['yield_estimate']['at_stake_kg'])
        return {'status':'recorded', 'label':label}

    @app.post('/api/farms/{fid}/outreach')
    def outreach(fid: str):
        farm = get_farm(fid)
        text = f"Fieldwise: Is irrigation working on your maize plot at {farm['name']}? Reply 1 yes, 2 no, 3 no irrigation."
        store.update(fid, {}, 'outreach', text)
        return {'delivery':'local_draft', 'text':text}

    @app.post('/api/farms/{fid}/weather')
    def refresh_weather(fid: str):
        farm = get_farm(fid)
        try: weather = fetch_forecast(farm['latitude'], farm['longitude'])
        except Exception: raise HTTPException(502, 'Open-Meteo unavailable or invalid response. Existing weather was preserved; retry later.')
        store.update(fid, {'weather':weather}, 'weather', 'Loaded 7-day Open-Meteo forecast.')
        return {'status':'updated', 'source':weather['source']}

    @app.delete('/api/farms/{fid}/weather')
    def reset_weather(fid: str):
        get_farm(fid)
        store.update(fid, {'weather':None}, 'weather', 'Switched to synthetic 14-day demo weather.')
        return {'status':'demo_restored'}

    @app.get('/api/route')
    def route(minutes: int = Query(240, ge=20, le=480)):
        farms = [evaluate(f) for f in store.farms()]
        return plan_visits([dict(f, score=f['priority']['score']) for f in farms], minutes)

    def supported_condition(fid, disease_id):
        farm = get_farm(fid)
        try: return farm, condition_for_crop(disease_id, farm['crop'])
        except ValueError as error: raise HTTPException(422, str(error))

    @app.post('/api/farms/{fid}/disease-observations')
    def disease_observation(fid: str, body: DiseaseObservation):
        farm, disease = supported_condition(fid, body.disease_id)
        observation = store.record_disease_observation(fid, disease, body.status, body.notes.strip())
        store.record_impact('farmer_signal', 'sa', 'disease_observation', 1)
        return {'status':'recorded', 'observation':observation, 'notification':'local_officer_queue'}

    @app.post('/api/farms/{fid}/disease-outreach')
    def disease_outreach(fid: str, body: DiseaseChoice):
        farm, disease = supported_condition(fid, body.disease_id)
        text = f"Fieldwise: Have you noticed unusual leaf spots on maize at {farm['name']}? Reply 1 symptoms noticed, 2 none noticed, 3 unsure. Officer review for {disease['name']}; this question does not diagnose disease."
        store.update(fid, {}, 'disease_outreach', text)
        return {'delivery':'local_draft', 'text':text}

    @app.get('/api/disease/alerts')
    def disease_alerts(): return {'alerts':store.disease_alerts(), 'delivery':'local_officer_queue'}

    @app.patch('/api/disease/alerts/{alert_id}')
    def review_alert(alert_id: int, body: AlertReview):
        try: store.set_disease_alert_state(alert_id, body.state)
        except KeyError: raise HTTPException(404, 'Alert not found')
        except ValueError as error: raise HTTPException(409, str(error))
        return {'status':body.state}

    @app.get('/api/disease/reference/demo')
    def reference_demo(): return demo_reference()

    @app.get('/api/disease/reference')
    def reference_cached(target_date: date, risk_days: int = Query(7, ge=1, le=7)):
        snapshot = store.get_disease_reference(f'{target_date.isoformat()}:{risk_days}')
        age = ((datetime.now(timezone.utc)-datetime.fromisoformat(snapshot['fetched_at'])).total_seconds()
               if snapshot else None)
        return {'status':'cached' if snapshot else 'not_loaded', 'snapshot':snapshot,
                'stale':age is not None and age > 86400}

    @app.post('/api/disease/reference')
    def reference_refresh(target_date: date, risk_days: int = Query(7, ge=1, le=7)):
        try: snapshot = fetch_reference(target_date, risk_days)
        except Exception:
            raise HTTPException(502, 'UW forecast service unavailable or response invalid. Existing reference cache was preserved. Use the labelled offline sample or retry later.')
        store.save_disease_reference(f'{target_date.isoformat()}:{risk_days}', snapshot)
        return {'status':'updated', 'snapshot':snapshot, 'stale':False}

    return app


app = create_app()
