"""Previsão da maré astronômica em Itajaí (SC) por síntese harmônica.

    h(t) = Z0 + sum_i f_i * H_i * cos(V_i(t) + u_i - g_i)

V_i é o argumento de equilíbrio, montado com os números de Doodson sobre
tau = 15*t_UTC + h - s. Esse tau difere do T de Schureman (T = 180 + 15*t)
por 180 graus, e a coluna `shift` de cada constituinte compensa isso.
Exemplos: O1 = T + h - 2s + 90 = tau - s + 270 e M3 = 3T + 3h - 3s =
3*tau + 180.

As fases g do catálogo são tomadas como referidas à hora legal UTC-3
(S = 45 graus W). Pela relação g = G - a*S/15, a fase de Greenwich é
G = g + 3*a, onde a é a velocidade angular do constituinte em graus/hora.

Limitações:
  - prevê só a maré astronômica. Vazão do rio Itajaí-Açu e maré
    meteorológica (vento sul, frentes frias) podem somar dezenas de cm;
  - os fatores nodais do L2 são aproximados pelos do M2, porque o nodal
    real do L2 também depende de p. O erro é pequeno (H = 1,5 cm);
  - H, g e Z0 devem ser conferidos na ficha da estação (FEMAR/DHN).
"""

from datetime import datetime, timedelta, timezone

import numpy as np

# Estação 60235 (Itajaí - Nova Delegacia)
Z0 = 0.60  # nível médio acima do zero hidrográfico (m)
TZ_FASES = 3.0  # horas a oeste de Greenwich a que as fases g se referem

# 'Nome': (H_m, g_graus, [tau, s, h, p, N', ps, shift_graus])
CONSTITUENTES = {
    'M2': (0.2283, 74.78, [2, 0, 0, 0, 0, 0, 0]),
    'S2': (0.1558, 66.72, [2, 2, -2, 0, 0, 0, 0]),
    'O1': (0.1003, 83.36, [1, -1, 0, 0, 0, 0, 270]),
    'K1': (0.0619, 135.91, [1, 1, 0, 0, 0, 0, 90]),
    'K2': (0.0511, 50.11, [2, 2, 0, 0, 0, 0, 0]),
    'M3': (0.0408, 182.97, [3, 0, 0, 0, 0, 0, 180]),
    'N2': (0.0377, 156.77, [2, -1, 0, 1, 0, 0, 0]),
    'Q1': (0.0286, 58.60, [1, -2, 0, 1, 0, 0, 270]),
    'MO3': (0.0245, 341.54, [3, -1, 0, 0, 0, 0, 270]),
    'P1': (0.0225, 129.31, [1, 1, -2, 0, 0, 0, 270]),
    'MU2': (0.0169, 122.90, [2, -2, 2, 0, 0, 0, 0]),
    'L2': (0.0154, 82.59, [2, 1, 0, -1, 0, 0, 180]),
    '2N2': (0.0131, 153.10, [2, -2, 0, 2, 0, 0, 0]),
}

# Velocidades de tau, s, h, p, N', ps (graus/hora)
VELOCIDADES_DOODSON = np.array(
    [14.4920521, 0.5490165, 0.0410686, 0.0046418, 0.0022064, 0.0000020]
)

J2000 = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)


