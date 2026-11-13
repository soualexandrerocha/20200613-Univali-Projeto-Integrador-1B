"""Curva-chave do Itajaí-Açu em Blumenau (ANA 83800002) e vazão a partir do
nível do AlertaBlu.

    python ferramentas/curva_chave_blumenau.py           # baixa da ANA, ajusta e aplica
    python ferramentas/curva_chave_blumenau.py --offline # usa o CSV gravado

Fonte: séries históricas da ANA (HidroSerieHistorica) da estação Blumenau
(83800002): cota diária 1939-2021 e vazão diária 1939-2014. Grava
dados/cota_vazao_blumenau_83800002.csv (data, cota em m, vazão em m³/s).

Ajusta Q = a * (h - h0)^b aos pares diários de um período recente
(PERIODO) e aplica ao nível do AlertaBlu coletado em dados/niveis/
(estação BLU). Supõe que a régua do AlertaBlu e a da ANA têm o mesmo zero:
não há período comum para comparar; os indícios são as cheias de 2008 e
2011, com médias diárias na ANA (9,9 e 8,9 m) abaixo dos picos oficiais
(11,5 e 12,8 m), como se espera. A vazão no porto é maior que a de
Blumenau, que não inclui o Itajaí-Mirim nem os afluentes de jusante.
"""

import calendar
import csv
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / 'dados' / 'cota_vazao_blumenau_83800002.csv'
URL = ('https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica?codEstacao=83800002'
       '&dataInicio=01/01/1900&dataFim=31/12/2100&tipoDados={tipo}&nivelConsistencia=')
PERIODO = (2005, 2014)  # anos usados no ajuste (os mais recentes com vazão)
FUSO = timezone(timedelta(hours=-3))


def _diario(xml, campo):
  dias = {}
  for bloco in re.findall(r'<SerieHistorica[^>]*>(.*?)</SerieHistorica>', xml, re.S):
    r = dict(re.findall(r'<(\w+)>([^<]*)</\1>', bloco))
    if r.get('MediaDiaria', '1').strip() not in ('1', ''):
      continue  # só médias diárias
    ano, mes, nivel = int(r['DataHora'][:4]), int(r['DataHora'][5:7]), int(r.get('NivelConsistencia', 1))
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
      v = r.get(f'{campo}{dia:02d}', '').strip()
      chave = f'{ano:04d}-{mes:02d}-{dia:02d}'
      if v and (chave not in dias or nivel > dias[chave][1]):
        dias[chave] = (float(v), nivel)
  return dias


def baixar():
  xml = {}
  for tipo in (1, 3):  # 1 = cota, 3 = vazão
    req = urllib.request.Request(URL.format(tipo=tipo), headers={'User-Agent': 'projeto-academico-mare/1.0'})
    xml[tipo] = urllib.request.urlopen(req, timeout=300).read().decode('utf-8')
  cota, vazao = _diario(xml[1], 'Cota'), _diario(xml[3], 'Vazao')
  with ARQ.open('w') as f:
    f.write('data,cota_m,vazao_m3s\n')
    for d in sorted(set(cota) | set(vazao)):
      c = f'{cota[d][0] / 100:.2f}' if d in cota else ''
      q = f'{vazao[d][0]:.1f}' if d in vazao else ''
      f.write(f'{d},{c},{q}\n')
  return len(cota), len(vazao)


def ajustar(periodo=PERIODO):
  """(a, h0, b, erro RMS relativo) de Q = a*(h - h0)^b nos pares do período."""
  h, q = [], []
  with ARQ.open() as f:
    for r in csv.DictReader(f):
      if r['cota_m'] and r['vazao_m3s'] and periodo[0] <= int(r['data'][:4]) <= periodo[1]:
        h.append(float(r['cota_m']))
        q.append(float(r['vazao_m3s']))
  h, q = np.array(h), np.array(q)
  ok = q > 0
  h, q = h[ok], q[ok]
  melhor = None
  for h0 in np.arange(-3.0, h.min() - 0.01, 0.05):
    A = np.c_[np.ones(len(h)), np.log(h - h0)]
    c, *_ = np.linalg.lstsq(A, np.log(q), rcond=None)
    rms = float(np.sqrt(np.mean((A @ c - np.log(q)) ** 2)))
    if melhor is None or rms < melhor[3]:
      melhor = (float(np.exp(c[0])), float(h0), float(c[1]), rms)
  return melhor


def vazao(h, curva):
  a, h0, b, _ = curva
  return a * (np.asarray(h, float) - h0) ** b


def main():
  if '--offline' not in sys.argv:
    nc, nq = baixar()
    print(f'{nc} dias de cota e {nq} de vazão gravados em {ARQ}')
  curva = ajustar()
  a, h0, b, rms = curva
  print(f'Curva-chave {PERIODO[0]}-{PERIODO[1]}: Q = {a:.1f} * (h - ({h0:.2f}))^{b:.2f}  '
        f'(erro típico {100 * (np.exp(rms) - 1):.0f}%)')
  leituras = {}
  for arq in sorted((RAIZ / 'dados' / 'niveis').glob('*.csv')):
    with arq.open() as f:
      for r in csv.DictReader(f):
        if r['codigo'] == 'BLU':
          leituras[r['medido_em']] = float(r['nivel_rio_m'])
  print('Vazão estimada em Blumenau a partir do AlertaBlu (UTC-3):')
  for k in sorted(leituras)[::3]:
    t = datetime.strptime(k, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(FUSO)
    print(f'  {t:%d/%m %H:%M}  nível {leituras[k]:.2f} m  ->  {float(vazao(leituras[k], curva)):5.0f} m³/s')


if __name__ == '__main__':
  main()
