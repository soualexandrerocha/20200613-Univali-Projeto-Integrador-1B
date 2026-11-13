"""Vazão a montante do Itajaí-Açu, da telemetria da ANA (usinas Salto Pilão).

Uso:
    python vazao_montante.py --so-coletar   # baixa e grava (usado no GitHub Actions)
    python vazao_montante.py                # baixa, grava e resume
    python vazao_montante.py --offline      # só resume o que já está gravado

Por que: a vazão do rio no porto não é medida. As usinas hidrelétricas Salto
Pilão, na parte alta do Itajaí-Açu, reportam vazão a cada hora pelo serviço de
telemetria da ANA (DadosHidrometeorologicos), enquanto as estações da rede
nacional da ANA na bacia não têm dados recentes. Cada coleta traz os últimos
JANELA_DIAS dias (o serviço devolveu pelo menos 12 dias), então a primeira
execução já preenche o passado e as seguintes só acrescentam o que é novo.

Estações (vazão em m³/s, nível em cm):
  83461000  Salto Pilão Jusante, no Itajaí-Açu, abaixo do encontro dos três braços
  83059000  Itajaí do Oeste;  83270000  Itajaí do Sul (Aurora);
  83349600  Itajaí do Norte (Boiteux)
A vazão de Salto Pilão Jusante é o piso do que chega a Blumenau; a diferença
vem dos afluentes de baixo (não medidos aqui).

Horários: a ANA publica em hora de Brasília (UTC-3); conferido contra o
AlertaBlu, com correlação de 0,99 para esse deslocamento. Os arquivos gravam
UTC, como dados/niveis/.

Grava um arquivo novo por coleta em dados/vazao_montante/
(AAAA-MM-DDTHHMMZ.csv), nunca edita um existente, e a leitura descarta
repetições, pelo mesmo motivo de dados/niveis/: evitar conflitos de merge.
Só o workflow de coleta commita esses arquivos (ver CLAUDE.md).

Verificação (30/10 a 13/11/2026, 341 pares horários): o nível da PCH Salto
Jusante (ANA 83800010, ~7 cm acima do AlertaBlu), passado pelas curvas-chave de
Blumenau por período (ferramentas/curva_chave_blumenau.py), acompanha a vazão de
Salto Pilão Jusante com correlação de 0,985 e defasagem de ~2 h (a de melhor
correlação, em passos de 2 h). Razão Blumenau / Salto Pilão (mediana; P10-P90):
  1939-1985 0,88 (0,77-1,04)  <- menos água em Blumenau que a montante: não serve
  1990-2001 1,21;  2002-2007 1,15;  2008-2010 1,23;  2011 1,14;
  2012-2014 1,07 (0,96-1,24), de 1,04 a 1,10 nas três faixas de vazão: a mais
  estável, por isso o padrão. O acréscimo de ~7% é o dos afluentes de baixo.
Com o nível do AlertaBlu, que é a entrada do painel, nos 3 dias estáveis de 11 a
13/11 (32 leituras), a razão é de 0,96 para a curva de 2012-2014 e de 1,00 para a
de 2002-2007: abaixo de 1 não é possível, então a curva padrão pode estar ~5%
baixa, e a escolha entre as curvas de 2002 a 2014 não se resolve com 3 dias.
Rodar `python vazao_montante.py --offline` refaz a tabela com os dados novos.

Limitações: a "vazão" é a que a usina reporta; não sei se inclui a água
vertida além da turbinada. As leituras podem ser revisadas depois pela ANA, e
a coleta mantém a primeira que viu.
"""

import csv
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent / 'dados' / 'vazao_montante'
CABECALHO = ['codigo', 'nome', 'data_hora_utc', 'vazao_m3s', 'nivel_cm']
URL = ('https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos'
       '?codEstacao={cod}&dataInicio={ini:%d/%m/%Y}&dataFim={fim:%d/%m/%Y}')
ESTACOES = {
    '83461000': 'UHE Salto Pilão Jusante (Itajaí-Açu)',
    '83059000': 'UHE Salto Pilão, Itajaí do Oeste',
    '83270000': 'UHE Salto Pilão, Itajaí do Sul (Aurora)',
    '83349600': 'UHE Salto Pilão, Itajaí do Norte (Boiteux)',
}
JANELA_DIAS = 14
UTC_MENOS_3 = timedelta(hours=3)  # hora local + 3 h = UTC
TENTATIVAS, TIMEOUT_S, PRAZO_TOTAL_S = 3, 100, 600


def _baixar_estacao(cod, agora, prazo):
  """Linhas (data_hora_utc, vazao, nivel) da estação; levanta OSError se não houver resposta."""
  url = URL.format(cod=cod, ini=agora - timedelta(days=JANELA_DIAS), fim=agora)
  req = urllib.request.Request(url, headers={'User-Agent': 'projeto-academico-mare/1.0'})
  for tentativa in range(TENTATIVAS):
    if time.monotonic() > prazo:
      raise OSError('prazo total esgotado')
    try:
      xml = urllib.request.urlopen(req, timeout=TIMEOUT_S).read().decode('utf-8', 'ignore')
      break
    except OSError:
      if tentativa == TENTATIVAS - 1:
        raise
      time.sleep(10 * 2**tentativa)
  linhas = []
  for bloco in re.findall(r'<DadosHidrometereologicos[^>]*>(.*?)</DadosHidrometereologicos>', xml, re.S):
    g = dict(re.findall(r'<(\w+)>([^<]*)</\1>', bloco))
    if not g.get('Vazao', '').strip():
      continue
    local = datetime.strptime(g['DataHora'].strip(), '%Y-%m-%d %H:%M:%S')
    nivel = g.get('Nivel', '').strip()
    linhas.append(((local + UTC_MENOS_3).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   float(g['Vazao']), float(nivel) if nivel else None))
  return linhas


