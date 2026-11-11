"""Ajusta as constantes harmônicas de Itajaí à Tábua das Marés do CHM/DHN.

Uso:
    python ajuste_constantes_itajai.py "52 - PORTO DE ITAJAÍ - 166 - 168.pdf" [--gravar]

Entrada: o PDF da tábua anual (3 páginas, 4 meses por página), lido com o
`pdftotext -bbox` do poppler-utils. O PDF não fica no repositório.

Método: a tábua só traz extremos (hora e altura). Em cada extremo t_i valem
duas equações, ambas lineares nas incógnitas a_k = H_k cos G_k e
b_k = H_k sin G_k:

    Z0 + sum_k f_k (a_k cos th_k + b_k sin th_k)          = h_i   (altura)
    W * sum_k f_k w_k (-a_k sin th_k + b_k cos th_k)      = 0     (dh/dt = 0)

onde th_k = V_k + u_k e w_k é a velocidade angular em rad/h. W (horas) põe
a equação da derivada na mesma escala da altura. O sistema é resolvido por
mínimos quadrados.

Validação: ajusta só com os meses ímpares e mede o erro nos pares (e o
inverso) antes do ajuste final com o ano inteiro. Com --gravar, escreve as
constantes em previsao_mare_itajai.py, entre os marcadores CONSTANTES.
"""

import calendar
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import previsao_mare_itajai as pm

MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
         'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
ANO = 2026
FUSO = timezone(timedelta(hours=-3))  # a tábua indica "Fuso UTC -03.0 horas"
W_DERIVADA = 1.0  # horas


def ler_tabua(pdf):
  """Extrai [(datetime, altura_m)] de todas as páginas da tábua."""
  padrao = re.compile(
      r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]+)<')
  saida = set()
  for pagina in (1, 2, 3):
    html = subprocess.run(
        ['pdftotext', '-f', str(pagina), '-l', str(pagina), '-bbox', pdf, '-'],
        capture_output=True, text=True, check=True).stdout
    ws = [(float(a), float(b), float(c), float(d), t)
          for a, b, c, d, t in padrao.findall(html)]
    cab = sorted([w for w in ws if w[4] in MESES], key=lambda w: w[0])
    assert len(cab) == 4, f'página {pagina}: cabeçalhos {cab}'
    y_topo = cab[0][3]
    centros = [(w[0] + w[2]) / 2 for w in cab]
    passo = centros[1] - centros[0]
    for k, w in enumerate(cab):
      mes = MESES.index(w[4]) + 1
      c = centros[k]
      for x_ini, x_fim in ((c - passo / 2, c), (c, c + passo / 2)):  # dias 1-16 e 17-31
        col = [q for q in ws if x_ini <= q[0] < x_fim and q[1] > y_topo + 8]
        x_esq = min(q[0] for q in col)
        dias = sorted([q for q in col if re.fullmatch(r'\d\d', q[4]) and q[0] < x_esq + 6],
                      key=lambda q: q[1])
        horas = [q for q in col if re.fullmatch(r'\d{4}', q[4])]
        alturas = [q for q in col if re.fullmatch(r'-?\d\.\d\d', q[4])]
        for t in horas:
          dia = int([d for d in dias if d[1] <= t[1] + 2][-1][4])
          cy = (t[1] + t[3]) / 2
          h = min((q for q in alturas if q[0] > t[0]),
                  key=lambda q: abs((q[1] + q[3]) / 2 - cy) + abs(q[0] - t[2]) / 50)
          assert abs((h[1] + h[3]) / 2 - cy) < 1.5, (mes, dia, t, h)
          saida.add((datetime(ANO, mes, dia, int(t[4][:2]), int(t[4][2:]), tzinfo=FUSO),
                     float(h[4])))
  saida = sorted(saida)
  for mes in range(1, 13):
    dias = {t.day for t, _ in saida if t.month == mes}
    assert dias == set(range(1, calendar.monthrange(ANO, mes)[1] + 1)), f'mês {mes} incompleto'
  return saida


def matriz(pontos, nomes):
  """Linhas de altura e de derivada para os extremos dados."""
  n = len(nomes)
  A_h = np.zeros((len(pontos), 2 * n + 1))
  A_d = np.zeros((len(pontos), 2 * n + 1))
  A_h[:, -1] = 1.0  # Z0
  for i, (t, _) in enumerate(pontos):
    tm = pm.termos(t)
    for k, nome in enumerate(nomes):
      f, theta, a = tm[nome]
      th, w = np.radians(theta), np.radians(a)
      A_h[i, 2 * k:2 * k + 2] = f * np.cos(th), f * np.sin(th)
      A_d[i, 2 * k:2 * k + 2] = W_DERIVADA * f * w * -np.sin(th), W_DERIVADA * f * w * np.cos(th)
  return A_h, A_d


