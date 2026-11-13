"""Extrai os dados do painel de um chartplotter filmado com o celular.

O vídeo mostra a carta eletrônica e, à direita, o painel de dados do
plotter (SOG, PROF, COG, posição, data/hora). O script:

1. tira um quadro por segundo do vídeo (ffmpeg);
2. lê o painel com OCR (Tesseract) em dois modos de segmentação e
   vota entre as leituras;
3. descarta leituras fora do plausível (posição que salta, rumo fora de
   0–359, hora fora de ordem) e deixa o campo vazio quando não confia;
4. grava um CSV com uma linha por hora mostrada na tela e, opcionalmente,
   os quadros correspondentes (para uma IA que lê imagens).

Campos que o plotter mostra como "---" (por exemplo, PROF sem sonda
ligada) ficam vazios no CSV.

Lancha como flutuador (padrão): nos vídeos deste projeto a lancha deriva
com o motor desligado, então SOG e COG medem a corrente superficial. O CSV
traz a corrente em m/s e a direção para onde ela vai em graus verdadeiros
(COG magnético mais a declinação do WMM 2025 no local e na data). Com
`--motor` (lancha navegando), essas colunas não são geradas.

O vento também empurra o casco. A velocidade medida inclui esse arrasto,
que costuma ser pequeno com vento fraco. Com `--vento`, o script desconta
esse arrasto: supõe que o casco anda com uma fração (`--arrasto`, padrão
0,03) da velocidade do vento, no sentido para onde o vento sopra, e
grava também a corrente corrigida. O vento é informado como "vindo de",
em graus verdadeiros ou pontos da rosa (SE, ESE, NO, NW...):

    --vento 11.5@SE              vento constante
    --vento vento.csv            leituras com hora; interpola no tempo

O CSV de vento tem as colunas `hora,vel_nos,dir` (hora local, HH:MM ou
HH:MM:SS, no mesmo relógio do plotter).

A fração de arrasto depende da lancha (área exposta ao vento contra
área submersa). O padrão de 3% é uma regra prática de busca e salvamento
para embarcações pequenas, uma ordem de grandeza e não uma medida.

Requisitos: ffmpeg e tesseract no sistema; `pip install opencv-python-headless
pytesseract pygeomag`.

Uso:
    python ferramentas/extrair_video_plotter.py VIDEO.mp4 saida/ [--quadros] [--motor]
        [--vento 11.5@SE | --vento vento.csv] [--arrasto 0.03]
"""

import argparse
import csv
import math
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import pytesseract

NO_EM_MS = 1852 / 3600

# Fração da largura do quadro onde começa o painel de dados (lado direito).
# O celular se move um pouco; 0.72 deixa folga dos dois lados.
INICIO_PAINEL = 0.72

RE_HORA = re.compile(r"\b([0-2]\d):([0-5]\d):([0-5]\d)\b")
RE_DATA = re.compile(r"\b([0-3]\d)/([01]\d)/(20\d\d)\b")
# O OCR troca S, 5 e $ entre si e às vezes põe lixo depois do W.
RE_LAT = re.compile(r"[S$5]\W{0,2}\s*(\d{1,2})\s*°\s*([\dS]{1,2}\.[\dS]{3})")
RE_LON = re.compile(r"W\D{0,4}?(\d{1,3})\s*°\s*([\dS]{1,2}\.[\dS]{3})")
RE_NUM = re.compile(r"^\s*(\d{1,3}(?:[.,]\d)?)\s*$")


