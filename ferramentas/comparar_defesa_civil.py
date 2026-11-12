"""Compara o modelo com o nível MEDIDO nas réguas telemétricas da Defesa Civil
de Itajaí (últimas 12 h, leituras a cada 10 min).

    python ferramentas/comparar_defesa_civil.py            # baixa os dados atuais
    python ferramentas/comparar_defesa_civil.py app.json   # usa um arquivo salvo

Fonte: https://monitoramento.defesacivil.itajai.sc.gov.br/data/current/app.json
(o mesmo JSON público que alimenta o portal de monitoramento).

As réguas têm zero próprio (não o NR), por isso, para cada estação, ajusta-se
nível = a + b * maré_prevista(t - atraso) e informa-se atraso, ganho b,
correlação e resíduo. Estações longe da foz mostram a maré atrasada e
amortecida; estações sem resposta à maré aparecem com ganho ~0.
"""
import json, os, sys, urllib.request
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'https://monitoramento.defesacivil.itajai.sc.gov.br/data/current/app.json'


def carregar(arq=None):
    if arq:
        return json.load(open(arq))
    with urllib.request.urlopen(URL, timeout=30) as r:
        return json.load(r)


if __name__ == '__main__':
    arq = sys.argv[1] if len(sys.argv) > 1 else None
    sys.path.insert(0, RAIZ)
    import mare_itajai as m
    M = m.Mare()
    d = carregar(arq)
    print('dados gerados em', d.get('gerado_em'))
    for r in d['dados']['rios']:
        s = r.get('serie_12_h') or []
        if len(s) < 20:
            continue
        t = np.array([np.datetime64(x['medido_em'][:19], 's') for x in s])
        y = np.array([x.get('nivel_rio_m', np.nan) for x in s], float)
        ok = np.isfinite(y)
        t, y = t[ok], y[ok]
        melhor = None
        for atraso in range(-120, 181):
            hp = M.altura_utc((t - np.timedelta64(atraso, 'm')).astype('datetime64[m]'))
            A = np.c_[np.ones_like(hp), hp]
            c = np.linalg.lstsq(A, y, rcond=None)[0]
            rms = np.sqrt(np.mean((y - A @ c) ** 2))
            if melhor is None or rms < melhor[0]:
                melhor = (rms, atraso, c, np.corrcoef(hp, y)[0, 1])
        rms, atraso, c, cc = melhor
        print(f"{r['codigo']:11s} {r['nome'][:48]:48s} variação {y.max() - y.min():4.2f} m | "
              f"corr {cc:+.2f} | atraso {atraso:+4d} min | ganho {c[1]:5.2f} | resíduo {rms * 100:4.1f} cm")
