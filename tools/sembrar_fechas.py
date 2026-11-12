"""Crea fechas.json a partir de un orden ya verificado a mano (el txt de Mix ordenado).

Uso (una vez, o para regenerar):
    python -m tools.sembrar_fechas data/ordenadas-2026-09/Mix_nueva.txt

Idea: en el txt verificado, la secuencia no decreciente más larga de fechas de Spotify se da por buena
(fuente 'spotify'). Las demás canciones son las que Spotify fecha mal y se corrigieron a mano: se les
asigna la fecha de la anterior canción fiable (fuente 'orden', aprox) y su posición, para que el
orden se reproduzca exacto. Las entradas 'manual' o 'musicbrainz' existentes no se tocan.
"""
import bisect
import sys
from pathlib import Path

from core.config import guardar_fechas
from core.exportify import cargar
from core.fechas import Fechas, normalizar

INFO = ("Fecha real de cada canción. fuente: spotify | orden (deducida del orden verificado) | "
        "musicbrainz | manual. aprox=true -> revisar. orden = posición en el orden verificado.")


def ids_txt(path):
    return [l.strip().rsplit("/", 1)[-1].split("?")[0] for l in Path(path).read_text(encoding="utf-8").splitlines()
            if l.strip()]


def fiables(fechas_norm):
    """Índices de la subsecuencia no decreciente más larga (ignora None)."""
    idx = [i for i, f in enumerate(fechas_norm) if f is not None]
    colas, colas_i, prev = [], [], {}
    for i in idx:
        p = bisect.bisect_right(colas, fechas_norm[i])
        if p == len(colas):
            colas.append(fechas_norm[i]); colas_i.append(i)
        else:
            colas[p] = fechas_norm[i]; colas_i[p] = i
        prev[i] = colas_i[p - 1] if p else None
    out, k = set(), (colas_i[-1] if colas_i else None)
    while k is not None:
        out.add(k); k = prev[k]
    return out


def main(txt):
    _, cat = cargar()
    orden = ids_txt(txt)
    F = Fechas()
    fn = [normalizar(cat[t].fecha_spotify) if t in cat and cat[t].fecha_spotify else None for t in orden]
    ok = fiables(fn)
    sig_fiable = [None] * len(orden)
    nxt = None
    for i in range(len(orden) - 1, -1, -1):
        sig_fiable[i] = nxt
        if i in ok:
            nxt = i
    ultima, n_orden = None, 0
    for i, t in enumerate(orden):
        e = F.pistas.get(t, {})
        p = cat.get(t)
        if e.get("fuente") in ("manual", "musicbrainz"):
            e["orden"] = i
            continue
        if i in ok:
            F.fijar(t, cat[t].fecha_spotify, "spotify", p)
            ultima = cat[t].fecha_spotify
        else:
            ref = ultima or (cat[orden[sig_fiable[i]]].fecha_spotify if sig_fiable[i] is not None else "")
            F.fijar(t, ref, "orden", p, aprox=True)
            n_orden += 1
        F.pistas[t]["orden"] = i
    F.data["_info"] = INFO
    guardar_fechas(F.data)
    print(f"{len(orden)} canciones: {len(ok)} con fecha de Spotify coherente, {n_orden} deducidas del orden (aprox)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/ordenadas-2026-09/Mix_nueva.txt")
