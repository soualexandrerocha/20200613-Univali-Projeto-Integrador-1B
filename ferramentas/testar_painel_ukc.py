"""Confere o cálculo da folga da página (pagina/nucleo_ukc.js) contra um
cálculo independente em Python com mare_itajai.py.

    python ferramentas/testar_painel_ukc.py     (precisa de node)

Para vários casos (regras vigentes da NPCP-SC com o adicional do Ofício
755/2026 e regras alteradas; referenciais NR, outro zero e medida no instante;
com e sem FWA; manobra instantânea e longa) compara calado
corrigido, maré necessária e cada janela de início de manobra. Falha se a
diferença passar de 1 mm, se o número de janelas diferir ou se uma borda
diferir mais de 1 min.
"""
import json
import os
import subprocess
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'ferramentas'))
import gerar_pagina  # noqa: E402
import mare_itajai as m  # noqa: E402

MIN = np.timedelta64(1, 'm')
VIGENTES = {  # NPCP-SC + Res. SPI 013/2024 + Ofício 755/2026-DelItajaí
    'ce': ('Canal externo', 15, 'pct', 0.0), 'ci': ('Canal interno', 10, 'pct', 0.80),
    'b1': ('Bacia 1', 0.60, 'm', 0.80), 'b2': ('Bacia 2', 10, 'pct', 0.80), 'be': ('Berços', 0.60, 'm', 0.0),
}
CASOS = [
    dict(ini='2026-11-13T00:00', fim='2026-11-16T00:00', dur=60, margem=0.0, tav=11.30, tar=11.60,
         rref=1.025, rloc=1.012, fwa=None, trechos=VIGENTES,
         pontos=[('Externo', 'ce', 13.40, 'nr', None, None), ('Interno', 'ci', 13.10, 'nr', None, None),
                 ('Bacia 1', 'b1', 12.80, 'nr', None, None), ('Bacia 2', 'b2', 13.50, 'nr', None, None)]),
    dict(ini='2027-03-01T06:00', fim='2027-03-08T06:00', dur=0, margem=0.10, tav=11.8, tar=11.8,
         rref=1.025, rloc=1.000, fwa=280, trechos={**VIGENTES, 'ci': ('Canal interno', 0.9, 'm', 0.0)},
         pontos=[('Régua', 'ci', 10.95, 'outro', -1.896, None), ('Canal', 'ce', 13.6, 'nr', None, None),
                 ('Berço', 'be', 13.9, 'inst', None, '2027-02-27T10:00')]),
    dict(ini='2030-07-10T00:00', fim='2030-07-12T00:00', dur=150, margem=0.20, tav=11.8, tar=12.2,
         rref=1.020, rloc=1.015, fwa=None, trechos={k: (v[0], v[1], v[2], 0.0) for k, v in VIGENTES.items()},
         pontos=[('A', 'b2', 14.2, 'nr', None, None), ('B', 'be', 13.0, 'outro', 0.4, None)]),
]


def local_ms(s):
    return int((np.datetime64(s) - np.timedelta64(-3, 'h')).astype('datetime64[ms]').astype(np.int64))


def em_python(mare, c):
    tmax = max(c['tav'], c['tar'])
    if c['fwa']:
        tc = tmax + c['fwa'] / 1000 * (c['rref'] - c['rloc']) / 0.025
    else:
        tc = tmax * c['rref'] / c['rloc']
    nec = []
    for _, trecho, prof, ref, cota, inst in c['pontos']:
        if ref == 'nr':
            dnr = prof
        elif ref == 'outro':
            dnr = prof - cota
        else:
            dnr = prof - mare.altura(np.datetime64(inst))[0]
        _, valor, unidade, adicional = c['trechos'][trecho]
        faq = (valor / 100 * tc if unidade == 'pct' else valor) + adicional
        nec.append(tc + faq - dnr)
    hnec = max(nec) + c['margem']
    ini, fim = np.datetime64(c['ini']), np.datetime64(c['fim'])
    n = int((fim - ini) / MIN) + 1
    t = ini + np.arange(n + c['dur']) * MIN
    h = mare.altura(t)
    janela_min = np.lib.stride_tricks.sliding_window_view(h, c['dur'] + 1).min(axis=1)[:n]
    ok = janela_min >= hnec
    bordas = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
    janelas = [(str(t[a]), str(t[b - 1])) for a, b in zip(bordas[::2], bordas[1::2])]
    return tc, hnec, janelas


