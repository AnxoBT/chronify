"""Comprobaciones entre listas y orden cronológico de cada una."""
import bisect
import re
import unicodedata
from collections import Counter

from core.config import norm, rules
from core.exportify import buscar
from core.fechas import Fechas


def _pista_json(tid, cat, F):
    p = cat.get(tid)
    fecha, fuente, aprox = F.info(tid, p)
    return {"id": tid, "t": p.etiqueta() if p else "(sin datos: aparece en un txt pero no en los CSV)",
            "fecha": fecha, "fuente": fuente, "aprox": aprox,
            "spotify": p.fecha_spotify if p else "", "generos": p.generos if p else []}


# Señales de que la canción de la lista no es la versión original de estudio (aviso "versión dudosa")
_DIRECTO = re.compile(r"\b(live|en directo|en vivo|ao vivo|unplugged|in concert|concierto)\b", re.I)
_VERSION = re.compile(r"\b(remix|rmx|re-?edit|edit|versi[oó]n|version|re-?recorded|regrabad\w*|acoustic|"
                      r"ac[uú]stic\w*|demo|instrumental|karaoke|sped up|slowed|orchestral|sinf[oó]nic\w*|symphonic|"
                      r"extended|club mix|take \d+)\b", re.I)
# versiones que sí son la original (o equivalentes): no avisan
_BUENA = re.compile(r"\b(single|album|original|stereo|mono|uncensored|explicit|clean|main|lp|radio|vocal|tv|7\"?|45)\s+"
                    r"(version|versi[oó]n|mix|edit)\b|\b(mono|stereo)\b$", re.I)
_RECOPILATORIO = re.compile(r"(greatest hits|best of|the best|grandes [eé]xitos|lo mejor de|essential|collection|"
                            r"colecci[oó]n|antholog|antolog|\bgold\b|\bhits\b|platinum collection|very best|[eé]xitos|"
                            r"now that|recopilatorio|\bsingles\b|definitive|the story of|top 40|compilation)", re.I)
_REMASTER = re.compile(r"remaster", re.I)


def _sufijo(titulo):
    """Parte del título que describe la versión: tras ' - ' y entre paréntesis ('Live And Let Die' no es un directo)."""
    partes = titulo.split(" - ", 1)
    return " | ".join([partes[1] if len(partes) > 1 else "", *re.findall(r"[(\[]([^)\]]*)[)\]]", partes[0])])


def motivos_version(p, fecha_real=""):
    """Por qué esta versión podría no ser la original: [(categoría, texto)]. Vacía si parece la buena."""
    if not p:
        return []
    out, titulo, album = [], _sufijo(p.titulo or ""), p.album or ""
    if _DIRECTO.search(titulo) or re.search(r"[(\[]live\b|\blive (at|in|from|on)\b|(^|[\s(\[])live$|en directo|en vivo|unplugged|in concert",
                                                     album, re.I):
        out.append(("directo", "en directo"))
    m = _VERSION.search(_BUENA.sub("", titulo))
    if m:
        out.append(("version", f"versión: «{m.group(0)}»"))
    if p.album_tipo == "compilation" or _RECOPILATORIO.search(album):
        out.append(("recopilatorio", f"de un recopilatorio ({album})"))
    if _REMASTER.search(titulo) or _REMASTER.search(album):
        out.append(("reedicion", "remasterizada"))
    a_sp, a_real = (p.fecha_spotify or "")[:4], (fecha_real or "")[:4]
    if a_sp.isdigit() and a_real.isdigit() and int(a_sp) - int(a_real) >= 3 and not out:
        out.append(("reedicion", f"el disco de Spotify es de {a_sp}, la canción de {a_real}"))
    if p.popularidad is not None and p.popularidad <= 5:  # Spotify tiene varias copias: la escuchada es otra
        out.append(("copia", f"popularidad {p.popularidad}/100"))
    return out


