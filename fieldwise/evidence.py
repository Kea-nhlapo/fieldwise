"""Public environmental data, with persistent request receipts and explicit freshness."""
import hashlib
import json
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone

import requests
from fastapi import HTTPException

SOURCES = {
    'weather': ('Open-Meteo', 'https://api.open-meteo.com/v1/forecast', 21600),
    'soil': ('ISRIC SoilGrids', 'https://rest.isric.org/soilgrids/v2.0/properties/query', 2592000),
    'map': ('OpenStreetMap / Overpass', 'https://overpass-api.de/api/interpreter', 2592000),
}
BOUNDS = [-13.045, 33.482, -13.029, 33.498]


def now():
    return datetime.now(timezone.utc)


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Missing or invalid environmental value.')
    return float(value)


def normalize(source, payload):
    if source == 'weather':
        units = payload['daily_units']
        if units['precipitation_sum'] != 'mm' or units['temperature_2m_max'] != '°C':
            raise ValueError('Unexpected weather units.')
        if payload['timezone'] != 'Africa/Blantyre' or payload['utc_offset_seconds'] != 7200:
            raise ValueError('Unexpected forecast timezone.')
        daily = payload['daily']
        dates = [date.fromisoformat(d) for d in daily['time']]
        today = now().astimezone(timezone(timedelta(hours=2))).date()
        if dates != [today + timedelta(days=i) for i in range(3)]:
            raise ValueError('Forecast must cover today and the following two days.')
        if len(daily['precipitation_sum']) != 3 or len(daily['temperature_2m_max']) != 3:
            raise ValueError('Incomplete three-day forecast.')
        rain = [number(v, 0, 2000) for v in daily['precipitation_sum']]
        heat = [number(v, -90, 65) for v in daily['temperature_2m_max']]
        return {'mode':'live_fetch', 'source':'Open-Meteo forecast (modelled, not observed)',
                'start':dates[0].isoformat(), 'end':dates[-1].isoformat(), 'timezone':'Africa/Blantyre',
                'rain_mm':sum(rain), 'heat_c':max(heat),
                'grid_latitude':number(payload['latitude'], -90, 90),
                'grid_longitude':number(payload['longitude'], -180, 180),
                'model_issued_at':None, 'days':[{'date':d.isoformat(), 'rain_mm':r, 'tmax_c':h}
                                             for d,r,h in zip(dates,rain,heat)]}
    if source == 'soil':
        layer = next(layer for layer in payload['properties']['layers'] if layer['name'] == 'clay')
        unit = layer['unit_measure']
        if unit['mapped_units'] != 'g/kg' or unit['target_units'] != '%' or unit['d_factor'] != 10:
            raise ValueError('Unexpected clay unit conversion.')
        depth = next(d for d in layer['depths'] if d['label'] == '0-5cm')
        return {'clay_percent':number(depth['values']['mean'], 0, 1000) / 10,
                'depth':'0–5 cm', 'resolution':'250 m mapped estimate', 'mapped_at':None,
                'source':'ISRIC SoilGrids; modelled soil property, not a moisture measurement'}
    if payload.get('remark'):
        raise ValueError('Map provider returned a runtime warning or incomplete query.')
    features = []
    for item in payload['elements']:
        if item.get('type') != 'way':
            continue
        tags = item.get('tags', {})
        kind = 'waterway' if 'waterway' in tags else 'highway' if 'highway' in tags else None
        if not kind:
            continue
        points = [[number(p['lat'], -90, 90), number(p['lon'], -180, 180)] for p in item['geometry']]
        if len(points) >= 2:
            features.append({'kind':kind, 'value':str(tags[kind]), 'points':points})
    if not features:
        raise ValueError('No road or waterway geometry returned.')
    return {'bounds':BOUNDS, 'features':features, 'mode':'live_fetch',
            'map_base_at':payload.get('osm3s', {}).get('timestamp_osm_base'),
            'source':'© OpenStreetMap contributors, ODbL; retrieved through Overpass'}


