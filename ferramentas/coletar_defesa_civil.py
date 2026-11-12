"""Acumula o nível medido pelas réguas da Defesa Civil de Itajaí.

    python ferramentas/coletar_defesa_civil.py              # baixa os dados atuais
    python ferramentas/coletar_defesa_civil.py app.json     # importa um arquivo salvo

O JSON público do monitoramento só guarda as últimas 12 h (leituras a cada
10 min). Rodando esta coleta a cada 6 h, as janelas se sobrepõem e nada se
perde. Cada execução acrescenta, sem duplicar:

  dados/defesa_civil/niveis_rios.csv    medido_em_utc, codigo, nome, nivel_m
  dados/defesa_civil/meteorologia.csv   leitura do instante (vento, pressão...)

Fonte: https://monitoramento.defesacivil.itajai.sc.gov.br/data/current/app.json
"""
import csv, json, os, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, 'dados', 'defesa_civil')
URL = 'https://monitoramento.defesacivil.itajai.sc.gov.br/data/current/app.json'
CAMPOS_MET = ['medido_em_utc', 'codigo', 'pressao_atmosferica_hpa', 'velocidade_vento_kmh',
              'direcao_vento_graus', 'velocidade_maxima_vento_6_h_kmh', 'temperatura_c', 'umidade_percentual']


def acrescentar(arq, cabecalho, linhas, chave):
    """Acrescenta linhas novas (pela chave) e mantém o arquivo ordenado."""
    existentes = {}
    if os.path.exists(arq):
        with open(arq, newline='') as f:
            for r in csv.DictReader(f):
                existentes[chave(r)] = r
    n0 = len(existentes)
    for r in linhas:
        existentes.setdefault(chave(r), r)
    with open(arq, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cabecalho, lineterminator='\n')
        w.writeheader()
        for k in sorted(existentes):
            w.writerow(existentes[k])
    return len(existentes) - n0, len(existentes)


def main(arq=None):
    if arq:  # importa um app.json salvo
        d = json.load(open(arq))
    else:
        with urllib.request.urlopen(URL, timeout=60) as r:
            d = json.load(r)
    os.makedirs(PASTA, exist_ok=True)
    niveis = []
    for e in d['dados'].get('rios', []):
        for x in e.get('serie_12_h') or []:
            if x.get('nivel_rio_m') is not None:
                niveis.append({'medido_em_utc': x['medido_em'][:19], 'codigo': e['codigo'],
                               'nome': e['nome'], 'nivel_m': x['nivel_rio_m']})
    novos, total = acrescentar(os.path.join(PASTA, 'niveis_rios.csv'),
                               ['medido_em_utc', 'codigo', 'nome', 'nivel_m'], niveis,
                               lambda r: (r['medido_em_utc'], r['codigo']))
    met = [{'medido_em_utc': e['medido_em'][:19], 'codigo': e['codigo'],
            **{k: e.get(k) for k in CAMPOS_MET[2:]}}
           for e in d['dados'].get('meteorologia', []) if e.get('medido_em')]
    novos_m, total_m = acrescentar(os.path.join(PASTA, 'meteorologia.csv'), CAMPOS_MET, met,
                                   lambda r: (r['medido_em_utc'], r['codigo']))
    print(f"gerado_em {d.get('gerado_em')}: +{novos} leituras de nível (total {total}), "
          f"+{novos_m} de meteorologia (total {total_m})")


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
