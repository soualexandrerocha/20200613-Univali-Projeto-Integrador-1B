"""Largura do Itajaí-Açu ao longo do canal, medida na Carta Náutica 1841
(DHN, Porto de Itajaí, GeoTIFF), da foz até o fim da cobertura da carta.

    python ferramentas/larguras_carta1841.py PASTA_COM_OS_TIF         # larguras (CSV)
    python ferramentas/larguras_carta1841.py PASTA_COM_OS_TIF --mapa  # geometria do mapa (JSON)

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

Com --mapa, grava também dados/mapa_itajai_acu.json, que o painel
pagina/berco2.html usa para desenhar os vetores de corrente: as margens da água
(contornos simplificados da mesma máscara), o eixo suavizado do rio (0 a 6 km
pela folha principal) e, a cada 400 m, a posição, o rumo do eixo e a largura de
margem a margem, medida na normal ao eixo (inclui os baixios). Coordenadas em
metros, a leste (x) e ao norte (y) de DC01, na projeção Mercator da carta, que
é conforme: os rumos são verdadeiros.

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
SAIDA_MAPA = os.path.join(RAIZ, 'dados', 'mapa_itajai_acu.json')
FOZ = (-48.6516, -26.9085)  # junto a DC01 (CEPSUL)
PASSO_M = 500.0

# (arquivo, subamostragem, início (lon, lat), fim (lon, lat), corte a leste do qual não há rio)
FOLHAS = [
    ('1841geotiff.tif', 4, FOZ, (-48.693, -26.8675), -48.650),
    ('plA1841geotiff.tif', 2, (-48.6917, -26.8825), (-48.7195, -26.8465), None),  # abaixo da ponte
]


def _preparar(arquivo, sub, corte):
    """Máscara de água, transformação, CRS e conversores de coordenadas de uma folha."""
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
    return agua, T, crs, para_px, para_lonlat


def _tracar(arquivo, agua, T, para_px, para_lonlat, ini, fim):
    """Eixo do rio entre ini e fim: (lon, lat, s, largura, caminho em pixels (linha, coluna))."""
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
    return lon, lat, s, largura, caminho


def eixo(arquivo, sub, ini, fim, corte):
    agua, T, crs, para_px, para_lonlat = _preparar(arquivo, sub, corte)
    return _tracar(arquivo, agua, T, para_px, para_lonlat, ini, fim)[:4]


def mapa(pasta, extensao_m=6000.0, passo_estacao_m=400.0, tolerancia_px=1.2):
    """Grava SAIDA_MAPA: margens, eixo suavizado e estações (posição, rumo e largura)."""
    from scipy.ndimage import gaussian_filter1d
    from skimage.measure import approximate_polygon, find_contours

    arquivo = os.path.join(pasta, FOLHAS[0][0])
    sub, ini, fim, corte = FOLHAS[0][1:]
    corte = -48.649  # ~250 m a leste de DC01: a boca fica fora do mapa
    agua, T, crs, para_px, para_lonlat = _preparar(arquivo, sub, corte)
    _, _, _, _, caminho = _tracar(arquivo, agua, T, para_px, para_lonlat, ini, fim)
    res = abs(T.a)  # m por pixel

    def xy(r, c):  # pixel -> metros a leste/norte da origem (projeção conforme: rumos verdadeiros)
        x, y = T * (np.asarray(c, float) + 0.5, np.asarray(r, float) + 0.5)
        return np.asarray(x) - x0, np.asarray(y) - y0

    r_foz, c_foz = para_px(*FOZ)
    x0, y0 = T * (c_foz + 0.5, r_foz + 0.5)
    # eixo suavizado (150 m) e reamostrado a cada 100 m
    cx, cy = xy(caminho[:, 0], caminho[:, 1])
    sig = 150.0 / res
    cx, cy = gaussian_filter1d(cx, sig, mode='nearest'), gaussian_filter1d(cy, sig, mode='nearest')
    arco = np.r_[0, np.cumsum(np.hypot(np.diff(cx), np.diff(cy)))]
    grade = np.arange(0, min(extensao_m, arco[-1]) + 1, 100.0)
    ex, ey = np.interp(grade, arco, cx), np.interp(grade, arco, cy)
    # rumo do eixo no sentido rio acima (graus a partir do norte, horário)
    dx, dy = np.gradient(ex, grade), np.gradient(ey, grade)
    rumo = (np.degrees(np.arctan2(dx, dy)) + 360) % 360

    def largura_normal(px_, py_, rumo_graus):
        """Largura de margem a margem na normal ao eixo (m): soma dos dois lados até a primeira terra."""
        tx, ty = np.sin(np.radians(rumo_graus)), np.cos(np.radians(rumo_graus))
        total = 0.0
        for lado in (+1, -1):
            nx, ny = -ty * lado, tx * lado
            d = 0.0
            while d < 800:
                d += 2.5
                c = (px_ + nx * d + x0 - T.c) / T.a - 0.5
                r = (py_ + ny * d + y0 - T.f) / T.e - 0.5
                ri, ci = int(round(r)), int(round(c))
                if not (0 <= ri < agua.shape[0] and 0 <= ci < agua.shape[1]) or not agua[ri, ci]:
                    break
            total += d
        return total

    estacoes = []
    for sm in np.arange(passo_estacao_m, min(extensao_m, grade[-1]) - 1, passo_estacao_m):
        k = int(round(sm / 100.0))
        estacoes.append({'s_m': int(sm), 'x': round(float(ex[k]), 1), 'y': round(float(ey[k]), 1),
                         'rumo': round(float(rumo[k]), 1),
                         'largura_m': round(float(largura_normal(ex[k], ey[k], rumo[k])))})

    # margens: contornos da água ligada ao eixo, numa janela em torno dele
    k_max = int(round(grade[-1] / 100.0))
    xmin, xmax = ex[: k_max + 1].min() - 500, ex[: k_max + 1].max() + 250
    ymin, ymax = ey[: k_max + 1].min() - 250, ey[: k_max + 1].max() + 500
    rr, cc = np.mgrid[0:agua.shape[0], 0:agua.shape[1]]
    xx, yy = xy(rr, cc)
    janela = (xx >= xmin) & (xx <= xmax) & (yy >= ymin) & (yy <= ymax)
    rotulos, _ = ndi.label(agua & janela)
    rio = rotulos == rotulos[caminho[0, 0], caminho[0, 1]]  # descarta braços antigos e outros corpos d'água
    recorte = np.pad(rio.astype(float), 1)
    margens = []
    for cont in find_contours(recorte, 0.5):
        cont = approximate_polygon(cont, tolerancia_px) - 1  # desfaz o pad
        if len(cont) < 6:
            continue
        mx, my = xy(cont[:, 0], cont[:, 1])
        margens.append([[int(round(a)), int(round(b))] for a, b in zip(mx, my)])

    dados = {
        'fonte': 'Carta Nautica 1841 (DHN), folha principal; ferramentas/larguras_carta1841.py --mapa',
        'origem': 'DC01 (CEPSUL), x para leste e y para norte, em metros',
        'bbox': [int(xmin), int(ymin), int(xmax), int(ymax)],
        'eixo': [[round(float(a), 1), round(float(b), 1)] for a, b in zip(ex, ey)],
        'passo_eixo_m': 100,
        'estacoes': estacoes,
        'margens': margens,
    }
    import json
    with open(SAIDA_MAPA, 'w') as f:
        json.dump(dados, f, separators=(',', ':'))
    print(f'{SAIDA_MAPA}: eixo de {grade[-1] / 1e3:.1f} km, {len(estacoes)} estações, '
          f'{len(margens)} contornos, {sum(len(m) for m in margens)} pontos, '
          f'{os.path.getsize(SAIDA_MAPA) / 1e3:.0f} kB')
    for e in estacoes:
        print(f'  s = {e["s_m"] / 1e3:4.1f} km  rumo {e["rumo"]:5.1f}  largura {e["largura_m"]:4d} m')


def main():
    pasta = sys.argv[1]
    if '--mapa' in sys.argv:
        return mapa(pasta)
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
