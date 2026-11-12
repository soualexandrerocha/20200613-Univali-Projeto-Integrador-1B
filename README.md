# 20200613-Univali-Projeto-Integrador-1B
 Repositório criado para reunir os códigos criados para a disciplina

Conteúdo:

- `cisalhamento_berco2_zp21.py`: corrente de vazante junto ao cais do Berço 2 (ZP-21).
- **Maré astronômica do Porto de Itajaí**: previsão em qualquer instante
  (script, página web e validações), descrita abaixo.

---

# Maré astronômica do Porto de Itajaí

Prevê a altura da maré astronômica no Porto de Itajaí em qualquer instante,
com preamares (PM) e baixa-mares (BM). Horários em hora legal de Brasília
(UTC−3). Alturas em metros acima do **nível de redução (NR)** da DHN, o zero
das cartas náuticas e da Tábua das Marés.

**Resumo da precisão.** O modelo foi ajustado com as tábuas oficiais da
Marinha (CHM). Ajustado só com 2024 e 2025, previu a tábua de 2026 com erro de
altura de 2,9 cm. O horário dos extremos bem marcados tem erro mediano de
6 min, e 90 % ficam dentro de 17 min. Contra o nível **medido** na foz do
Itajaí-Açu (Defesa Civil, primeiras 15 h), a curva coincide sem atraso, com
erro de 4,6 cm. Nos estofos rasos (maré quase parada) o horário do extremo
pode errar 30 min ou mais. **Não inclui** vento, maré meteorológica nem vazão
do rio.

## Como usar

### Página (celular ou computador)

`pagina/mare_itajai.html` é um arquivo único que abre em qualquer navegador,
sem Python. Também está publicada como página privada no claude.ai, com o
nome "Maré de Itajaí". A página mostra:

- altura no instante escolhido ou agora, tendência em cm/h e próximas PM/BM;
- curva de 1, 2 ou 4 dias (toque na curva para escolher o instante);
- extremos do dia. Cobre 2015 a 2050.

### Script

```bash
pip install numpy utide plotly
python mare_itajai.py "2026-11-12 14:30"            # hora legal (UTC−3)
python mare_itajai.py "2026-11-12 14:30" --dias 5   # janela maior no gráfico HTML
python mare_itajai.py --sem-grafico                 # agora, só texto
python mare_itajai.py --constantes                  # regrava dados/constantes_harmonicas_itajai.csv
```

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

A tábua oficial de 2026 dá, para o mesmo dia: PM 03:34 1,02 · BM 07:47 0,31 ·
PM 15:59 0,81 · BM 21:19 0,13. Em código: `Mare().altura(datetime)`,
`Mare().extremos(ini, fim)`, `grafico(...)`.

## Método

A DHN/CHM prevê a maré de Itajaí com 77 (tábua de 2024) ou 78 (2025, 2026)
componentes harmônicas, mas não publica a tabela de constantes. Aqui elas são
**reconstruídas a partir da previsão oficial**: os 5422 extremos das Tábuas
das Marés do Porto de Itajaí de 2024, 2025 e 2026.

- Cada extremo fornece duas equações lineares nos mesmos coeficientes:
  `h(tᵢ) = altura tabelada` e `dh/dt(tᵢ) = 0`. A segunda usa o horário da
  tábua e reduz o erro de horário à metade.
- As componentes são escolhidas pelo critério de Rayleigh do UTide (68 no
  total). Correções nodais e argumentos astronômicos também vêm do UTide, de
  modo que as constantes valem para qualquer ano.
- Resultado em `dados/constantes_harmonicas_itajai.csv`: M2 = 25,4 cm,
  S2 = 17,2 cm, O1 = 10,7 cm, M4 = 6,4 cm, …
- Nível médio ajustado: 0,596 m, sem ter sido imposto. O oficial é 0,6 m nas
  tábuas de 2025–2026 e 59,4 cm na ficha F-41 da estação 60235.

A página usa as mesmas constantes. Para cada componente guarda o fator nodal f
e a fase astronômica a cada 30 dias e interpola entre eles. O teste
automático confere o JavaScript contra o Python: diferença de 0,02 mm nas
alturas e 2 s nos extremos.

## Validação

### 1. Entre anos da tábua oficial (`ferramentas/validar_anos.py`)

Ajusta com algumas tábuas e mede o erro na tábua de um ano que ficou de fora.
"Bem marcados" são os extremos com variação ≥ 20 cm.

| Ajuste → ano testado | Altura (RMS) | Horário, bem marcados |
|---|---|---|
| 2024 → 2026 | 5,0 cm | mediana 6 min, 90 % ≤ 18 min |
| 2025 → 2026 | 3,8 cm | mediana 5 min, 90 % ≤ 16 min |
| **2024 + 2025 → 2026** | **2,9 cm** | **mediana 6 min, 90 % ≤ 17 min** |
| 2025 + 2026 → 2024 | 5,7 cm | mediana 5 min, 90 % ≤ 14 min |

Mais anos melhoram a altura; o horário fica em ~5–6 min em todos os casos.
A tábua de 2024 vem de uma análise anterior da Marinha (77 componentes,
posição da estação um pouco diferente) e discorda das de 2025–2026 em ~5 cm.
O modelo publicado usa os três anos.

### 2. Outra previsão: Tábua de Maré 2026 da EPAGRI (`ferramentas/comparar_epagri.py`)

