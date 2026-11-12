"""Confere o JavaScript da página (pagina/mare_itajai.html) contra mare_itajai.py.

    python ferramentas/testar_pagina.py     (precisa de node)

Compara alturas em 3000 instantes aleatórios de 2015-2050 e os extremos de 20
janelas de 2 dias. Falha se a diferença passar de 1 mm ou 1 min.
"""
import json, os, re, subprocess, sys
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import mare_itajai as m  # noqa: E402

html = open(os.path.join(RAIZ, 'pagina', 'mare_itajai.html'), encoding='utf-8').read()
script = html[html.index('<script>') + 8:]
nucleo = script[:script.index('const FUSO_MS')]  # criarMare + dados

mare = m.Mare()
rng = np.random.default_rng(0)
ini, fim = np.datetime64('2015-01-05T00:00'), np.datetime64('2050-12-25T00:00')
span = int((fim - ini) / np.timedelta64(1, 'm'))
t = ini + np.sort(rng.integers(0, span, 3000)).astype('timedelta64[m]')
h_py = mare.altura_utc(t)
ms = t.astype('datetime64[ms]').astype(np.int64)
janelas = (ini + np.sort(rng.integers(0, span, 20)).astype('timedelta64[m]'))

js = nucleo + f"""
const T = {json.dumps(ms.tolist())};
const J = {json.dumps(janelas.astype('datetime64[ms]').astype(np.int64).tolist())};
console.log(JSON.stringify({{h: T.map(MARE.altura), e: J.map(j => MARE.extremos(j, j + 2*86400e3))}}));
"""
out = json.loads(subprocess.run(['node', '-'], input=js, capture_output=True, text=True, check=True).stdout)
dh = np.abs(np.array(out['h']) - h_py).max()
print(f'alturas: diferença máxima {dh * 1000:.4f} mm')
pior_t = pior_h = 0
for j, ej in zip(janelas, out['e']):
    loc = j - np.timedelta64(3, 'h')  # extremos() do Python recebe hora local
    ep = [e for e in mare.extremos(loc, loc + np.timedelta64(2, 'D'))]
    assert len(ep) == len(ej), (j, len(ep), len(ej))
    for (tp, hp, tipo), e in zip(ep, ej):
        tj = np.datetime64(int(e['t']), 'ms') - np.timedelta64(3, 'h')
        assert e['tipo'] == tipo
        pior_t = max(pior_t, abs((tj - tp) / np.timedelta64(1, 's')))
        pior_h = max(pior_h, abs(e['h'] - hp))
print(f'extremos: diferença máxima {pior_t:.0f} s, {pior_h * 1000:.3f} mm')
assert dh < 1e-3 and pior_t <= 60 and pior_h < 1e-3
print('OK')
