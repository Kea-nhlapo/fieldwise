"""Real pyfao56 calculations; demo assumptions are deliberately explicit."""
from datetime import date
import pyfao56 as fao
from .weather import validate_weather


def simulate(farm, rows, irrigated):
    validate_weather(rows)
    fc, wp, root = farm['theta_fc'], farm['theta_wp'], farm['root_m']
    fraction = farm['initial_depletion']
    if not (0 < wp < fc < 0.6 and 0.1 <= root <= 2.5 and 0 <= fraction <= 1):
        raise ValueError('Invalid soil or initial moisture assumptions.')
    par = fao.Parameters(Kcbini=0.15, Kcbmid=1.1, Kcbend=0.5,
                         Kcmini=1.15, Kcmmid=1.15, Kcmend=1.15,
                         Lini=30, Ldev=1, Lmid=60, Lend=30,
                         hini=2.0, hmax=2.0, thetaFC=fc, thetaWP=wp,
                         theta0=fc-fraction*(fc-wp), Zrini=root, Zrmax=root,
                         pbase=0.55, Ze=0.1, REW=6.0)
    weather = fao.Weather()
    weather.lat, weather.z, weather.wndht = farm['latitude'], 1400, 2.0
    irrigation = fao.Irrigation()
    updates = fao.Update()
    for i, row in enumerate(rows):
        day = date.fromisoformat(row['date'])
        nan = float('nan')
        updates.udata.loc[day.strftime('%Y-%j')] = [1.1, 2.0, nan]
        weather.wdata.loc[day.strftime('%Y-%j')] = [nan, row['tmax_c'], row['tmin_c'],
            nan, nan, nan, nan, nan, row['rain_mm'], row['et0_mm'], 'P']
        if irrigated and i % farm['irrigation_interval_days'] == 0:
            irrigation.addevent(day.year, day.timetuple().tm_yday,
                                farm['irrigation_mm'], 1.0, 85.0)
    model = fao.Model(date.fromisoformat(rows[0]['date']).strftime('%Y-%j'),
                      date.fromisoformat(rows[-1]['date']).strftime('%Y-%j'),
                      par, weather, irr=irrigation, upd=updates, cons_p=True)
    model.run()
    fields = {'Dr':'depletion_mm', 'RAW':'raw_mm', 'TAW':'taw_mm', 'Ks':'ks',
              'ETa':'eta_mm', 'Irrig':'irrigation_mm', 'Rain':'rain_mm'}
    return [dict(date=rows[i]['date'], **{name: round(float(row[col]), 3)
                 for col, name in fields.items()}) for i, (_, row) in enumerate(model.odata.iterrows())]


# FAO Irrigation and Drainage Paper 33: 1 - Ya/Ym = Ky (1 - ETa/ETm). Maize Ky over the season is 1.25.
YIELD_ASSUMPTIONS = {'ky': 1.25, 'season_etm_mm': 600, 'potential_kg_per_ha': 6000, 'kcb': 1.1}


def yield_loss(farm, series, rows):
    """Estimate seasonal maize loss caused by the water deficit inside this scenario window."""
    a = YIELD_ASSUMPTIONS
    deficit_mm = sum((1 - day['ks']) * a['kcb'] * row['et0_mm'] for day, row in zip(series, rows))
    loss = min(1.0, a['ky'] * deficit_mm / a['season_etm_mm'])
    area = farm.get('field_ha', 1.0)
    return {'deficit_mm': round(deficit_mm, 1), 'loss_pct': round(loss * 100, 1),
            'loss_kg': round(loss * a['potential_kg_per_ha'] * area)}


def yield_at_stake(farm, scenarios, rows):
    working, interrupted = yield_loss(farm, scenarios['working'], rows), yield_loss(farm, scenarios['interrupted'], rows)
    return {'working': working, 'interrupted': interrupted,
            'at_stake_kg': max(0, interrupted['loss_kg'] - working['loss_kg']),
            'field_ha': farm.get('field_ha', 1.0), 'assumptions': YIELD_ASSUMPTIONS,
            'method': 'FAO-33 yield response: loss = Ky × (water deficit ÷ seasonal crop water need). Estimate, not a measured harvest.'}


def compare(farm, rows):
    return {'working': simulate(farm, rows, True), 'interrupted': simulate(farm, rows, False)}


def prioritize(series, reply):
    last = series[-1]
    stress_days = sum(day['depletion_mm'] > day['raw_mm'] for day in series)
    depletion = last['depletion_mm'] / last['taw_mm']
    score = min(100, round(60 * depletion + 25 * stress_days / len(series)
                          + (15 if reply == '2' else 0)))
    label = 'Urgent' if score >= 70 else 'Watch' if score >= 40 else 'Routine'
    reason = f"{last['depletion_mm']:.0f} mm estimated depletion; {stress_days}/{len(series)} days above the stress threshold."
    if reply == '2': reason += ' Farmer reports irrigation interruption (+15 priority points).'
    elif reply == '3': reason += ' Rainfed scenario; no irrigation assumed.'
    elif reply == 'unknown': reason += ' Irrigation is unconfirmed; functioning schedule assumed.'
    return {'score': score, 'label': label, 'reason': reason, 'stress_days': stress_days,
            'depletion_pct': round(depletion * 100), 'confidence': 'Low — uncalibrated demo inputs'}
