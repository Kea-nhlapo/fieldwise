"""Reproduce upstream test05's basic maize case, then remove irrigation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pyfao56 as fao

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'examples' / 'upstream-maize'
out = ROOT / 'artifacts'
out.mkdir(exist_ok=True)
parameters = fao.Parameters()
parameters.loadfile(str(source / 'E12FF2022.par'))
weather = fao.Weather(str(source / 'LIRF.wth'))
irrigation = fao.Irrigation(str(source / 'E12FF2022.irr'))
series = {}
for label, schedule in [('Working irrigation', irrigation), ('No irrigation', None)]:
    model = fao.Model('2022-129', '2022-299', parameters, weather, irr=schedule, cons_p=True)
    model.run()
    series[label] = model.odata
    model.odata.to_csv(out / ('maize_' + ('working' if schedule else 'interrupted') + '.csv'))
wet, dry = series.values()
assert len(wet) == 171 and len(dry) == 171
assert dry.Dr.mean() > wet.Dr.mean()
assert wet.ETa.sum() > dry.ETa.sum()
summary = {'source':'pyfao56 test05, Greeley Colorado 2022; not South African calibration',
           'days':len(wet), 'working_mean_depletion_mm':round(float(wet.Dr.mean()), 2),
           'no_irrigation_mean_depletion_mm':round(float(dry.Dr.mean()), 2),
           'working_total_eta_mm':round(float(wet.ETa.sum()), 2),
           'no_irrigation_total_eta_mm':round(float(dry.ETa.sum()), 2)}
(out / 'maize_comparison.json').write_text(json.dumps(summary, indent=2))
fig, ax = plt.subplots(figsize=(11,5), layout='constrained')
for (label, frame), color in zip(series.items(), ['#34674e','#d78745']):
    ax.plot(frame.DOY.astype(float), frame.Dr.astype(float), label=label, color=color, linewidth=1.6)
ax.set(title='Maize water depletion: upstream pyfao56 example', xlabel='Day of year · 2022', ylabel='Root-zone depletion (mm)')
ax.text(.01,.98,'Greeley, Colorado · demonstration only', transform=ax.transAxes, va='top', color='#777777')
ax.legend(loc='lower right')
ax.grid(alpha=.15)
fig.savefig(out / 'maize_comparison.png', dpi=160)
print(json.dumps(summary, indent=2))