def main():
    mare = m.Mare()
    D = gerar_pagina.dados(mare)
    nucleo = open(os.path.join(RAIZ, 'pagina', 'nucleo_mare.js'), encoding='utf-8').read()
    ukc = open(os.path.join(RAIZ, 'pagina', 'nucleo_ukc.js'), encoding='utf-8').read()
    entradas = []
    for c in CASOS:
        entradas.append(dict(
            ini=local_ms(c['ini']), fim=local_ms(c['fim']), dur=c['dur'], margem=c['margem'],
            tav=c['tav'], tar=c['tar'], rref=c['rref'], rloc=c['rloc'],
            fwa=c['fwa'] if c['fwa'] else None,
            trechos={k: dict(nome=v[0], valor=v[1], unidade=v[2], adicional=v[3]) for k, v in c['trechos'].items()},
            pontos=[dict(nome=p[0], trecho=p[1], prof=p[2], ref=p[3], cota=p[4], inst=local_ms(p[5]) if p[5] else None)
                    for p in c['pontos']]))
    js = (nucleo + ukc + f"""
const MARE = criarMare({json.dumps(D, separators=(',', ':'))});
const nul = x => x === null ? NaN : x;
const E = {json.dumps(entradas)};
const out = E.map(e => {{
  e.fwa = nul(e.fwa); e.pontos.forEach(p => {{ p.cota = nul(p.cota); p.inst = nul(p.inst); }});
  const R = calcularFolga(MARE, e);
  return {{erros: R.erros, tc: R.tc, hnec: R.hnec, J: (R.J || []).map(j => [j.a, j.b])}};
}});
console.log(JSON.stringify(out));
""")
    res = json.loads(subprocess.run(['node', '-'], input=js, capture_output=True, text=True, check=True).stdout)
    falhou = False
    for i, (c, r) in enumerate(zip(CASOS, res), 1):
        tc, hnec, jp = em_python(mare, c)
        assert not r['erros'], r['erros']
        jj = [(str(np.datetime64(a, 'ms').astype('datetime64[m]') - np.timedelta64(3, 'h')),
               str(np.datetime64(b, 'ms').astype('datetime64[m]') - np.timedelta64(3, 'h'))) for a, b in r['J']]
        d_tc, d_h = abs(tc - r['tc']), abs(hnec - r['hnec'])
        # Bordas podem diferir em 1 min quando a maré empata com a necessária: o núcleo
        # JS interpola f e u entre nós e difere do UTide em até 0,02 mm.
        um = np.timedelta64(1, 'm')
        iguais = len(jj) == len(jp) and all(
            abs(np.datetime64(x) - np.datetime64(y)) <= um for a, b in zip(jp, jj) for x, y in zip(a, b))
        print(f'caso {i}: calado {tc:.3f} m (dif {d_tc * 1000:.3f} mm), maré necessária {hnec:.3f} m '
              f'(dif {d_h * 1000:.3f} mm), janelas {len(jp)} Python / {len(jj)} página: '
              f'{"iguais" if iguais else "DIFERENTES"}')
        if not iguais:
            for a, b in zip(jp, jj):
                if a != b:
                    print('   borda difere: Python', a, ' página', b)
        falhou |= d_tc > 1e-3 or d_h > 1e-3 or not iguais
    sys.exit(1 if falhou else 0)


if __name__ == '__main__':
    main()
