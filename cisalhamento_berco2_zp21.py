"""Campo de corrente de vazante ilustrativo na Bacia 1 / Berço 2 (ZP-21).

ATENÇÃO: o campo de velocidades abaixo é um modelo cinemático analítico,
NÃO o resultado de um modelo hidrodinâmico nem de medições. Serve para
visualização didática do efeito de borda junto ao cais.

O campo deriva de uma função de corrente

    psi(x, y) = v_nom * [ y - A * L * (1 - exp(-y/L)) * sin(pi*x/C) ]
    u =  d(psi)/dy = v_nom * [1 - A * exp(-y/L) * sin(pi*x/C)]
    v = -d(psi)/dx = v_nom * A * L * (pi/C) * (1 - exp(-y/L)) * cos(pi*x/C)

o que garante, por construção:
  - continuidade (du/dx + dv/dy = 0, escoamento incompressível 2D);
  - impermeabilidade no cais: psi(x, 0) = 0, logo v(x, 0) = 0.
A componente transversal não é livre: decorre do déficit de u junto ao cais.

Limitações conhecidas:
  - não há condição de não-deslizamento: u no cais vale (1 - A) * v_nom;
  - A e L são escolhas arbitrárias, não calibradas;
  - a borda do canal (y = 100 m) é aberta, não uma parede.
"""

import numpy as np
import plotly.figure_factory as ff
import plotly.graph_objects as go

NO_PARA_MS = 1852 / 3600  # 1 nó = 0,514444 m/s
C_CAIS = 300.0  # m, comprimento do trecho de cais modelado
A_DEFICIT = 0.3  # fração de redução de u no cais, no centro do trecho
L_CISALHAMENTO = 30.0  # m, decaimento do déficit de u a partir do cais

# Velocidades de vazante a testar (0,5 a 2,5 nós)
velocidades_nos = np.arange(0.5, 2.6, 0.5)
velocidades_ms = velocidades_nos * NO_PARA_MS


def funcao_corrente(X, Y, v_nom):
    """psi (m²/s); as linhas de psi constante são as linhas de corrente."""
    s = np.sin(np.pi * X / C_CAIS)
    return v_nom * (Y - A_DEFICIT * L_CISALHAMENTO * (1 - np.exp(-Y / L_CISALHAMENTO)) * s)


def campo(X, Y, v_nom):
    """Velocidades (u, v) = (dpsi/dy, -dpsi/dx), derivadas analiticamente."""
    k = np.pi / C_CAIS
    u = v_nom * (1 - A_DEFICIT * np.exp(-Y / L_CISALHAMENTO) * np.sin(k * X))
    v = v_nom * A_DEFICIT * L_CISALHAMENTO * k * (1 - np.exp(-Y / L_CISALHAMENTO)) * np.cos(k * X)
    return u, v


# Malha grossa para as setas e malha fina para o mapa de |V| ao fundo
xs, ys = np.meshgrid(np.linspace(0, C_CAIS, 30), np.linspace(0, 100, 11))
xf_1d, yf_1d = np.linspace(0, C_CAIS, 151), np.linspace(0, 100, 51)
xf, yf = np.meshgrid(xf_1d, yf_1d)

# Escalas FIXAS entre os passos do slider, para que 0,5 kn e 2,5 kn
# sejam visualmente comparáveis (cor e comprimento das setas).
v_max = max(np.hypot(*campo(xf, yf, v)).max() for v in velocidades_ms)
dx = xs[0, 1] - xs[0, 0]
escala_seta = 0.9 * dx / v_max  # seta mais longa ~ 0,9 espaçamento da malha

fig = go.Figure()
for i, v_nom in enumerate(velocidades_ms):
    uf, vf = campo(xf, yf, v_nom)
    fig.add_trace(
        go.Heatmap(
            x=xf_1d, y=yf_1d, z=np.hypot(uf, vf),
            colorscale='Viridis', zmin=0, zmax=v_max,
            colorbar=dict(title='|V| (m/s)'),
            visible=(i == 0),
            hovertemplate=(
                'X: %{x:.0f} m<br>Y: %{y:.0f} m<br>'
                '|V|: %{z:.2f} m/s<extra></extra>'
            ),
        )
    )
    u, v = campo(xs, ys, v_nom)
    seta = ff.create_quiver(
        xs, ys, u, v, scale=escala_seta, arrow_scale=0.3,
        line=dict(color='white', width=1.2),
    ).data[0]
    seta.update(visible=(i == 0), hoverinfo='skip', showlegend=False)
    fig.add_trace(seta)
    # Linhas de corrente = isolinhas de psi; a de psi = 0 coincide com o cais.
    fig.add_trace(
        go.Contour(
            x=xf_1d, y=yf_1d, z=funcao_corrente(xf, yf, v_nom),
            contours=dict(coloring='none', start=0, end=v_nom * 100, size=v_nom * 10),
            line=dict(color='rgba(0,0,0,0.45)', width=1, dash='dot'),
            showscale=False, showlegend=False, hoverinfo='skip', visible=(i == 0),
        )
    )


def titulo(nos):
    return f'Campo de corrente na Bacia 1 (ZP-21) — vazante de {nos:.1f} nós'


n = len(velocidades_nos)
steps = [
    dict(
        method='update',
        args=[
            {'visible': [j // 3 == i for j in range(3 * n)]},  # 3 traços por passo
            {'title': {'text': titulo(nos)}},
        ],
        label=f'{nos:.1f} kn',
    )
    for i, nos in enumerate(velocidades_nos)
]

fig.update_layout(
    title={'text': titulo(velocidades_nos[0])},
    showlegend=False,
    xaxis=dict(title='Eixo longitudinal do cais (m)', range=[0, C_CAIS], constrain='domain'),
    yaxis=dict(
        title='Distância do cais (m)', range=[0, 100],
        scaleanchor='x', scaleratio=1,  # escala real 300 m x 100 m
    ),
    shapes=[dict(  # linha do cais
        type='line', x0=0, x1=C_CAIS, y0=0, y1=0, line=dict(color='black', width=4),
    )],
    sliders=[dict(active=0, currentvalue={'prefix': 'Vazante: '}, pad={'t': 50}, steps=steps)],
)

if __name__ == '__main__':
    fig.write_html('cisalhamento_berco2_zp21.html', include_plotlyjs='cdn')
    fig.show()
