"""Maré astronômica do Porto de Itajaí (SC): previsão em qualquer instante.

Uso:
    python mare_itajai.py "2026-11-12 14:30"        # altura, tendência, PM/BM vizinhas
    python mare_itajai.py "2026-11-12 14:30" --dias 3   # janela do gráfico (padrão 2)
    python mare_itajai.py                              # agora
    python mare_itajai.py --constantes                 # grava a tabela de constantes

Horários em hora legal de Brasília (UTC-3, o "fuso +3" da tábua). Alturas em
metros acima do nível de redução (NR) da DHN, o mesmo zero das cartas
náuticas e da Tábua das Marés.

Origem das constantes
---------------------
A DHN/CHM prevê a maré de Itajaí com 77 (2024) ou 78 (2025, 2026)
componentes harmônicas, mas não publica a tabela de constantes. Elas são
reconstruídas aqui por mínimos quadrados a partir da própria previsão
oficial: os 5422 extremos (preamares e baixa-mares) das Tábuas das Marés de
2024, 2025 e 2026 do Porto de Itajaí (dados/tabua_mare_itajai_AAAA.csv).
Cada extremo fornece duas equações lineares nos mesmos coeficientes:

    h(t_i) = altura tabelada     e     dh/dt(t_i) = 0  (é um extremo)

A segunda usa a informação de horário da tábua; sem ela o erro de horário
dobra. Correções nodais e argumentos astronômicos (f, u, V0) vêm do UTide
(Codiga 2011), de modo que as constantes valem para qualquer ano.

Validação (ver README): ajustado só com 2024 e 2025, previu a tábua oficial
de 2026 com erro RMS de altura de 2,9 cm e erro mediano de horário de 6 min
(90 % dentro de 17 min). Em estofos rasos (preamar ou baixa-mar quase planas)
o horário do extremo é mal definido por natureza e o erro pode passar de 30 min.

Limitações: é a maré ASTRONÔMICA. Vento, maré meteorológica e vazão do rio
Itajaí-Açu podem alterar o nível observado em dezenas de centímetros.
"""

import argparse
import csv
import datetime as dt
import os

import numpy as np
import plotly.graph_objects as go
import utide
from utide._time_conversion import _normalize_time
from utide.harmonics import FUV

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ_TABUAS = [os.path.join(AQUI, 'dados', f'tabua_mare_itajai_{ano}.csv') for ano in (2024, 2025, 2026)]
ARQ_CONST = os.path.join(AQUI, 'dados', 'constantes_harmonicas_itajai.csv')

LAT = -26.91  # Porto de Itajaí (tábua: 26°54,6' S, 048°39,2' W)
FUSO = dt.timedelta(hours=-3)  # hora legal = UTC - 3 h
MIN = np.timedelta64(1, 'm')
Z0_OFICIAL = 0.60  # m, nível médio acima do NR (tábuas 2025-2026; 2024: 0,59; F-41: 59,4 cm)

# Escolhidos por validação cruzada (ver README)
RAYLEIGH_MIN = 1.0  # critério de Rayleigh na seleção automática de componentes
PESO_DERIVADA = 1.0  # peso (h) das equações dh/dt = 0 frente às de altura (m)


# --- Tempo ------------------------------------------------------------------
def local_para_utc64(t):
    """datetime local (ingênuo, UTC-3) ou array deles -> numpy datetime64 UTC."""
    t = np.atleast_1d(np.asarray(t, dtype='datetime64[s]'))
    return t - np.timedelta64(int(FUSO.total_seconds()), 's')


def utc64_para_local(t):
    return (np.asarray(t, dtype='datetime64[s]') + np.timedelta64(int(FUSO.total_seconds()), 's'))


