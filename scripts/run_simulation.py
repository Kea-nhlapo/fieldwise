"""Run every simulation comparison and write static/sim/results.json for the /simulation page.

Seeded, so anyone can rerun it and get the same numbers:
    .venv\\Scripts\\python.exe scripts\\run_simulation.py
"""
import json
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fieldwise.simulation import Assumptions, FieldwisePrior, compare, describe, example_day  # noqa: E402

RUNS = 200


def fieldwise_row(result):
    return {'reach': result['policies']['fieldwise']['mean'], 'vs_officer': result['fieldwise_minus_officer'],
            'vs_rotation': result['fieldwise_minus_rotation'],
            'faw_reach': result['policies']['fieldwise']['faw_reach'], 'mln_reach': result['policies']['fieldwise']['mln_reach']}


def main():
    started = time.time()
    prior = FieldwisePrior()
    out = describe()
    out['simulated'] = True
    out['generated_at'] = datetime.now(timezone.utc).isoformat()
    try:
        out['commit'] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        out['commit'] = None
    out['main'] = compare(RUNS)
    out['no_signal'] = compare(RUNS, scramble=True)
    out['no_signal_strict'] = compare(RUNS, scramble=True, use_findings=False)
    out['ablation'] = {
        'all signals': fieldwise_row(out['main']),
        'without weather': fieldwise_row(compare(RUNS, prior=replace(prior, weather_gain=0.0))),
        'without nearby MLN': fieldwise_row(compare(RUNS, prior=replace(prior, neighbour_gain=0.0))),
        'without Felix’s own MLN finds': fieldwise_row(compare(RUNS, use_findings=False)),
    }
    out['sensitivity'] = {f'weights ×{k}': fieldwise_row(compare(RUNS, prior=prior.scaled(k))) for k in (0.5, 1, 2)}
    out['scale'] = []
    for farms, runs in ((100, RUNS), (250, 100), (1000, 40)):
        r = compare(runs, a=replace(Assumptions(), farms=farms))
        out['scale'].append({'farms': farms, 'runs': runs, 'policies': {p: v['mean'] for p, v in r['policies'].items()},
                             'vs_officer': r['fieldwise_minus_officer']})
    out['example'] = example_day()
    out['seconds'] = round(time.time() - started, 1)
    target = ROOT / 'static' / 'sim' / 'results.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {target.relative_to(ROOT)} in {out["seconds"]} s')


if __name__ == '__main__':
    main()
