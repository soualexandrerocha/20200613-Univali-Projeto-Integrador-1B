"""Extrai a Tábua de Maré de Itajaí 2026 da EPAGRI (PDF) para CSV.

    python ferramentas/extrair_tabua_epagri.py dados/tabua_mare_itajai_2026_EPAGRI.pdf dados/tabua_mare_itajai_2026_epagri.csv

Layout: 4 páginas x 3 meses, 5 colunas por mês. Cada dia começa com um
cabeçalho "d/m" e as colunas continuam umas nas outras (o fim de uma coluna
segue no topo da próxima). O tipo (PM/BM) é o símbolo da tábua; em 55 casos
ele contradiz as alturas vizinhas, por isso a comparação não depende dele.
"""
import re, sys, csv, datetime as dt, collections
import pdfplumber
ANO = 2026
regs = []
dia = None
for ip, p in enumerate(pdfplumber.open(sys.argv[1]).pages):
    ws = p.extract_words(x_tolerance=1.5)
    hx = sorted({round(w['x0']) for w in ws if w['text'] == 'Hora'})
    assert len(hx) == 15, hx
    ycab = max(w['top'] for w in ws if w['text'] == 'Hora')
    bordas = [x - 6 for x in hx] + [p.width]
    for k in range(15):
        col = [w for w in ws if bordas[k] <= w['x0'] < bordas[k + 1] and w['top'] > ycab + 3]
        linhas = collections.defaultdict(list)
        for w in col: linhas[round(w['top'])].append(w)
        for y in sorted(linhas):
            toks = [w['text'] for w in sorted(linhas[y], key=lambda w: w['x0'])]
            s = ' '.join(toks)
            mdia = re.search(r'\b(\d{1,2})/(\d{1,2})\b', s)
            if mdia:
                dia = dt.date(ANO, int(mdia.group(2)), int(mdia.group(1))); continue
            mt = re.fullmatch(r'(\d\d):(\d\d)\s*([▲▼])\s*(-?\d,\d)', s)
            if mt:
                assert dia, (ip, k, s)
                regs.append((dt.datetime.combine(dia, dt.time(int(mt[1]), int(mt[2]))), mt[3], float(mt[4].replace(',', '.'))))
            elif s.strip() and not re.fullmatch(r'[○◐●◑ ]+', s):
                print('ignorado:', ip, k, repr(s))
regs.sort()
for a, b in zip(regs, regs[1:]): assert b[0] > a[0], (a, b)
dias = collections.Counter(r[0].date() for r in regs)
print(len(regs), 'extremos;', len(dias), 'dias;', sorted(collections.Counter(dias.values()).items()))
alt = sum(1 for a, b in zip(regs, regs[1:]) if a[1] == b[1]); print('tipos repetidos em sequência:', alt)
with open(sys.argv[2], 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['data_hora_local', 'tipo', 'altura_m'])
    for t, s, h in regs: w.writerow([t.strftime('%Y-%m-%d %H:%M'), 'PM' if s == '▲' else 'BM', f'{h:.1f}'])
