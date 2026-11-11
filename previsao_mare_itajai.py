"""Previsão da maré astronômica em Itajaí (SC) por síntese harmônica.

    h(t) = Z0 + sum_i f_i * H_i * cos(V_i(t) + u_i - G_i),   G_i = g_i + TZ_FASES * a_i

V_i é o argumento de equilíbrio, montado com os números de Doodson sobre
tau = 15*t_UTC + h - s. Esse tau difere do T de Schureman (T = 180 + 15*t)
por 180 graus, e a coluna `shift` de cada constituinte compensa isso.
Exemplos: O1 = T + h - 2s + 90 = tau - s + 270 e M3 = 3T + 3h - 3s =
3*tau + 180. As fases g são referidas à hora legal UTC-3 (g = G - a*S/15,
S = 45 graus W), e a_i é a velocidade angular em graus/hora.

Constantes harmônicas: ajustadas por mínimos quadrados aos 1812 extremos
(preamares e baixa-mares) da Tábua das Marés 2026 do CHM/DHN para o Porto de
Itajaí, que usa 78 componentes. Ver ajuste_constantes_itajai.py. Com 48
componentes, o erro contra a tábua é de 1,7 cm RMS na altura (máx. 5,4 cm),
e a hora dos extremos erra 6 min na mediana. Validação cruzada entre meses
pares e ímpares dá o mesmo RMS, sem sinal de sobreajuste.

Em estofas (preamar ou baixa-mar longa e quase plana), `extremos` pode
achar ondulações de poucos mm que a tábua lista como um único extremo.

Limitações:
  - prevê só a maré astronômica. Vazão do rio Itajaí-Açu e maré
    meteorológica (vento sul, frentes frias) podem somar dezenas de cm;
  - as constantes reproduzem a tábua de 2026, que já é uma previsão. Fora de
    2026, a qualidade depende dos fatores nodais aproximados (o do L2 é o do
    M2; o nodal real do L2 também depende de p);
  - Sa e Ssa, ajustados num único ano, representam o ciclo sazonal
    embutido na tábua, não uma climatologia.
"""

from datetime import datetime, timedelta, timezone

import numpy as np

Z0 = 0.60  # nível médio acima do zero hidrográfico (m); sobrescrito pelo ajuste abaixo
TZ_FASES = 3.0  # horas a oeste de Greenwich a que as fases g se referem

