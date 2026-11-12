"""Genera web/mundo.json (mapa del mundo en SVG ya proyectado) a partir de Natural Earth (dominio público).

Uso puntual (solo hace falta si se quiere regenerar el mapa):
    curl -L -o ne50.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
    python -m tools.generar_mapa ne50.geojson

Proyección cilíndrica de Miller: mapa plano y rectangular (meridianos y paralelos rectos), sin la
exageración de Mercator en los polos. Los contornos se simplifican (Douglas-Peucker) para que el archivo
pese poco. Países diminutos llevan además un punto `p` para que se vean y se puedan señalar con el ratón.
"""
import json
import math
import sys
from pathlib import Path

ANCHO = 1000
TOLERANCIA = 0.35  # px
ESCALA = ANCHO / (2 * math.pi)
LAT_MIN = -60  # por debajo solo hay Antártida (fuera) y mar


def proyectar(lon, lat):
    f = math.radians(max(LAT_MIN, min(84, lat)))
    y = 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * f))
    return (math.radians(lon) + math.pi) * ESCALA, -y * ESCALA


def simplificar(pts, tol):
    if len(pts) < 4:
        return pts
    marcas, pila = [False] * len(pts), [(0, len(pts) - 1)]
    marcas[0] = marcas[-1] = True
    while pila:
        a, b = pila.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy)
        peor, i_peor = 0, None
        for i in range(a + 1, b):  # anillo cerrado (a == b): distancia al punto en vez de a la recta
            d = (abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / n if n
                 else math.hypot(pts[i][0] - x1, pts[i][1] - y1))
            if d > peor:
                peor, i_peor = d, i
        if i_peor is not None and peor > tol:
            marcas[i_peor] = True
            pila += [(a, i_peor), (i_peor, b)]
    return [p for p, m in zip(pts, marcas) if m]


def area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def main(origen, destino=Path(__file__).resolve().parent.parent / "web" / "mundo.json"):
    d = json.loads(Path(origen).read_text(encoding="utf-8"))
    paises, ymin, ymax = {}, 1e9, -1e9
    for f in d["features"]:
        p = f["properties"]
        iso = p["ISO_A2_EH"] if p["ISO_A2_EH"] != "-99" else p["ISO_A2"]
        if iso in ("-99", "AQ"):
            continue  # Antártida y territorios en disputa sin código
        g = f["geometry"]
        polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        e = paises.setdefault(iso, {"c": iso, "n": p["NAME_ES"] or p["NAME"], "anillos": [], "area": 0})
        for poli in polis:
            for anillo in poli:
                pts = [proyectar(lon, lat) for lon, lat in anillo]
                e["area"] += area(pts) if anillo is poli[0] else 0
                s = simplificar(pts, TOLERANCIA)
                if len(s) >= 3 and area(s) > 0.15:
                    e["anillos"].append(s)
                    ymin, ymax = min(ymin, *(y for _, y in s)), max(ymax, *(y for _, y in s))
                e.setdefault("_todos", []).extend(pts)
    out = []
    for e in sorted(paises.values(), key=lambda e: e["n"]):
        d = "".join("M" + "L".join(f"{x:.1f},{y - ymin:.1f}" for x, y in a) + "Z" for a in e["anillos"])
        item = {"c": e["c"], "n": e["n"], "d": d}
        if e["area"] < 6 or not d:  # diminuto (Andorra, Malta, Barbados…): punto para verlo y señalarlo
            xs, ys = [x for x, _ in e["_todos"]], [y for _, y in e["_todos"]]
            item["p"] = [round((min(xs) + max(xs)) / 2, 1), round((min(ys) + max(ys)) / 2 - ymin, 1)]
        out.append(item)
    Path(destino).write_text(json.dumps({"w": ANCHO, "h": round(ymax - ymin, 1), "paises": out},
                                        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out)} países -> {destino} ({Path(destino).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
