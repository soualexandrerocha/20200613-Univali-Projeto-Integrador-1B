"""Corrente de vazante junto ao cais da Bacia 1 / Berço 2 (ZP-21).

Modelo físico: equação de quantidade de movimento integrada na vertical,
com atrito de fundo e viscosidade turbulenta lateral (método de Shiono &
Knight, SKM), para profundidade H constante e cais retilíneo vertical:

    rho*g*H*S0 - rho*(f/8)*U^2 + d/dy[ rho*lambda*H^2*(f/8)^(1/2) * U * dU/dy ] = 0

Com U = 0 no cais (não-deslizamento) e U -> U_inf longe dele, a solução
analítica exata é

    U(y) = U_inf * sqrt(1 - exp(-gamma*y)),   gamma = sqrt(2/lambda)*(f/8)^(1/4)/H
    U_inf = sqrt(8*g*S0*H/f)                  (equilíbrio declividade x atrito de fundo)

Referências: Shiono & Knight (1991), J. Fluid Mech. 222; Tang & Knight
(2015), J. Hydro-environment Research (expressões de gamma e k conferidas);
Knight (1999) para valores típicos de lambda.

O que a solução satisfaz exatamente:
  - continuidade (função de corrente psi = integral de U dy);
  - impermeabilidade (v = 0) e não-deslizamento (U = 0) no cais;
  - quantidade de movimento longitudinal (balanço acima) e transversal
    (escoamento paralelo: termos advectivos nulos, pressão uniforme em y);
  - tensão cisalhante finita na parede.

Idealizações que restam (todas listadas para calibração/refino posterior):
  - cais retilíneo e profundidade uniforme: por isso o escoamento é paralelo
    ao cais e não há ângulo de ataque. Variações ao longo do cais exigem a
    geometria real (batimetria, recesso do berço, navio atracado);
  - escoamento permanente (quase-estático frente ao período da maré);
  - escoamento secundário desprezado (Gamma = 0 no SKM);
  - modelo 2D na horizontal (sem perfil vertical de velocidade);
  - perto da parede (centímetros) a lei de parede real é logarítmica; aqui
    U ~ sqrt(y), com dU/dy -> infinito em y = 0 (a tensão permanece finita).
Parâmetros f e lambda abaixo são valores de partida, a calibrar.

Profundidade e maré: H = PROF_ZH + eta(t), com eta a maré astronômica
acima do zero hidrográfico prevista por mare_itajai.py (Mare) no instante
INSTANTE. Consequência da solução acima: com U_inf fixo, a tensão na parede

    tau_parede = rho*lambda*H*(f/8)^(1/2) * U_inf^2/2 * gamma
               = rho*sqrt(lambda/2)*(f/8)^(3/4) * U_inf^2

NÃO depende de H. A maré só altera a largura da camada de cisalhamento
(3/gamma, proporcional a H) e a declividade S0 implícita. Ela muda a tensão
apenas por meio de U_inf.

Vazão do rio: numa seção retangular de largura B_RIO, com um cais e a
camada de cisalhamento descrita acima,

    Q = U_inf * H * (B_RIO - delta),   delta = 2*(1 - ln 2)/gamma

onde delta é a espessura de deslocamento da camada (integral de 1 - U/U_inf).
Para Q fixo, U_inf ~ 1/H e tau_parede ~ 1/H^2: a mesma vazão gera mais
tensão na baixa-mar que na preamar. Limitações: só a vazão fluvial (a
corrente de maré não está incluída); Q é o do trecho do porto, não o medido
em Blumenau (faltam a curva-chave e os afluentes de jusante, como o
Itajaí-Mirim).

Corrente de maré (método do prisma de maré, com propagação medida): o trecho a
montante do berço enche e esvazia pelo berço. A maré sobe o Itajaí-Açu
até o Salto, em Blumenau, que fecha o estuário. Com a amplitude e o atraso
medidos em pontos do rio, variando exponencialmente entre eles, e a largura
B(s) do rio ao longo do canal, o fluxo no berço equivale ao de uma área
A_ef = |integral B(s) rho(s) ds| com nível em fase, defasada de ATRASO_FLUXO:

    Q_mare(t) = -A_ef * d(eta)/dt (t - ATRASO_FLUXO)   (+ = vazante)
    U_inf(t)  = (Q_RIO + Q_mare(t)) / (H(t) * (B_RIO - delta))

A_ef e ATRASO_FLUXO vêm de analise_propagacao_mare.areas_efetivas, com os
pontos de PONTOS_ACU em distância pelo rio: DC01 (CEPSUL, junto ao porto),
DC11 (Santa Regina, 11,4 km em linha reta) e a régua do AlertaBlu em
Blumenau (41,1 km em linha reta), com o fim no Salto (45,5 km em linha
reta). Larguras: dados/largura_itajai_acu.csv, medidas na Carta Náutica
1841 (DHN) até 17,4 km pelo rio (ferramentas/larguras_carta1841.py); além
disso, 200 m. Distâncias pelo rio: linha reta x 1,81 até DC11 (sinuosidade
medida na carta) e x 1,56 até Blumenau e o Salto (Indaial a 90 km pelo rio
e 57,6 km em linha reta, Zaleski & Schettini, 2003). Com 33 h de
dados em Itajaí (11 e 12/11/2026, sizígia) e 23 h em Blumenau: DC11 com
razão 0,68 e atraso de 80 min; Blumenau com razão 0,09 e atraso de ~6 h
(mal determinado: atrasos de 290 a 420 min ajustam quase igual, e parte da
oscilação pode vir da operação da PCH do Salto). Resultado: A_ef = 5,0 km²
e fluxo 1,4 h atrasado em relação a d(eta)/dt na foz. L_EFETIVO = A_ef /
B_RIO = 12,5 km é o trecho de enchimento equivalente na largura do porto.

A_ef não é o prisma de maré. O prisma, no sentido clássico (Dyer & Taylor,
1973; Alcântara, 2008, RBRH 13(3)), é a soma, trecho a trecho, do volume na
preamar menos o volume na baixa-mar: A_PRISMA * amplitude, com A_PRISMA =
integral de B(s) |rho(s)| ds = 6,6 km². Como os trechos não enchem ao mesmo
tempo, o volume líquido que passa pela foz é menor (A_ef < A_PRISMA).

Incertezas: as sinuosidades e a largura de 200 m além da carta são
estimativas (as hipóteses de 1,56 a 1,81 até DC11 e de 150 a 200 m de
largura dão A_ef de 4,3 a 5,0 km²); o prisma do Itajaí-Mirim, que
também tem maré (DC03, DC04, DC06) e deságua a montante do berço, não está
incluído; poucos ciclos de dados. Duas camadas (cunha salina): o Itajaí-Açu é estratificado. A vazante sai
por uma camada superficial de espessura h_sup, e a água do mar entra por
baixo. Pelo balanço de volume e sal de Knudsen (Zaleski & Schettini, 2003,
Notas Téc. Facimar 7:63-72), com sigma = S_sup/S_fundo:

    Q_sup = Q_RIO / (1 - sigma) + max(Q_mare, 0)       (sai, + = vazante)
    Q_inf = Q_RIO + Q_mare - Q_sup                      (entra, < 0 sem vazante de maré)
    u_sup = Q_sup / (B * h_sup),   u_inf = Q_inf / (B * (H - h_sup))

com a vazante de maré pela camada de cima e a enchente pela de baixo.

sigma e h_sup variam com a vazão do rio, calibrados em dois pontos:
  - vazão baixa (Q_BAIXA = 230 m³/s no porto): sigma = 0,7 e h_sup = 3,8 m,
    pelos fluxos de sal de Zaleski & Schettini junto à barra em janeiro de
    2000 (Indaial a 162 m³/s nos dados consistidos da ANA, / 0,70 de área);
    a razão entre os fluxos de fundo e de superfície dá a camada de cima com
    ~48% dos ~8 m do canal da época. Conferência: com esses valores e a
    geometria de 2000, residual de 0,58 m/s na superfície e 0,37 m/s no
    fundo; o artigo indica ~0,35-0,8 e ~0,26-0,37 m/s;
  - vazão alta (Q_ALTA = 1100 m³/s no porto): sigma = 0 (cunha expulsa
    acima de ~1000 m³/s, segundo Schettini) e h_sup = 4,7 m, que dá 2 nós
    na superfície do trecho A (280 m) às 08:00 de 12/11/2026, quando se
    observaram mais de 2 nós (h_sup é, portanto, um limite superior). A
    vazão daquele dia vem da curva-chave de Blumenau de 2012-2014
    (ferramentas/curva_chave_blumenau.py): ~850 m³/s em Blumenau com o
    AlertaBlu em 3,61 m, vezes 1,27 (razão das áreas de drenagem, extremo
    alto da faixa 1,13-1,27) para chegar ao porto: ~1080, e de 960 a 1080
    conforme a razão. A vazão medida a montante, em Salto Pilão
    (vazao_montante.py), era de ~880 m³/s, o piso do que passa em Blumenau.
    Arredondei para 1100.
Entre os dois pontos, sigma e h_sup variam linearmente com a vazão; fora
deles, ficam constantes (acima de Q_ALTA é extrapolação). h_sup = 3,8 m vem
do canal de 2000, com ~8 m; no canal atual, de ~13 m, a camada pode ser
outra. A tensão no cais usa a corrente da camada superior.

As medições de Schettini & Carvalho (1998), com variação de 77 a
140 cm/s ao longo do ciclo, são de 1994-95, com o canal a ~8 m, e não servem
para validar.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import plotly.figure_factory as ff
import plotly.graph_objects as go

from analise_propagacao_mare import areas_efetivas
from mare_itajai import Mare

MARE = Mare()  # ajusta as constantes às tábuas CHM 2024-2026 (alguns segundos)


def _local(t):
    """datetime com fuso -> hora legal UTC-3 ingênua, como Mare espera."""
    if t.tzinfo is not None:
        t = t.astimezone(timezone(timedelta(hours=-3))).replace(tzinfo=None)
    return t


def mare(tempos):
    """Maré astronômica (m acima do NR) para um datetime ou uma lista deles."""
    if isinstance(tempos, datetime):
        return float(MARE.altura(_local(tempos))[0])
    return MARE.altura([_local(t) for t in tempos])

# --- Constantes físicas -----------------------------------------------------
G = 9.81  # m/s²
RHO = 1025.0  # kg/m³, água do mar
NO_PARA_MS = 1852 / 3600  # 1 nó = 0,514444 m/s

# --- Parâmetros a calibrar --------------------------------------------------
# Profundidade abaixo do zero hidrográfico. Fonte: Avisos da Atalaia
# (praticagem), "Itajaí e Navegantes - menores profundidades", validade
# 10/12/2026: Itajaí 2 (= Berço 2) = 12,8 m; Bacia de evolução 01 = 12,8 m. É a menor
# profundidade levantada (não a cota de projeto de 14,5 m) e muda a cada
# levantamento batimétrico; atualizar quando o aviso for renovado.
# Referência vertical: a Marinha só aceita sondagens de 200 kHz, que refletem
# no topo da lama fluida. PROF_ZH é, portanto, a coluna de água acima da lama,
# que é a que escoa (a lama densa quase não acompanha a corrente). Abaixo dela
# há lama (1,05-1,25 t/m³) até o fundo consolidado, de espessura não medida
# aqui; ela não entra na corrente, mas aumenta o empuxo lateral no cais e faz a
# profundidade oficial variar com o assoreamento (por exemplo, a redução de
# 30 cm no canal em 2026).
PROF_ZH = 12.8  # m
INSTANTE = datetime(2026, 11, 12, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
ETA = mare(INSTANTE)  # m acima do zero hidrográfico
H = PROF_ZH + ETA  # m, profundidade junto ao berço no INSTANTE
F_DARCY = 0.02  # fator de atrito de Darcy-Weisbach do fundo
# Viscosidade turbulenta adimensional do SKM. Knight (1999, Int. J. Sediment
# Res. 14(2):217-236), citado por Khatua et al. (2016): faixa 0,07-0,50;
# 0,067 camadas-limite, 0,13 canais abertos, 0,16 seções trapezoidais.
LAMBDA = 0.13

# --- Domínio ----------------------------------------------------------------
C_CAIS = 300.0  # m, trecho de cais representado
B_CANAL = 100.0  # m, distância ao cais representada (borda aberta)

B_RIO = 400.0  # m, largura do rio no Berço 2
# Vazão do rio no porto (m³/s). 215 é a média dos dias do experimento de
# Zaleski & Schettini (2003, Notas Téc. Facimar 7:63-72, Tabela 2), janeiro
# de 2000, medida em Indaial (ANA 83690000, ~90 km acima, ~70% da bacia); não
# é média de longo prazo. Pela série de Indaial 1929-2021
# (ferramentas/vazao_indaial.py): média 229, mediana 139, P10 56, P90 494
# m³/s; escalando pela área (/0,70), no porto a mediana fica em ~200 e a média
# em ~330 m³/s. 215 representa um dia típico no porto. A vazão real de
# 12/11/2026 (~850 m³/s em Blumenau, ~1100 no porto) vem da curva-chave de
# Blumenau (ferramentas/curva_chave_blumenau.py), não deste valor.
# Trocar pela vazão do dia quando houver.
Q_RIO = 215.0  # m³/s
# Propagação da maré medida (analise_propagacao_mare.py, 11-12/11/2026):
# (distância pelo rio da foz em km, razão de amplitude, atraso em min)
SINUOSIDADE_CARTA = 1.81  # rio / linha reta, medida na Carta 1841 até 9,6 km em linha reta
SINUOSIDADE_ALTO = 1.56   # Indaial: 90 km pelo rio, 57,6 km em linha reta
PONTOS_ACU = [
    (0.0, 1.0, 0.0),                           # DC01, CEPSUL, junto ao porto
    (11.4 * SINUOSIDADE_CARTA, 0.68, 80.0),   # DC11, Santa Regina
    (41.1 * SINUOSIDADE_ALTO, 0.09, 360.0),   # Blumenau, AlertaBlu (atraso mal determinado)
]
X_SALTO_KM = 45.5 * SINUOSIDADE_ALTO  # fim do estuário: Salto, Blumenau (pelo rio)
LARGURA_ALEM_CARTA = 200.0  # m, mediana dos últimos km medidos na carta
_larg = np.loadtxt(Path(__file__).with_name('dados') / 'largura_itajai_acu.csv',
                   delimiter=',', comments='#', skiprows=3)
A_MONTANTE, ATRASO_FLUXO_S, A_PRISMA = areas_efetivas(
    PONTOS_ACU, X_SALTO_KM, _larg[:, 0], _larg[:, 1], LARGURA_ALEM_CARTA)  # m², s, m²
L_EFETIVO = A_MONTANTE / B_RIO  # m, trecho de enchimento equivalente na largura do porto
L_PRISMA = A_PRISMA / B_RIO     # m; prisma de maré = A_PRISMA * amplitude

# Duas camadas (cunha salina), calibradas em dois pontos de vazão; ver docstring
Q_BAIXA, SIGMA_BAIXA, H_SUP_BAIXA = 230.0, 0.7, 3.8  # Zaleski & Schettini, jan/2000
Q_ALTA, SIGMA_ALTA, H_SUP_ALTA = 1100.0, 0.0, 4.7    # observação de 12/11/2026, trecho A
SECOES = {'Berço 2': 400.0, 'Trecho A (canal entre as bacias)': 280.0}  # largura (m), Carta 1841


def gamma(h):
    """Inverso da escala da camada de cisalhamento (1/m) para profundidade h."""
    return np.sqrt(2 / LAMBDA) * (F_DARCY / 8) ** 0.25 / h


GAMMA = gamma(H)  # 1/m

velocidades_nos = np.arange(0.5, 2.6, 0.5)  # vazante longe do cais (U_inf)
velocidades_ms = velocidades_nos * NO_PARA_MS


def velocidade(Y, u_inf):
    """U(y) do SKM; v = 0 (escoamento paralelo ao cais)."""
    return u_inf * np.sqrt(1 - np.exp(-GAMMA * Y))


def funcao_corrente(Y, u_inf):
    """psi(y) = integral de 0 a y de U dy (m²/s), forma fechada."""
    s = np.sqrt(1 - np.exp(-GAMMA * Y))
    return u_inf * (2 / GAMMA) * (np.arctanh(np.minimum(s, 1 - 1e-15)) - s)


def tensao_lateral(Y, u_inf):
    """tau_yx = rho*lambda*H*(f/8)^(1/2) * U dU/dy (Pa); finita no cais."""
    return RHO * LAMBDA * H * np.sqrt(F_DARCY / 8) * 0.5 * u_inf**2 * GAMMA * np.exp(-GAMMA * Y)


def vazao(u_inf, h=H):
    """Vazão (m³/s) que produz U_inf com profundidade h."""
    return u_inf * h * (B_RIO - 2 * (1 - np.log(2)) / gamma(h))


def u_inf_de_vazao(q, h=H):
    """U_inf (m/s) produzido pela vazão q (m³/s) com profundidade h."""
    return q / (h * (B_RIO - 2 * (1 - np.log(2)) / gamma(h)))


def tensao_parede(u_inf):
    """tau na parede (Pa); não depende de H para U_inf dado."""
    return RHO * np.sqrt(LAMBDA / 2) * (F_DARCY / 8) ** 0.75 * u_inf**2


def declividade(u_inf):
    """S0 implícito pelo equilíbrio atrito de fundo x gravidade."""
    return F_DARCY * u_inf**2 / (8 * G * H)


# Malha grossa para setas; malha fina (refinada no cais) para os mapas
xs, ys = np.meshgrid(np.linspace(0, C_CAIS, 30), np.linspace(0, B_CANAL, 11))
xf_1d = np.linspace(0, C_CAIS, 61)
yf_1d = B_CANAL * np.linspace(0, 1, 201) ** 2  # pontos concentrados junto ao cais
xf, yf = np.meshgrid(xf_1d, yf_1d)

v_max = velocidades_ms.max()  # U < U_inf em todo o domínio
dx = xs[0, 1] - xs[0, 0]
escala_seta = 0.9 * dx / v_max  # seta mais longa ~ 0,9 espaçamento da malha

fig = go.Figure()
for i, u_inf in enumerate(velocidades_ms):
    U = velocidade(yf, u_inf)
    tau = tensao_lateral(yf, u_inf)
    fig.add_trace(
        go.Heatmap(
            x=xf_1d, y=yf_1d, z=U,
            customdata=tau,
            colorscale='Viridis', zmin=0, zmax=v_max,
            colorbar=dict(title='|V| (m/s)'),
            visible=(i == 0),
            hovertemplate=(
                'X: %{x:.0f} m<br>Y: %{y:.1f} m<br>'
                'U: %{z:.2f} m/s<br>τ lateral: %{customdata:.2f} Pa<extra></extra>'
            ),
        )
    )
    seta = ff.create_quiver(
        xs, ys, velocidade(ys, u_inf), np.zeros_like(ys),
        scale=escala_seta, arrow_scale=0.3,
        line=dict(color='white', width=1.2),
    ).data[0]
    seta.update(visible=(i == 0), hoverinfo='skip', showlegend=False)
    fig.add_trace(seta)
    # Linhas de corrente = isolinhas de psi (vazão de 10 m x U_inf entre elas)
    fig.add_trace(
        go.Contour(
            x=xf_1d, y=yf_1d, z=funcao_corrente(yf, u_inf),
            contours=dict(coloring='none', start=0, end=u_inf * B_CANAL, size=u_inf * 10),
            line=dict(color='rgba(0,0,0,0.45)', width=1, dash='dot'),
            showscale=False, showlegend=False, hoverinfo='skip', visible=(i == 0),
        )
    )


def titulo(nos, u_inf):
    return (
        f'Corrente junto ao cais, Bacia 1 (ZP-21) — vazante de {nos:.1f} nós'
        f'<br><sup>{INSTANTE:%d/%m/%Y %H:%M} (UTC-3): maré {ETA:.2f} m, H = {H:.2f} m · '
        f'Q equivalente ≈ {vazao(u_inf):.0f} m³/s · '
        f'τ na parede = {tensao_lateral(0.0, u_inf):.2f} Pa · '
        f'S₀ implícito = {declividade(u_inf):.1e} · '
        f'camada de cisalhamento ≈ {3 / GAMMA:.0f} m (3/γ)</sup>'
    )


n = len(velocidades_nos)
steps = [
    dict(
        method='update',
        args=[
            {'visible': [j // 3 == i for j in range(3 * n)]},  # 3 traços por passo
            {'title': {'text': titulo(nos, u)}},
        ],
        label=f'{nos:.1f} kn',
    )
    for i, (nos, u) in enumerate(zip(velocidades_nos, velocidades_ms))
]

fig.update_layout(
    title={'text': titulo(velocidades_nos[0], velocidades_ms[0])},
    showlegend=False,
    xaxis=dict(title='Eixo longitudinal do cais (m)', range=[0, C_CAIS], constrain='domain'),
    yaxis=dict(
        title='Distância do cais (m)', range=[0, B_CANAL],
        scaleanchor='x', scaleratio=1,  # escala real
    ),
    shapes=[dict(  # linha do cais
        type='line', x0=0, x1=C_CAIS, y0=0, y1=0, line=dict(color='black', width=4),
    )],
    sliders=[dict(active=0, currentvalue={'prefix': 'Vazante: '}, pad={'t': 50}, steps=steps)],
)

def serie_corrente(inicio, horas=24, passo_min=10, q_rio=None, area=A_MONTANTE):
    """Série temporal no berço: tempos, maré (m), H (m), U_inf (m/s, + vazante), tau (Pa, com sinal)."""
    q_rio = Q_RIO if q_rio is None else q_rio
    n = int(horas * 60 / passo_min) + 1
    tempos = [inicio + timedelta(minutes=passo_min * k) for k in range(n)]
    eta = mare(tempos)
    atrasado = mare([t - timedelta(seconds=ATRASO_FLUXO_S) for t in tempos])
    deta = np.gradient(atrasado, 60.0 * passo_min)  # m/s, na foz, defasado
    h = PROF_ZH + eta
    u = u_inf_de_vazao(q_rio - area * deta, h)
    return tempos, eta, h, u, np.sign(u) * tensao_parede(u)


def parametros_cunha(q_rio):
    """(sigma, h_sup) para a vazão do rio, interpolando entre Q_BAIXA e Q_ALTA."""
    f = min(1.0, max(0.0, (q_rio - Q_BAIXA) / (Q_ALTA - Q_BAIXA)))
    return SIGMA_BAIXA + (SIGMA_ALTA - SIGMA_BAIXA) * f, H_SUP_BAIXA + (H_SUP_ALTA - H_SUP_BAIXA) * f


def camadas(q_rio, q_mare, h, largura):
    """(u_sup, u_inf) em m/s para vazão do rio, vazão de maré (+ vazante), coluna h e largura."""
    q_mare, h = np.asarray(q_mare, float), np.asarray(h, float)
    sigma, h_sup = parametros_cunha(q_rio)
    q_sup = q_rio / (1 - sigma) + np.maximum(q_mare, 0)
    q_inf = q_rio + q_mare - q_sup
    return q_sup / (largura * h_sup), q_inf / (largura * (h - h_sup))


def serie_camadas(inicio, largura, horas=24, passo_min=10, q_rio=None):
    """Série no trecho de largura dada: tempos, u_sup, u_inf (m/s, + vazante) e tau (Pa) com u_sup."""
    q_rio = Q_RIO if q_rio is None else q_rio
    tempos, eta, h, u, _ = serie_corrente(inicio, horas, passo_min, q_rio)
    q_mare = vazao(u, h) - q_rio
    u_sup, u_inf = camadas(q_rio, q_mare, h, largura)
    return tempos, u_sup, u_inf, np.sign(u_sup) * tensao_parede(u_sup)


def tabela_camadas(inicio=None):
    """Máximos de corrente na superfície e no fundo, por seção, no dia do INSTANTE."""
    inicio = inicio or INSTANTE.replace(hour=0, minute=0, second=0, microsecond=0)
    sigma, h_sup = parametros_cunha(Q_RIO)
    print(f'\nDuas camadas, {inicio:%d/%m/%Y} (Q_rio = {Q_RIO:.0f} m³/s: sigma = {sigma:.2f}, '
          f'camada superior {h_sup:.1f} m)')
    for nome, larg in SECOES.items():
        tempos, us, ui, tau = serie_camadas(inicio, larg)
        i, j = int(np.argmax(us)), int(np.argmin(ui))
        print(f'  {nome} ({larg:.0f} m): superfície até {us[i] / NO_PARA_MS:.2f} nós às {tempos[i]:%H:%M} '
              f'(τ = {tau[i]:.2f} Pa); fundo entrando até {-ui[j] / NO_PARA_MS:.2f} nós às {tempos[j]:%H:%M}')


def tabela_corrente(inicio=None):
    """Corrente e tensão de hora em hora no dia do INSTANTE."""
    inicio = inicio or INSTANTE.replace(hour=0, minute=0, second=0, microsecond=0)
    tempos, eta, h, u, tau = serie_corrente(inicio)
    print(f'\nCorrente no berço, {inicio:%d/%m/%Y} (Q_rio = {Q_RIO:.0f} m³/s, '
          f'A_ef = {A_MONTANTE / 1e6:.1f} km², atraso {ATRASO_FLUXO_S / 3600:.1f} h; '
          f'+ vazante, - enchente)')
    print(f"{'hora':>5} | {'maré (m)':>8} | {'U (nós)':>8} | {'τ (Pa)':>7}")
    for k in range(0, len(tempos), 6):
        print(f'{tempos[k]:%H:%M} | {eta[k]:>8.2f} | {u[k] / NO_PARA_MS:>8.2f} | {tau[k]:>7.3f}')
    i, j = int(np.argmax(u)), int(np.argmin(u))
    print(f'máx. vazante {u[i] / NO_PARA_MS:.2f} nós às {tempos[i]:%H:%M} (τ = {tau[i]:.3f} Pa); '
          f'máx. enchente {-u[j] / NO_PARA_MS:.2f} nós às {tempos[j]:%H:%M} (τ = {tau[j]:.3f} Pa)')


def tabela_vazoes(vazoes=(250, 500, 1000, 2000, 4000)):
    """U_inf e tau na parede por vazão, na baixa-mar e na preamar do dia do INSTANTE."""
    dia = INSTANTE.replace(hour=0, minute=0, second=0, microsecond=0)
    etas = [e[1] for e in MARE.extremos(_local(dia), _local(dia) + timedelta(days=1))]
    h_min, h_max = PROF_ZH + min(etas), PROF_ZH + max(etas)
    print(f'{dia:%d/%m/%Y}: H de {h_min:.2f} m (baixa-mar) a {h_max:.2f} m (preamar), B = {B_RIO:.0f} m')
    print(f"{'Q (m³/s)':>9} | {'U_inf (nós)':>17} | {'τ parede (Pa)':>17}")
    for q in vazoes:
        u1, u2 = u_inf_de_vazao(q, h_min), u_inf_de_vazao(q, h_max)
        print(f'{q:>9.0f} | {u1 / NO_PARA_MS:>7.2f} a {u2 / NO_PARA_MS:>6.2f} | '
              f'{tensao_parede(u1):>7.3f} a {tensao_parede(u2):>6.3f}')


if __name__ == '__main__':
    tabela_vazoes()
    tabela_corrente()
    tabela_camadas()
    fig.write_html('cisalhamento_berco2_zp21.html', include_plotlyjs='cdn')
    fig.show()
