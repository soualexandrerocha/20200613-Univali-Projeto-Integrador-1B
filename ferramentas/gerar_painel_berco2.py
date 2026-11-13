"""Gera pagina/berco2.html: painéis interativos da corrente e da tensão no
Berço 2, autossuficientes (abrem no navegador ou no celular, sem Python).

    python ferramentas/gerar_painel_berco2.py

A página recebe:
  - os dados da maré (os mesmos de pagina/mare_itajai.html, via
    gerar_pagina.dados) e o núcleo pagina/nucleo_mare.js;
  - os parâmetros físicos de cisalhamento_berco2_zp21.py (profundidade,
    largura, atrito, lambda, vazão, propagação da maré);
  - as séries de nível da Defesa Civil de Itajaí acumuladas em
    dados/niveis/, com o ajuste de cada estação
    (razão de amplitude, atraso, zero da régua e tendência).

O modelo físico é recalculado no navegador, então os controles da página
(data, vazão, trecho de enchimento da maré, profundidade) mudam todos os painéis.
"""

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'ferramentas'))

import plotly.graph_objects as go  # noqa: E402

go.Figure.show = lambda *a, **k: None  # importar o script do berço não abre figura
import analise_propagacao_mare as ap  # noqa: E402
import cisalhamento_berco2_zp21 as cb  # noqa: E402
import curva_chave_blumenau as ccb  # noqa: E402
import gerar_pagina  # noqa: E402

ESTACOES_COM_MARE = ('DC01', 'DC11', 'BLU', 'DC03', 'DC04', 'DC06', 'DC09')


def parametros():
    return {
        'prof_zh': cb.PROF_ZH,
        'b_rio': cb.B_RIO,
        'q_rio': cb.Q_RIO,
        'f_darcy': cb.F_DARCY,
        'lambda': cb.LAMBDA,
        'rho': cb.RHO,
        'g': cb.G,
        'pontos_acu': cb.PONTOS_ACU,
        'x_salto_km': cb.X_SALTO_KM,
        'l_ef_km': round(float(cb.L_EFETIVO) / 1e3, 2),
        'l_prisma_km': round(float(cb.L_PRISMA) / 1e3, 2),
        'q_baixa': cb.Q_BAIXA, 'sigma_baixa': cb.SIGMA_BAIXA, 'h_baixa': cb.H_SUP_BAIXA,
        'q_alta': cb.Q_ALTA, 'sigma_alta': cb.SIGMA_ALTA, 'h_alta': cb.H_SUP_ALTA,
        'secoes': cb.SECOES,
        'curva_blumenau': dict(zip(('a', 'h0', 'b', 'erro_log'), ccb.ajustar())),
        'faixa_curva_m': ccb.faixa_cotas(),
        'periodo_curva': ccb.PERIODO,
        'razao_areas': ccb.RAZAO_AREAS_PORTO,
        'razao_areas_faixa': ccb.RAZAO_AREAS_FAIXA,
        'atraso_fluxo_h': round(float(cb.ATRASO_FLUXO_S) / 3600, 3),
        'no_ms': cb.NO_PARA_MS,
    }


def observacoes():
    series, meta = ap.ler()
    saida = []
    for c in ESTACOES_COM_MARE:
        if c not in series:
            continue
        s = series[c]
        r, atraso, rms = ap.ajustar(s)
        t, h = s[:, 0], s[:, 1]
        eta = ap._MARE.altura_utc(np.array(t - 60 * atraso, dtype='int64').astype('datetime64[s]'))
        tm = float(t.mean())
        A = np.c_[eta, np.ones_like(eta), (t - tm) / 86400]
        coef, *_ = np.linalg.lstsq(A, h, rcond=None)
        x = ap.distancia_km(meta[ap.REFERENCIA], meta[c])
        item = {
            'codigo': c, 'nome': meta[c][0], 'dist_km': round(float(x), 1),
            'r': round(r, 3), 'atraso_min': atraso, 'rms_cm': round(rms * 100, 1),
            'c0': round(float(coef[1]), 4), 'c1': round(float(coef[2]), 5), 'tm_ms': int(tm * 1000),
            't0_ms': int(t[0] * 1000), 'dt_s': np.diff(t).astype(int).tolist(),
            'h_cm': np.rint(h * 100).astype(int).tolist(),
        }
        if c != ap.REFERENCIA and ap.R_MIN <= r < 1 and atraso > 0:
            L, tq = ap.comprimento_efetivo(r, atraso, x)
            item['l_ef_km'] = round(float(L), 1)
            item['atraso_fluxo_h'] = round(float(tq) / 3600, 2)
        saida.append(item)
    ini = min(o['t0_ms'] for o in saida)
    fim = max(o['t0_ms'] + 1000 * sum(o['dt_s']) for o in saida)
    return {'estacoes': saida, 'ini_ms': ini, 'fim_ms': fim}


if __name__ == '__main__':
    mare = ap._MARE = cb.MARE  # reaproveita o ajuste já feito ao importar o script do berço
    d = gerar_pagina.dados(mare)
    pasta = os.path.join(RAIZ, 'pagina')
    modelo = open(os.path.join(pasta, 'modelo_berco2.html'), encoding='utf-8').read()
    nucleo = open(os.path.join(pasta, 'nucleo_mare.js'), encoding='utf-8').read()
    obs = observacoes()
    with open(os.path.join(RAIZ, 'dados', 'mapa_itajai_acu.json')) as f:
        mapa = json.load(f)
    gerado = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    html = (modelo.replace('/*NUCLEO*/', nucleo)
                  .replace('/*DADOS*/', json.dumps(d, separators=(',', ':')))
                  .replace('/*PARAM*/', json.dumps(parametros(), separators=(',', ':')))
                  .replace('/*OBS*/', json.dumps(obs, separators=(',', ':')))
                  .replace('/*MAPA*/', json.dumps(mapa, separators=(',', ':')))
                  .replace('/*GERADO*/', json.dumps(gerado)))
    saida = os.path.join(pasta, 'berco2.html')
    with open(saida, 'w', encoding='utf-8') as f:
        f.write(html)
    n = sum(len(o['h_cm']) for o in obs['estacoes'])
    print(f'{saida}: {len(html) / 1e3:.0f} kB; {len(obs["estacoes"])} estações, {n} leituras')