def clave_cancion(p):
    """Misma canción aunque Spotify tenga varias copias: primer artista + título sin la parte de versión.
    Conserva letras no latinas (japonés…) para no juntar canciones distintas."""
    from core.musicbrainz import limpiar

    def k(x):
        x = unicodedata.normalize("NFKD", x).casefold()
        return re.sub(r"[\W_]+", "", "".join(c for c in x if not unicodedata.combining(c)))
    return k((p.artistas or "").split(";")[0]), k(limpiar(p.titulo or ""))


def duplicadas_por_copia(ids, cat):
    """Grupos de ids distintos que son la misma canción (mismo ISRC, o mismo artista y título)."""
    grupos = {}
    for t in ids:
        p = cat.get(t)
        if p and all(clave_cancion(p)):
            grupos.setdefault(("c",) + clave_cancion(p), set()).add(t)
        if p and p.isrc:
            grupos.setdefault(("i", p.isrc), set()).add(t)
    vistos, out = set(), []
    for g in grupos.values():
        g = frozenset(g)
        if len(g) > 1 and g not in vistos:
            vistos.add(g)
            out.append(sorted(g))
    return out


def sugerir_generos(tid, listas, cat, R):
    """Listas de género para una canción: primero donde tienes otras canciones de sus artistas,
    si no por los géneros de Spotify. [(lista, motivo)]"""
    p = cat.get(tid)
    if not p:
        return []
    mios = set(p.artistas.split(";"))
    cuenta = Counter()
    for g in R.get("generos") or []:
        l = buscar(listas, g)
        if l:
            cuenta[g] = sum(1 for t in set(l.pistas) if t != tid and t in cat and mios & set(cat[t].artistas.split(";")))
    top = [(g, f"{n} {'canciones' if n > 1 else 'canción'} del artista ahí") for g, n in cuenta.most_common(2) if n]
    if top:
        return top
    palabras = {k: v for k, v in R.get("generos_spotify", {}).items() if not k.startswith("_")}
    gen = " | ".join(p.generos).casefold()
    puntos = Counter({g: sum(1 for w in ws if w in gen) for g, ws in palabras.items()})
    return [(g, "géneros de Spotify: " + ", ".join(p.generos[:3])) for g, n in puntos.most_common(2)
            if n and buscar(listas, g)]  # solo listas que existen (las palabras traen nombres de ejemplo)


def _decada(anio, decadas):
    for nombre, (a, b) in decadas.items():
        if (a is None or anio >= a) and (b is None or anio <= b):
            return nombre
    return None


