"""Gera pagina/folga_quilha.html: formulário de folga estática sob a quilha
(UKC) e janelas de manobra no Porto de Itajaí, autossuficiente (abre no
navegador ou no celular, sem Python).

    python ferramentas/gerar_painel_ukc.py
    python ferramentas/testar_painel_ukc.py    # confere o cálculo contra o Python

A página recebe:
  - os dados da maré (os mesmos de pagina/mare_itajai.html, via
    gerar_pagina.dados) e o núcleo pagina/nucleo_mare.js;
  - o núcleo do cálculo da folga, pagina/nucleo_ukc.js (sem DOM);
  - o modelo pagina/modelo_ukc.html (formulário, gráfico e tabelas).

Entradas no formulário: período, duração da manobra, reserva de nível,
pontos de profundidade com o referencial de cada um (NR, outro zero com cota
em relação ao NR, ou medida no instante), calados AV/AR ou médio e trim,
densidades e FWA, folga mínima em metros ou % do calado.
"""

import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'ferramentas'))

import gerar_pagina  # noqa: E402
import mare_itajai as m  # noqa: E402

PASTA = os.path.join(RAIZ, 'pagina')


def ler(nome):
    with open(os.path.join(PASTA, nome), encoding='utf-8') as f:
        return f.read()


def montar(dados):
    return (ler('modelo_ukc.html')
            .replace('/*NUCLEO*/', ler('nucleo_mare.js'))
            .replace('/*NUCLEO_UKC*/', ler('nucleo_ukc.js'))
            .replace('/*DADOS*/', json.dumps(dados, separators=(',', ':'))))


if __name__ == '__main__':
    html = montar(gerar_pagina.dados(m.Mare()))
    saida = os.path.join(PASTA, 'folga_quilha.html')
    with open(saida, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'{saida}: {len(html) / 1e3:.0f} kB')
