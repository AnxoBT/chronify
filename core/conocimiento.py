"""Conocimiento compartido que viaja con cada versión (carpeta conocimiento/ del repo): países, tipo y género de
artistas buscados en MusicBrainz, áreas, oyentes de ListenBrainz y fechas propuestas por MusicBrainz.

Así quien instala Chronify no tiene que esperar los ~40 min de búsqueda de países para sus artistas que ya
estén buscados. Al arrancar se añade a la caché local lo que falte (lo local manda). Las fechas verificadas
van aparte, en fechas.json, y los países corregidos a mano en artistas.json.

`exportar()` (lo usa tools/publicar) copia la caché de este PC a conocimiento/ para la próxima versión.
"""
import hashlib
import json

from core import config

ARCHIVOS = ("artistas_mb.json", "areas_mb.json", "oyentes_lb.json", "musicbrainz.json")
CARPETA = config.ROOT / "conocimiento"
MARCA = ".conocimiento"


def _huella():
    h = hashlib.sha1()
    for n in ARCHIVOS:
        p = CARPETA / n
        if p.exists():
            h.update(n.encode() + p.read_bytes())
    return h.hexdigest()


def sembrar():
    """Añade a la caché local lo que trae esta versión y aún no está. Solo trabaja cuando cambia conocimiento/.
    Devuelve cuántas entradas se han añadido."""
    if not CARPETA.exists():
        return 0
    huella = _huella()
    marca = config.CACHE / MARCA
    if marca.exists() and marca.read_text(encoding="utf-8").strip() == huella:
        return 0
    nuevas = 0
    for n in ARCHIVOS:
        p = CARPETA / n
        if not p.exists():
            continue
        traido = json.loads(p.read_text(encoding="utf-8"))
        local = config.cache_json(n)
        faltan = {k: v for k, v in traido.items() if k not in local}
        if faltan:
            config.save_cache(n, {**faltan, **local})
            nuevas += len(faltan)
    config.CACHE.mkdir(exist_ok=True)
    marca.write_text(huella, encoding="utf-8")
    return nuevas


def exportar():
    """Copia a conocimiento/ la caché de este PC (unida a lo que ya hubiera). Devuelve los archivos cambiados."""
    CARPETA.mkdir(exist_ok=True)
    cambiados = []
    for n in ARCHIVOS:
        p = CARPETA / n
        antes = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        datos = {**antes, **config.cache_json(n)}
        if datos != antes or not p.exists():
            # una entrada por línea: diffs legibles
            txt = "{\n" + ",\n".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
                                     for k, v in sorted(datos.items())) + "\n}\n"
            p.write_text(txt, encoding="utf-8")
            cambiados.append(n)
    return cambiados
