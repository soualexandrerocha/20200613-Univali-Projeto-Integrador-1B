"""Propagação da maré no baixo Itajaí-Açu a partir da telemetria da Defesa Civil.

Uso:
    python analise_propagacao_mare.py            # baixa as últimas 12 h e analisa o acumulado
    python analise_propagacao_mare.py --offline  # só analisa o que já está em dados/
    python analise_propagacao_mare.py --so-coletar  # só baixa e grava (usado no GitHub Actions)

Fonte: https://monitoramento.defesacivil.itajai.sc.gov.br/monitoramento/rios
(nível a cada 10 min, últimas 12 h, rede "Telemetria Itajaí"). O site não
oferece histórico, então cada execução acrescenta as leituras novas a
dados/niveis_defesacivil_itajai.csv. Rodar a cada poucas horas forma uma
série longa, que melhora o ajuste e cobre sizígia e quadratura.

Para cada estação, ajusta por mínimos quadrados

    nivel(t) = r * eta(t - atraso) + c0 + c1 * t

onde eta é a maré prevista na foz (previsao_mare_itajai.py), r é a razão de
amplitude, `atraso` é procurado em passos de 5 min e c0 + c1*t absorve o
zero da régua e a tendência fluvial. Com r e o atraso de uma estação a uma
distância x da foz, uma onda amortecida exponencialmente equivale, para o
fluxo que passa na foz, a um trecho em fase de comprimento

    L_ef = x / sqrt(ln(r)^2 + (w*atraso)^2)

com atraso de fase atan(w*atraso / -ln r) (w = frequência do M2).
"""

import csv
import html
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import previsao_mare_itajai as pm

URL = 'https://monitoramento.defesacivil.itajai.sc.gov.br/monitoramento/rios'
ARQ = Path(__file__).with_name('dados') / 'niveis_defesacivil_itajai.csv'
REFERENCIA = 'DC01'  # Rio Itajaí-Açu - ICMBio/CEPSUL, junto à foz e ao porto
W_M2 = 2 * np.pi / (12.4206012 * 3600)  # rad/s


def baixar():
  """Estações e séries de 12 h publicadas na página (dados Inertia em data-page)."""
  req = urllib.request.Request(URL, headers={'User-Agent': 'projeto-academico-mare/1.0'})
  for tentativa in range(4):
    try:
      pagina = urllib.request.urlopen(req, timeout=120).read().decode('utf-8')
      break
    except OSError:
      if tentativa == 3:
        raise
      time.sleep(30 * 2**tentativa)
  dados = json.loads(html.unescape(re.search(r'data-page="([^"]*)"', pagina).group(1)))
  return [e for e in dados['props']['estacoes'] if 'rios' in e['capacidades']]


def acumular(estacoes):
  """Acrescenta ao CSV as leituras ainda não gravadas; retorna quantas entraram."""
  ARQ.parent.mkdir(exist_ok=True)
  existentes = set()
  if ARQ.exists():
    with ARQ.open() as f:
      existentes = {(r['codigo'], r['medido_em']) for r in csv.DictReader(f)}
  novas = []
  for e in estacoes:
    for p in e.get('serie_12_h') or []:
      if p.get('nivel_rio_m') is None:
        continue
      chave = (e['codigo'], datetime.fromisoformat(p['medido_em']).astimezone(timezone.utc)
               .strftime('%Y-%m-%dT%H:%M:%SZ'))
      if chave not in existentes:
        existentes.add(chave)
        novas.append([*chave, e['nome'], e['latitude'], e['longitude'], p['nivel_rio_m']])
  novo_arquivo = not ARQ.exists()
  with ARQ.open('a', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    if novo_arquivo:
      w.writerow(['codigo', 'medido_em', 'nome', 'latitude', 'longitude', 'nivel_rio_m'])
    w.writerows(sorted(novas))
  return len(novas)


def ler():
  series, meta = {}, {}
  with ARQ.open() as f:
    for r in csv.DictReader(f):
      t = datetime.strptime(r['medido_em'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
      series.setdefault(r['codigo'], []).append((t.timestamp(), float(r['nivel_rio_m'])))
      meta[r['codigo']] = (r['nome'], float(r['latitude']), float(r['longitude']))
  return {c: np.array(sorted(v)) for c, v in series.items()}, meta


def distancia_km(a, b):
  """Distância em linha reta (km); o caminho pelo rio é maior."""
  la1, lo1, la2, lo2 = map(np.radians, (a[1], a[2], b[1], b[2]))
  return 6371 * np.hypot(la2 - la1, (lo2 - lo1) * np.cos(la1))


def ajustar(serie, atrasos_min=range(-30, 181, 5)):
  """(r, atraso_min, rms_m) do melhor ajuste nivel = r*eta(t - atraso) + c0 + c1*t."""
  t, h = serie[:, 0], serie[:, 1]
  melhor = None
  for atraso in atrasos_min:
    eta = np.array([pm.prever_mare_itajai(datetime.fromtimestamp(x - 60 * atraso, timezone.utc))
                    for x in t])
    A = np.c_[eta, np.ones_like(eta), (t - t.mean()) / 86400]
    c, *_ = np.linalg.lstsq(A, h, rcond=None)
    rms = float(np.sqrt(np.mean((h - A @ c) ** 2)))
    if melhor is None or rms < melhor[2]:
      melhor = (float(c[0]), atraso, rms)
  return melhor


def comprimento_efetivo(r, atraso_min, x_km):
  """(L_ef em km, atraso de fase do fluxo em s) para onda amortecida exponencialmente."""
  a, b = -np.log(r), W_M2 * 60 * atraso_min
  return x_km / np.hypot(a, b), np.arctan2(b, a) / W_M2


def main():
  if '--offline' not in sys.argv:
    print(f'{acumular(baixar())} leituras novas gravadas em {ARQ}')
  if '--so-coletar' in sys.argv:
    return
  series, meta = ler()
  print(f"\n{'estação':<6} {'nome':<52} {'dist (km)':>9} {'horas':>6} {'r':>5} "
        f"{'atraso':>7} {'RMS':>6}  L_ef / atraso do fluxo")
  for c in sorted(series):
    s = series[c]
    horas = (s[-1, 0] - s[0, 0]) / 3600
    if len(s) < 36 or np.ptp(s[:, 1]) < 0.05:
      print(f'{c:<6} {meta[c][0][:52]:<52} {"":>9} {horas:>6.0f}  sem sinal de maré ou poucos dados')
      continue
    r, atraso, rms = ajustar(s)
    x = distancia_km(meta[REFERENCIA], meta[c])
    extra = ''
    if c != REFERENCIA and 0 < r < 1 and atraso > 0:
      L, tq = comprimento_efetivo(r, atraso, x)
      extra = f'{L:5.1f} km / {tq / 3600:.1f} h'
    print(f'{c:<6} {meta[c][0][:52]:<52} {x:>9.1f} {horas:>6.0f} {r:>5.2f} '
          f'{atraso:>+5d} m {rms * 100:>5.1f}cm  {extra}')


if __name__ == '__main__':
  main()
