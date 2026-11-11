"""Extrai preamares/baixa-mares da Tábua das Marés (CHM/DHN) em PDF para CSV.

Uso:
    python ferramentas/extrair_tabua_chm.py dados/tabua_mare_porto_itajai_2024_CHM.pdf 2024 \
        dados/tabua_mare_itajai_2024.csv

Fonte do PDF: https://assets.marinha.mil.br/chm/sites/www.marinha.mil.br.chm/files/dados_de_mare/52_-_porto_de_itajai_2024_ok.pdf

Formato da tábua: 3 páginas x 4 meses; cada mês em 2 colunas (dias 1-16 e
17-fim), cada coluna com dia | HORA | ALT. As linhas ficam a só 4,7 pt umas
das outras, e o agrupamento de palavras padrão do pdfplumber funde linhas
vizinhas; por isso as palavras são remontadas a partir dos caracteres,
agrupados por linha de base exata.

Verificações (assert): 8 colunas HORA por página; todos os dias do mês
presentes, na ordem; uma altura para cada horário; horários estritamente
crescentes ao longo do ano.
"""

import calendar
import csv
import datetime as dt
import re
import sys

import pdfplumber


def palavras(pagina):
    """Palavras montadas a partir dos caracteres, por linha de base exata."""
    linhas = {}
    for ch in pagina.chars:
        if ch['text'].strip():
            linhas.setdefault(round(ch['top'], 1), []).append(ch)
    out = []
    for topo, chs in linhas.items():
        chs.sort(key=lambda c: c['x0'])
        atual = None
        for c in chs:
            if atual and c['x0'] - atual['x1'] < 1.0:
                atual['text'] += c['text']
                atual['x1'] = c['x1']
            else:
                atual = {'text': c['text'], 'x0': c['x0'], 'x1': c['x1'], 'top': topo}
                out.append(atual)
    return out


def extrair(arq_pdf, ano):
    linhas = []
    for ip, pagina in enumerate(pdfplumber.open(arq_pdf).pages):
        ws = palavras(pagina)
        horas = sorted([w for w in ws if w['text'] == 'HORA'], key=lambda w: w['x0'])
        assert len(horas) == 8, (ip, len(horas))
        y_cab = horas[0]['top']
        for ic, hcol in enumerate(horas):
            mes = ip * 4 + ic // 2 + 1
            x = hcol['x0']
            abaixo = [w for w in ws if w['top'] > y_cab + 5]
            dias = sorted((w['top'], int(w['text'])) for w in abaixo
                          if re.fullmatch(r'\d\d', w['text']) and x - 16 <= w['x0'] <= x - 4)
            horarios = [w for w in abaixo if re.fullmatch(r'\d{4}', w['text']) and x + 12 <= w['x0'] <= x + 26]
            alturas = [w for w in abaixo if re.fullmatch(r'-?\d\.\d', w['text']) and x + 28 <= w['x0'] <= x + 46]
            esperado = (list(range(1, 17)) if ic % 2 == 0
                        else list(range(17, calendar.monthrange(ano, mes)[1] + 1)))
            assert [d for _, d in dias] == esperado, (mes, ic, dias)
            for hw in horarios:
                alt = [a for a in alturas if abs(a['top'] - hw['top']) < 1.0]
                assert len(alt) == 1, (mes, hw)
                dia = [d for (y, d) in dias if y <= hw['top'] + 4][-1]  # rótulo do dia no topo do bloco
                t = dt.datetime(ano, mes, dia, int(hw['text'][:2]), int(hw['text'][2:]))
                linhas.append((t, hw['top'], float(alt[0]['text'])))
    linhas.sort(key=lambda r: (r[0].date(), r[1]))
    for a, b in zip(linhas, linhas[1:]):
        assert b[0] > a[0], (a, b)
    return [(t, h) for t, _, h in linhas]


if __name__ == '__main__':
    arq_pdf, ano, arq_csv = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    dados = extrair(arq_pdf, ano)
    with open(arq_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['data_hora_local', 'altura_m'])
        for t, h in dados:
            w.writerow([t.strftime('%Y-%m-%d %H:%M'), f'{h:.1f}'])
    print(f'{len(dados)} extremos de {dados[0][0]} a {dados[-1][0]} -> {arq_csv}')
