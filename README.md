# 20200613-Univali-Projeto-Integrador-1B
 Repositório criado para reunir os códigos criados para a disciplina

## Maré astronômica do Porto de Itajaí — `mare_itajai.py`

Prevê a altura da maré astronômica em qualquer instante e desenha o gráfico
(HTML interativo, plotly) com preamares (PM) e baixa-mares (BM).

```bash
pip install numpy utide plotly
python mare_itajai.py "2026-11-12 14:30"            # hora legal (UTC-3)
python mare_itajai.py "2026-11-12 14:30" --dias 5   # janela maior no gráfico
python mare_itajai.py --constantes                  # regrava dados/constantes_harmonicas_itajai.csv
```

Saída de exemplo:

```
Porto de Itajaí — 12/11/2026 14:30 (UTC-3)
  altura: 0.79 m acima do NR  (enchendo, +9 cm/h)
Extremos anteriores:
  PM  12/11 03:29   1.06 m
  BM  12/11 07:43   0.38 m
Próximos extremos:
  PM  12/11 15:55   0.88 m
  BM  12/11 21:20   0.18 m
  PM  13/11 04:10   1.00 m
```

Em código: `Mare().altura(datetime)`, `Mare().extremos(ini, fim)`, `grafico(...)`.

### De onde vêm as constantes

A DHN/CHM prevê a maré do Porto de Itajaí com 77 componentes (análise
harmônica de 01/04/2010 a 01/04/2011, estação 60235, ficha F-41), mas não
publica a tabela de constantes. Aqui elas são **reconstruídas a partir da
previsão oficial**: os 1800 extremos da Tábua das Marés de 2024
(`dados/tabua_mare_porto_itajai_2024_CHM.pdf`, extraídos para
`dados/tabua_mare_itajai_2024.csv` por `ferramentas/extrair_tabua_chm.py`).

Mínimos quadrados com duas equações por extremo: `h(tᵢ) = altura tabelada`
e `dh/dt(tᵢ) = 0`. A segunda aproveita o horário da tábua e reduz o erro de
horário à metade. Componentes escolhidas pelo critério de Rayleigh (UTide) →
67 componentes; correções nodais e argumentos astronômicos do UTide, de modo
que as constantes servem para qualquer ano. Resultado em
`dados/constantes_harmonicas_itajai.csv` (M2 = 25,0 cm, S2 = 17,1 cm,
O1 = 10,8 cm, M4 = 6,6 cm, …).

### Validação (validação cruzada: 4 grupos de semanas alternadas de 2024)

| Grandeza | Resultado |
|---|---|
| Erro RMS de altura | 3,3 cm (o arredondamento da tábua a 0,1 m sozinho dá ~2,9 cm) |
| Horário de PM/BM bem marcadas (variação ≥ 20 cm) | mediana 7 min, 90 % ≤ 19 min |
| Horário de PM/BM em estofos rasos (< 20 cm) | mediana 13 min, 90 % ≤ 43 min |
| Ajuste em jan–ago, teste em set–dez | RMS 3,4 cm; horário mediana 7 min |
| Nível médio Z0 | 0,593 m (oficial: 0,59 m na tábua, 59,4 cm na F-41) — não imposto |

O modelo também gera alguns extremos minúsculos (mediana 0,7 cm de
amplitude) que a tábua não lista.

### Limitações

- **Maré astronômica apenas.** Vento, maré meteorológica e vazão do
  Itajaí-Açu podem mudar o nível real em dezenas de centímetros e adiantar
  ou atrasar os extremos.
- As constantes vêm de um único ano de previsões; componentes que exigem mais
  de um ano para serem separadas (p. ex. Sa) ficam mal determinadas.
- Validação feita contra a previsão oficial, não contra medições do marégrafo.
  Para comparar com outro ano, basta extrair outra tábua com o mesmo script e
  rodar `Mare().extremos(...)` no período.
- Alturas referidas ao NR da DHN (zero das cartas), 189,6 cm acima do zero
  da régua da Delegacia da Capitania dos Portos em Itajaí (F-41).
