"""Datos de cada artista para las estadísticas: país, tipo (persona/grupo), género, años en activo.

Salen de MusicBrainz (una búsqueda por artista, 1 petición/s, guardadas en cache/artistas_mb.json).
Las correcciones a mano van en artistas.json (se versiona, como fechas.json) y mandan sobre MusicBrainz.
"""
import json
import re
from pathlib import Path
from urllib.parse import quote

from core import musicbrainz
from core.config import DATOS, cache_json, save_cache

CACHE = "artistas_mb.json"
MANUAL = DATOS / "artistas.json"
API = "https://musicbrainz.org/ws/2/artist"
# Regiones que MusicBrainz da sin país (área de tipo subdivisión)
REGIONES = {"england": "GB", "scotland": "GB", "wales": "GB", "northern ireland": "GB", "catalonia": "ES",
            "andalusia": "ES", "galicia": "ES", "basque country": "ES", "community of madrid": "ES",
            "puerto rico": "PR", "quebec": "CA", "ontario": "CA", "california": "US", "new york": "US",
            "texas": "US", "florida": "US", "georgia": "US", "tennessee": "US", "illinois": "US",
            "new jersey": "US", "washington": "US", "michigan": "US", "massachusetts": "US", "louisiana": "US",
            "pennsylvania": "US", "ohio": "US", "bavaria": "DE", "flanders": "BE", "wallonia": "BE"}


def clave(nombre):
    return musicbrainz._clave(nombre)


def manuales():
    return json.loads(MANUAL.read_text(encoding="utf-8")) if MANUAL.exists() else {}


def guardar_manual(nombre, datos):
    m = manuales()
    m.setdefault(nombre, {}).update({k: v for k, v in datos.items() if v not in (None, "")})
    escribir(m)


def escribir(m):
    """Un artista por línea (diffs legibles). Escritura atómica: si se corta no deja el archivo a medias."""
    tmp = MANUAL.with_suffix(".json.tmp")
    tmp.write_text("{\n" + ",\n".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
                                      for k, v in sorted(m.items(), key=lambda kv: kv[0].casefold())) + "\n}\n",
                   encoding="utf-8")
    tmp.replace(MANUAL)


AREAS = "areas_mb.json"
VERSION = 2  # v2: país de origen = lugar de nacimiento/formación; desempate de homónimos por canciones
BUSQUEDA = 2  # v2: también por alias y sin distinguir y/&/and (los no encontrados antes se reintentan)


def pais_de_area(area_id, profundidad=0):
    """País (ISO 3166-1) de un área de MusicBrainz subiendo por 'parte de' (ciudad → región → país). Con caché."""
    if not area_id or profundidad > 5:
        return None
    cache = cache_json(AREAS)
    if area_id in cache:
        return cache[area_id]
    d = musicbrainz._get(f"{API.replace('artist', 'area')}/{area_id}?inc=area-rels&fmt=json")
    pais = ((d.get("iso-3166-1-codes") or [None])[0]
            or next((c[:2] for c in d.get("iso-3166-2-codes") or []), None))
    if not pais:
        padres = [r["area"] for r in d.get("relations", [])
                  if r.get("type") == "part of" and r.get("direction") == "backward" and r.get("area")]
        # el padre suele traer ya sus códigos ISO (región → GB-ENG): sin otra petición
        pais = next(((p.get("iso-3166-1-codes") or [None])[0] or next((c[:2] for c in p.get("iso-3166-2-codes") or []), None)
                     for p in padres if p.get("iso-3166-1-codes") or p.get("iso-3166-2-codes")), None)
        for p in ([] if pais else padres[:2]):
            pais = pais_de_area(p["id"], profundidad + 1)
            if pais:
                break
    cache = cache_json(AREAS)
    cache[area_id] = pais
    save_cache(AREAS, cache)
    return pais


def _tiene_cancion(mbid, titulos):
    """¿Hay en MusicBrainz alguna grabación de este artista con alguno de esos títulos?"""
    for t in titulos[:1]:
        t = musicbrainz.limpiar(t)
        q = quote(f'recording:{json.dumps(t)} AND arid:{mbid}')
        if musicbrainz._get(f"{API.replace('artist', 'recording')}?query={q}&fmt=json&limit=1").get("count", 0):
            return True
    return False