def _linhas():
  """Todas as leituras gravadas, sem repetições."""
  vistas = {}
  for arq in sorted(PASTA.glob('*.csv')):
    with arq.open() as f:
      for r in csv.DictReader(f):
        vistas.setdefault((r['codigo'], r['data_hora_utc']), r)
  return vistas


def coletar(agora=None):
  """Grava as leituras novas num arquivo novo; retorna (quantas, caminho ou None, estações com falha)."""
  agora = agora or datetime.now(timezone.utc)
  PASTA.mkdir(parents=True, exist_ok=True)
  existentes = set(_linhas())
  novas, falhas = [], []
  prazo = time.monotonic() + PRAZO_TOTAL_S
  for cod, nome in ESTACOES.items():
    try:
      for t, q, n in _baixar_estacao(cod, agora, prazo):
        if (cod, t) not in existentes:
          existentes.add((cod, t))
          novas.append([cod, nome, t, f'{q:.2f}', '' if n is None else f'{n:.0f}'])
    except OSError as erro:
      falhas.append(cod)
      print(f'Aviso: {cod} ({nome}) não respondeu: {erro}')
  if not novas:
    return 0, None, falhas
  arq = PASTA / f'{agora:%Y-%m-%dT%H%MZ}.csv'
  n = 1
  while arq.exists():
    arq = PASTA / f'{agora:%Y-%m-%dT%H%MZ}_{n}.csv'
    n += 1
  with arq.open('w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(CABECALHO)
    w.writerows(sorted(novas, key=lambda r: (r[0], r[2])))
  return len(novas), arq, falhas


def ler():
  """{codigo: [(t_utc em segundos, vazão m³/s), ...]} ordenado no tempo."""
  saida = {}
  for (cod, t), r in _linhas().items():
    ts = datetime.strptime(t, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
    saida.setdefault(cod, []).append((ts, float(r['vazao_m3s'])))
  return {c: sorted(v) for c, v in saida.items()}


def resumo():
  dados = ler()
  if not dados:
    print('Nenhuma leitura gravada em dados/vazao_montante/.')
    return
  fuso = timezone(timedelta(hours=-3))
  print('Vazão a montante (ANA, usinas Salto Pilão), horas em UTC-3:')
  for cod, nome in ESTACOES.items():
    s = dados.get(cod)
    if not s:
      print(f'  {cod} {nome}: sem dados')
      continue
    q = [v for _, v in s]
    ini, fim = datetime.fromtimestamp(s[0][0], fuso), datetime.fromtimestamp(s[-1][0], fuso)
    print(f'  {cod} {nome}: {len(s)} leituras, {ini:%d/%m %H:%M} a {fim:%d/%m %H:%M}; '
          f'min {min(q):.0f}, mediana {sorted(q)[len(q) // 2]:.0f}, máx {max(q):.0f} m³/s; '
          f'última {q[-1]:.0f}')
  comparar(dados)


def comparar(dados):
  """Razão entre a vazão de Blumenau pela curva-chave e a de Salto Pilão Jusante, por defasagem e por período."""
  import numpy as np
  sys.path.insert(0, str(Path(__file__).resolve().parent / 'ferramentas'))
  import analise_propagacao_mare as ap
  import curva_chave_blumenau as ccb
  sp = dados.get('83461000')
  series, _ = ap.ler()
  if not sp or 'BLU' not in series:
    return
  t_sp, q_sp = np.array([a for a, _ in sp]), np.array([b for _, b in sp])
  blu = series['BLU']
  curvas = {nome: c for nome, (c, _, _) in ccb.curvas_por_periodo().items()}
  print('\nVazão de Blumenau (curva-chave sobre o AlertaBlu) / vazão de Salto Pilão Jusante, '
        'com a água de Salto Pilão chegando a Blumenau após a defasagem (mediana, mín-máx):')
  print('  defasagem  ' + '  '.join(f'{nome:>16s}' for nome in curvas) + '   leituras')
  for horas in (0, 2, 6, 12, 18, 24):
    alvo = blu[:, 0] - horas * 3600
    ok = (alvo >= t_sp[0]) & (alvo <= t_sp[-1])
    if ok.sum() < 6:
      print(f'  {horas:4d} h     poucas leituras em comum')
      continue
    q_sp_l = np.interp(alvo[ok], t_sp, q_sp)
    cel = []
    for c in curvas.values():
      r = ccb.vazao(blu[ok, 1], c) / q_sp_l
      cel.append(f'{np.median(r):4.2f} ({r.min():.2f}-{r.max():.2f})')
    print(f'  {horas:4d} h     ' + '  '.join(f'{x:>16s}' for x in cel) + f'   {ok.sum()}')
  print('  (a curva de 2012-2014 é a usada pelo painel; razão abaixo de 1 não é fisicamente possível)')


def main():
  if '--offline' not in sys.argv:
    n, arq, falhas = coletar()
    print(f'{n} leituras novas gravadas em {arq}' if n else 'Nenhuma leitura nova.')
    if len(falhas) == len(ESTACOES):
      sys.exit('A ANA não respondeu para nenhuma estação.')
  if '--so-coletar' not in sys.argv:
    resumo()


if __name__ == '__main__':
  main()
