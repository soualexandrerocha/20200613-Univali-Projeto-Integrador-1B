"""Validação independente: modelo (constantes da tábua CHM 2024) x Tábua de
Maré de Itajaí 2026 da EPAGRI (outra fonte, outro ano).

    python ferramentas/comparar_epagri.py
"""
import csv, datetime as dt, os, sys
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import mare_itajai as m  # noqa: E402

M = m.Mare()
R = list(csv.DictReader(open(os.path.join(RAIZ, 'dados', 'tabua_mare_itajai_2026_epagri.csv'))))
t = np.array([np.datetime64(dt.datetime.strptime(r['data_hora_local'], '%Y-%m-%d %H:%M'), 'm') for r in R])
h = np.array([float(r['altura_m']) for r in R])

r = h - M.altura(t)
print(f'{len(t)} extremos da EPAGRI em 2026')
print(f'Altura nos horários da tábua: RMS {np.sqrt((r**2).mean())*100:.1f} cm, viés {r.mean()*100:+.1f} cm (EPAGRI − modelo)')

ext = M.extremos(np.datetime64('2025-12-31T00:00'), np.datetime64('2027-01-02T00:00'))
te = np.array([e[0] for e in ext]).astype('datetime64[s]')
he = np.array([e[1] for e in ext])
amp = np.minimum(np.abs(np.diff(he, prepend=np.nan)), np.abs(np.diff(he, append=np.nan)))
j = np.array([np.argmin(np.abs(te - ti.astype('datetime64[s]'))) for ti in t])
d = (te[j] - t.astype('datetime64[s]')) / np.timedelta64(1, 'm')  # modelo − EPAGRI
casa = np.abs(d) <= 90
print(f'Extremos com par no modelo (≤ 90 min): {casa.sum()} de {len(t)} '
      '(os demais são oscilações de poucos cm que o modelo suaviza)')
for nome, s in [('bem marcados (≥ 20 cm)', casa & (amp[j] >= 0.2)), ('estofos (< 20 cm)', casa & (amp[j] < 0.2))]:
    a = np.abs(d[s])
    print(f'Horário, {nome}, n={s.sum()}: mediana {np.median(a):.0f} min, 90 % ≤ {np.percentile(a, 90):.0f} min, '
          f'viés {np.median(d[s]):+.0f} min')
