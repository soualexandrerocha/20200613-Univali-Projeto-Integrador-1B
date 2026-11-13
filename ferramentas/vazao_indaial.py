"""Vazão diária do Itajaí-Açu em Indaial (ANA 83690000) e estatísticas.

    python ferramentas/vazao_indaial.py           # baixa da ANA e grava o CSV
    python ferramentas/vazao_indaial.py --offline # só resume o CSV gravado

Fonte: série histórica da ANA (HidroSerieHistorica, tipoDados=3), a mesma
estação usada por Zaleski & Schettini (2003). Indaial fica a ~90 km da foz
e drena 11.110 km², ~70% da bacia: não inclui o Itajaí-Mirim nem os
afluentes de jusante, então a vazão que passa no porto é maior. Quando há
dado bruto e consistido para o mesmo dia, vale o consistido.

Grava dados/vazao_indaial_83690000.csv (data, vazão em m³/s, consistência).
Em 13/11/2026 a série consistida ia de 1930 a 2021; a telemetria da ANA
não trazia vazão de Indaial para os dias recentes.
"""

import calendar
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np

URL = ('https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica?codEstacao=83690000'
       '&dataInicio=01/01/1900&dataFim=31/12/2100&tipoDados=3&nivelConsistencia=')
ARQ = Path(__file__).resolve().parent.parent / 'dados' / 'vazao_indaial_83690000.csv'
FRACAO_BACIA = 0.70  # área de Indaial / área da bacia (Zaleski & Schettini, 2003)


def baixar():
  req = urllib.request.Request(URL, headers={'User-Agent': 'projeto-academico-mare/1.0'})
  xml = urllib.request.urlopen(req, timeout=300).read().decode('utf-8')
  dias = {}
  for bloco in re.findall(r'<SerieHistorica[^>]*>(.*?)</SerieHistorica>', xml, re.S):
    r = dict(re.findall(r'<(\w+)>([^<]*)</\1>', bloco))
    ano, mes, nivel = int(r['DataHora'][:4]), int(r['DataHora'][5:7]), int(r.get('NivelConsistencia', 1))
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
      v = r.get(f'Vazao{dia:02d}', '').strip()
      chave = f'{ano:04d}-{mes:02d}-{dia:02d}'
      if v and (chave not in dias or nivel > dias[chave][1]):
        dias[chave] = (float(v), nivel)
  with ARQ.open('w') as f:
    f.write('data,vazao_m3s,consistencia\n')
    for chave in sorted(dias):
      f.write(f'{chave},{dias[chave][0]:.2f},{"consistido" if dias[chave][1] == 2 else "bruto"}\n')
  return len(dias)


def resumo():
  datas, q = [], []
  with ARQ.open() as f:
    next(f)
    for linha in f:
      d, v, _ = linha.strip().split(',')
      datas.append(d)
      q.append(float(v))
  q = np.array(q)
  meses = np.array([int(d[5:7]) for d in datas])
  print(f'Indaial (ANA 83690000): {datas[0]} a {datas[-1]}, {len(q)} dias')
  print(f'  média {q.mean():.0f} m³/s; mediana {np.median(q):.0f}; '
        f'P10 {np.percentile(q, 10):.0f}; P90 {np.percentile(q, 90):.0f}; P99 {np.percentile(q, 99):.0f}')
  print(f'  novembro: média {q[meses == 11].mean():.0f}; mediana {np.median(q[meses == 11]):.0f}')
  print(f'  no porto, escalando pela área (/{FRACAO_BACIA:.2f}, aproximação grosseira): '
        f'mediana ~{np.median(q) / FRACAO_BACIA:.0f}, média ~{q.mean() / FRACAO_BACIA:.0f} m³/s')


if __name__ == '__main__':
  if '--offline' not in sys.argv:
    print(f'{baixar()} dias gravados em {ARQ}')
  resumo()
