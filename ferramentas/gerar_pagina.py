"""Gera pagina/mare_itajai.html: página autossuficiente (abre no navegador ou
celular, sem Python nem internet além das fontes) com o mesmo modelo de
mare_itajai.py.

    python ferramentas/gerar_pagina.py

Para cada componente k a página recebe a_k, b_k e frq_k e, a cada 30 dias de
2015 a 2050, o fator nodal f_k e a fase astronômica r_k = (V+u)_k - frq_k*t.
Entre nós, f e r são interpolados linearmente (erro máximo < 0,01 mm em
altura frente ao cálculo completo do UTide). O teste
ferramentas/testar_pagina.js confere o JavaScript contra o Python.
"""

import json
import os
import sys

import numpy as np
from utide._time_conversion import _normalize_time
from utide.harmonics import FUV

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import mare_itajai as m  # noqa: E402

INICIO, FIM, PASSO_DIAS = '2015-01-01', '2051-01-01', 30


def dados(mare):
    n = len(mare.nomes)
    t0 = np.datetime64(INICIO + 'T00:00')
    dias = int((np.datetime64(FIM) - np.datetime64(INICIO)) / np.timedelta64(1, 'D'))
    nos = t0 + np.arange(0, dias + PASSO_DIAS, PASSO_DIAS).astype('timedelta64[D]')
    F, U, V = FUV(_normalize_time(nos.astype('datetime64[m]'), None), mare.tref, mare.lind, m.LAT, [0, 0, 0, 0])
    horas = (nos - t0) / np.timedelta64(1, 'h')
    r = (U + V) - np.outer(horas, mare.frq)
    r = np.unwrap(2 * np.pi * r, axis=0) / (2 * np.pi)  # contínuo para interpolar
    r -= np.floor(r[0])  # inteiros de ciclo não importam
    return {
        'z0': round(float(mare.z0), 5),
        'nomes': mare.nomes,
        'frq': [float(x) for x in mare.frq],
        'a': [round(float(x), 6) for x in mare.x[1:n + 1]],
        'b': [round(float(x), 6) for x in mare.x[n + 1:]],
        't0_ms': int(t0.astype('datetime64[ms]').astype(np.int64)),
        'passo_h': PASSO_DIAS * 24,
        'f': np.rint(F * 1e5).astype(int).tolist(),
        'r': np.rint(r * 1e6).astype(int).tolist(),
    }


if __name__ == '__main__':
    d = dados(m.Mare())
    pasta = os.path.join(RAIZ, 'pagina')
    modelo = open(os.path.join(pasta, 'modelo.html'), encoding='utf-8').read()
    nucleo = open(os.path.join(pasta, 'nucleo_mare.js'), encoding='utf-8').read()
    html = (modelo.replace('/*NUCLEO*/', nucleo)
                  .replace('/*DADOS*/', json.dumps(d, separators=(',', ':'))))
    saida = os.path.join(pasta, 'mare_itajai.html')
    with open(saida, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'{saida}: {len(html) / 1e3:.0f} kB, {len(d["f"])} nós, {len(d["nomes"])} componentes')