# Números de Doodson: [tau, s, h, p, N', ps, shift_graus]
# e especificação nodal: {constituinte_base: expoente}; f = prod f_b^|n|, u = sum n*u_b
DOODSON = {
    # longo período
    'Sa': ([0, 0, 1, 0, 0, -1, 0], {}),
    'Ssa': ([0, 0, 2, 0, 0, 0, 0], {}),
    'Mm': ([0, 1, 0, -1, 0, 0, 0], {'Mm': 1}),
    'MSf': ([0, 2, -2, 0, 0, 0, 0], {'M2': -1}),
    'Mf': ([0, 2, 0, 0, 0, 0, 0], {'Mf': 1}),
    # diurnos
    '2Q1': ([1, -3, 0, 2, 0, 0, 270], {'O1': 1}),
    'Q1': ([1, -2, 0, 1, 0, 0, 270], {'O1': 1}),
    'RHO1': ([1, -2, 2, -1, 0, 0, 270], {'O1': 1}),
    'O1': ([1, -1, 0, 0, 0, 0, 270], {'O1': 1}),
    'P1': ([1, 1, -2, 0, 0, 0, 270], {}),
    'K1': ([1, 1, 0, 0, 0, 0, 90], {'K1': 1}),
    'J1': ([1, 2, 0, -1, 0, 0, 90], {'J1': 1}),
    'OO1': ([1, 3, 0, 0, 0, 0, 90], {'OO1': 1}),
    'M1': ([1, 0, 0, 1, 0, 0, 90], {'O1': 1}),  # nodal aproximado
    'S1': ([1, 1, -1, 0, 0, 1, 180], {}),  # radiacional
    # semidiurnos compostos
    'MNS2': ([2, -3, 2, 1, 0, 0, 0], {'M2': 2}),
    'MKS2': ([2, 0, 2, 0, 0, 0, 0], {'M2': 1, 'K2': 1}),
    'MSN2': ([2, 3, -2, -1, 0, 0, 0], {'M2': 2}),
    # semidiurnos
    '2N2': ([2, -2, 0, 2, 0, 0, 0], {'M2': 1}),
    'MU2': ([2, -2, 2, 0, 0, 0, 0], {'M2': 1}),
    'N2': ([2, -1, 0, 1, 0, 0, 0], {'M2': 1}),
    'NU2': ([2, -1, 2, -1, 0, 0, 0], {'M2': 1}),
    'M2': ([2, 0, 0, 0, 0, 0, 0], {'M2': 1}),
    'LAM2': ([2, 1, -2, 1, 0, 0, 180], {'M2': 1}),
    'L2': ([2, 1, 0, -1, 0, 0, 180], {'M2': 1}),  # aproximação
    'S2': ([2, 2, -2, 0, 0, 0, 0], {}),
    'K2': ([2, 2, 0, 0, 0, 0, 0], {'K2': 1}),
    '2SM2': ([2, 4, -4, 0, 0, 0, 0], {'M2': -1}),
    # terdiurnos
    'MO3': ([3, -1, 0, 0, 0, 0, 270], {'M2': 1, 'O1': 1}),    'M3': ([3, 0, 0, 0, 0, 0, 180], {'M2': 1.5}),
    'SO3': ([3, 1, -2, 0, 0, 0, 270], {'O1': 1}),
    'MK3': ([3, 1, 0, 0, 0, 0, 90], {'M2': 1, 'K1': 1}),
    'SK3': ([3, 3, -2, 0, 0, 0, 90], {'K1': 1}),
    # quarto-diurnos
    'MN4': ([4, -1, 0, 1, 0, 0, 0], {'M2': 2}),
    'M4': ([4, 0, 0, 0, 0, 0, 0], {'M2': 2}),
    'MS4': ([4, 2, -2, 0, 0, 0, 0], {'M2': 1}),
    'MK4': ([4, 2, 0, 0, 0, 0, 0], {'M2': 1, 'K2': 1}),
    'S4': ([4, 4, -4, 0, 0, 0, 0], {}),
    'SN4': ([4, 1, -2, 1, 0, 0, 0], {'M2': 1}),
    # sexto-diurnos
    '2MN6': ([6, -1, 0, 1, 0, 0, 0], {'M2': 3}),
    'M6': ([6, 0, 0, 0, 0, 0, 0], {'M2': 3}),
    '2MS6': ([6, 2, -2, 0, 0, 0, 0], {'M2': 2}),
    '2SM6': ([6, 4, -4, 0, 0, 0, 0], {'M2': 1}),
    'MSN6': ([6, 1, -2, 1, 0, 0, 0], {'M2': 2}),
    # quinto- e oitavo-diurnos
    '2MO5': ([5, -1, 0, 0, 0, 0, 270], {'M2': 2, 'O1': 1}),
    '2MK5': ([5, 1, 0, 0, 0, 0, 90], {'M2': 2, 'K1': 1}),
    'M8': ([8, 0, 0, 0, 0, 0, 0], {'M2': 4}),
    '3MS8': ([8, 2, -2, 0, 0, 0, 0], {'M2': 3}),
}

# Velocidades de tau, s, h, p, N', ps (graus/hora)
VELOCIDADES_DOODSON = np.array(
    [14.4920521, 0.5490165, 0.0410686, 0.0046418, 0.0022064, 0.0000020]
)

# Constantes harmônicas (H em m, g em graus, fuso UTC-3), geradas por
# ajuste_constantes_itajai.py a partir da Tábua das Marés 2026 (CHM/DHN).
CONSTITUENTES = {}  # preenchido abaixo

J2000 = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)


def velocidade(nome):
  """Velocidade angular do constituinte (graus/hora)."""
  return float(np.array(DOODSON[nome][0][:6]) @ VELOCIDADES_DOODSON)


