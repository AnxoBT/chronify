"""Discos de una lista para Estadísticas: cuántas canciones tienes de cada disco, qué parte del disco es y cuánto dura.

Exportify no trae id del disco ni cuántas canciones tiene: los discos se agrupan por nombre del disco + primer
artista (sin tildes, mayúsculas ni signos) y el total de canciones y la duración del disco entero salen de
MusicBrainz (gratis, sin cuenta; 2 peticiones por disco, 1/s), guardados en cache/musicbrainz.json con la clave
`disco1|artista|disco` (así viajan en conocimiento/ y en la sincronización como el resto de MusicBrainz).
Calcular nunca hace peticiones: lo que aún no se ha buscado sale sin total.
"""
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean
from urllib.parse import quote

from core import musicbrainz
from core.config import cache_json, save_cache

API = "https://musicbrainz.org/ws/2/release"
VARIOS = "Varios artistas"
MIN_PISTAS_PCT = 5  # para "los más completos": discos de al menos 5 canciones (con menos, cualquier EP sale al 100 %)

_EDICION = r"(deluxe|edici[oó]n|edition|remaster\w*|expanded|anniversary|aniversario|version|versi[oó]n|bonus|special|" \
           r"especial|explicit|clean|reissue|reedici[oó]n|super|legacy|collector)"
_PARENTESIS = re.compile(r"\s*[(\[][^)\]]*\b" + _EDICION + r"\b[^)\]]*[)\]]", re.I)
_GUION = re.compile(r"\s+-\s+[^-]*\b" + _EDICION + r"\b.*$", re.I)


def _k(s):
    """Clave para comparar nombres: sin tildes, mayúsculas ni signos (conserva letras no latinas)."""
    s = unicodedata.normalize("NFKD", s or "").casefold()
    return re.sub(r"[\W_]+", "", "".join(c for c in s if not unicodedata.combining(c)))


def limpiar(disco):
    """'Rumours (Super Deluxe)' → 'Rumours'; 'Abbey Road - Remastered 2009' → 'Abbey Road'."""
    d = _GUION.sub("", _PARENTESIS.sub("", disco or "")).strip()
    return d or (disco or "").strip()


def es_edicion(disco):
    return bool(re.search(r"\b" + _EDICION + r"\b", disco or "", re.I)) and limpiar(disco) != (disco or "").strip()


def clave_cache(artista, disco):
    return f"disco1|{_k(artista)}|{_k(disco)}"


def _primero(p):
    return (p.artistas or "").split(";")[0]


def agrupar(P):
    """{clave: {'disco', 'artista', 'ids'}} de las canciones P {id: Pista}. Clave = (primer artista, disco).

    Recopilatorios de varios artistas (mismo nombre de disco y misma fecha con 3 o más artistas distintos, p. ej.
    una banda sonora) se juntan en uno solo con artista "Varios artistas"."""
    por_nombre = defaultdict(list)
    for t, p in P.items():
        if (p.album or "").strip():
            por_nombre[_k(p.album)].append(t)
    out = {}
    for kd, ts in por_nombre.items():
        artistas_ = {_k(_primero(P[t])) for t in ts}
        fechas = {P[t].fecha_spotify for t in ts}
        varios = len(artistas_) >= 3 and len(fechas) == 1
        for t in ts:
            p = P[t]
            k = ("*", kd) if varios else (_k(_primero(p)), kd)
            g = out.setdefault(k, {"disco": p.album, "artista": VARIOS if varios else _primero(p), "ids": [], "varios": varios})
            g["ids"].append(t)
    return out


def _single(g, P):
    """Sin MusicBrainz: un disco que se llama como una de sus canciones y del que tienes 1–2 es casi seguro un single."""
    kd = _k(limpiar(g["disco"]))
    return len(g["ids"]) <= 2 and any(_k(musicbrainz.limpiar(P[t].titulo)) == kd for t in g["ids"])


def pendientes(P, cache=None):
    """[(artista, disco)] que aún no se han buscado en MusicBrainz: primero los que más canciones tienes y al final los
    que parecen singles (un disco que se llama como tu canción puede ser también el álbum). Los de varios artistas no."""
    cache = cache_json(musicbrainz.CACHE) if cache is None else cache
    gs = sorted(agrupar(P).values(), key=lambda g: (_single(g, P), -len(g["ids"]), _k(g["disco"])))
    return [(g["artista"], g["disco"]) for g in gs
            if not g["varios"] and clave_cache(g["artista"], g["disco"]) not in cache]


_VIDEO = re.compile(r"dvd|blu-?ray|video|vhs|laserdisc|umd", re.I)
_GENERICAS = {"edition", "edición", "version", "versión"}


