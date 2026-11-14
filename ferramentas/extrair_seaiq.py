"""Extrai a trajetória do navio de uma gravação NMEA do SEAiq (prático).

O SEAiq grava, num arquivo `.nmea`, tudo o que o kit portátil do prático
recebe durante a manobra:

- `$GNGGA` / `$GNVTG`: posição, rumo e velocidade no fundo (GNSS do kit,
  1 Hz);
- `$CPHDT` / `$CPROT`: proa verdadeira e taxa de giro (sensor do kit);
- `$PSIQREC`: hora do relógio do app (época Unix e hora local);
- `$PSIQAIS`: alvos AIS já decodificados pelo app (posição, COG, SOG,
  proa);
- `!AIVDM`: mensagens AIS brutas; daqui só se tiram os dados estáticos
  (nome, indicativo, tipo, dimensões), mensagens 5 e 24.

O script grava, numa pasta de saída:

1. `trajetoria.csv`: uma linha por fixo GNSS (1 s) com hora UTC e local,
   posição, SOG, COG, proa, taxa de giro e deriva (COG − proa);
2. `ais_alvos.csv`: cada leitura `$PSIQAIS` com a hora UTC da amostra;
3. `ais_navios.csv`: um navio por MMSI, com os dados estáticos que
   apareceram na gravação.

Deriva: diferença entre o rumo no fundo e a proa, de −180 a +180 graus,
positiva quando o navio anda para boreste da proa. Mistura corrente,
vento e o efeito da máquina e do leme; não é a corrente. Abaixo de
`--sog-min` nós (padrão 1,0) o COG do GNSS é ruidoso ou ausente, e a
deriva fica vazia.

A proa e a taxa de giro chegam em sentenças separadas do fixo GNSS; cada
linha usa a última leitura, desde que tenha no máximo `--idade-max`
segundos (padrão 3). Leituras mais velhas ficam vazias.

Sentenças com checksum errado são descartadas. A hora local é UTC−3
(Brasil, sem horário de verão desde 2019).

Uso:
    python ferramentas/extrair_seaiq.py GRAVACAO.nmea saida/ [--sog-min 1.0]
        [--idade-max 3]
"""

import argparse
import csv
import math
from datetime import datetime, timedelta, timezone
from functools import reduce
from pathlib import Path

FUSO_LOCAL = timezone(timedelta(hours=-3))
NOS_PARA_MS = 1852 / 3600

TIPOS_AIS = {
    30: "pesca", 31: "rebocador", 32: "rebocador", 33: "dragagem",
    35: "militar", 36: "veleiro", 37: "recreio", 50: "praticagem",
    51: "busca e salvamento", 52: "rebocador", 53: "apoio portuário",
    55: "autoridade", 58: "médico",
}