A EPAGRI não entra no ajuste e usa análise harmônica própria.

| Grandeza | Resultado |
|---|---|
| Altura nos 1760 horários da tábua | RMS 5,6 cm; EPAGRI 1,9 cm acima do modelo, em média |
| Extremos com par no modelo (≤ 90 min) | 1731 de 1760; os demais são oscilações de ~5 cm que o modelo suaviza |
| Horário, bem marcados | mediana 8 min, 90 % ≤ 21 min; modelo ~5 min mais tarde |
| Horário, estofos | mediana 11 min, 90 % ≤ 28 min |

Na tábua da EPAGRI, 55 símbolos ▲/▼ contradizem as alturas vizinhas (por
exemplo, "preamar" de 0,1 m em 27/02 às 18:47).

### 3. Nível medido: réguas da Defesa Civil de Itajaí (`ferramentas/comparar_defesa_civil.py`)

O monitoramento público da Defesa Civil publica as últimas 12 h de cada régua
telemétrica, com leituras a cada 10 min. As réguas têm zero próprio, então
para cada estação ajusta-se `nível = a + b · maré_prevista(t − atraso)`.
Primeiras 15 h (11/11 19:21 a 12/11 10:21, hora local):

| Estação | Variação | Correlação | Atraso | Ganho | Resíduo |
|---|---|---|---|---|---|
| **DC01 Itajaí-Açu, ICMBio/CEPSUL (foz)** | 1,13 m | 0,99 | **0 min** | 1,02 | **4,6 cm** |
| DC03/DC04 Itajaí-Mirim, canal retificado | 0,93 m | 0,99 | +36 min | 0,91 | 3,2 cm |
| DC11 Itajaí-Açu, Santa Regina | 0,74 m | 0,99 | +87 min | 0,72 | 3,0 cm |

Na foz, a maré medida segue a prevista sem atraso e com a mesma amplitude.
Rio acima, ela chega atrasada e amortecida, o que é esperado. Por isso a
previsão vale para o porto e a foz, não para pontos rio acima. Com só 15 h de
dados isso ainda é indicativo; a coleta contínua está descrita abaixo.

## Coleta contínua do nível medido

`ferramentas/coletar_defesa_civil.py` baixa o JSON público do monitoramento
(`monitoramento.defesacivil.itajai.sc.gov.br/data/current/app.json`) e
acrescenta, sem duplicar:

- `dados/defesa_civil/niveis_rios.csv`: leituras de todas as réguas;
- `dados/defesa_civil/meteorologia.csv`: vento, pressão etc. no instante da
  coleta.

Uma tarefa agendada roda a coleta a cada 6 h (03:53, 09:53, 15:53 e 21:53,
hora local) e faz commit neste branch. A análise completa (medido × previsto,
efeito do vento e da pressão) está prevista para 10/12/2026.

```bash
python ferramentas/coletar_defesa_civil.py
python ferramentas/comparar_defesa_civil.py dados/defesa_civil/niveis_rios.csv
```

## Arquivos

| Caminho | Conteúdo |
|---|---|
| `mare_itajai.py` | modelo, previsão, extremos, gráfico plotly, linha de comando |
| `pagina/mare_itajai.html` | página pronta (gerada) |
| `pagina/modelo.html`, `pagina/nucleo_mare.js` | fonte da página |
| `dados/tabua_mare_porto_itajai_AAAA_CHM.pdf` | tábuas oficiais CHM 2024–2026 |
| `dados/tabua_mare_itajai_AAAA.csv` | extremos extraídos dessas tábuas |
| `dados/tabua_mare_itajai_2026_EPAGRI.pdf`, `..._epagri.csv` | tábua EPAGRI 2026 e extração |
| `dados/constantes_harmonicas_itajai.csv` | constantes ajustadas |
| `dados/defesa_civil/` | nível medido e meteorologia acumulados |
| `ferramentas/extrair_tabua_chm.py`, `extrair_tabua_epagri.py` | PDF → CSV, com verificações |
| `ferramentas/gerar_pagina.py`, `testar_pagina.py` | gera a página e confere JS × Python |
| `ferramentas/validar_anos.py`, `comparar_epagri.py`, `comparar_defesa_civil.py` | validações |
| `ferramentas/coletar_defesa_civil.py` | coleta do nível medido |

Para atualizar com a tábua de um ano novo:

1. Extraia o PDF com `extrair_tabua_chm.py`.
2. Acrescente o ano em `ARQ_TABUAS` (`mare_itajai.py`).
3. Rode `python mare_itajai.py --constantes`, `gerar_pagina.py` e `testar_pagina.py`.

## Limitações

- **Maré astronômica apenas.** Vento, frentes frias, maré meteorológica e
  vazão do Itajaí-Açu podem mudar o nível real em dezenas de centímetros e
  adiantar ou atrasar os extremos.
- As constantes reproduzem a previsão oficial, com seus próprios erros. A
  comparação com o nível medido ainda cobre poucas horas.
- Alturas referidas ao NR da DHN, 189,6 cm acima do zero da régua da
  Delegacia da Capitania dos Portos em Itajaí (ficha F-41).
- A série medida da praticagem (sistema WebPilot) ainda não foi avaliada: o
  acesso exige login, e a viabilidade da coleta não foi verificada.
