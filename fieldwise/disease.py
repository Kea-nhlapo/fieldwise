"""Disease reference forecasts and local observation triage are separate.

UW field names/date semantics: UW-Madison-DSI/llm-ag-forecasting-app,
features/config.py and features/api.py. No disease model is run locally.
"""
import math
import re
from datetime import date, datetime, timedelta, timezone
import requests

API_URL = 'https://connect.doit.wisc.edu/ag_forecasting_api/v2/ag_models_wrappers/wisconet_g'
CATALOG = [
    {'id':'grey_leaf_spot', 'name':'Grey leaf spot', 'crop':'Maize',
     'risk_field':'gls_risk', 'class_field':'gls_risk_class'},
    {'id':'tar_spot', 'name':'Tar spot', 'crop':'Maize',
     'risk_field':'tarspot_risk', 'class_field':'tarspot_risk_class'},
    {'id':'frogeye_leaf_spot', 'name':'Frogeye leaf spot', 'crop':'Soybean',
     'risk_field':'fe_risk', 'class_field':'fe_risk_class'},
    {'id':'white_mould', 'name':'White mould (non-irrigated)', 'crop':'Soybean',
     'risk_field':'whitemold_nirr_risk', 'class_field':'whitemold_nirr_risk_class'},
]


def condition_for_crop(disease_id, crop):
    for disease in CATALOG:
        if disease['id'] == disease_id and disease['crop'].casefold() == crop.casefold():
            return disease
    raise ValueError('This disease is not in the monitoring catalogue for this crop.')


def local_monitoring(farm, alerts):
    observations = farm.get('disease_observations', {})
    conditions = []
    for disease in CATALOG:
        if disease['crop'].casefold() != farm['crop'].casefold(): continue
        conditions.append({'id':disease['id'], 'name':disease['name'], 'risk':None,
                           'assessment':'Not assessed',
                           'observation':observations.get(disease['id']),
                           'alert':next((a for a in alerts if a['disease_id']==disease['id']), None)})
    return {'conditions':conditions, 'model_status':'No locally validated disease model connected',
            'applicable_reference_forecasts':False}


def combined_priority(water, alerts):
    active = [a for a in alerts if a['state'] != 'resolved']
    floor = max((a['priority_floor'] for a in active), default=0)
    score = max(water['score'], floor)
    reason = water['reason']
    if active:
        reason += f' {len(active)} unresolved disease-observation alert(s); inspection priority floor {floor}. This is not a diagnosis.'
    return dict(water, score=score, label='Urgent' if score>=70 else 'Watch' if score>=40 else 'Routine',
                reason=reason, disease_alert_count=len(active), water_score=water['score'])


def normalize_reference(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        raise ValueError('Unexpected UW forecast response.')
    records, seen = [], set()
    for feature in payload['features']:
        station = feature['station']
        station_id = str(station['station_id'])
        coordinates = station.get('coordinates') or {}
        for item in feature.get('timeseries', []):
            day = date.fromisoformat(item.get('date') or item['forecasting_date']).isoformat()
            if (station_id, day) in seen: raise ValueError('Duplicate station/date in provider response.')
            seen.add((station_id, day))
            fields = {entry['fieldname']:entry['value'] for entry in item.get('data', [])}
            for disease in CATALOG:
                raw = fields.get(disease['risk_field'])
                label = re.sub(r'^\s*\d+[.\-:)]\s*', '', str(fields.get(disease['class_field']) or '')).strip().title()
                try: risk = float(raw) if not isinstance(raw, bool) else None
                except (TypeError, ValueError): risk = None
                if risk == -1 or label == 'Inactive':
                    risk, label = None, 'Inactive'
                elif risk is None or not math.isfinite(risk) or not 0 <= risk <= 1:
                    risk, label = None, 'Unknown'
                elif label not in ('Low', 'Moderate', 'High', 'No Risk'):
                    label = 'Unknown'
                records.append({'station_id':station_id,
                    'station_name':str(station.get('station_name') or station_id)[:200],
                    'region':'Wisconsin, USA', 'latitude':coordinates.get('latitude'),
                    'longitude':coordinates.get('longitude'), 'date':day,
                    'disease_id':disease['id'], 'risk':risk, 'risk_class':label})
    if not records: raise ValueError('Provider returned no station forecasts.')
    return sorted(records, key=lambda r:(r['station_id'], r['date'], r['disease_id']))


def fetch_reference(target_date, risk_days):
    if not 1 <= risk_days <= 7: raise ValueError('Forecast horizon must be 1–7 days.')
    query_date = target_date - timedelta(days=1)
    response = requests.get(API_URL,
        params={'forecasting_date':query_date.isoformat(), 'risk_days':risk_days},
        headers={'accept':'application/json'}, timeout=25)
    response.raise_for_status()
    records = normalize_reference(response.json())
    end = target_date + timedelta(days=risk_days-1)
    if any(not target_date <= date.fromisoformat(r['date']) <= end for r in records):
        raise ValueError('Provider dates do not match the requested forecast window.')
    return {'source':'UW–Madison Agricultural Forecasting API', 'source_url':API_URL,
            'region':'Wisconsin, USA', 'target_date':target_date.isoformat(),
            'model_run_date':query_date.isoformat(), 'risk_days':risk_days,
            'fetched_at':datetime.now(timezone.utc).isoformat(), 'synthetic':False,
            'applicable_to_local_farms':False, 'records':records}


def demo_reference():
    start = date(2026,7,15)
    records = []
    curves = [[.12,.18,.23,.31,.46,.62,.71], [.22,.27,.30,.26,.20,.14,.10],
              [None,None,-1,-1,-1,-1,-1]]
    for number, curve in enumerate(curves, 1):
        for disease in CATALOG:
            for offset, risk in enumerate(curve):
                label = 'Unknown' if risk is None else 'Inactive' if risk == -1 else 'High' if risk>=.6 else 'Moderate' if risk>=.2 else 'Low'
                records.append({'station_id':f'demo-{number}', 'station_name':f'Illustrative station {number}',
                    'region':'Fictional Wisconsin-style sample', 'latitude':None, 'longitude':None,
                    'date':(start+timedelta(days=offset)).isoformat(), 'disease_id':disease['id'],
                    'risk':None if risk == -1 else risk, 'risk_class':label})
    return {'source':'Synthetic interface sample — not UW model output', 'region':'Illustrative only',
            'target_date':start.isoformat(), 'risk_days':7, 'fetched_at':None, 'synthetic':True,
            'applicable_to_local_farms':False, 'records':records}
