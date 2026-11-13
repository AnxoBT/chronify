"""Lectura de los CSV de Exportify (sueltos o dentro del zip de 'Export All').

Cada lista se toma del archivo más reciente que se encuentre con su nombre, así se pueden mezclar
un zip completo antiguo con CSV sueltos descargados después.
"""
import csv
import io
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.config import export_dirs, norm

CABECERA = "Track URI"


@dataclass
class Pista:
    id: str
    titulo: str
    artistas: str
    album: str
    fecha_spotify: str
    generos: list = field(default_factory=list)
    sello: str = ""
    isrc: str = ""
    anadida: str = ""
    bpm: float | None = None
    energia: float | None = None
    bailable: float | None = None
    tono: int | None = None
    modo: int | None = None
    duracion: int | None = None  # ms
    popularidad: int | None = None  # 0-100
    explicita: bool = False
    valencia: float | None = None  # 0 triste … 1 alegre
    acustica: float | None = None
    habla: float | None = None
    volumen: float | None = None  # dB
    album_tipo: str = ""  # album | single | compilation (solo por la API)

    @property
    def url(self):
        return f"https://open.spotify.com/track/{self.id}"

    def etiqueta(self):
        return f"{self.artistas.replace(';', ', ')} - {self.titulo}"


@dataclass
class Lista:
    nombre: str
    origen: str
    mtime: float
    pistas: list  # ids en el orden actual de Spotify (con duplicados si los hay)
    autor: str = ""  # usuario que más canciones añadió (en listas que sigues de otra persona, esa persona)
    ajena: bool = False
    solo_lectura: bool = False  # se lee para comprobar, nunca se ordena ni se modifica (p. ej. Liked_Songs)
    spotify_id: str = ""  # solo si se leyó por la API (necesario para aplicar el orden)
    anadidas: dict = field(default_factory=dict)  # id -> fecha de añadido en ESTA lista


def _num(x, conv=float):
    try:
        return conv(x)
    except (TypeError, ValueError):
        return None


def _parse(texto, nombre, origen, mtime, catalogo):
    filas = list(csv.DictReader(io.StringIO(texto)))
    ids, autores, anadidas = [], Counter(), {}
    for r in filas:
        uri = r.get(CABECERA, "")
        if not uri.startswith("spotify:track:"):
            continue  # episodios de podcast o pistas locales
        tid = uri.rsplit(":", 1)[-1]
        ids.append(tid)
        anadidas.setdefault(tid, r.get("Added At", ""))
        autores[r.get("Added By", "")] += 1
        catalogo[tid] = Pista(
            id=tid, titulo=r.get("Track Name", ""), artistas=r.get("Artist Name(s)", ""),
            album=r.get("Album Name", ""), fecha_spotify=r.get("Release Date", ""),
            generos=[g for g in r.get("Genres", "").split(",") if g], sello=r.get("Record Label", ""),
            isrc=r.get("ISRC", ""),
            anadida=r.get("Added At", ""), bpm=_num(r.get("Tempo")), energia=_num(r.get("Energy")),
            bailable=_num(r.get("Danceability")), tono=_num(r.get("Key"), int), modo=_num(r.get("Mode"), int),
            duracion=_num(r.get("Duration (ms)"), int), popularidad=_num(r.get("Popularity"), int),
            explicita=r.get("Explicit", "").lower() == "true", valencia=_num(r.get("Valence")),
            acustica=_num(r.get("Acousticness")), habla=_num(r.get("Speechiness")), volumen=_num(r.get("Loudness")))
    autor = autores.most_common(1)[0][0] if autores else ""
    return Lista(nombre=nombre, origen=origen, mtime=mtime, pistas=ids, autor=autor, anadidas=anadidas)


def _candidatos():
    """(nombre, texto, origen, mtime) de cada CSV de Exportify encontrado."""
    for d in export_dirs():
        if not d.exists():
            continue
        # carpeta y un nivel de subcarpetas (data/exportify-AAAA-MM/…); no recorre Descargas entera
        for p in [*d.glob("*"), *d.glob("*/*")]:
            suf = p.suffix.lower()
            try:
                if suf == ".csv":
                    with open(p, encoding="utf-8-sig") as f:
                        if not f.readline().startswith(CABECERA):
                            continue
                    yield p.stem, p.read_text(encoding="utf-8-sig"), str(p), p.stat().st_mtime, False
                elif suf == ".zip":
                    with zipfile.ZipFile(p) as z:
                        for n in z.namelist():
                            if n.lower().endswith(".csv"):
                                t = z.read(n).decode("utf-8-sig")
                                if t.startswith(CABECERA):
                                    yield Path(n).stem, t, f"{p.name}:{n}", p.stat().st_mtime, True
            except (OSError, zipfile.BadZipFile, UnicodeDecodeError):
                continue  # zip a medio descargar, archivo bloqueado…


def cargar(ignorar=(), mix="", solo_lectura=()):
    """Devuelve (listas propias por nombre exacto, catálogo de pistas por id).

    - Listas que sigues de otra persona (la mayoría de canciones las añadió otro usuario): se descartan
      enteras, ni sus canciones entran en el catálogo. 'Español' (tuya) y 'español' (ajena) no se mezclan.
    - 'ignorar' (DJ, Saved_Albums…): se descartan. 'solo_lectura' (Liked_Songs): se leen pero nunca se ordenan.
    - Un zip de 'Export All' tiene todas las listas: lo anterior a él se descarta (listas borradas no reaparecen).
      CSV sueltos posteriores al zip sí lo actualizan.
    """
    cands = [(unicodedata.normalize("NFC", n), *rest) for n, *rest in _candidatos()]
    zips = [c[3] for c in cands if c[4]]
    corte = max(zips) if zips else 0
    elegidos, fuera = {}, {norm(n) for n in ignorar}  # "Mi lista" = "Mi_lista" (nombre del CSV)
    for nombre, texto, origen, mtime, _ in cands:
        if mtime < corte or norm(nombre) in fuera:
            continue
        if nombre not in elegidos or mtime > elegidos[nombre][3]:
            elegidos[nombre] = (nombre, texto, origen, mtime)
    leidas = []
    for nombre, texto, origen, mtime in sorted(elegidos.values(), key=lambda v: v[3]):
        cat = {}
        leidas.append((_parse(texto, nombre, origen, mtime, cat), cat))
    autores = {l.nombre: l.autor for l, _ in leidas}
    yo = autores.get(mix) or (Counter(autores.values()).most_common(1)[0][0] if autores else "")
    catalogo, listas = {}, {}
    for l, cat in leidas:  # de más antiguo a más reciente: los metadatos más nuevos ganan
        if l.autor and l.autor != yo:
            continue
        l.solo_lectura = l.nombre in solo_lectura
        listas[l.nombre] = l
        catalogo.update(cat)
    return listas, catalogo


def buscar(listas, nombre):
    """Lista por nombre: exacto o, si no, sin tildes/mayúsculas entre las propias (si no hay ambigüedad)."""
    if nombre in listas:
        return listas[nombre]
    c = [l for l in listas.values() if not l.ajena and norm(l.nombre) == norm(nombre)]
    return c[0] if len(c) == 1 else None


def describir(listas):
    return [{"nombre": l.nombre, "pistas": len(l.pistas), "origen": l.origen, "ajena": l.ajena,
             "fecha": datetime.fromtimestamp(l.mtime).strftime("%d/%m/%Y %H:%M")}
            for l in sorted(listas.values(), key=lambda l: norm(l.nombre))]