# --- Modelo harmônico -----------------------------------------------------
class Mare:
    """h(t) = Z0 + sum_k f_k(t) [a_k cos(V_k+u_k) + b_k sin(V_k+u_k)],  A = |a+ib|, g = arg."""

    def __init__(self, arq_tabuas=ARQ_TABUAS):
        t_loc, h = [], []
        for arq in arq_tabuas:
            with open(arq, newline='') as f:
                for linha in csv.DictReader(f):
                    t_loc.append(dt.datetime.strptime(linha['data_hora_local'], '%Y-%m-%d %H:%M'))
                    h.append(float(linha['altura_m']))
        self.t_tabua = local_para_utc64(t_loc)
        self.h_tabua = np.array(h)

        # Seleção de componentes resolvíveis no período (critério de Rayleigh), como no UTide
        sel = utide.solve(
            self.t_tabua.astype('datetime64[m]'), self.h_tabua, lat=LAT, method='ols',
            conf_int='none', trend=False, Rayleigh_min=RAYLEIGH_MIN, verbose=False,
        )
        self.nomes = list(sel.name)
        self.lind = sel.aux.lind
        self.frq = sel.aux.frq  # ciclos/hora
        self.tref = sel.aux.reftime
        self.x = self._ajustar(self.t_tabua, self.h_tabua, PESO_DERIVADA)

    def _base(self, t_utc):
        tn = _normalize_time(np.asarray(t_utc, dtype='datetime64[m]'), None)
        F, U, V = FUV(tn, self.tref, self.lind, LAT, [0, 0, 0, 0])
        fase = 2 * np.pi * (U + V)
        return F * np.cos(fase), F * np.sin(fase), 2 * np.pi * self.frq  # w em rad/h

    def _matriz(self, t_utc, derivada=False):
        C, S, w = self._base(t_utc)
        n = len(C)
        if derivada:  # dh/dt em m/h (f e u variam em 18,6 anos: derivada desprezível)
            return np.hstack([np.zeros((n, 1)), -w * S, w * C])
        return np.hstack([np.ones((n, 1)), C, S])

    def _ajustar(self, t, h, peso):
        A = np.vstack([self._matriz(t), peso * self._matriz(t, derivada=True)])
        b = np.concatenate([h, np.zeros(len(t))])
        return np.linalg.lstsq(A, b, rcond=None)[0]

    # Constantes no formato usual: amplitude (m) e fase de Greenwich g (graus)
    @property
    def z0(self):
        return self.x[0]

    def constantes(self):
        n = len(self.nomes)
        a, b = self.x[1:n + 1], self.x[n + 1:]
        amp = np.hypot(a, b)
        g = np.degrees(np.arctan2(b, a)) % 360
        ordem = np.argsort(-amp)
        return [(self.nomes[i], self.frq[i], amp[i], g[i]) for i in ordem]

    def altura_utc(self, t_utc):
        return self._matriz(np.atleast_1d(t_utc)) @ self.x

    def altura(self, t_local):
        """Altura (m acima do NR) em instante(s) local(is)."""
        return self.altura_utc(local_para_utc64(t_local))

    def serie(self, ini_local, fim_local, passo_min=1):
        t = np.arange(np.datetime64(ini_local, 'm'), np.datetime64(fim_local, 'm'),
                      np.timedelta64(passo_min, 'm'))
        return t, self.altura(t)

    def extremos(self, ini_local, fim_local):
        """Preamares/baixa-mares (resolução de 1 min, com refino parabólico)."""
        t, h = self.serie(np.datetime64(ini_local, 'm') - MIN, np.datetime64(fim_local, 'm') + 2 * MIN)
        d = np.diff(h)
        i = np.where(np.sign(d[1:]) != np.sign(d[:-1]))[0] + 1
        out = []
        for k in i:
            y0, y1, y2 = h[k - 1], h[k], h[k + 1]
            den = y0 - 2 * y1 + y2
            dx = 0.5 * (y0 - y2) / den if den != 0 else 0.0
            tk = t[k] + np.timedelta64(int(round(dx * 60)), 's')
            hk = y1 - 0.25 * (y0 - y2) * dx
            out.append((tk, hk, 'PM' if den < 0 else 'BM'))
        return out


