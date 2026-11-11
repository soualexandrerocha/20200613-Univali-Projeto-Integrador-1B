"""Campo de corrente de vazante ilustrativo na Bacia 1 / Berço 2 (ZP-21).

ATENÇÃO: o campo de velocidades abaixo é um modelo cinemático analítico,
NÃO o resultado de um modelo hidrodinâmico nem de medições. Serve para
visualização didática do efeito de borda junto ao cais. Limitações conhecidas:
  - não satisfaz continuidade (du/dx + dv/dy != 0);
  - a componente transversal v não se anula no cais (Y=0), ou seja, há
    fluxo "atravessando" a parede (viola a condição de impermeabilidade);
  - não há condição de não-deslizamento: u no cais vale 70% de v_nom.
"""

import numpy as np
import plotly.graph_objects as go

NO_PARA_MS = 1852 / 3600  # 1 nó = 0,514444 m/s

# 1. Malha espacial
y = np.linspace(0, 100, 20)  # coordenada transversal do canal (m)
x = np.linspace(0, 300, 30)  # coordenada longitudinal ao longo do cais (m)
X, Y = np.meshgrid(x, y)
Z = np.zeros_like(X)

# Velocidades de vazante a testar (0,5 a 2,5 nós)
velocidades_nos = np.arange(0.5, 2.6, 0.5)
velocidades_ms = velocidades_nos * NO_PARA_MS


def campo(v_nom):
    """Perfil simplificado: mais rápido no canal (Y alto), desacelera perto do cais."""
    u = v_nom * (1 - 0.3 * np.exp(-Y / 30.0) * np.sin(np.pi * X / 300))
    v = v_nom * 0.15 * np.cos(np.pi * X / 300)  # componente transversal (ângulo de ataque)
    return u, v


# Escala de cor e tamanho FIXAS entre os passos do slider; sem isso cada traço
# se autonormaliza e 0,5 kn fica visualmente idêntico a 2,5 kn.
v_max = max(np.hypot(*campo(v)).max() for v in velocidades_ms)
dx = x[1] - x[0]

fig = go.Figure()
for i, v_nom in enumerate(velocidades_ms):
    u, v = campo(v_nom)
    fig.add_trace(
        go.Cone(
            x=X.ravel(), y=Y.ravel(), z=Z.ravel(),
            u=u.ravel(), v=v.ravel(), w=Z.ravel(),
            colorscale='Viridis',
            cmin=0, cmax=v_max,
            sizemode='raw',  # comprimento do cone = |V| * sizeref (unidades do eixo)
            sizeref=0.9 * dx / v_max,  # cone mais longo ~ 0,9 espaçamento da malha
            anchor='tail',
            name=f'{velocidades_nos[i]:.1f} nós',
            visible=(i == 0),
            colorbar=dict(title='|V| (m/s)'),
            hovertemplate=(
                'X: %{x:.0f} m<br>Y: %{y:.0f} m<br>'
                'u: %{u:.2f} m/s<br>v: %{v:.2f} m/s<br>'
                '|V|: %{norm:.2f} m/s<extra></extra>'
            ),
        )
    )


def titulo(nos):
    return f'Campo de corrente na Bacia 1 (ZP-21) — vazante de {nos:.1f} nós'


steps = [
    dict(
        method='update',
        args=[
            {'visible': [j == i for j in range(len(velocidades_nos))]},
            {'title': {'text': titulo(nos)}},
        ],
        label=f'{nos:.1f} kn',
    )
    for i, nos in enumerate(velocidades_nos)
]

fig.update_layout(
    title={'text': titulo(velocidades_nos[0])},
    scene=dict(
        xaxis_title='Eixo longitudinal do cais (m)',
        yaxis_title='Distância do cais (m)',
        zaxis=dict(visible=False),
        aspectmode='manual',
        aspectratio=dict(x=3, y=1, z=0.1),  # escala real 300 m x 100 m
        camera=dict(eye=dict(x=0, y=-1.5, z=1.2)),
    ),
    sliders=[dict(active=0, currentvalue={'prefix': 'Vazante: '}, pad={'t': 50}, steps=steps)],
)

if __name__ == '__main__':
    fig.write_html('cisalhamento_berco2_zp21.html', include_plotlyjs='cdn')
    fig.show()