def comprobar(listas, cat, F=None, R=None):
    """Lista de avisos {tipo, gravedad, lista, texto, pistas[]} . gravedad: error | aviso | info."""
    F = F or Fechas()
    R = R or rules()
    exc = {k: set(v) for k, v in R.get("excepciones", {}).items() if isinstance(v, list)}
    out = []

    def L(nombre):
        return buscar(listas, nombre)

    def S(nombre):
        l = L(nombre)
        return set(l.pistas) if l else set()

    def aviso(tipo, gravedad, texto, ids, lista=""):
        ids = sorted(ids, key=lambda t: F.clave(t, cat.get(t)))
        if ids:
            out.append({"tipo": tipo, "gravedad": gravedad, "lista": lista, "texto": texto,
                        "pistas": [_pista_json(t, cat, F) for t in ids]})

    # Todo es opcional: cada usuario configura sus listas en Ajustes (rules.json). Sin Mix, las comprobaciones de
    # canciones se hacen sobre todas tus listas.
    nmix, partes = R.get("mix") or "", list(R.get("idiomas") or [])
    decadas, nombres_gen = R.get("decadas") or {}, list(R.get("generos") or [])
    faltan = [n for n in [nmix, *partes, *decadas, *nombres_gen] if n and not L(n)]
    if faltan:
        out.append({"tipo": "faltan_listas", "gravedad": "error", "lista": "", "pistas": [],
                    "texto": "No encuentro estas listas (revisa Ajustes → Tus listas): " + ", ".join(faltan)})

    propias = set().union(*(set(l.pistas) for l in listas.values() if not l.ajena and not l.solo_lectura))
    mix = S(nmix) if nmix else propias
    idiomas = set().union(*(S(n) for n in partes))
    nfriki = R.get("friki") or ""
    friki = S(nfriki) if nfriki else set()
    solo_friki = friki - set().union(*(S(n) for n in partes if norm(n) != norm(nfriki)))

    # duplicados dentro de una lista
    for l in listas.values():
        if l.ajena or l.solo_lectura:
            continue
        d = [t for t, c in Counter(l.pistas).items() if c > 1]
        aviso("duplicadas", "aviso", "Canciones repetidas dentro de la lista", d, l.nombre)

    # Mix = unión de las listas que lo forman (en el ejemplo: idiomas)
    if nmix and partes:
        aviso("falta_en_mix", "error", f"Está en {' / '.join(partes)} pero no en {nmix}",
              idiomas - mix - exc.get("fuera_de_mix", set()), nmix)
        aviso("sin_idioma", "error", f"Está en {nmix} pero en ninguna de las listas que lo forman ({', '.join(partes)})",
              mix - idiomas, nmix)

    # el resto de listas tienen que estar dentro de Mix
    if nmix:
        for n in [*decadas, *nombres_gen]:
            aviso("fuera_de_mix", "error", f"Está en {n} pero no en {nmix}",
                  S(n) - mix - exc.get("fuera_de_mix", set()), n)

    # cada canción (salvo las de la lista sin género obligatorio) en al menos un género y en exactamente una época
    candidatas = mix - solo_friki
    generos = set().union(*(S(n) for n in nombres_gen))
    if nombres_gen:
        aviso("sin_genero", "aviso", "No está en ninguna lista de género", candidatas - generos - exc.get("sin_genero", set()))
        if out and out[-1]["tipo"] == "sin_genero":  # propuesta de lista (botón "añadir a …")
            for p in out[-1]["pistas"]:
                p["sugeridas"] = [{"lista": g, "motivo": m} for g, m in sugerir_generos(p["id"], listas, cat, R)]
    en_dec = Counter(t for n in decadas for t in S(n))
    if decadas:
        aviso("sin_decada", "aviso", "No está en ninguna lista de época",
              {t for t in candidatas if not en_dec[t]} - exc.get("sin_decada", set()))
        if out and out[-1]["tipo"] == "sin_decada":
            for p in out[-1]["pistas"]:
                a = F.anio(p["id"], cat.get(p["id"]))
                if a is not None:
                    p["sugeridas"] = [{"lista": _decada(a, decadas), "motivo": f"fecha {p['fecha']}"}]
        aviso("varias_decadas", "aviso", "Está en más de una lista de época", {t for t, c in en_dec.items() if c > 1})
    if nfriki:
        aviso("solo_friki_en_otras", "info", f"Solo está en {nfriki} pero aparece en listas de género/época",
              solo_friki & (generos | set(en_dec)))

    # la época de la lista tiene que cuadrar con la fecha real
    for n in decadas:
        mal_seguro, mal_aprox = set(), set()
        for t in S(n) - exc.get("decada_distinta", set()):
            a = F.anio(t, cat.get(t))
            if a is None:
                continue
            ok = _decada(a, decadas)
            if ok and norm(ok) != norm(n):
                (mal_aprox if F.info(t, cat.get(t))[2] else mal_seguro).add(t)
        aviso("decada_distinta", "error", f"La fecha no cuadra con {n}", mal_seguro, n)
        if mal_seguro:  # a qué lista de época le toca (para el botón "mover a …")
            for p in out[-1]["pistas"]:
                p["destino"] = _decada(F.anio(p["id"], cat.get(p["id"])), decadas)
        aviso("decada_aprox", "info", f"Fecha aproximada que no cuadra con {n} (revisa la fecha)", mal_aprox, n)

    # canciones sin fecha verificada (nuevas desde la última vez)
    nuevas = {t for t in mix if t not in F.pistas}
    aviso("fecha_sin_verificar", "aviso", "Canciones nuevas: la fecha es la de Spotify, sin verificar", nuevas)
    if out and out[-1]["tipo"] == "fecha_sin_verificar":
        for p in out[-1]["pistas"]:
            p["motivos"] = [m for _, m in motivos_version(cat.get(p["id"]))]

    # la misma canción guardada dos veces con ids distintos (dos copias de Spotify): los duplicados normales
    # no lo detectan porque el id es otro
    dup = [g for g in duplicadas_por_copia(mix, cat) if not set(g) & exc.get("misma_cancion", set())]
    aviso("misma_cancion", "aviso", f"La misma canción está dos veces en {nmix or 'tus listas'} (copias distintas de Spotify): quita una",
          {t for g in dup for t in g}, nmix)
    if out and out[-1]["tipo"] == "misma_cancion":
        for p in out[-1]["pistas"]:
            p["motivos"] = [f"disco: {cat[p['id']].album}" if p["id"] in cat else ""]

    # versiones que quizá no son la original de estudio (directo, remix, recopilatorio, reedición)
    grupos, textos = {"directo": [], "version": [], "recopilatorio": [], "reedicion": [], "copia": []}, {}
    for t in mix - exc.get("version_dudosa", set()):
        ms = motivos_version(cat.get(t), F.info(t, cat.get(t))[0])
        if ms:
            grupos[ms[0][0]].append(t)
            textos[t] = [m for _, m in ms]
    titulos = {"directo": ("aviso", "Versión en directo (¿hay una de estudio?)"),
               "version": ("aviso", "Remix, edit, acústica u otra versión (¿es la que quieres?)"),
               "recopilatorio": ("info", "Sacada de un recopilatorio (mejor la del disco original)"),
               "reedicion": ("info", "Reedición o remaster (la fecha usada es la original; revisa que sea la versión buena)"),
               "copia": ("info", "Copia poco escuchada (popularidad 0–5): Spotify tiene otra copia de esta canción, "
                                 "quizá en otra edición del disco, que es la que escucha todo el mundo")}
    for k, (grav, txt) in titulos.items():
        aviso("version_dudosa", grav, txt, grupos[k])
        if out and out[-1]["tipo"] == "version_dudosa" and out[-1]["texto"] == txt:
            out[-1]["categoria"] = k
            for p in out[-1]["pistas"]:
                p["motivos"] = textos.get(p["id"], [])
    return out