def ler_painel(caminho):
    """Devolve as linhas de texto do painel, em dois modos de OCR."""
    im = cv2.imread(str(caminho))
    w = im.shape[1]
    g = cv2.cvtColor(im[:, int(w * INICIO_PAINEL):], cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    leituras = []
    for psm in (4, 11):
        t = pytesseract.image_to_string(b, config=f"--psm {psm}")
        leituras.append([x.strip() for x in t.splitlines() if x.strip()])
    return leituras


def valor_apos(linhas, rotulo, exceto=None):
    """Número na primeira linha numérica depois da linha com o rótulo.

    Devolve None se o próximo rótulo aparecer antes (campo "---").
    """
    for i, linha in enumerate(linhas):
        rot = linha.upper().replace("0", "O")  # "S0G" -> "SOG"
        if rotulo in rot and not (exceto and exceto in rot):
            for seguinte in linhas[i + 1:i + 4]:
                if "PILOT" in seguinte.upper() or "°M" in seguinte:
                    return None
                # Tira lixo do OCR nas bordas ("| 178" -> "178").
                m = RE_NUM.match(seguinte.strip(" |[](){}'\"`_-—=~"))
                if m:
                    return float(m.group(1).replace(",", "."))
            return None
    return None


def graus(m):
    """Graus decimais (hemisférios S e W, negativos) de um match."""
    if not m:
        return None
    minutos = float(m.group(2).replace("S", "5"))
    return None if minutos >= 60 else -(int(m.group(1)) + minutos / 60)


def interpretar(linhas):
    texto = "\n".join(linhas)
    r = {}
    m = RE_HORA.search(texto)
    r["hora"] = ":".join(m.groups()) if m else None
    m = RE_DATA.search(texto)
    r["data"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
    m = RE_LAT.search(texto)
    r["lat"] = graus(m)
    m = RE_LON.search(texto)
    r["lon"] = graus(m)
    r["sog_nos"] = valor_apos(linhas, "OG PILOT", exceto="COG")
    r["prof_m"] = valor_apos(linhas, "PROF")
    r["cog_graus"] = valor_apos(linhas, "COG")
    if r["cog_graus"] is not None and not 0 <= r["cog_graus"] < 360:
        r["cog_graus"] = None
    if r["sog_nos"] is not None and r["sog_nos"] > 40:
        r["sog_nos"] = None
    return r


def votar(valores):
    """Valor mais frequente entre as leituras não vazias."""
    v = [x for x in valores if x is not None]
    return Counter(v).most_common(1)[0][0] if v else None


def distancia_m(a, b):
    dlat = (a[0] - b[0]) * 111_320
    dlon = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon)


def declinacao(lat, lon, data):
    """Declinação magnética (graus, leste positivo) pelo WMM 2025."""
    from datetime import date

    from pygeomag import GeoMag

    d = date.fromisoformat(data)
    ano = d.year + (d.timetuple().tm_yday - 0.5) / 365.25
    gm = GeoMag(coefficients_file="wmm/WMM_2025.COF")
    return gm.calculate(glat=lat, glon=lon, alt=0, time=ano).d


# Rosa dos ventos de 16 pontos, em inglês e português (O = W).
_PONTOS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
ROSA = {p: i * 22.5 for i, p in enumerate(_PONTOS)}
ROSA.update({p.replace("W", "O"): g for p, g in ROSA.items() if "W" in p})


def direcao(texto):
    """Graus de uma direção dada em graus ou em ponto da rosa."""
    t = texto.strip().upper()
    if t in ROSA:
        return ROSA[t]
    g = float(t.replace(",", "."))
    if not 0 <= g <= 360:
        raise ValueError(f"direção fora de 0–360: {texto}")
    return g % 360


def segundos(hora):
    partes = [int(x) for x in hora.split(":")]
    partes += [0] * (3 - len(partes))
    return partes[0] * 3600 + partes[1] * 60 + partes[2]


def ler_vento(especificacao):
    """Lista ordenada de (segundos, u, v) do vento em m/s, "indo para".

    u é a componente leste e v a norte. Aceita "VEL@DIR" (vento
    constante, nós e direção de onde vem) ou um CSV hora,vel_nos,dir.
    """
    def vetor(vel_nos, de_graus):
        para = math.radians(de_graus + 180)
        vel = vel_nos * NO_EM_MS
        return vel * math.sin(para), vel * math.cos(para)

    if "@" in especificacao and not Path(especificacao).exists():
        vel, dirc = especificacao.split("@")
        return [(0, *vetor(float(vel.replace(",", ".")), direcao(dirc)))]
    leituras = []
    with open(especificacao, newline="") as f:
        for linha in csv.DictReader(f):
            leituras.append((segundos(linha["hora"]),
                             *vetor(float(linha["vel_nos"].replace(",", ".")),
                                    direcao(linha["dir"]))))
    if not leituras:
        raise ValueError(f"nenhuma leitura de vento em {especificacao}")
    return sorted(leituras)


def vento_em(leituras, t):
    """Vento (u, v) no instante t: interpola por componentes; fora do
    intervalo das leituras, usa a mais próxima."""
    if t <= leituras[0][0]:
        return leituras[0][1:]
    for (t0, u0, v0), (t1, u1, v1) in zip(leituras, leituras[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return u0 + f * (u1 - u0), v0 + f * (v1 - v0)
    return leituras[-1][1:]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("video")
    p.add_argument("saida")
    p.add_argument("--quadros", action="store_true",
                   help="salva um PNG por linha do CSV")
    p.add_argument("--motor", action="store_true",
                   help="lancha navegando: não converte SOG/COG em corrente")
    p.add_argument("--vento",
                   help='"VEL@DIR" (nós, de onde vem) ou CSV hora,vel_nos,dir')
    p.add_argument("--arrasto", type=float, default=0.03,
                   help="fração da velocidade do vento com que o casco "
                        "deriva (padrão 0.03)")
    args = p.parse_args()

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-v", "error", "-i", args.video,
                        "-vf", "fps=1", f"{tmp}/q_%05d.png"], check=True)
        quadros = sorted(Path(tmp).glob("q_*.png"))

        # Agrupa as leituras pela hora mostrada na tela.
        grupos = {}
        sem_hora = 0
        for n, q in enumerate(quadros):
            leituras = [interpretar(l) for l in ler_painel(q)]
            hora = votar([r["hora"] for r in leituras])
            if hora is None:
                sem_hora += 1
                continue
            g = grupos.setdefault(hora, {"t_video_s": n, "quadro": q,
                                         "leituras": []})
            g["leituras"].extend(leituras)

        linhas = []
        anterior = None
        for hora in sorted(grupos):
            g = grupos[hora]
            ls = g["leituras"]
            r = {"t_video_s": g["t_video_s"],
                 "data": votar([x["data"] for x in ls]),
                 "hora": hora}
            for campo in ("lat", "lon", "sog_nos", "cog_graus", "prof_m"):
                r[campo] = votar([x[campo] for x in ls])
            # Posição que salta mais de 50 m em relação à anterior é
            # tratada como erro de leitura.
            if r["lat"] is not None and r["lon"] is not None:
                pos = (r["lat"], r["lon"])
                if anterior and distancia_m(pos, anterior) > 50:
                    r["lat"] = r["lon"] = None
                else:
                    anterior = pos
            if args.quadros:
                destino = saida / f"quadro_{hora.replace(':', '')}.png"
                destino.write_bytes(g["quadro"].read_bytes())
                r["quadro"] = destino.name
            linhas.append(r)

    # SOG que difere mais de 0,3 nó da mediana dos vizinhos (±3 s) é
    # leitura de um dígito em transição; fica vazio.
    for i, r in enumerate(linhas):
        viz = sorted(x["sog_nos"] for x in linhas[max(0, i - 3):i + 4]
                     if x is not r and x["sog_nos"] is not None)
        if r["sog_nos"] is not None and viz:
            if abs(r["sog_nos"] - viz[len(viz) // 2]) > 0.3:
                r["sog_nos"] = None

    campos = ["t_video_s", "data", "hora", "lat", "lon", "sog_nos",
              "cog_graus", "prof_m"]
    decl = None
    if not args.motor:
        # Lancha como flutuador: SOG/COG são a corrente superficial.
        ref = next((r for r in linhas if r["lat"] is not None
                    and r["lon"] is not None and r["data"]), None)
        if ref:
            decl = declinacao(ref["lat"], ref["lon"], ref["data"])
            for r in linhas:
                if r["sog_nos"] is not None:
                    r["corr_vel_ms"] = round(r["sog_nos"] * NO_EM_MS, 3)
                if r["cog_graus"] is not None:
                    r["corr_dir_verd"] = round((r["cog_graus"] + decl) % 360, 1)
            campos += ["corr_vel_ms", "corr_dir_verd"]
            if args.vento:
                leituras_vento = ler_vento(args.vento)
                for r in linhas:
                    u, v = vento_em(leituras_vento, segundos(r["hora"]))
                    vel = math.hypot(u, v)
                    r["vento_nos"] = round(vel / NO_EM_MS, 1)
                    r["vento_de_verd"] = round(
                        (math.degrees(math.atan2(u, v)) + 180) % 360, 1)
                    if r["sog_nos"] is None or r["cog_graus"] is None:
                        continue
                    # Deriva medida menos o arrasto do vento no casco.
                    rumo = math.radians(r["corr_dir_verd"])
                    cu = r["corr_vel_ms"] * math.sin(rumo) - args.arrasto * u
                    cv = r["corr_vel_ms"] * math.cos(rumo) - args.arrasto * v
                    r["corr_vel_ms_sem_vento"] = round(math.hypot(cu, cv), 3)
                    r["corr_dir_verd_sem_vento"] = round(
                        math.degrees(math.atan2(cu, cv)) % 360, 1)
                campos += ["vento_nos", "vento_de_verd",
                           "corr_vel_ms_sem_vento", "corr_dir_verd_sem_vento"]
    campos += ["quadro"] if args.quadros else []
    with open(saida / "painel.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in linhas:
            for k in ("lat", "lon"):
                if r[k] is not None:
                    r[k] = f"{r[k]:.6f}"
            w.writerow(r)

    vazios = {c: sum(r[c] in (None, "") for r in linhas)
              for c in ("lat", "lon", "sog_nos", "cog_graus", "prof_m")}
    print(f"{len(quadros)} quadros, {len(linhas)} horas distintas, "
          f"{sem_hora} quadros sem hora legível")
    print("campos vazios:", vazios)
    if decl is not None:
        print(f"lancha como flutuador; declinação {decl:+.1f}° "
              "(COG magnético -> direção verdadeira da corrente)")
        if args.vento:
            print(f"vento descontado com arrasto de {args.arrasto:.0%} "
                  "(colunas *_sem_vento)")
    elif not args.motor:
        print("sem posição e data legíveis: colunas de corrente não geradas")
    print("CSV:", saida / "painel.csv")


if __name__ == "__main__":
    main()
