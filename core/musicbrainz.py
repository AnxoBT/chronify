"""Fecha original de una canción en MusicBrainz (gratis, sin clave, máx. 1 petición/segundo).

Busca grabaciones del mismo artista con el mismo título (sin "Remastered", "Radio Edit", "feat."…)
y toma la 'first-release-date' más antigua. Es una PROPUESTA: la web la enseña y tú la aceptas.
Las respuestas se guardan en cache/musicbrainz.json para no repetir búsquedas.
"""
import json
import re
import threading
import time
import unicodedata
from collections import Counter
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request

from core.config import cache_json, save_cache
from core.red import abrir

API = "https://musicbrainz.org/ws/2/recording"
UA = "Chronify/1.6 (https://github.com/AnxoBT/chronify)"  # genérico: nunca datos del usuario
CACHE = "musicbrainz.json"
_ultimo = [0.0]

_PARENTESIS = re.compile(
    r"\s*[(\[][^)\]]*\b(remaster\w*|edit|version|versi[oó]n|live|directo|feat|ft|with|con|mix|mono|stereo|"
    r"deluxe|bonus|from|soundtrack|banda sonora)\b[^)\]]*[)\]]", re.I)


def limpiar(titulo):
    """'Hey Jude - Remastered 2015' -> 'Hey Jude'; 'Wiggle (feat. Snoop Dogg)' -> 'Wiggle'."""
    t = (titulo or "").split(" - ")[0]  # Spotify pone la versión tras ' - '
    t = _PARENTESIS.sub("", t).strip()
    return t or (titulo or "").strip()


def _clave(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", s)


_LOCK = threading.Lock()  # búsquedas a la vez (fechas y países) comparten el límite de 1 petición/s


def _turno():
    with _LOCK:
        espera = 1.1 - (time.time() - _ultimo[0])
        if espera > 0:
            time.sleep(espera)
        _ultimo[0] = time.time()


def _get(url):
    for intento in range(6):
        _turno()
        try:
            with abrir(Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            # 503/429: MusicBrainz pide ir más despacio (p. ej. dos búsquedas a la vez): espera creciente
            if e.code in (429, 502, 503) and intento < 5:
                time.sleep(3 * 2 ** intento)
                continue
            raise


def elegir(fechas):
    """Año más antiguo que aparece al menos 2 veces (un dato suelto suele ser un error o una versión
    distinta con el mismo nombre). Si ningún año se repite, el más antiguo. Devuelve la fecha más precisa
    más temprana de ese año."""
    fechas = [f for f in fechas if f and re.match(r"^\d{4}", f)]
    if not fechas:
        return None
    anios = Counter(f[:4] for f in fechas)
    repetidos = [a for a, n in anios.items() if n >= 2]
    anio = min(repetidos) if repetidos else min(anios)
    del_anio = sorted(f for f in fechas if f.startswith(anio))
    completas = [f for f in del_anio if len(f) == 10]
    return (completas or sorted(del_anio, key=len, reverse=True))[0]


def buscar(pista):
    """Devuelve {'fecha', 'todas', 'titulo', 'artista', 'n'} o None. Usa caché."""
    artista = pista.artistas.split(";")[0]
    titulo = limpiar(pista.titulo)
    k = f"v2|{_clave(artista)}|{_clave(titulo)}|{getattr(pista, 'isrc', '')}"
    cache = cache_json(CACHE)
    if k in cache:
        r = cache[k]
        return r and {**r, "fecha": elegir(r["todas"])}
    def del_artista(item):
        creditos = " ".join(c.get("name", "") + c.get("artist", {}).get("name", "") for c in item.get("artist-credit", []))
        return _clave(artista) in _clave(creditos)

    fechas = []
    # 0) ISRC exacto (identifica la grabación; un remaster suele tener otro ISRC, por eso se combina con 1 y 2)
    if getattr(pista, "isrc", ""):
        for rec in _get(f"{API}?query={quote('isrc:' + pista.isrc)}&fmt=json&limit=25").get("recordings", []):
            if pista.isrc in rec.get("isrcs", []) and del_artista(rec):  # la búsqueda devuelve también parecidos
                fechas.append(rec.get("first-release-date"))
    # 1) grabaciones con el mismo título
    q = quote(f'recording:"{titulo}" AND artist:"{artista}"')
    for rec in _get(f"{API}?query={q}&fmt=json&limit=100").get("recordings", []):
        if rec.get("score", 0) >= 70 and _clave(limpiar(rec.get("title", ""))) == _clave(titulo) and del_artista(rec):
            fechas.append(rec.get("first-release-date"))
    # 2) singles/EP cuyo título empieza igual ('Hit the Road Jack / The Danger Zone'): suelen tener la fecha original
    q = quote(f'releasegroup:"{titulo}" AND artist:"{artista}"')
    for g in _get(f"{API.replace('recording', 'release-group')}?query={q}&fmt=json&limit=50").get("release-groups", []):
        if (g.get("primary-type") in ("Single", "EP") and _clave(g.get("title", "")).startswith(_clave(titulo))
                and del_artista(g)):
            fechas.append(g.get("first-release-date"))
    fechas = sorted(f for f in fechas if f and re.match(r"^\d{4}", f))
    res = {"fecha": elegir(fechas), "todas": fechas, "n": len(fechas), "titulo": titulo, "artista": artista} if fechas else None
    cache[k] = res
    save_cache(CACHE, cache)
    return res