def buscar(nombre, titulos=()):
    """{'pais', 'tipo', 'genero', 'inicio', 'fin', 'zona', 'mbid'} o {} si no se encuentra. Usa caché.

    pais = país del lugar de nacimiento (personas) o de formación (grupos); si MusicBrainz no lo tiene,
    el país con el que figura el artista. Si hay varios artistas con ese nombre, se elige el que tiene
    grabaciones con los títulos de tus canciones.
    """
    k = clave(nombre)
    cache = cache_json(CACHE)
    if not _pendiente(cache.get(k)):
        return cache[k]
    # nombre o alias ("Kanye West" es alias de "Ye"); "Fito y Fitipaldis" = "Fito & Fitipaldis"
    q = f"artist:{json.dumps(nombre)} OR alias:{json.dumps(nombre)}"
    d = musicbrainz._get(f"{API}?query={quote(q)}&fmt=json&limit=10")
    kc = _comparable(nombre)
    exactos = [a for a in d.get("artists", []) if _comparable(a.get("name", "")) == kc
               or any(_comparable(x.get("name", "")) == kc for x in a.get("aliases", []))]
    res = {"v": VERSION, "q": BUSQUEDA}
    if exactos:
        a = exactos[0]  # MusicBrainz ordena por relevancia: el primero suele ser el conocido
        if len(exactos) > 1 and titulos:
            a = next((x for x in exactos[:3] if _tiene_cancion(x["id"], list(titulos))), a)
        area, origen = a.get("area") or {}, a.get("begin-area") or {}
        pais_mb = a.get("country") or REGIONES.get((area.get("name") or "").casefold())
        # personas: país donde nacieron (Rihanna → Barbados aunque figure en EE. UU.); grupos: el suyo si lo
        # tienen (casi siempre es donde se formaron) y así se ahorran peticiones
        pais = (pais_mb if a.get("type") != "Person" and pais_mb else None) or pais_de_area(origen.get("id")) or pais_mb
        vida = a.get("life-span") or {}
        res.update(pais=pais, pais_mb=pais_mb, tipo=a.get("type"), genero=a.get("gender"), inicio=vida.get("begin"),
                   fin=vida.get("end"), zona=origen.get("name") or area.get("name"), mbid=a.get("id"),
                   homonimos=len(exactos))
    cache = cache_json(CACHE)
    cache[k] = res
    save_cache(CACHE, cache)
    return res


def info(nombre, cache=None, manual=None):
    """Datos del artista combinando MusicBrainz (caché) y correcciones manuales. No hace peticiones."""
    cache = cache_json(CACHE) if cache is None else cache
    manual = manuales() if manual is None else manual
    return {**(cache.get(clave(nombre)) or {}), **manual.get(nombre, {})}


def _comparable(nombre):
    return clave(re.sub(r"\s+(y|and|&|e|\+)\s+", " ", nombre, flags=re.I))


def _pendiente(e):
    """Sin buscar, buscado con un método anterior, o no encontrado con una búsqueda más antigua que la actual."""
    return not e or e.get("v") != VERSION or (not e.get("mbid") and e.get("q") != BUSQUEDA)


def pendientes(nombres):
    cache = cache_json(CACHE)
    return [n for n in nombres if _pendiente(cache.get(clave(n)))]


OYENTES = "oyentes_lb.json"
LB = "https://api.listenbrainz.org/1/popularity/artist"


def actualizar_oyentes(mbids, bloque=200):
    """Oyentes de cada artista en ListenBrainz (comunidad de MusicBrainz), por lotes. Guarda en caché
    {mbid: oyentes} y devuelve cuántos ha consultado. Sirve para ver qué artistas son más de nicho."""
    import time
    from urllib.request import Request
    from core.red import abrir
    cache = cache_json(OYENTES)
    faltan = [m for m in dict.fromkeys(mbids) if m and m not in cache]
    for i in range(0, len(faltan), bloque):
        lote = faltan[i:i + bloque]
        req = Request(LB, data=json.dumps({"artist_mbids": lote}).encode(), method="POST",
                      headers={"User-Agent": musicbrainz.UA, "Content-Type": "application/json"})
        with abrir(req) as r:
            for x in json.loads(r.read()):
                cache[x["artist_mbid"]] = x.get("total_user_count") or 0
        for m in lote:
            cache.setdefault(m, 0)
        save_cache(OYENTES, cache)
        time.sleep(1)
    return len(faltan)


def oyentes():
    return cache_json(OYENTES)