def argumentos_astronomicos(dt_utc):
  """Retorna (tau, s, h, p, N', ps) em graus e os fatores nodais {nome: (f, u)}."""
  T = (dt_utc - J2000).total_seconds() / 86400.0 / 36525.0

  # Longitudes médias (Meeus); usar UTC em vez de TT erra ~69 s, desprezível
  s = (218.3164477 + 481267.88123421 * T) % 360.0  # Lua
  h = (280.466069 + 36000.76982779 * T) % 360.0  # Sol
  p = (83.3532465 + 4069.0137287 * T) % 360.0  # perigeu lunar
  N = (125.04452 - 1934.136261 * T) % 360.0  # nodo ascendente lunar
  ps = (282.9373 + 1.7195 * T) % 360.0  # perigeu solar

  hora_utc = (
      dt_utc.hour
      + dt_utc.minute / 60.0
      + (dt_utc.second + dt_utc.microsecond / 1e6) / 3600.0
  )
  tau = (15.0 * hora_utc + h - s) % 360.0

  Nr = np.radians(N)
  cosN, sinN, cos2N, sin2N = np.cos(Nr), np.sin(Nr), np.cos(2 * Nr), np.sin(2 * Nr)

  # Fatores nodais f e ângulos u (graus), aproximações usuais de Schureman
  m2 = (1.0004 - 0.0373 * cosN + 0.0002 * cos2N, -2.14 * sinN)
  o1 = (1.0089 + 0.1871 * cosN - 0.0147 * cos2N, 10.80 * sinN - 1.34 * sin2N)
  nodal = {
      'M2': m2,
      'N2': m2,
      'MU2': m2,
      '2N2': m2,
      'L2': m2,  # aproximação, ver docstring do módulo
      'S2': (1.0, 0.0),
      'K2': (1.0241 + 0.2863 * cosN + 0.0083 * cos2N, -17.74 * sinN + 0.68 * sin2N),
      'O1': o1,
      'Q1': o1,
      'K1': (1.0060 + 0.1150 * cosN - 0.0088 * cos2N, -8.86 * sinN + 0.68 * sin2N),
      'P1': (1.0, 0.0),
      'M3': (m2[0] ** 1.5, 1.5 * m2[1]),
      'MO3': (m2[0] * o1[0], m2[1] + o1[1]),
  }
  return np.array([tau, s, h, p, -N, ps]), nodal


def prever_mare_itajai(dt):
  """Altura da maré astronômica (m acima do zero hidrográfico) para um datetime com fuso."""
  args, nodal = argumentos_astronomicos(dt.astimezone(timezone.utc))

  altura = Z0
  for nome, (H, g, doodson) in CONSTITUENTES.items():
    coef = np.array(doodson[:6])
    V = coef @ args + doodson[6]
    f, u = nodal[nome]
    velocidade = coef @ VELOCIDADES_DOODSON  # graus/hora
    G = g + TZ_FASES * velocidade  # fase referida a Greenwich
    altura += f * H * np.cos(np.radians(V + u - G))

  return float(altura)


def extremos(inicio, horas=24, passo_min=5):
  """Preamares e baixa-mares por busca em grade fina, refinadas por parábola."""
  n = int(horas * 60 / passo_min) + 1
  tempos = [inicio + timedelta(minutes=passo_min * k) for k in range(n)]
  alturas = np.array([prever_mare_itajai(t) for t in tempos])

  resultado = []
  for i in range(1, n - 1):
    a, b, c = alturas[i - 1], alturas[i], alturas[i + 1]
    if (b - a) * (c - b) < 0:
      # vértice da parábola por três pontos (deslocamento em passos)
      denom = a - 2 * b + c
      x = 0.5 * (a - c) / denom if denom != 0 else 0.0
      t = tempos[i] + timedelta(minutes=passo_min * x)
      tipo = 'preamar' if b > a else 'baixa-mar'
      resultado.append((t, prever_mare_itajai(t), tipo))
  return resultado


if __name__ == '__main__':
  tz_brt = timezone(timedelta(hours=-3))
  inicio = datetime(2026, 11, 12, 0, 0, tzinfo=tz_brt)

  print(f"{'Hora local (UTC-3)':<22} | {'Altura (m)':>10}")
  print('-' * 36)
  for hora in range(0, 25, 2):
    t = inicio + timedelta(hours=hora)
    print(f"{t.strftime('%Y-%m-%d %H:%M'):<22} | {prever_mare_itajai(t):>10.3f}")

  print('\nExtremos:')
  for t, h_m, tipo in extremos(inicio):
    print(f"{t.strftime('%Y-%m-%d %H:%M'):<22} | {h_m:>10.3f} | {tipo}")
