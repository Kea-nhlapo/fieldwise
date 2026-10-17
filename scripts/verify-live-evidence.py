"""Fetch actual public data for one fictional farm and preserve app receipts.

No fixtures, messages, farmer identities or credentials are used.
Run from the project root with .venv/Scripts/python.exe.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from fieldwise.app import create_app

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--farm', default='F014')
parser.add_argument('--db', type=Path, help='Optional isolated database; defaults to the local app database')
args = parser.parse_args()

report = {'farm_id':args.farm, 'verification':'actual provider calls; no fixtures', 'sources':{}}
with TestClient(create_app(args.db)) as client:
    for source in ('weather', 'soil', 'map'):
        response = client.post(f'/api/felix/farms/{args.farm}/evidence/{source}')
        result = response.json()
        receipt = result.get('receipt', {})
        report['sources'][source] = {k:receipt.get(k) for k in
            ('id','success','http_status','attempted_at','completed_at','sha256','error')}
        report['sources'][source]['api_status'] = response.status_code
        if not receipt:
            report['sources'][source]['error'] = result.get('detail')
        print(source, json.dumps(report['sources'][source]), flush=True)
    farm = next(f for f in client.get('/api/felix/dashboard').json()['farms'] if f['id']==args.farm)
    report['profile'] = {k:farm[k] for k in ('name','rain_mm','heat_c','clay_percent','score','risk_profile')}
Path('artifacts').mkdir(exist_ok=True)
Path('artifacts/live-evidence-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Saved artifacts/live-evidence-verification.json; original responses are in the app evidence receipts.')
if not all(item.get('success') for item in report['sources'].values()):
    sys.exit(1)
