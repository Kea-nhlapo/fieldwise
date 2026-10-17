import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEMO_FARMS = []
for fid, name, area, lat, lon, fc, wp, root, initial, reply in [
    ('makhaya', 'Makhaya Maize', 'Delmas', -26.15, 28.68, .28, .12, .8, .25, 'unknown'),
    ('siyakhula', 'Siyakhula Cooperative', 'Bapsfontein', -25.99, 28.44, .23, .10, .65, .45, '2'),
    ('ubuntu', 'Ubuntu Fields', 'Bronkhorstspruit', -25.84, 28.75, .30, .14, 1.0, .3, '1'),
    ('khanyisa', 'Khanyisa Farm', 'Springs', -26.22, 28.47, .24, .11, .7, .4, '3'),
    ('thandeka', 'Thandeka Smallholding', 'Benoni', -26.10, 28.34, .29, .12, .9, .2, 'unknown'),
]:
    DEMO_FARMS.append(dict(id=fid, name=name, area=area, latitude=lat, longitude=lon,
                          theta_fc=fc, theta_wp=wp, root_m=root, initial_depletion=initial,
                          reply=reply, crop='Maize', irrigation_mm=30.0,
                          irrigation_interval_days=4, visit_minutes=35))


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # WAL lets a write (for example a demo reset) commit while other requests are still reading;
        # in the default journal mode a long read could make the write give up with 'database is locked'.
        wal = sqlite3.connect(self.path, timeout=10)
        try:
            wal.execute('PRAGMA journal_mode=WAL')
        finally:
            wal.close()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS farms (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, farm_id TEXT, kind TEXT, text TEXT, created_at TEXT)')
            db.execute('''CREATE TABLE IF NOT EXISTS disease_alerts (
                id INTEGER PRIMARY KEY, farm_id TEXT NOT NULL, disease_id TEXT NOT NULL,
                disease_name TEXT NOT NULL, state TEXT NOT NULL, priority_floor INTEGER NOT NULL,
                summary TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(farm_id,disease_id))''')
            db.execute('CREATE TABLE IF NOT EXISTS disease_reference (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            # De-identified, append-only impact log: no farm IDs, names or answers, so it survives erasure requests.
            db.execute('''CREATE TABLE IF NOT EXISTS impact_events (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, workspace TEXT NOT NULL,
                detail TEXT, value REAL, created_at TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, status INTEGER, body BLOB, created_at TEXT)')
            for farm in DEMO_FARMS:
                db.execute('INSERT OR IGNORE INTO farms VALUES (?,?)', (farm['id'], json.dumps(farm)))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def farms(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM farms ORDER BY id')]

    def get_farm(self, fid):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM farms WHERE id=?', (fid,)).fetchone()
        if row is None: raise KeyError(fid)
        return json.loads(row[0])

    def update(self, fid, changes, kind, text):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM farms WHERE id=?', (fid,)).fetchone()
            if row is None: raise KeyError(fid)
            farm = json.loads(row[0])
            farm.update(changes)
            db.execute('UPDATE farms SET payload=? WHERE id=?', (json.dumps(farm), fid))
            db.execute('INSERT INTO activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                       (fid, kind, text, datetime.now(timezone.utc).isoformat()))
        return farm

    def activity(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 20')]

    def disease_alerts(self, fid=None):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            query = 'SELECT * FROM disease_alerts'
            args = ()
            if fid is not None:
                query += ' WHERE farm_id=?'
                args = (fid,)
            return [dict(row) for row in db.execute(query + ' ORDER BY updated_at DESC,id DESC', args)]

    def record_disease_observation(self, fid, disease, status, notes):
        now = datetime.now(timezone.utc).isoformat()
        observation = {'status':status, 'notes':notes, 'recorded_at':now, 'source':'local_simulation'}
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM farms WHERE id=?', (fid,)).fetchone()
            if row is None: raise KeyError(fid)
            farm = json.loads(row[0])
            farm.setdefault('disease_observations', {})[disease['id']] = observation
            db.execute('UPDATE farms SET payload=? WHERE id=?', (json.dumps(farm), fid))
            text = f"Simulated {disease['name']} observation: {status}. Not a diagnosis."
            db.execute('INSERT INTO activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                       (fid, 'disease_observation', text, now))
            if status != 'none':
                floor = 80 if status == 'symptoms' else 50
                db.execute('''INSERT INTO disease_alerts
                    (farm_id,disease_id,disease_name,state,priority_floor,summary,created_at,updated_at)
                    VALUES (?,?,?,'open',?,?,?,?)
                    ON CONFLICT(farm_id,disease_id) DO UPDATE SET
                    state=CASE WHEN disease_alerts.state='resolved' THEN 'open' ELSE disease_alerts.state END,
                    priority_floor=CASE WHEN disease_alerts.state='resolved' THEN excluded.priority_floor
                        ELSE MAX(disease_alerts.priority_floor,excluded.priority_floor) END,
                    summary=excluded.summary, updated_at=excluded.updated_at''',
                    (fid, disease['id'], disease['name'], floor, text, now, now))
        return observation

    def set_disease_alert_state(self, alert_id, state):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT farm_id,disease_name,state FROM disease_alerts WHERE id=?', (alert_id,)).fetchone()
            if row is None: raise KeyError(alert_id)
            if row[2] == 'resolved' and state == 'acknowledged':
                raise ValueError('A resolved alert can be reopened only by a new farmer observation.')
            if row[2] != state:
                db.execute('UPDATE disease_alerts SET state=?,updated_at=? WHERE id=?', (state, now, alert_id))
                db.execute('INSERT INTO activity (farm_id,kind,text,created_at) VALUES (?,?,?,?)',
                    (row[0], 'disease_review', f"Felix marked {row[1]} alert {state} (local demo).", now))

    def save_disease_reference(self, key, snapshot):
        with self.connect() as db:
            db.execute('INSERT INTO disease_reference VALUES (?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload',
                       (key, json.dumps(snapshot, allow_nan=False)))

    def get_disease_reference(self, key):
        with self.connect() as db:
            row = db.execute('SELECT payload FROM disease_reference WHERE cache_key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def reset_demo(self):
        """Restore the five South Africa demo farms; cached reference data is kept."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for farm in DEMO_FARMS:
                db.execute('INSERT OR REPLACE INTO farms VALUES (?,?)', (farm['id'], json.dumps(farm)))
            db.execute('DELETE FROM activity')
            db.execute('DELETE FROM disease_alerts')

    def record_impact(self, kind, workspace, detail=None, value=None, db=None):
        row = (kind, workspace, detail, value, datetime.now(timezone.utc).isoformat())
        sql = 'INSERT INTO impact_events (kind,workspace,detail,value,created_at) VALUES (?,?,?,?,?)'
        if db is not None: return db.execute(sql, row)
        with self.connect() as connection: connection.execute(sql, row)

    def impact_events(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM impact_events ORDER BY id')]

    def replayed(self, key):
        with self.connect() as db:
            return db.execute('SELECT status,body FROM idempotency WHERE key=?', (key,)).fetchone()

    def remember(self, key, status, body):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO idempotency VALUES (?,?,?,?)',
                       (key, status, body, datetime.now(timezone.utc).isoformat()))
