"""Curva-chave do Itajaí-Açu em Blumenau (ANA 83800002) e vazão a partir do
nível do AlertaBlu.

    python ferramentas/curva_chave_blumenau.py           # baixa da ANA, ajusta e aplica
    python ferramentas/curva_chave_blumenau.py --offline # usa o CSV gravado

Fonte: séries históricas da ANA (HidroSerieHistorica) da estação Blumenau
(83800002): cota diária 1939-2021 e vazão diária 1939-2014. Grava
dados/cota_vazao_blumenau_83800002.csv (data, cota em m, vazão em m³/s).

Ajusta Q = a * (h - h0)^b aos pares diários de um período (PERIODO) e aplica
ao nível do AlertaBlu coletado em dados/niveis/ (estação BLU).

A curva-chave de Blumenau mudou ao longo do tempo (a ANA calcula a vazão da
cota pela curva vigente em cada época; para a mesma cota, ~40% mais vazão a
partir de 1990 nas cotas baixas), então há uma curva por período, como no
repositório Orbis_Hydro_ITJ2 (vazao_blumenau.py), de onde vêm os períodos.
O padrão é o mais recente com dados, 2012-2014 (erro de ajuste ~1%, dentro
do período; a curva pode ter mudado depois). Contra a vazão medida a montante
em Salto Pilão (vazao_montante.py): em 14 dias, com o nível da PCH Salto
Jusante (341 pares), a razão Blumenau / Salto Pilão é de 1,07 e a mais
estável entre as faixas de vazão; nos 3 dias estáveis de 11 a 13/11 com o
nível do AlertaBlu (32 leituras), é de 0,96, abaixo do piso físico de 1, e a
curva de 2002-2007 dá 1,00. Ou seja, a escolha entre as curvas de 2002 a 2014
não se resolve com esses dados: elas diferem em ~±7% para 3,6 m (850 a 985
m³/s), da ordem da incerteza da razão de áreas. A de 1939-1985 dá menos água
em Blumenau que a montante (0,77 a 0,88) e não serve para hoje (680 m³/s).

Supõe que a régua do AlertaBlu e a da ANA têm o mesmo zero: o nível da PCH
Salto Jusante (ANA) concorda com o do AlertaBlu em ~7 cm (correlação 0,99),
mas não há período comum com a estação histórica de Blumenau. A série de
vazão da ANA acaba em 2014, e a curva pode ter mudado de novo depois.

Vazão no porto: a de Blumenau vezes RAZAO_AREAS_PORTO, razão entre as áreas
de drenagem do porto e de Blumenau (11.803 km², inventário da ANA). O
Itajaí-Mirim deságua ~2 km a montante da Bacia 1, então vale o extremo alto
da faixa de 1,13 a 1,27 do repositório Orbis; a área do porto não foi
conferida em fonte. Em cheia, a razão de áreas é aproximação grosseira.
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
# Períodos com curva-chave aproximadamente única (do repositório Orbis_Hydro_ITJ2)
PERIODOS = {
    '1939-1985': (1939, 1985),
    '1990-2001': (1990, 2001),
    '2002-2007': (2002, 2007),
    '2008-2010': (2008, 2010),
    '2011': (2011, 2011),
    '2012-2014': (2012, 2014),
}
PERIODO = PERIODOS['2012-2014']  # o mais recente com vazão
COTA_MIN_AJUSTE_M = 1.0  # abaixo disso a curva é menos estável
# Blumenau -> porto, por áreas de drenagem (Blumenau 11.803 km², ANA)
RAZAO_AREAS_FAIXA = (1.13, 1.27)
RAZAO_AREAS_PORTO = 1.27  # extremo alto: o Itajaí-Mirim deságua a montante do berço
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
  ok = (q > 0) & (h > COTA_MIN_AJUSTE_M)
  h, q = h[ok], q[ok]
  melhor = None
  for h0 in np.arange(-3.0, h.min() - 0.01, 0.05):
    A = np.c_[np.ones(len(h)), np.log(h - h0)]
    c, *_ = np.linalg.lstsq(A, np.log(q), rcond=None)
    rms = float(np.sqrt(np.mean((A @ c - np.log(q)) ** 2)))
    if melhor is None or rms < melhor[3]:
      melhor = (float(np.exp(c[0])), float(h0), float(c[1]), rms)
  return melhor


def faixa_cotas(periodo=PERIODO):
  """(mínima, máxima) das cotas diárias usadas no ajuste, em m."""
  h = []
  with ARQ.open() as f:
    for r in csv.DictReader(f):
      if (r['cota_m'] and r['vazao_m3s'] and periodo[0] <= int(r['data'][:4]) <= periodo[1]
          and float(r['cota_m']) > COTA_MIN_AJUSTE_M):
        h.append(float(r['cota_m']))
  return min(h), max(h)


def curvas_por_periodo():
  """{nome: (curva, erro relativo típico, cota máxima dos dados em m)} para todos os períodos."""
  saida = {}
  for nome, per in PERIODOS.items():
    curva = ajustar(per)
    hmax = faixa_cotas(per)[1]
    saida[nome] = (curva, float(np.exp(curva[3]) - 1), hmax)
  return saida


def vazao_porto(h, curva):
  """Vazão no porto (m³/s) a partir do nível em Blumenau (m)."""
  return vazao(h, curva) * RAZAO_AREAS_PORTO


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
