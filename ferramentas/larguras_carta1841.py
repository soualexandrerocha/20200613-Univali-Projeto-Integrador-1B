"""Largura do Itajaí-Açu ao longo do canal, medida na Carta Náutica 1841
(DHN, Porto de Itajaí, GeoTIFF), da foz até o fim da cobertura da carta.

    python ferramentas/larguras_carta1841.py PASTA_COM_OS_TIF

Usa 1841geotiff.tif (folha principal) e plA1841geotiff.tif (plano A,
Volta Grande). Os GeoTIFF não ficam no repositório. Grava
dados/largura_itajai_acu.csv com a distância pelo rio a partir da foz
(junto a DC01) e a largura mediana a cada 500 m.

Método: a água é separada pelas cores da carta (ciano, ciano-claro e
branco; terra é bege e área urbana, cinza); um fechamento morfológico apaga
os números de sondagem. O eixo do rio é o caminho de menor custo entre a foz
e o fim da carta, com custo 1/(distância à margem)^2, o que o mantém no meio
do canal. A largura em cada ponto do eixo é o dobro da distância à margem
mais próxima. As duas folhas são emendadas no ponto do eixo da folha
principal mais próximo do início do eixo do plano A.

Requer rasterio, scipy e scikit-image.
"""

import os
import sys

import numpy as np
import rasterio
from rasterio.warp import transform as reprojetar
from scipy import ndimage as ndi
from skimage.graph import route_through_array
from skimage.morphology import closing, disk, remove_small_holes

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, 'dados', 'largura_itajai_acu.csv')
FOZ = (-48.6516, -26.9085)  # junto a DC01 (CEPSUL)
PASSO_M = 500.0

# (arquivo, subamostragem, início (lon, lat), fim (lon, lat), corte a leste do qual não há rio)
FOLHAS = [
    ('1841geotiff.tif', 4, FOZ, (-48.693, -26.8675), -48.650),
    ('plA1841geotiff.tif', 2, (-48.6917, -26.8825), (-48.7195, -26.8465), None),  # abaixo da ponte
]


def eixo(arquivo, sub, ini, fim, corte):
    with rasterio.open(arquivo) as d:
        a = d.read()[:, ::sub, ::sub]
        T = d.transform * d.transform.scale(sub, sub)
        crs = d.crs
    agua = (a[1] >= 230) & (a[2] >= 230)
    agua = remove_small_holes(closing(agua, disk(3)).astype(bool), max_size=2000)

    def para_px(lon, lat):
        x, y = reprojetar('EPSG:4326', crs, [lon], [lat])
        c, r = ~T * (x[0], y[0])
        return int(r), int(c)

    def para_lonlat(rs, cs):
        xs, ys = T * (np.asarray(cs) + 0.5, np.asarray(rs) + 0.5)
        lon, lat = reprojetar(crs, 'EPSG:4326', list(np.atleast_1d(xs)), list(np.atleast_1d(ys)))
        return np.array(lon), np.array(lat)

    if corte is not None:
        lon_col, _ = para_lonlat([0] * agua.shape[1], range(agua.shape[1]))
        agua[:, lon_col > corte] = False
    rotulos, _ = ndi.label(agua)
    _, (ri, ci) = ndi.distance_transform_edt(~agua, return_indices=True)
    r0, c0 = para_px(*ini)
    r1, c1 = para_px(*fim)
    r0, c0, r1, c1 = ri[r0, c0], ci[r0, c0], ri[r1, c1], ci[r1, c1]  # encaixa na água
    if rotulos[r0, c0] != rotulos[r1, c1]:
        raise SystemExit(f'{arquivo}: início e fim caíram em corpos d’água diferentes')
    rio = rotulos == rotulos[r0, c0]
    dist = ndi.distance_transform_edt(rio)
    custo = np.where(rio, 1.0 / (dist + 1) ** 2, 1e6)
    caminho, _ = route_through_array(custo, (r0, c0), (r1, c1), fully_connected=True, geometric=True)
    caminho = np.array(caminho)
    res = abs(T.a)  # m por pixel na latitude padrão da folha
    lon, lat = para_lonlat(caminho[:, 0], caminho[:, 1])
    s = np.cumsum(np.r_[0, np.hypot(*np.diff(caminho, axis=0).T)]) * res
    largura = 2 * dist[caminho[:, 0], caminho[:, 1]] * res
    return lon, lat, s, largura


def main():
    pasta = sys.argv[1]
    (lon0, lat0, s0, w0), (lon1, lat1, s1, w1) = [
        eixo(os.path.join(pasta, f), *resto) for f, *resto in FOLHAS]
    c = np.cos(np.radians(-26.88))
    d = np.hypot((lon0 - lon1[0]) * c, lat0 - lat1[0]) * 111.2e3
    k = int(np.argmin(d))
    s = np.r_[s0[:k], s0[k] + s1]
    w = np.r_[w0[:k], w1]
    ok = (s > 200) & (s < s[-1] - 300)  # descarta as pontas, encaixadas nas margens
    s, w = s[ok], w[ok]
    grade = np.arange(0, s[-1], PASSO_M)
    medianas = [np.median(w[(s >= g) & (s < g + PASSO_M)]) for g in grade]
    reta = np.hypot((lon1[-1] - FOZ[0]) * c, lat1[-1] - FOZ[1]) * 111.2
    with open(SAIDA, 'w') as f:
        f.write('# Largura do Itajai-Acu medida na Carta Nautica 1841 (DHN); ferramentas/larguras_carta1841.py\n')
        f.write(f'# fim da carta: {s[-1] / 1e3:.2f} km pelo rio, {reta:.2f} km em linha reta da foz\n')
        f.write('s_km,largura_m\n')
        for g, m in zip(grade, medianas):
            f.write(f'{(g + PASSO_M / 2) / 1e3:.2f},{m:.0f}\n')
    print(f'{SAIDA}: {len(grade)} trechos; fim da carta a {s[-1] / 1e3:.1f} km pelo rio, '
          f'{reta:.1f} km em linha reta (sinuosidade {s[-1] / 1e3 / reta:.2f}); '
          f'largura mediana {np.median(medianas):.0f} m')


if __name__ == '__main__':
    main()
