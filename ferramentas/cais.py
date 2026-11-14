"""Posição em relação ao cais do Porto de Itajaí (berços 1 a 4).

Lê `dados/cais_porto_itajai.json` e, para um ponto (lat, lon), devolve:

- `s_cais_m`: distância ao longo do cais a partir da quina entre os berços
  2 e 3, positiva para montante (berços 3 e 4) e negativa para jusante
  (berços 1 e 2);
- `afast_m`: distância à linha do cais, positiva para o lado do rio;
- `berco`: o berço em frente (1 a 4), qualquer que seja `afast_m`; vazio
  fora da extensão do cais.

As divisas entre os berços 1|2 e 3|4 são estimadas (±50 m); veja o campo
`incerteza` do JSON.

Uso:
    python ferramentas/cais.py -26.89937 -48.66796
    python ferramentas/cais.py trajetoria.csv saida.csv   # CSV com colunas lat e lon
"""

import csv
import json
import math
import sys
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / 'dados' / 'cais_porto_itajai.json'
FOZ = (-48.6516, -26.9085)  # DC01 (CEPSUL), como em larguras_carta1841.py
COS = math.cos(math.radians(-26.88))
M_GRAU = 111.2e3

CAIS = json.loads(ARQ.read_text(encoding='utf-8'))
_Q = {k: (v['x'], v['y']) for k, v in CAIS['quinas'].items()}


def xy(lat, lon):
    """Graus -> metros a leste e ao norte de DC01."""
    return (lon - FOZ[0]) * M_GRAU * COS, (lat - FOZ[1]) * M_GRAU


def _unit(p, q):
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    return (q[0] - p[0]) / L, (q[1] - p[1]) / L, L


def posicao(lat, lon):
    x, y = xy(lat, lon)
    B = _Q['B']
    # trecho de montante (B -> C) e de jusante (B -> A), ambos a partir de B
    ux, uy, _ = _unit(B, _Q["C"])
    vx, vy, _ = _unit(B, _Q["A"])
    sc = (x - B[0]) * ux + (y - B[1]) * uy
    sa = (x - B[0]) * vx + (y - B[1]) * vy
    if sc >= 0:   # a montante de B: berços 3 e 4
        s = sc
        afast = (x - B[0]) * uy - (y - B[1]) * ux     # à direita de B->C = rio
    else:         # a jusante de B: berços 1 e 2
        s = -sa
        afast = -(x - B[0]) * vy + (y - B[1]) * vx    # à esquerda de B->A = rio
    berco = next((b['berco'] for b in CAIS['bercos']
                  if b['s_cais_m'][0] <= s <= b['s_cais_m'][1]), None)
    return {'s_cais_m': round(s, 1), 'afast_m': round(afast, 1), 'berco': berco}


def main():
    a = sys.argv[1:]
    if len(a) == 2 and not a[0].endswith('.csv'):
        print(posicao(float(a[0]), float(a[1])))
        return
    if len(a) != 2:
        raise SystemExit(__doc__)
    with open(a[0], newline='', encoding='utf-8') as f:
        linhas = list(csv.DictReader(f))
    colunas = list(linhas[0]) + ['s_cais_m', 'afast_m', 'berco']
    with open(a[1], 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        for r in linhas:
            p = posicao(float(r['lat']), float(r['lon']))
            w.writerow({**r, **{k: '' if v is None else v for k, v in p.items()}})


if __name__ == '__main__':
    main()
