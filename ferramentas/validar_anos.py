"""Validação fora da amostra entre anos: ajusta com algumas tábuas oficiais
(CHM) e mede o erro na tábua de um ano que ficou de fora.

    python ferramentas/validar_anos.py      (leva ~1 min)
"""
import csv, datetime as dt, os, sys
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import mare_itajai as m  # noqa: E402

arq = lambda ano: os.path.join(RAIZ, 'dados', f'tabua_mare_itajai_{ano}.csv')


def ler(caminho):
    L = list(csv.DictReader(open(caminho)))
    t = np.array([np.datetime64(dt.datetime.strptime(r['data_hora_local'], '%Y-%m-%d %H:%M'), 'm') for r in L])
    return t, np.array([float(r['altura_m']) for r in L])


def avaliar(M, t, h):
    """t em hora local. Devolve RMS de altura (cm) e |erro de horário| (min) dos extremos bem marcados."""
    r = h - M.altura(t)
    ext = M.extremos(t[0] - np.timedelta64(1, 'D'), t[-1] + np.timedelta64(1, 'D'))
    te = np.array([e[0] for e in ext]).astype('datetime64[s]')
    he = np.array([e[1] for e in ext])
    amp = np.minimum(np.abs(np.diff(he, prepend=np.nan)), np.abs(np.diff(he, append=np.nan)))
    j = np.array([np.argmin(np.abs(te - x)) for x in t.astype('datetime64[s]')])
    d = np.abs((te[j] - t.astype('datetime64[s]')) / np.timedelta64(1, 'm'))
    s = (d <= 90) & (amp[j] >= 0.2)
    return np.sqrt((r ** 2).mean()) * 100, np.median(d[s]), np.percentile(d[s], 90)


if __name__ == '__main__':
    for treino, teste in [((2024,), 2026), ((2025,), 2026), ((2024, 2025), 2026), ((2025, 2026), 2024)]:
        M = m.Mare([arq(a) for a in treino])
        rms, med, p90 = avaliar(M, *ler(arq(teste)))
        print(f'ajuste {"+".join(map(str, treino)):9s} -> tábua {teste}: altura RMS {rms:.1f} cm; '
              f'horário (bem marcados) mediana {med:.0f} min, 90 % <= {p90:.0f} min')