# --- Gráfico ----------------------------------------------------------------
def grafico(mare, instante, dias=2.0):
    meio = np.timedelta64(int(dias * 12 * 60), 'm')
    t0 = np.datetime64(instante, 'm')
    t, h = mare.serie(t0 - meio, t0 + meio, passo_min=5)
    ext = mare.extremos(t0 - meio, t0 + meio)
    h0 = mare.altura(t0)[0]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=t.astype('datetime64[ms]').astype(object), y=h, mode='lines', name='Maré astronômica',
        line=dict(color='#1f6fb2', width=2.5),
        hovertemplate='%{x|%d/%m %H:%M}<br>%{y:.2f} m<extra></extra>',
    ))
    for tipo, cor, pos in (('PM', '#c0392b', 'top center'), ('BM', '#16a085', 'bottom center')):
        sel = [e for e in ext if e[2] == tipo]
        fig.add_trace(go.Scatter(
            x=[e[0].astype('datetime64[ms]').astype(object) for e in sel], y=[e[1] for e in sel],
            mode='markers+text', name='Preamar' if tipo == 'PM' else 'Baixa-mar',
            marker=dict(color=cor, size=8),
            text=[f"{e[0].astype(dt.datetime):%H:%M}<br>{e[1]:.2f}" for e in sel],
            textposition=pos, textfont=dict(size=10, color=cor),
            hovertemplate='%{x|%d/%m %H:%M}<br>%{y:.2f} m<extra>' + tipo + '</extra>',
        ))
    fig.add_trace(go.Scatter(
        x=[t0.astype('datetime64[ms]').astype(object)], y=[h0], mode='markers', name='Instante consultado',
        marker=dict(color='black', size=12, symbol='diamond'),
        hovertemplate='%{x|%d/%m/%Y %H:%M}<br>%{y:.2f} m<extra></extra>',
    ))
    fig.add_hline(y=mare.z0, line=dict(color='gray', dash='dot'),
                  annotation_text=f'Nível médio {mare.z0:.2f} m', annotation_position='bottom right')
    fig.add_hline(y=0, line=dict(color='black', width=1),
                  annotation_text='NR (zero da carta)', annotation_position='bottom right')
    fig.add_vline(x=t0.astype('datetime64[ms]').astype(object), line=dict(color='black', dash='dash', width=1))
    fig.update_layout(
        title=dict(text=(f'Maré astronômica — Porto de Itajaí · {t0.astype(dt.datetime):%d/%m/%Y %H:%M} '
                         f'(UTC−3): {h0:.2f} m<br><sup>Alturas acima do NR da DHN · '
                         f'{len(mare.nomes)} componentes ajustadas às Tábuas das Marés 2024–2026 (CHM) · '
                         'não inclui efeitos meteorológicos nem vazão do rio</sup>')),
        xaxis=dict(title='Hora legal (UTC−3)', tickformat='%d/%m\n%H:%M'),
        yaxis=dict(title='Altura (m acima do NR)'),
        hovermode='x unified', legend=dict(orientation='h', y=-0.2),
        template='plotly_white',
    )
    return fig


# --- Linha de comando ------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('instante', nargs='?', help='"AAAA-MM-DD HH:MM" em hora local (padrão: agora)')
    ap.add_argument('--dias', type=float, default=2.0, help='largura da janela do gráfico (dias)')
    ap.add_argument('--saida', default='grafico_mare_itajai.html')
    ap.add_argument('--sem-grafico', action='store_true')
    ap.add_argument('--constantes', action='store_true', help=f'grava {os.path.relpath(ARQ_CONST, AQUI)}')
    args = ap.parse_args()

    mare = Mare()
    if args.constantes:
        with open(ARQ_CONST, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['componente', 'frequencia_ciclos_por_hora', 'amplitude_m', 'fase_greenwich_graus'])
            w.writerow(['Z0', '0', f'{mare.z0:.4f}', ''])
            for nome, frq, amp, g in mare.constantes():
                w.writerow([nome, f'{frq:.8f}', f'{amp:.4f}', f'{g:.1f}'])
        print(f'{len(mare.nomes)} componentes gravadas em {ARQ_CONST}')

    if args.instante:
        t0 = np.datetime64(dt.datetime.fromisoformat(args.instante), 'm')
    else:
        t0 = np.datetime64(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + FUSO, 'm')

    h0 = mare.altura(t0)[0]
    dh = (mare.altura(t0 + MIN * 5)[0] - mare.altura(t0 - MIN * 5)[0]) / (10 / 60)  # m/h
    ext = mare.extremos(t0 - np.timedelta64(14, 'h'), t0 + np.timedelta64(14, 'h'))
    antes = [e for e in ext if e[0] <= t0][-2:]
    depois = [e for e in ext if e[0] > t0][:3]
    fmt = lambda e: f"  {e[2]}  {e[0].astype(dt.datetime):%d/%m %H:%M}  {e[1]:5.2f} m"
    print(f'Porto de Itajaí — {t0.astype(dt.datetime):%d/%m/%Y %H:%M} (UTC-3)')
    print(f'  altura: {h0:.2f} m acima do NR  ({"enchendo" if dh > 0 else "vazando"}, {dh*100:+.0f} cm/h)')
    print('Extremos anteriores:'); print('\n'.join(map(fmt, antes)))
    print('Próximos extremos:'); print('\n'.join(map(fmt, depois)))

    if not args.sem_grafico:
        grafico(mare, t0, args.dias).write_html(args.saida, include_plotlyjs='cdn')
        print(f'Gráfico: {args.saida}')


if __name__ == '__main__':
    main()