def argumentos_astronomicos(dt_utc):
  """Retorna (tau, s, h, p, N', ps) em graus e os fatores nodais base {nome: (f, u)}."""
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
  nodal = {
      'M2': (1.0004 - 0.0373 * cosN + 0.0002 * cos2N, -2.14 * sinN),
      'O1': (1.0089 + 0.1871 * cosN - 0.0147 * cos2N, 10.80 * sinN - 1.34 * sin2N),
      'K1': (1.0060 + 0.1150 * cosN - 0.0088 * cos2N, -8.86 * sinN + 0.68 * sin2N),
      'K2': (1.0241 + 0.2863 * cosN + 0.0083 * cos2N, -17.74 * sinN + 0.68 * sin2N),
      'J1': (1.0129 + 0.1676 * cosN - 0.0170 * cos2N, -12.94 * sinN + 1.34 * sin2N),
      'OO1': (1.1027 + 0.6504 * cosN + 0.0317 * cos2N, -36.68 * sinN + 4.02 * sin2N),
      'Mm': (1.0000 - 0.1300 * cosN + 0.0013 * cos2N, 0.0),
      'Mf': (1.0429 + 0.4135 * cosN - 0.0040 * cos2N, -23.74 * sinN + 2.68 * sin2N),
  }
  return np.array([tau, s, h, p, -N, ps]), nodal


def termos(dt):
  """Para cada constituinte: (f, theta = V + u em graus, velocidade em graus/hora)."""
  args, nodal = argumentos_astronomicos(dt.astimezone(timezone.utc))
  out = {}
  for nome, (doodson, spec) in DOODSON.items():
    coef = np.array(doodson[:6])
    V = coef @ args + doodson[6]
    f, u = 1.0, 0.0
    for base, n in spec.items():
      fb, ub = nodal[base]
      f *= fb ** abs(n)
      u += n * ub
    out[nome] = (f, V + u, coef @ VELOCIDADES_DOODSON)
  return out


def prever_mare_itajai(dt):
  """Altura da maré astronômica (m acima do zero hidrográfico) para um datetime com fuso."""
  altura = Z0
  for nome, (f, theta, a) in termos(dt).items():
    if nome in CONSTITUENTES:
      H, g = CONSTITUENTES[nome]
      G = g + TZ_FASES * a  # fase referida a Greenwich
      altura += f * H * np.cos(np.radians(theta - G))
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


# --- Constantes ajustadas (geradas por ajuste_constantes_itajai.py) ---
# CONSTANTES-INICIO
Z0 = 0.5972
CONSTITUENTES = {
    'Sa': (0.0486, 54.59),
    'Ssa': (0.0021, 75.89),
    'Mm': (0.0028, 236.82),
    'MSf': (0.0416, 207.43),
    'Mf': (0.0009, 143.54),
    '2Q1': (0.0056, 42.47),
    'Q1': (0.0270, 43.42),
    'RHO1': (0.0012, 149.49),
    'O1': (0.1016, 75.37),
    'P1': (0.0177, 129.76),
    'K1': (0.0594, 138.60),
    'J1': (0.0023, 178.98),
    'OO1': (0.0025, 314.23),
    'M1': (0.0055, 117.73),
    'S1': (0.0101, 54.01),
    'MNS2': (0.0033, 46.34),
    'MKS2': (0.0044, 58.20),
    'MSN2': (0.0035, 229.12),
    '2N2': (0.0093, 131.37),
    'MU2': (0.0178, 94.85),
    'N2': (0.0424, 138.23),
    'NU2': (0.0045, 134.50),
    'M2': (0.2500, 68.01),
    'LAM2': (0.0018, 187.78),
    'L2': (0.0097, 303.17),
    'S2': (0.1726, 68.47),
    'K2': (0.0518, 57.63),
    '2SM2': (0.0015, 139.37),
    'MO3': (0.0229, 14.09),
    'M3': (0.0376, 180.35),
    'SO3': (0.0145, 79.44),
    'MK3': (0.0221, 58.48),
    'SK3': (0.0064, 225.80),
    'MN4': (0.0261, 58.09),
    'M4': (0.0615, 113.94),
    'MS4': (0.0366, 199.10),
    'MK4': (0.0100, 192.31),
    'S4': (0.0024, 189.08),
    'SN4': (0.0049, 155.04),
    '2MN6': (0.0016, 11.80),
    'M6': (0.0016, 17.19),
    '2MS6': (0.0052, 351.68),
    '2SM6': (0.0037, 32.09),
    'MSN6': (0.0013, 306.59),
    '2MO5': (0.0078, 232.56),
    '2MK5': (0.0050, 331.55),
    'M8': (0.0032, 193.69),
    '3MS8': (0.0031, 215.61),
}
# CONSTANTES-FIM


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