def ordenar(listas, cat, F=None, R=None):
    """Por lista: orden actual vs cronológico. Las listas 'no_reordenar' se informan pero no se ordenan."""
    F = F or Fechas()
    R = R or rules()
    fijas = {id(buscar(listas, n)) for n in R.get("no_reordenar", [])}
    out = []
    for k, l in sorted(listas.items(), key=lambda kv: norm(kv[0])):
        visto, unicas = set(), []
        for t in l.pistas:  # quita duplicados conservando la primera aparición
            if t not in visto:
                visto.add(t); unicas.append(t)
        nuevo = sorted(unicas, key=lambda t: F.clave(t, cat.get(t)))
        movidas = a_mover(unicas, nuevo) + (len(l.pistas) - len(unicas))
        out.append({"lista": l.nombre, "clave": k, "fija": id(l) in fijas or l.ajena or l.solo_lectura,
                    "solo_lectura": l.solo_lectura, "pistas": len(l.pistas),
                    "ordenada": movidas == 0, "movidas": movidas, "orden": nuevo,
                    # fecha de Spotify sin revisar: ordenar las colocaría quizá mal (ver Fechas → Nuevas)
                    "sin_verificar": [t for t in unicas if t not in F.pistas]})
    return out


def a_mover(actual, objetivo):
    """Mínimo de canciones que hay que mover = total - subsecuencia creciente más larga."""
    pos = {t: i for i, t in enumerate(objetivo)}
    colas = []
    for t in actual:
        i = bisect.bisect_left(colas, pos[t])
        colas[i:i + 1] = [pos[t]]
    return len(actual) - len(colas)


def txt(orden_ids):
    return "\n".join(f"https://open.spotify.com/track/{t}" for t in orden_ids) + "\n"