def _pistas(r):
    """Canciones de una edición sin contar DVD/vídeo (un box set con DVD no es un disco más largo)."""
    media = r.get("media") or []
    if not media:
        return r.get("track-count") or 0
    return sum(m.get("track-count") or 0 for m in media if not _VIDEO.search(m.get("format") or ""))


def _moda(ns):
    """Número de canciones más repetido (empate → el menor)."""
    cuenta = Counter(ns)
    return min(cuenta, key=lambda c: (-cuenta[c], c))


def buscar(artista, disco):
    """{'titulo', 'tipo', 'secundarios', 'pistas', 'ms', 'fecha', 'mbid'} del disco en MusicBrainz, o '' si no está.
    'ms' = duración del disco entero (None si a alguna canción le falta). Usa caché."""
    k = clave_cache(artista, disco)
    cache = cache_json(musicbrainz.CACHE)
    if k in cache:
        return cache[k]
    nombre = limpiar(disco)

    def del_artista(r):
        creditos = " ".join(c.get("name", "") + (c.get("artist") or {}).get("name", "") for c in r.get("artist-credit", []))
        return _k(artista) in _k(creditos)
    cands = []
    # nombre exacto y, si no sale nada, por palabras ("LP2" y "LP 2" son la misma búsqueda así)
    for titulo in (f'"{nombre.replace(chr(34), "")}"', "(" + re.sub(r'[\\"():\[\]{}^~*?!+&|/-]', " ", nombre) + ")"):
        q = f'release:{titulo} AND artist:"{artista.replace(chr(34), "")}"'
        rels = musicbrainz._get(f"{API}?query={quote(q)}&fmt=json&limit=50").get("releases", [])
        cands = [r for r in rels if r.get("score", 0) >= 80 and _k(limpiar(r.get("title", ""))) == _k(nombre)
                 and del_artista(r) and (r.get("release-group") or {}).get("id") and _pistas(r)]
        if cands:
            break
    res = ""
    if cands:
        rg = cands[0]["release-group"]
        grupo = [r for r in cands if r["release-group"]["id"] == rg["id"]]
        oficiales = [r for r in grupo if r.get("status") in (None, "Official")] or grupo
        n = _moda(_pistas(r) for r in oficiales)  # la edición normal: la más repetida
        if es_edicion(disco):  # "(Deluxe Edition)": la que se llama así o, si no, la más repetida de las más largas
            palabras = {w.casefold() for w in re.findall(_EDICION, disco, re.I)} - _GENERICAS
            esa = [r for r in oficiales if any(w in f"{r.get('title', '')} {r.get('disambiguation', '')}".casefold()
                                               for w in palabras)]
            mas = [r for r in oficiales if _pistas(r) > n]
            if esa or mas:
                n = _moda(_pistas(r) for r in (esa or mas))
        elegido = min((r for r in oficiales if _pistas(r) == n), key=lambda r: r.get("date") or "9999")
        d = musicbrainz._get(f"{API}/{elegido['id']}?inc=recordings&fmt=json")
        largos = [t.get("length") for m in d.get("media", []) if not _VIDEO.search(m.get("format") or "")
                  for t in m.get("tracks", [])]
        fechas = sorted(r["date"] for r in grupo if re.match(r"^\d{4}", r.get("date") or ""))
        res = {"titulo": rg.get("title") or elegido.get("title", ""), "tipo": rg.get("primary-type") or "",
               "secundarios": rg.get("secondary-types") or [], "pistas": len(largos) or n,
               "ms": sum(largos) if largos and all(largos) else None,
               "fecha": fechas[0] if fechas else "", "mbid": rg["id"]}
    cache = cache_json(musicbrainz.CACHE)  # otra búsqueda pudo guardar mientras tanto
    cache[k] = res
    save_cache(musicbrainz.CACHE, cache)
    return res


def _decada(a):
    return f"{a // 10 * 10}s"


def _busqueda(d):
    return d["disco"] if d["varios"] else f"{d['artista']} {d['disco']}"


