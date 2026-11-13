"""Propagação da maré no baixo Itajaí-Açu a partir da telemetria da Defesa Civil.

Uso:
    python analise_propagacao_mare.py            # baixa as últimas 12 h e analisa o acumulado
    python analise_propagacao_mare.py --offline  # só analisa o que já está em dados/
    python analise_propagacao_mare.py --so-coletar  # só baixa e grava (usado no GitHub Actions)

Fonte: https://monitoramento.defesacivil.itajai.sc.gov.br/monitoramento/rios
(nível a cada 10 min, últimas 12 h, rede "Telemetria Itajaí"). O site não
oferece histórico, então cada execução grava as leituras novas num arquivo
próprio em dados/niveis/ (AAAA-MM-DDTHHMMZ.csv, hora UTC da coleta). Nenhum
arquivo é editado depois de criado, o que evita conflitos de merge entre a
coleta automática e outras branches; a leitura junta todos os arquivos e
descarta repetições. Rodar a cada poucas horas forma uma série longa, que
melhora o ajuste e cobre sizígia e quadratura.

Para cada estação, ajusta por mínimos quadrados

    nivel(t) = r * eta(t - atraso) + c0 + c1 * t

onde eta é a maré prevista na foz (mare_itajai.py), r é a razão de
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

URL = 'https://monitoramento.defesacivil.itajai.sc.gov.br/monitoramento/rios'
# Nível oficial do Itajaí-Açu em Blumenau (AlertaBlu): leituras horárias, últimas 24 h.
URL_BLUMENAU = 'https://defesacivil.blumenau.sc.gov.br/static/data/nivel_oficial.json'
# Posição aproximada da régua (a da estação ANA 83800002, Blumenau PCD).
BLUMENAU = {'codigo': 'BLU', 'nome': 'Rio Itajaí-Açu - Blumenau (AlertaBlu)',
            'latitude': -26.9186, 'longitude': -49.0656}
# Fim do estuário: a maré sobe o Itajaí-Açu até o Salto (barragem da PCH Salto, Blumenau).
SALTO = ('Salto (Blumenau)', -26.8800, -49.1089)
ACU = ('DC01', 'DC11', 'BLU')  # pontos medidos no Itajaí-Açu, da foz para montante
PASTA = Path(__file__).with_name('dados') / 'niveis'  # um CSV por coleta
CABECALHO = ['codigo', 'medido_em', 'nome', 'latitude', 'longitude', 'nivel_rio_m']
REFERENCIA = 'DC01'  # Rio Itajaí-Açu - ICMBio/CEPSUL, junto à foz e ao porto
W_M2 = 2 * np.pi / (12.4206012 * 3600)  # rad/s
R_MIN = 0.05  # razão de amplitude abaixo disso é tratada como sem maré
_MARE = None


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


def baixar_blumenau():
  """Série de 24 h do AlertaBlu no mesmo formato das estações de Itajaí."""
  req = urllib.request.Request(URL_BLUMENAU, headers={'User-Agent': 'projeto-academico-mare/1.0'})
  dados = json.loads(urllib.request.urlopen(req, timeout=120).read().decode('utf-8'))
  serie = [{'medido_em': n['horaLeitura'], 'nivel_rio_m': n['nivel']} for n in dados['niveis']]
  return dict(BLUMENAU, serie_12_h=serie)


def _linhas():
  """Todas as leituras gravadas, sem repetições (a mesma leitura pode estar em dois arquivos)."""
  vistas = {}
  for arq in sorted(PASTA.glob('*.csv')):
    with arq.open() as f:
      for r in csv.DictReader(f):
        vistas.setdefault((r['codigo'], r['medido_em']), r)
  return vistas


def acumular(estacoes, agora=None):
  """Grava as leituras ainda não gravadas num arquivo novo; retorna (quantas, caminho ou None)."""
  PASTA.mkdir(parents=True, exist_ok=True)
  existentes = set(_linhas())
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
  if not novas:
    return 0, None
  agora = agora or datetime.now(timezone.utc)
  arq = PASTA / f'{agora:%Y-%m-%dT%H%MZ}.csv'
  n = 1
  while arq.exists():  # duas coletas no mesmo minuto
    arq = PASTA / f'{agora:%Y-%m-%dT%H%MZ}_{n}.csv'
    n += 1
  with arq.open('w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(CABECALHO)
    w.writerows(sorted(novas))
  return len(novas), arq


def ler():
  series, meta = {}, {}
  for r in _linhas().values():
    t = datetime.strptime(r['medido_em'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    series.setdefault(r['codigo'], []).append((t.timestamp(), float(r['nivel_rio_m'])))
    meta[r['codigo']] = (r['nome'], float(r['latitude']), float(r['longitude']))
  return {c: np.array(sorted(v)) for c, v in series.items()}, meta


def distancia_km(a, b):
  """Distância em linha reta (km); o caminho pelo rio é maior."""
  la1, lo1, la2, lo2 = map(np.radians, (a[1], a[2], b[1], b[2]))
  return 6371 * np.hypot(la2 - la1, (lo2 - lo1) * np.cos(la1))


def ajustar(serie, atrasos_min=range(-30, 481, 5)):
  """(r, atraso_min, rms_m) do melhor ajuste nivel = r*eta(t - atraso) + c0 + c1*t, com r > 0."""
  from mare_itajai import Mare  # importado aqui: a coleta não precisa de utide/plotly
  global _MARE
  if _MARE is None:
    _MARE = Mare()
  t, h = serie[:, 0], serie[:, 1]
  melhor = None
  for atraso in atrasos_min:
    eta = _MARE.altura_utc(np.array(t - 60 * atraso, dtype='int64').astype('datetime64[s]'))
    A = np.c_[eta, np.ones_like(eta), (t - t.mean()) / 86400]
    c, *_ = np.linalg.lstsq(A, h, rcond=None)
    rms = float(np.sqrt(np.mean((h - A @ c) ** 2)))
    if c[0] > 0 and (melhor is None or rms < melhor[2]):
      melhor = (float(c[0]), atraso, rms)
  return melhor or (0.0, 0, float('nan'))


def trecho_enchimento(pontos, x_fim_km):
  """(L_ef em km, atraso do fluxo em s) com o estuário fechado em x_fim_km.

  pontos: [(x_km, r, atraso_min), ...] da foz (0, 1, 0) para montante. Entre
  pontos, a amplitude complexa r*exp(-i*w*atraso) varia exponencialmente;
  do último ponto até o fim, fica constante. O fluxo na foz é
  i*w*B*integral(rho dx), então L_ef = |integral| e o atraso sai da fase.
  """
  rho = lambda r, a: r * np.exp(-1j * W_M2 * 60 * a)
  soma = 0j
  for (x0, r0, a0), (x1, r1, a1) in zip(pontos[:-1], pontos[1:]):
    p0, p1 = rho(r0, a0), rho(r1, a1)
    k = -np.log(p1 / p0) / (x1 - x0)
    soma += p0 * (1 - p1 / p0) / k
  x, r, a = pontos[-1]
  soma += rho(r, a) * max(0.0, x_fim_km - x)
  return abs(soma), -np.angle(soma) / W_M2


def areas_efetivas(pontos, x_fim_km, s_km, largura_m, largura_alem_m, n=20001):
  """(A_ef em m², atraso do fluxo em s, área do prisma em m²) com largura variável.

  pontos: [(s_km pelo rio, r, atraso_min), ...] da foz para montante, até o
  fim do estuário em x_fim_km. A amplitude complexa varia exponencialmente
  entre pontos e fica constante depois do último. s_km e largura_m dão o
  perfil de largura medido; além dele, vale largura_alem_m.
    A_ef      = |integral B(s) rho(s) ds|   (volume líquido pela foz por metro de maré)
    A_prisma  = integral B(s) |rho(s)| ds   (prisma de maré por metro de amplitude)
  """
  x = np.linspace(0.0, x_fim_km, n)
  rho = np.empty(n, complex)
  for (x0, r0, a0), (x1, r1, a1) in zip(pontos[:-1], pontos[1:]):
    p0 = r0 * np.exp(-1j * W_M2 * 60 * a0)
    p1 = r1 * np.exp(-1j * W_M2 * 60 * a1)
    m = (x >= x0) & (x <= x1)
    rho[m] = p0 * (p1 / p0) ** ((x[m] - x0) / (x1 - x0))
  xu, ru, au = pontos[-1]
  rho[x > xu] = ru * np.exp(-1j * W_M2 * 60 * au)
  b = np.interp(x, s_km, largura_m)
  b[x > s_km[-1] + 0.25] = largura_alem_m
  integral = np.trapezoid(b * rho, x * 1e3)
  return abs(integral), -np.angle(integral) / W_M2, float(np.trapezoid(b * np.abs(rho), x * 1e3))


def comprimento_prisma(pontos, x_fim_km):
  """Integral da razão de amplitude r(x) da foz ao fim do estuário (km).

  Multiplicada pela largura e pela amplitude da maré na foz, dá o prisma de
  maré no sentido clássico (Dyer & Taylor, 1973): a soma, trecho a trecho,
  do volume na preamar menos o volume na baixa-mar, sem descontar a
  defasagem entre trechos. Difere de L_ef, que desconta a defasagem e dá o
  volume líquido que passa pela foz.
  """
  soma = 0.0
  for (x0, r0, _), (x1, r1, _) in zip(pontos[:-1], pontos[1:]):
    soma += (r0 - r1) * (x1 - x0) / np.log(r0 / r1) if r0 != r1 else r0 * (x1 - x0)
  x, r, _ = pontos[-1]
  return soma + r * max(0.0, x_fim_km - x)


def comprimento_efetivo(r, atraso_min, x_km):
  """(L_ef em km, atraso de fase do fluxo em s) para onda amortecida exponencialmente."""
  a, b = -np.log(r), W_M2 * 60 * atraso_min
  return x_km / np.hypot(a, b), np.arctan2(b, a) / W_M2


def main():
  if '--offline' not in sys.argv:
    estacoes = baixar()
    try:
      estacoes.append(baixar_blumenau())
    except (OSError, ValueError, KeyError) as erro:
      print(f'Aviso: Blumenau (AlertaBlu) não respondeu: {erro}')
    n, arq = acumular(estacoes)
    print(f'{n} leituras novas gravadas em {arq}' if n else 'Nenhuma leitura nova.')
  if '--so-coletar' in sys.argv:
    return
  series, meta = ler()
  resultados = {}
  print(f"\n{'estação':<6} {'nome':<52} {'dist (km)':>9} {'horas':>6} {'r':>5} "
        f"{'atraso':>7} {'RMS':>6}  L_ef / atraso do fluxo")
  for c in sorted(series):
    s = series[c]
    horas = (s[-1, 0] - s[0, 0]) / 3600
    if horas < 20 or np.ptp(s[:, 1]) < 0.05:
      print(f'{c:<6} {meta[c][0][:52]:<52} {"":>9} {horas:>6.0f}  sem sinal de maré ou poucos dados')
      continue
    r, atraso, rms = ajustar(s)
    x = distancia_km(meta[REFERENCIA], meta[c])
    extra = ''
    if c != REFERENCIA and R_MIN <= r < 1 and atraso > 0:
      L, tq = comprimento_efetivo(r, atraso, x)
      extra = f'{L:5.1f} km / {tq / 3600:.1f} h'
    print(f'{c:<6} {meta[c][0][:52]:<52} {x:>9.1f} {horas:>6.0f} {r:>5.2f} '
          f'{atraso:>+5d} m {rms * 100:>5.1f}cm  {extra}')
    resultados[c] = (x, r, atraso)
  pontos = [(0.0, 1.0, 0)] + [resultados[c] for c in ACU[1:] if c in resultados and resultados[c][1] >= R_MIN]
  x_salto = distancia_km(meta[REFERENCIA], (SALTO[0], SALTO[1], SALTO[2]))
  L, tq = trecho_enchimento(pontos, x_salto)
  print(f'\nItajaí-Açu fechado no {SALTO[0]} ({x_salto:.1f} km), com '
        f'{", ".join(c for c in ACU[1:] if c in resultados)}: L_ef = {L:.1f} km, atraso do fluxo {tq / 3600:.2f} h')


if __name__ == '__main__':
  main()
