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

Saída de exemplo (tábua oficial de 2026 para o mesmo dia: PM 03:34 1,02 ·
BM 07:47 0,31 · PM 15:59 0,81 · BM 21:19 0,13):

```
Porto de Itajaí — 12/11/2026 14:30 (UTC-3)
  altura: 0.75 m acima do NR  (enchendo, +8 cm/h)
Extremos anteriores:
  PM  12/11 03:28   1.03 m
  BM  12/11 07:43   0.34 m
Próximos extremos:
  PM  12/11 15:55   0.83 m
  BM  12/11 21:19   0.15 m
  PM  13/11 04:08   0.97 m
```

Em código: `Mare().altura(datetime)`, `Mare().extremos(ini, fim)`, `grafico(...)`.

### Página para consulta rápida — `pagina/mare_itajai.html`

Arquivo único, abre em qualquer navegador (computador ou celular) sem Python:
altura no instante escolhido ou agora, tendência em cm/h, próximas PM/BM,
curva de 1, 2 ou 4 dias (toque na curva para escolher o instante) e os
extremos do dia. Cobre 2015 a 2050.

Usa as mesmas constantes do script. Para cada componente guarda o fator nodal
f e a fase astronômica a cada 30 dias e interpola entre eles (erro < 0,01 mm).

```bash
python ferramentas/gerar_pagina.py    # regera a página a partir de pagina/modelo.html
python ferramentas/testar_pagina.py   # confere o JavaScript contra o Python (precisa de node)
```

Última conferência: alturas iguais ao Python dentro de 0,02 mm; extremos dentro de 2 s.

### De onde vêm as constantes

A DHN/CHM prevê a maré do Porto de Itajaí com 77 (tábua de 2024) ou 78
(2025 e 2026) componentes, mas não publica a tabela de constantes. Aqui elas
são **reconstruídas a partir da previsão oficial**: os 5422 extremos das
Tábuas das Marés de 2024, 2025 e 2026 (`dados/tabua_mare_porto_itajai_AAAA_CHM.pdf`,
extraídos para `dados/tabua_mare_itajai_AAAA.csv` por
`ferramentas/extrair_tabua_chm.py`). As tábuas de 2025 e 2026 trazem alturas
em centímetros; a de 2024, em decímetros.

Mínimos quadrados com duas equações por extremo: `h(tᵢ) = altura tabelada`
e `dh/dt(tᵢ) = 0`. A segunda aproveita o horário da tábua e reduz o erro de
horário à metade. Componentes escolhidas pelo critério de Rayleigh (UTide) →
68 componentes; correções nodais e argumentos astronômicos do UTide, de modo
que as constantes servem para qualquer ano. Resultado em
`dados/constantes_harmonicas_itajai.csv` (M2 = 25,4 cm, S2 = 17,2 cm,
O1 = 10,7 cm, M4 = 6,4 cm, …). Nível médio ajustado: 0,596 m (oficial:
0,6 m nas tábuas de 2025–2026; 59,4 cm na F-41), sem ter sido imposto.

### Validação entre anos (`ferramentas/validar_anos.py`)

Ajusta com algumas tábuas oficiais e mede o erro na tábua de um ano que ficou
de fora. "Bem marcados" = extremos com variação ≥ 20 cm.

| Ajuste → ano testado | Altura (RMS) | Horário, bem marcados |
|---|---|---|
| 2024 → 2026 | 5,0 cm | mediana 6 min, 90 % ≤ 18 min |
| 2025 → 2026 | 3,8 cm | mediana 5 min, 90 % ≤ 16 min |
| **2024 + 2025 → 2026** | **2,9 cm** | **mediana 6 min, 90 % ≤ 17 min** |
| 2025 + 2026 → 2024 | 5,7 cm | mediana 5 min, 90 % ≤ 14 min |

Mais anos melhoram a altura; o horário fica em ~5–6 min em todos os casos.
A tábua de 2024 vem de uma análise anterior (77 componentes, posição da
estação um pouco diferente) e discorda das de 2025–2026 em ~5 cm. O modelo
publicado usa os três anos. Nos estofos rasos (variação < 20 cm) o horário
do extremo é mal definido: mediana ~10 min, 90 % ≤ ~30 min.

