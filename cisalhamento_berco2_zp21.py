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
acima do zero hidrográfico prevista por previsao_mare_itajai.py no instante
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

Corrente de maré (modelo de bombeamento, ou prisma de maré): o volume
entre o berço e o limite da maré enche e esvazia pelo berço, com

    Q_mare(t) = -A_MONTANTE * d(eta)/dt     (positivo = vazante)
    U_inf(t)  = (Q_RIO + Q_mare(t)) / (H(t) * (B_RIO - delta))

A_MONTANTE é a área da superfície livre a montante do berço. O valor
adotado, 400 m x 90 km (limite da maré em Indaial), é um limite superior:
supõe largura constante e nível em fase em todo o estuário, sem a atenuação
por atrito da maré observada no Itajaí-Açu. Ele é conservador para a tensão.
Ordem de grandeza conferida com medições de Schettini & Carvalho (1998),
na barra e 12 km a montante: variação da corrente média na vertical de 77 a
140 cm/s ao longo do ciclo de maré. Ressalva: essas medições são de
1994-95, com o canal a ~8 m (hoje ~13 m). Para a mesma vazão, a seção
atual reduz a velocidade em ~8/13, o que levaria a faixa para ~0,5 a 0,8 nó
de amplitude. Já o aprofundamento tende a aumentar o prisma (menos atrito),
e o efeito líquido é desconhecido. Isso não é validação; falta medição de
corrente atual. O modelo ignora a estratificação da
cunha salina, que separa a corrente de superfície (vazante) da de fundo
(enchente).
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import plotly.figure_factory as ff
import plotly.graph_objects as go

from previsao_mare_itajai import prever_mare_itajai

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
PROF_ZH = 12.8  # m
INSTANTE = datetime(2026, 11, 12, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
ETA = prever_mare_itajai(INSTANTE)  # m acima do zero hidrográfico
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
# Vazão fluvial média do Itajaí-Açu no estuário, ~215 m³/s (Zaleski &
# Schettini, 2003, Notas Téc. Facimar 7:63-72). Trocar pela vazão do dia.
Q_RIO = 215.0  # m³/s
A_MONTANTE = 400.0 * 90e3  # m², limite superior (ver docstring)


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
    eta = np.array([prever_mare_itajai(t) for t in tempos])
    deta = np.gradient(eta, 60.0 * passo_min)  # m/s
    h = PROF_ZH + eta
    u = u_inf_de_vazao(q_rio - area * deta, h)
    return tempos, eta, h, u, np.sign(u) * tensao_parede(u)


def tabela_corrente(inicio=None):
    """Corrente e tensão de hora em hora no dia do INSTANTE."""
    inicio = inicio or INSTANTE.replace(hour=0, minute=0, second=0, microsecond=0)
    tempos, eta, h, u, tau = serie_corrente(inicio)
    print(f'\nCorrente no berço, {inicio:%d/%m/%Y} (Q_rio = {Q_RIO:.0f} m³/s, '
          f'A_montante = {A_MONTANTE / 1e6:.0f} km²; + vazante, - enchente)')
    print(f"{'hora':>5} | {'maré (m)':>8} | {'U (nós)':>8} | {'τ (Pa)':>7}")
    for k in range(0, len(tempos), 6):
        print(f'{tempos[k]:%H:%M} | {eta[k]:>8.2f} | {u[k] / NO_PARA_MS:>8.2f} | {tau[k]:>7.3f}')
    i, j = int(np.argmax(u)), int(np.argmin(u))
    print(f'máx. vazante {u[i] / NO_PARA_MS:.2f} nós às {tempos[i]:%H:%M} (τ = {tau[i]:.3f} Pa); '
          f'máx. enchente {-u[j] / NO_PARA_MS:.2f} nós às {tempos[j]:%H:%M} (τ = {tau[j]:.3f} Pa)')


def tabela_vazoes(vazoes=(250, 500, 1000, 2000, 4000)):
    """U_inf e tau na parede por vazão, na baixa-mar e na preamar do dia do INSTANTE."""
    from previsao_mare_itajai import extremos
    dia = INSTANTE.replace(hour=0, minute=0, second=0, microsecond=0)
    etas = [e[1] for e in extremos(dia)]
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
    fig.write_html('cisalhamento_berco2_zp21.html', include_plotlyjs='cdn')
    fig.show()
