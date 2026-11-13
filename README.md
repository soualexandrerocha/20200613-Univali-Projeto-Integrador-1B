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
- a corrente ao longo do dia: vazão fluvial (215 m³/s, um dia típico no porto) mais a
  corrente de maré pelo método do prisma de maré, com a atenuação medida rio acima.

Com velocidade fixa, a tensão na parede não depende da profundidade; a
maré só pesa por meio da vazão e da corrente de maré.

A corrente é calculada em duas camadas (cunha salina, balanço de Knudsen):
a camada superior leva Q_rio/(1 − σ) mais a vazante de maré. σ e a espessura
da camada variam com a vazão, calibrados em dois pontos: 230 m³/s (σ = 0,7,
3,8 m), pelos fluxos de sal de Zaleski & Schettini (2003); e 1.200 m³/s
(σ = 0, 5,1 m), pela corrente acima de 2 nós observada no trecho A às 08:00
de 12/11/2026, com a vazão do dia estimada pela curva-chave de Blumenau.

## Curva-chave de Blumenau — `ferramentas/curva_chave_blumenau.py`

Ajusta Q = a·(h − h₀)ᵇ às séries de cota e vazão da ANA em Blumenau (83800002;
`dados/cota_vazao_blumenau_83800002.csv`) e converte o nível do AlertaBlu
coletado em vazão. Em 12/11/2026, com 3,5–3,6 m, deu ~870–920 m³/s.
No painel `pagina/berco2.html`, o nível de Blumenau pode ser a entrada: o
painel converte em vazão em Blumenau e no porto (÷ 0,75) e, ao abrir um dia
com leituras coletadas do AlertaBlu, usa a média delas.

```bash
python ferramentas/curva_chave_blumenau.py            # baixa, ajusta e aplica
python ferramentas/curva_chave_blumenau.py --offline  # usa o CSV gravado
```

## Propagação da maré e coleta de níveis — `analise_propagacao_mare.py`

Baixa as séries de 12 h da telemetria da Defesa Civil de Itajaí
(monitoramento.defesacivil.itajai.sc.gov.br) e o nível de 24 h do AlertaBlu
em Blumenau, acumula em
`dados/niveis/` (um arquivo por coleta) e ajusta, para cada estação, a razão
de amplitude e o atraso da maré em relação à foz. Com DC11 e Blumenau, calcula o
trecho de enchimento do Itajaí-Açu fechado no Salto, onde a maré termina.

As larguras do rio ao longo do canal (`dados/largura_itajai_acu.csv`) vêm da
Carta Náutica 1841 (DHN) em GeoTIFF, que não fica no repositório:

```bash
python ferramentas/larguras_carta1841.py PASTA_DOS_TIF   # requer rasterio, scipy e scikit-image
``` O workflow
`.github/workflows/coleta-niveis.yml` roda a coleta a cada 6 h e commita as
leituras novas, pois o site não guarda histórico. Só o workflow commita `dados/niveis/` e
`pagina/berco2.html`; as regras para sessões estão em `CLAUDE.md`.

```bash
python analise_propagacao_mare.py              # coleta e analisa
python analise_propagacao_mare.py --offline    # só analisa
python analise_propagacao_mare.py --so-coletar # só coleta (usado no workflow)
```

## Painéis do Berço 2 — `pagina/berco2.html`

Página autossuficiente com painéis interativos: maré, corrente e tensão no
cais ao longo do dia; perfil junto ao cais na hora escolhida; relação entre
vazão e corrente; e a propagação da maré medida pela Defesa Civil. Data,
vazão, trecho de enchimento da maré, seção (Berço 2 ou trecho A, canal entre
as bacias), profundidade, largura, atrito e parâmetros da cunha salina são ajustáveis, e o
modelo é recalculado no navegador.

```bash
python ferramentas/gerar_painel_berco2.py   # regenera com as leituras mais recentes
```

O workflow de coleta (`.github/workflows/coleta-niveis.yml`) regenera a
página sempre que há leituras novas, a cada 6 h.

## Folga sob a quilha e janelas de manobra — `pagina/folga_quilha.html`

Formulário para calcular a folga estática sob a quilha (UKC) de um navio no
Porto de Itajaí e os horários em que a manobra pode começar, com a maré
astronômica de `mare_itajai.py`. Abre no navegador ou no celular, sem Python.

**Entradas:** período e duração da manobra; reserva de nível (vento, maré
meteorológica, vazão do rio); pontos de profundidade, cada um com seu trecho
e seu referencial: NR da DHN, outro zero (com a cota desse zero em relação ao
NR) ou medida no instante (a página desconta a maré daquele instante); calados
AV/AR ou médio e trim; densidade em que o calado vale e densidade local, com
FWA opcional; folga abaixo da quilha (FAQ) de cada trecho, editável.