### Validação independente: Tábua de Maré 2026 da EPAGRI

Outra fonte (EPAGRI/SC), sem nenhum uso no ajuste
(`dados/tabua_mare_itajai_2026_EPAGRI.pdf`, extraída por
`ferramentas/extrair_tabua_epagri.py`; comparação em
`ferramentas/comparar_epagri.py`):

| Grandeza | Resultado |
|---|---|
| Altura nos 1760 horários da tábua | RMS 5,6 cm; EPAGRI 1,9 cm acima do modelo, em média |
| Extremos da EPAGRI com par no modelo (≤ 90 min) | 1731 de 1760; os restantes são oscilações de ~5 cm que o modelo suaviza |
| Horário, extremos bem marcados (≥ 20 cm) | mediana 8 min, 90 % ≤ 21 min; modelo ~5 min mais tarde, em média |
| Horário, estofos | mediana 11 min, 90 % ≤ 28 min |

A EPAGRI usa análise harmônica própria. Sem medições do marégrafo não dá
para dizer qual das tábuas está mais perto da maré real. Na tábua da EPAGRI,
55 símbolos ▲/▼ contradizem as alturas vizinhas (por exemplo, "preamar" de
0,1 m em 27/02 às 18:47).

### Limitações

- **Maré astronômica apenas.** Vento, maré meteorológica e vazão do
  Itajaí-Açu podem mudar o nível real em dezenas de centímetros e adiantar
  ou atrasar os extremos.
- Validação feita contra previsões oficiais (CHM 2024–2026 e EPAGRI 2026),
  não contra medições do marégrafo.
- Alturas referidas ao NR da DHN (zero das cartas), 189,6 cm acima do zero
  da régua da Delegacia da Capitania dos Portos em Itajaí (F-41).

## Corrente e tensão no Berço 2 — `cisalhamento_berco2_zp21.py`

Campo de corrente junto ao cais (solução analítica do SKM) e tensão
cisalhante na parede. A profundidade é a menor profundidade do aviso da
praticagem (Itajaí 2 = Berço 2, 12,8 m) mais a maré de `mare_itajai.py`.
Ao rodar, também imprime:

- a vazão equivalente a cada velocidade (largura do rio de 400 m);
- a corrente ao longo do dia: vazão fluvial (215 m³/s, média) mais a
  corrente de maré pelo prisma de maré, com a atenuação medida rio acima.

Com velocidade fixa, a tensão na parede não depende da profundidade; a
maré só pesa por meio da vazão e da corrente de maré.

## Propagação da maré e coleta de níveis — `analise_propagacao_mare.py`

Baixa as séries de 12 h da telemetria da Defesa Civil de Itajaí
(monitoramento.defesacivil.itajai.sc.gov.br), acumula em
`dados/niveis_defesacivil_itajai.csv` e ajusta, para cada estação, a razão
de amplitude e o atraso da maré em relação à foz. O workflow
`.github/workflows/coleta-niveis.yml` roda a coleta a cada 6 h e commita as
leituras novas, pois o site não guarda histórico.

```bash
python analise_propagacao_mare.py              # coleta e analisa
python analise_propagacao_mare.py --offline    # só analisa
python analise_propagacao_mare.py --so-coletar # só coleta (usado no workflow)
```

## Painéis do Berço 2 — `pagina/berco2.html`

Página autossuficiente com painéis interativos: maré, corrente e tensão no
cais ao longo do dia; perfil junto ao cais na hora escolhida; relação entre
vazão e corrente; e a propagação da maré medida pela Defesa Civil. Data,
vazão, prisma de maré, profundidade, largura e atrito são ajustáveis, e o
modelo é recalculado no navegador.

```bash
python ferramentas/gerar_painel_berco2.py   # regenera com as leituras mais recentes
```

O workflow de coleta (`.github/workflows/coleta-niveis.yml`) regenera a
página sempre que há leituras novas, a cada 6 h.
