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
apenas por meio de U_inf, que depende da vazão do rio e da fase da maré e
ainda é dado de entrada aqui.
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
# 10/12/2026: Itajaí 2 = 12,8 m; Bacia de evolução 01 = 12,8 m. É a menor
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

GAMMA = np.sqrt(2 / LAMBDA) * (F_DARCY / 8) ** 0.25 / H  # 1/m

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

if __name__ == '__main__':
    fig.write_html('cisalhamento_berco2_zp21.html', include_plotlyjs='cdn')
    fig.show()