**Regras de FAQ preenchidas** (verificadas em 12/11/2026):

| Trecho | FAQ base | Adicional temporário |
|---|---|---|
| Canal externo | 15 % do calado | — |
| Canal interno | 10 % do calado | 0,80 m |
| Bacia de evolução 1 | 0,60 m | 0,80 m |
| Bacia de evolução 2 | 10 % do calado | 0,80 m |
| Berços | 0,60 m | — |

- FAQ base: NPCP-SC, Portaria 45/2023-CPSC, e Resolução SPI 013/2024 do Porto
  de Itajaí, que dão CMR = MPO + Hmaré − FAQ.
- Adicional: Ofício 755/2026 da Delegacia da Capitania dos Portos em Itajaí
  (14/10/2026), pelas correntezas do El Niño, temporário e sem data de fim.
  Os valores vêm de três veículos (Diarinho, BE News, Efficienza) que concordam
  entre si; o adicional foi confirmado em vigor em 12/11/2026. Quando for
  revogado, zere a coluna de adicional no formulário.
- O exemplo usa as menores profundidades divulgadas pela Superintendência em
  outubro de 2026 (canal externo 13,40 m, canal interno 13,10 m, bacia 1
  12,80 m, bacia 2 13,50 m), válidas até 10/12/2026.

**Cálculo** (`pagina/nucleo_ukc.js`):

- calado corrigido = maior calado + ΔT. Com FWA, ΔT = FWA × (ρref − ρlocal) / 0,025;
  sem FWA, T × ρref/ρlocal (casco tratado como caixa, o que superestima o afundamento).
  A fórmula da NPCP-SC não tem essa correção; ela foi mantida de propósito,
  por ser mais conservadora;
- FAQ do ponto = valor do trecho (% sobre o maior calado já corrigido, ou m) +
  adicional. A norma diz só "calado do navio"; usar o maior calado corrigido
  é a leitura mais conservadora;
- UKC(t) = profundidade no NR + maré(t) − reserva − calado corrigido;
- a manobra pode começar em s se UKC ≥ FAQ em todos os pontos durante todo o
  intervalo [s, s + duração], com passo de 1 min.

Corrente, vento, ondas, visibilidade e rebocadores também limitam as manobras
na NPCP-SC e não entram neste cálculo.

**Saídas:** janelas de início, maré necessária e ponto limitante, gráfico,
sensibilidade a nível 0,10–0,30 m abaixo do previsto, folga em cada PM/BM e
resumo em texto para copiar.

É folga **estática**: não inclui squat, balanço nem ondas. A maré é só a
astronômica, com as limitações descritas acima.

```bash
python ferramentas/gerar_painel_ukc.py     # regenera a página
python ferramentas/testar_painel_ukc.py    # confere o JavaScript contra o Python (precisa de node)
```

## Vazão do rio em Indaial — `ferramentas/vazao_indaial.py`

Baixa da ANA a série diária de vazão de Indaial (estação 83690000, ~70% da
bacia), grava `dados/vazao_indaial_83690000.csv` e resume: em 1929–2021,
média de 229 m³/s, mediana de 139 m³/s, P90 de 494 m³/s. A série consistida
termina em 2021.

```bash
python ferramentas/vazao_indaial.py            # baixa e resume
python ferramentas/vazao_indaial.py --offline  # só resume
```

## Vetores de corrente no painel

O painel `pagina/berco2.html` tem um mapa com setas de corrente ao longo do eixo
do Itajaí-Açu (0 a 6 km da foz), na hora escolhida, para a camada superior, a de
fundo ou a média vertical. É o modelo unidimensional aplicado a cada seção, com
a largura medida na Carta 1841; não é um campo bidimensional, e as limitações
estão escritas no próprio painel. A geometria (margens, eixo, estações) está em
`dados/mapa_itajai_acu.json`, gerada com o GeoTIFF da carta:

```bash
python ferramentas/larguras_carta1841.py PASTA_DOS_TIF --mapa
```

## Vazão a montante — `vazao_montante.py`

Coleta a vazão horária das usinas Salto Pilão (alto Itajaí-Açu e seus três
braços) pela telemetria da ANA, a única fonte de vazão recente que
conseguimos acessar para a bacia. O workflow roda a coleta a cada 6 h, com
janela de 14 dias, e grava um arquivo por coleta em `dados/vazao_montante/`.

```bash
python vazao_montante.py              # coleta e resume
python vazao_montante.py --offline    # só resume
```

O resumo compara a vazão de Blumenau, pela curva-chave sobre o AlertaBlu, com a
de Salto Pilão Jusante, o que verifica a curva-chave e a fração usada para
chegar à vazão no porto.