def tipo_ais(codigo):
    """Descrição curta do tipo de navio AIS (tabela da ITU-R M.1371)."""
    if codigo in TIPOS_AIS:
        return TIPOS_AIS[codigo]
    faixas = {2: "WIG", 4: "alta velocidade", 6: "passageiros",
              7: "carga", 8: "tanque", 9: "outro"}
    return faixas.get(codigo // 10, "") if codigo else ""


def checksum_ok(linha):
    """Confere o checksum NMEA; linhas sem '*' (as $PSIQ) passam."""
    if "*" not in linha:
        return True
    corpo, _, cs = linha[1:].partition("*")
    try:
        return reduce(lambda a, c: a ^ ord(c), corpo, 0) == int(cs[:2], 16)
    except ValueError:
        return False


def num(campo):
    try:
        return float(campo)
    except ValueError:
        return None


def graus(valor, hemisferio, n_graus):
    """'2654.68245','S',2 -> -26.91137..."""
    if not valor:
        return None
    g = int(valor[:n_graus]) + float(valor[n_graus:]) / 60
    return -g if hemisferio in "SW" else g


def ang(a):
    """Diferença angular normalizada para [-180, 180)."""
    return (a + 180) % 360 - 180


# --- AIS: só o necessário para nome e dimensões (mensagens 5 e 24) ---

def bits_ais(payload, preench):
    b = "".join(format((v - 48) - 8 * ((v - 48) > 40), "06b")
                for v in map(ord, payload))
    return b[: len(b) - preench] if preench else b


def uint(b, i, n):
    return int(b[i:i + n], 2) if len(b) >= i + n else None


def texto(b, i, n_car):
    tab = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"
    s = "".join(tab[uint(b, i + 6 * k, 6)] for k in range(n_car)
                if len(b) >= i + 6 * (k + 1))
    return s.split("@")[0].strip()


def estaticos_ais(b, navios):
    tipo = uint(b, 0, 6)
    mmsi = uint(b, 8, 30)
    if mmsi is None:
        return
    n = navios.setdefault(mmsi, {})
    if tipo == 5 and len(b) >= 424:
        n["imo"] = uint(b, 40, 30) or ""
        n["indicativo"] = texto(b, 70, 7)
        n["nome"] = texto(b, 112, 20)
        n["tipo"] = uint(b, 232, 8)
        proa, popa = uint(b, 240, 9), uint(b, 249, 9)
        bb, be = uint(b, 258, 6), uint(b, 264, 6)
        n["comprimento_m"] = proa + popa
        n["boca_m"] = bb + be
        n["calado_m"] = uint(b, 294, 8) / 10
        n["destino"] = texto(b, 302, 20)
    elif tipo == 24:
        parte = uint(b, 38, 2)
        if parte == 0 and len(b) >= 160:
            n.setdefault("nome", texto(b, 40, 20))
        elif parte == 1 and len(b) >= 162:
            n.setdefault("tipo", uint(b, 40, 8))
            n.setdefault("indicativo", texto(b, 90, 7))
            n.setdefault("comprimento_m", uint(b, 132, 9) + uint(b, 141, 9))
            n.setdefault("boca_m", uint(b, 150, 6) + uint(b, 156, 6))


# --- leitura do arquivo ---

def ler(caminho, sog_min, idade_max):
    trajetoria, alvos, navios = [], [], {}
    epoca = None           # época Unix da última $PSIQREC
    hdt = rot = vtg = None  # (época, valor)
    partes = []            # fragmentos de !AIVDM com várias partes
    descartadas = 0

    with open(caminho, encoding="ascii", errors="replace") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha[0] not in "$!":
                continue
            if not checksum_ok(linha):
                descartadas += 1
                continue
            p = linha.split("*")[0].split(",")
            k = p[0]

            if k == "$PSIQREC" and len(p) > 3:
                epoca = num(p[3])
            elif k.endswith("HDT") and len(p) > 1 and p[1]:
                hdt = (epoca, float(p[1]) % 360)
            elif k.endswith("ROT") and len(p) > 2 and p[1] and p[2] == "A":
                rot = (epoca, float(p[1]))
            elif k.endswith("VTG") and len(p) > 7:
                cog, sog = num(p[1]), num(p[5])
                vtg = (epoca, None if cog is None else cog % 360, sog)
            elif k == "$PSIQAIS" and len(p) >= 7 and p[2] and epoca:
                alvos.append({
                    "utc": iso(epoca), "mmsi": p[1],
                    "lat": num(p[3]), "lon": num(p[2]),
                    "cog_verd": num(p[4]), "sog_nos": num(p[5]),
                    "proa_verd": num(p[6]),
                    "rot_gpm": num(p[7]) if len(p) > 7 else None,
                })
            elif k.endswith("VDM") and len(p) >= 7:
                n_partes, n_parte = int(p[1]), int(p[2])
                if n_parte == 1:
                    partes = []
                partes.append(p[5])
                if n_parte == n_partes:
                    estaticos_ais(bits_ais("".join(partes), int(p[6][:1] or 0)),
                                  navios)
                    partes = []
            elif k.endswith("GGA") and len(p) > 9 and p[2] and epoca:
                trajetoria.append(linha_fixo(p, epoca, hdt, rot, vtg,
                                             sog_min, idade_max))

    return trajetoria, alvos, navios, descartadas


def iso(epoca):
    return datetime.fromtimestamp(epoca, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"


def hora_fixo(hhmmss, epoca):
    """Hora UTC do GGA, com a data tirada do relógio do app."""
    ref = datetime.fromtimestamp(epoca, timezone.utc)
    h, m, s = int(hhmmss[:2]), int(hhmmss[2:4]), float(hhmmss[4:])
    t = ref.replace(hour=h, minute=m, second=int(s),
                    microsecond=round((s % 1) * 1e6))
    if (t - ref).total_seconds() > 43200:   # virada do dia UTC
        t -= timedelta(days=1)
    elif (ref - t).total_seconds() > 43200:
        t += timedelta(days=1)
    return t


def recente(leitura, epoca, idade_max):
    return leitura is not None and leitura[0] is not None and \
        epoca - leitura[0] <= idade_max


def linha_fixo(p, epoca, hdt, rot, vtg, sog_min, idade_max):
    t = hora_fixo(p[1], epoca)
    proa = hdt[1] if recente(hdt, epoca, idade_max) else None
    giro = rot[1] if recente(rot, epoca, idade_max) else None
    cog = sog = None
    if recente(vtg, epoca, idade_max):
        cog, sog = vtg[1], vtg[2]
    deriva = None
    if None not in (cog, proa, sog) and sog >= sog_min:
        deriva = round(ang(cog - proa), 1)
    return {
        "utc": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hora_local": t.astimezone(FUSO_LOCAL).strftime("%Y-%m-%d %H:%M:%S"),
        "lat": round(graus(p[2], p[3], 2), 7),
        "lon": round(graus(p[4], p[5], 3), 7),
        "qualidade_fixo": p[6], "satelites": p[7], "hdop": p[8],
        "sog_nos": sog,
        "sog_ms": None if sog is None else round(sog * NOS_PARA_MS, 3),
        "cog_verd": None if cog is None else round(cog, 1),
        "proa_verd": proa, "rot_gpm": giro, "deriva_graus": deriva,
    }


def gravar(caminho, linhas, colunas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        w.writeheader()
        for r in linhas:
            w.writerow({c: "" if r.get(c) is None else r.get(c)
                        for c in colunas})


def distancia_m(a, b):
    dlat = (a["lat"] - b["lat"]) * 111_320
    dlon = (a["lon"] - b["lon"]) * 111_320 * math.cos(math.radians(a["lat"]))
    return math.hypot(dlat, dlon)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("nmea", type=Path)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--sog-min", type=float, default=1.0,
                    help="SOG mínimo (nós) para calcular a deriva")
    ap.add_argument("--idade-max", type=float, default=3.0,
                    help="idade máxima (s) de proa, giro e VTG em cada fixo")
    a = ap.parse_args()

    traj, alvos, navios, desc = ler(a.nmea, a.sog_min, a.idade_max)
    if not traj:
        raise SystemExit("nenhum fixo GNSS ($..GGA) com hora $PSIQREC no arquivo")
    a.saida.mkdir(parents=True, exist_ok=True)

    gravar(a.saida / "trajetoria.csv", traj, list(traj[0]))
    gravar(a.saida / "ais_alvos.csv", alvos,
           ["utc", "mmsi", "lat", "lon", "cog_verd", "sog_nos",
            "proa_verd", "rot_gpm"])
    lista = []
    for mmsi in sorted({int(x["mmsi"]) for x in alvos} | set(navios)):
        if not mmsi:
            continue
        n = dict(navios.get(mmsi, {}), mmsi=mmsi)
        for c in ("comprimento_m", "boca_m", "calado_m", "imo"):
            if not n.get(c):     # 0 no AIS = não informado
                n.pop(c, None)
        if isinstance(n.get("tipo"), int):
            n["tipo_desc"] = tipo_ais(n["tipo"])
        lista.append(n)
    gravar(a.saida / "ais_navios.csv", lista,
           ["mmsi", "nome", "indicativo", "imo", "tipo", "tipo_desc",
            "comprimento_m", "boca_m", "calado_m", "destino"])

    percurso = sum(distancia_m(x, y) for x, y in zip(traj, traj[1:]))
    t0 = datetime.fromisoformat(traj[0]["utc"].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(traj[-1]["utc"].replace("Z", "+00:00"))
    falhas = [(x["hora_local"], (datetime.fromisoformat(y["utc"][:-1]) -
               datetime.fromisoformat(x["utc"][:-1])).total_seconds())
              for x, y in zip(traj, traj[1:])
              if y["utc"][:-1] > x["utc"][:-1] and
              (datetime.fromisoformat(y["utc"][:-1]) -
               datetime.fromisoformat(x["utc"][:-1])).total_seconds() > 2]
    print(f"{len(traj)} fixos, {traj[0]['hora_local']} a "
          f"{traj[-1]['hora_local'][11:]} (local), "
          f"{(t1 - t0).total_seconds() / 60:.0f} min, "
          f"{percurso / 1852:.2f} mn percorridas")
    print(f"{len(alvos)} leituras AIS de {len(lista)} navios; "
          f"{sum(1 for n in lista if n.get('nome'))} com nome")
    if falhas:
        print("falhas na gravação (> 2 s): " +
              ", ".join(f"{h} ({s:.0f} s)" for h, s in falhas))
    if desc:
        print(f"{desc} sentenças descartadas por checksum")
    print(f"gravado em {a.saida}/")


if __name__ == "__main__":
    main()