def ajustar(A_h, A_d, h):
  A = np.vstack([A_h, A_d])
  y = np.concatenate([h, np.zeros(len(h))])
  x, *_ = np.linalg.lstsq(A, y, rcond=None)
  return x


def constantes(x, nomes):
  """Converte (a, b) em (H, g local)."""
  out = {}
  for k, nome in enumerate(nomes):
    a, b = x[2 * k], x[2 * k + 1]
    G = np.degrees(np.arctan2(b, a))
    g = (G - pm.TZ_FASES * pm.velocidade(nome)) % 360.0
    out[nome] = (float(np.hypot(a, b)), float(g))
  return out, float(x[-1])


def erro_extremos(pontos):
  """Compara extremos do modelo com os da tábua: (dt em min, dh em m) por extremo."""
  dias = sorted({t.date() for t, _ in pontos})
  modelo = []
  for d in dias:
    ini = datetime(d.year, d.month, d.day, tzinfo=FUSO) - timedelta(hours=1)
    modelo += [(t, h) for t, h, _ in pm.extremos(ini, horas=26, passo_min=5)]
  tm = np.array([t.timestamp() for t, _ in modelo])
  dt, dh = [], []
  for t, h in pontos:
    j = int(np.argmin(abs(tm - t.timestamp())))
    dt.append((tm[j] - t.timestamp()) / 60)
    dh.append(modelo[j][1] - h)
  return np.array(dt), np.array(dh)


def main():
  pdf = sys.argv[1]
  pontos = ler_tabua(pdf)
  h = np.array([v for _, v in pontos])
  nomes = list(pm.DOODSON)
  print(f'{len(pontos)} extremos lidos; {len(nomes)} constituintes, {2 * len(nomes) + 1} incógnitas')

  A_h, A_d = matriz(pontos, nomes)

  # validação cruzada: meses ímpares x pares
  impar = np.array([t.month % 2 == 1 for t, _ in pontos])
  for nome_treino, treino in (('ímpares', impar), ('pares', ~impar)):
    x = ajustar(A_h[treino], A_d[treino], h[treino])
    e = A_h[~treino] @ x - h[~treino]
    print(f'treino nos meses {nome_treino}: RMS altura nos demais = {np.sqrt(np.mean(e**2)) * 100:.1f} cm,'
          f' max = {np.max(abs(e)) * 100:.1f} cm')

  x = ajustar(A_h, A_d, h)
  e = A_h @ x - h
  print(f'ajuste no ano todo: RMS altura = {np.sqrt(np.mean(e**2)) * 100:.1f} cm,'
        f' max = {np.max(abs(e)) * 100:.1f} cm')
  const, z0 = constantes(x, nomes)

  pm.CONSTITUENTES.clear()
  pm.CONSTITUENTES.update(const)
  pm.Z0 = z0
  dt, dh = erro_extremos(pontos)
  print(f'extremos do modelo x tábua: |dt| mediano {np.median(abs(dt)):.0f} min, '
        f'P95 {np.percentile(abs(dt), 95):.0f} min; |dh| P95 {np.percentile(abs(dh), 95) * 100:.1f} cm')

  print(f'\nZ0 = {z0:.3f} m')
  for nome, (H, g) in sorted(const.items(), key=lambda kv: -kv[1][0]):
    print(f'{nome:<5} H = {H:.4f} m   g = {g:6.2f}')

  if '--gravar' in sys.argv:
    linhas = [f'Z0 = {z0:.4f}', 'CONSTITUENTES = {']
    linhas += [f"    '{n}': ({H:.4f}, {g:.2f})," for n, (H, g) in const.items()]
    linhas += ['}']
    arq = Path(pm.__file__)
    txt = arq.read_text()
    novo = re.sub(r'(# CONSTANTES-INICIO\n).*?(# CONSTANTES-FIM)',
                  lambda m: m.group(1) + '\n'.join(linhas) + '\n' + m.group(2), txt, flags=re.S)
    arq.write_text(novo)
    print(f'\nconstantes gravadas em {arq.name}')


if __name__ == '__main__':
  main()