class Evidence:
    def __init__(self, store, assets):
        self.store = store
        self.bundled_map = json.loads((assets / 'kasungu_map.json').read_text(encoding='utf-8-sig'))
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS felix_evidence (
                id INTEGER PRIMARY KEY, farm_id TEXT, source TEXT, attempted_at TEXT,
                completed_at TEXT, success INTEGER DEFAULT 0, http_status INTEGER,
                request_url TEXT, request_params TEXT, response_text TEXT, sha256 TEXT,
                normalized TEXT, error TEXT)''')
            if 'request_method' not in {row[1] for row in db.execute('PRAGMA table_info(felix_evidence)')}:
                db.execute("ALTER TABLE felix_evidence ADD COLUMN request_method TEXT NOT NULL DEFAULT 'GET'")

    @staticmethod
    def receipt(row, full=False):
        if row is None:
            return None
        result = dict(row)
        result['success'] = bool(result['success'])
        result['request_params'] = json.loads(result['request_params'])
        result.pop('normalized', None)
        if not full:
            result.pop('response_text', None)
        result['provider'] = SOURCES[result['source']][0]
        return result

    def get_receipt(self, identifier):
        with self.store.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM felix_evidence WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Evidence receipt not found')
        return self.receipt(row, full=True)

    def context(self, fid, source):
        owner = '*' if source == 'map' else fid
        with self.store.connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM felix_evidence WHERE farm_id=? AND source=? ORDER BY id DESC',
                              (owner, source)).fetchall()
        last = rows[0] if rows else None
        good = next((row for row in rows if row['success']), None)
        current = False
        normalized = json.loads(good['normalized']) if good else None
        if good:
            age = (now() - datetime.fromisoformat(good['completed_at'])).total_seconds()
            current = 0 <= age <= SOURCES[source][2]
            if source == 'weather':
                current = current and normalized['start'] == now().astimezone(timezone(timedelta(hours=2))).date().isoformat()
        state = 'current' if current else 'stale' if good else 'bundled' if source in ('weather','map') else 'missing'
        return {'provider':SOURCES[source][0], 'state':state, 'last_attempt':self.receipt(last),
                'used_receipt':self.receipt(good) if current else None,
                'last_success':self.receipt(good), 'normalized':normalized if current else None,
                'used_in_score':source != 'map' and current,
                'freshness_hours':SOURCES[source][2] / 3600}

    def map(self):
        context = self.context('*', 'map')
        return dict(context['normalized'] or self.bundled_map,
                    mode='live_fetch' if context['normalized'] else 'bundled_snapshot',
                    evidence={k:v for k,v in context.items() if k != 'normalized'})

    def refresh(self, farm, source):
        if source not in SOURCES:
            raise HTTPException(404, 'Unknown environmental source')
        endpoint = SOURCES[source][1]
        if source == 'weather':
            params = {'latitude':farm['latitude'], 'longitude':farm['longitude'],
                      'daily':'precipitation_sum,temperature_2m_max', 'forecast_days':3,
                      'timezone':'Africa/Blantyre', 'temperature_unit':'celsius', 'precipitation_unit':'mm'}
        elif source == 'soil':
            params = {'lon':farm['longitude'], 'lat':farm['latitude'], 'property':'clay', 'depth':'0-5cm', 'value':'mean'}
        else:
            bbox = ','.join(str(v) for v in BOUNDS)
            params = {'data':f'[out:json][timeout:20];(way["highway"]({bbox});way["waterway"]({bbox}););out geom;'}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Reserve before fetching so concurrent clicks respect provider limits.
            if source in ('soil','map'):
                interval = 13 if source == 'soil' else 30
                previous = db.execute('SELECT attempted_at FROM felix_evidence WHERE source=? ORDER BY id DESC LIMIT 1', (source,)).fetchone()
                if previous and (now()-datetime.fromisoformat(previous[0])).total_seconds() < interval:
                    raise HTTPException(429, f'{SOURCES[source][0]} is paced to one request per {interval} seconds. Wait before fetching again.')
            cursor = db.execute('''INSERT INTO felix_evidence
                (farm_id,source,attempted_at,request_url,request_params,request_method) VALUES (?,?,?,?,?,?)''',
                ('*' if source == 'map' else farm['id'], source, now().isoformat(), endpoint, json.dumps(params), 'POST' if source=='map' else 'GET'))
            identifier = cursor.lastrowid
        status, raw, digest, normalized, error = None, None, None, None, None
        try:
            options = {'timeout':(5,25), 'allow_redirects':False,
                       'headers':{'User-Agent':'FieldwiseLocalDemo/1.0 (manual environmental evidence retrieval)', 'Accept':'application/json'}}
            response = requests.post(endpoint, data=params, **options) if source=='map' else requests.get(endpoint, params=params, **options)
            status = response.status_code
            if len(response.content) > 2_000_000:
                raise ValueError('Provider response exceeded the local size limit.')
            raw = response.content.decode('utf-8')
            digest = hashlib.sha256(response.content).hexdigest()
            if status != 200:
                raise ValueError(f'Provider returned HTTP {status}.')
            normalized = normalize(source, json.loads(raw))
        except requests.RequestException:
            error = 'Provider could not be reached or timed out. Previous evidence was preserved.'
        except (ValueError, KeyError, TypeError, StopIteration, UnicodeError):
            error = f'Provider response invalid or unavailable (HTTP {status}). Previous evidence was preserved.'
        with self.store.connect() as db:
            db.execute('''UPDATE felix_evidence SET completed_at=?,success=?,http_status=?,response_text=?,
                       sha256=?,normalized=?,error=? WHERE id=?''',
                       (now().isoformat(), int(normalized is not None), status, raw, digest,
                        json.dumps(normalized, allow_nan=False) if normalized is not None else None, error, identifier))
        return self.get_receipt(identifier)