def calcular(P, cache, hoy=None):
    """Estadísticas de discos de las canciones P {id: Pista} con lo que ya hay en la caché de MusicBrainz (sin red)."""
    hoy = hoy or datetime.now().year
    discos = []
    for g in agrupar(P).values():
        mb = None if g["varios"] else cache.get(clave_cache(g["artista"], g["disco"]))
        anios = [int(P[t].fecha_spotify[:4]) for t in g["ids"] if (P[t].fecha_spotify or "")[:4].isdigit()]
        if mb and mb.get("fecha", "")[:4].isdigit():
            anios.append(int(mb["fecha"][:4]))
        tipo = (mb or {}).get("tipo") or ("Single" if _single(g, P) else "")
        n = len(g["ids"])
        total = (mb or {}).get("pistas") or None
        discos.append({
            "disco": g["disco"], "artista": g["artista"], "n": n, "varios": g["varios"],
            "id": g["ids"][0], "titulos": [P[t].titulo for t in g["ids"]][:12],
            "anio": min(anios) if anios else None, "tipo": "Recopilatorio" if g["varios"] else tipo,
            "secundarios": (mb or {}).get("secundarios") or [], "buscado": mb is not None,
            "total": total, "ms": (mb or {}).get("ms"),
            "pct": min(100, round(100 * n / total)) if total else None})
    singles = [d for d in discos if d["tipo"] in ("Single", "EP")]
    albumes = [d for d in discos if d["tipo"] not in ("Single", "EP")]
    # discos "de verdad" para duración/canciones: álbumes de un artista según MusicBrainz
    largos = [d for d in albumes if d["tipo"] == "Album" and not d["varios"] and d["total"]]

    def fila(d, **extra):
        return {k: d[k] for k in ("disco", "artista", "n", "anio", "id", "titulos", "total", "ms", "pct", "tipo")} | extra
    orden_n = sorted(albumes, key=lambda d: (-d["n"], -(d["pct"] or 0), _k(d["disco"])))
    con_pct = [d for d in albumes if d["pct"] is not None and d["total"] >= MIN_PISTAS_PCT and not d["varios"]]
    completos = sorted((d for d in con_pct if d["pct"] >= 100), key=lambda d: (-d["total"], _k(d["disco"])))
    por_ms = sorted((d for d in largos if d["ms"]), key=lambda d: d["ms"])
    por_pistas = sorted(largos, key=lambda d: (d["total"], d["ms"] or 0))
    con_anio = [d for d in albumes if d["anio"]]
    dec = Counter(_decada(d["anio"]) for d in con_anio)
    de_artista = Counter(d["artista"] for d in albumes if not d["varios"])
    uno = [d for d in albumes if d["n"] == 1]
    canciones_single = sum(d["n"] for d in singles)
    cur = []
    if albumes:
        cur.append({"t": "Discos de los que solo tienes una canción", "v": f"{round(100 * len(uno) / len(albumes))} %",
                    "d": f"{len(uno)} de {len(albumes)}"})
    if con_pct:
        cur.append({"t": "Lo que tienes de cada disco, de media", "v": f"{round(mean(d['pct'] for d in con_pct))} %",
                    "d": f"{sum(d['n'] for d in con_pct)} de {sum(d['total'] for d in con_pct)} canciones"})
    if con_anio:
        viejo = min(con_anio, key=lambda d: (d["anio"], -d["n"]))
        nuevo = max(con_anio, key=lambda d: (d["anio"], d["n"]))
        cur.append({"t": "El disco más antiguo", "v": f"{viejo['artista']} - {viejo['disco']}", "buscar": _busqueda(viejo),
                    "d": str(viejo["anio"])})
        cur.append({"t": "El disco más reciente", "v": f"{nuevo['artista']} - {nuevo['disco']}", "buscar": _busqueda(nuevo),
                    "d": str(nuevo["anio"])})
    if P:
        cur.append({"t": "Canciones que son de un single o EP", "v": f"{round(100 * canciones_single / len(P))} %",
                    "d": f"{canciones_single} de {len(P)} canciones"})
    return {
        "resumen": {"discos": len(albumes), "singles": len(singles), "completos": len(completos),
                    "media": round(mean(d["n"] for d in albumes), 1) if albumes else None,
                    "edad_media": round(mean(hoy - d["anio"] for d in con_anio)) if con_anio else None,
                    "con_total": sum(1 for d in albumes if d["total"]),
                    "buscados": sum(1 for d in discos if d["buscado"])},
        "mas_canciones": [fila(d) for d in orden_n[:10]],
        # a medias (los completos van aparte): los que tienes casi enteros, primero
        "mas_completos": [fila(d) for d in sorted((d for d in con_pct if d["n"] >= 2 and d["pct"] < 100),
                                                   key=lambda d: (-d["pct"], d["total"] - d["n"], _k(d["disco"])))[:10]],
        "completos": [fila(d) for d in completos[:12]],
        "largos": [fila(d) for d in por_ms[::-1][:5]],
        "cortos": [fila(d) for d in por_ms[:5]],
        "mas_pistas": [fila(d) for d in por_pistas[::-1][:5]],
        "menos_pistas": [fila(d) for d in por_pistas[:5]],
        "por_decada": [{"decada": d, "n": n} for d, n in sorted(dec.items())],
        "artistas": [{"nombre": a, "n": n, "discos": [d["disco"] for d in orden_n if d["artista"] == a][:10]}
                     for a, n in de_artista.most_common(10) if n > 1],
        "curiosidades": cur,
    }
