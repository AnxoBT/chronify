"""Estadísticas de una lista (por defecto Mix) para la pestaña Estadísticas.

Todo se calcula en local con lo que ya hay: fechas reales (fechas.json), metadatos de Exportify/Spotify
(géneros, duración, popularidad, características de audio, fecha de añadido) y los datos de artistas de
MusicBrainz (core/artistas.py: país, persona/grupo, género, fecha de nacimiento).
"""
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, median

from core import artistas as A
from core.config import cache_json, norm
from core.exportify import buscar
from core.fechas import Fechas

TONOS = ["Do", "Do♯", "Re", "Re♯", "Mi", "Fa", "Fa♯", "Sol", "Sol♯", "La", "La♯", "Si"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
VACIAS = set("""a al and are as at be by con de del el en es for from i in is it la las le lo los me mi my no
nos of on or que se su te the this to tu un una y you your yo it's i'm don't""".split())


def _artistas(p):
    return [a for a in (p.artistas or "").split(";") if a]


def _pista(t, p, anio, **extra):
    return {"id": t, "t": p.etiqueta(), "anio": anio, **extra}


def _media(xs):
    xs = list(xs)
    return mean(xs) if xs else 0


def _decada(a):
    return f"{a // 10 * 10}s"


def calcular(listas, cat, F=None, R=None, lista=None):
    F = F or Fechas()
    R = R or {}
    # por defecto Mix; si no hay (otro usuario sin configurar), la lista propia más grande
    mayor = max((x for x in listas.values() if not x.ajena and not x.solo_lectura), key=lambda x: len(set(x.pistas)), default=None)
    nombre = lista or R.get("mix") or (mayor.nombre if mayor else "")
    l = buscar(listas, nombre)
    if not l:
        return {"error": f"No encuentro la lista {nombre}"}
    ids = [t for t in dict.fromkeys(l.pistas) if t in cat]
    P = {t: cat[t] for t in ids}
    anio = {t: F.anio(t, P[t]) for t in ids}
    con_anio = [t for t in ids if anio[t]]
    cache_mb, manual = cache_json(A.CACHE), A.manuales()
    info = {}
    for p in P.values():
        for a in _artistas(p):
            if a not in info:
                info[a] = A.info(a, cache_mb, manual)

    def principal(p):
        """Artista que manda para país/tipo: el primero con datos."""
        arts = _artistas(p)
        return next((a for a in arts if info.get(a, {}).get("pais")), arts[0] if arts else "")

    # selector: primero las canciones que te gustan (Liked_Songs), luego de más a menos canciones
    elegibles = [x for x in listas.values() if not x.ajena]
    out = {"lista": l.nombre,
           "listas": [{"nombre": x.nombre, "n": len(set(x.pistas)), "favoritas": x.solo_lectura}
                      for x in sorted(elegibles, key=lambda x: (not x.solo_lectura, -len(set(x.pistas)), norm(x.nombre)))],
           "artistas_mb": {"total": len(info), "con_datos": sum(1 for a in info if A.clave(a) in cache_mb)}}

    # ── resumen ──
    dur = [p.duracion for p in P.values() if p.duracion]
    pop = [p.popularidad for p in P.values() if p.popularidad is not None]
    anios = [anio[t] for t in con_anio]
    out["resumen"] = {
        "canciones": len(ids), "artistas": len(info), "horas": round(sum(dur) / 3_600_000, 1),
        "anio_min": min(anios, default=None), "anio_max": max(anios, default=None),
        "anio_medio": round(mean(anios)) if anios else None, "anio_mediana": round(median(anios)) if anios else None,
        "popularidad": round(mean(pop)) if pop else None,
        "explicitas": round(100 * sum(1 for p in P.values() if p.explicita) / max(1, len(P)), 1),
        "duracion_media": round(mean(dur) / 1000) if dur else None,
    }

    # ── línea temporal ──
    por_anio = defaultdict(list)
    for t in con_anio:
        por_anio[anio[t]].append(t)
    out["por_anio"] = [{"anio": a, "n": len(por_anio.get(a, [])),
                        "ejemplos": [P[t].etiqueta() for t in sorted(por_anio.get(a, []),
                                     key=lambda t: -(P[t].popularidad or 0))[:3]]}
                       for a in range(min(anios), max(anios) + 1)] if anios else []
    dec = Counter(_decada(anio[t]) for t in con_anio)
    out["por_decada"] = [{"decada": d, "n": n} for d, n in sorted(dec.items())]
    decadas = [d for d, _ in sorted(dec.items())]

    # ── idiomas por década (listas de idioma) ──
    series = []
    for n in R.get("idiomas", []):
        li = buscar(listas, n)
        if li:
            s = set(li.pistas)
            c = Counter(_decada(anio[t]) for t in con_anio if t in s)
            series.append({"nombre": li.nombre, "n": len(s & set(ids)), "valores": [c.get(d, 0) for d in decadas]})
    out["idiomas"] = {"decadas": decadas, "series": series}

    # ── géneros ──
    filas = []
    for g in R.get("generos", []):
        lg = buscar(listas, g)
        if lg:
            s = set(lg.pistas)
            c = Counter(_decada(anio[t]) for t in con_anio if t in s)
            filas.append({"nombre": lg.nombre, "n": len(s & set(ids)), "valores": [c.get(d, 0) for d in decadas]})
    out["generos_listas"] = {"decadas": decadas, "filas": sorted(filas, key=lambda f: -f["n"])}
    gs = Counter(g for p in P.values() for g in set(p.generos))
    out["generos_spotify"] = [{"nombre": g, "n": n} for g, n in gs.most_common(25)]
    out["generos_spotify_total"] = len(gs)

    # ── artistas ──
    canciones_de = defaultdict(list)
    for t, p in P.items():
        for a in _artistas(p):
            canciones_de[a].append(t)
    top = sorted(canciones_de.items(), key=lambda kv: (-len(kv[1]), kv[0].casefold()))[:25]
    out["top_artistas"] = [{"nombre": a, "n": len(ts), "pais": info[a].get("pais"),
                            "desde": min((anio[t] for t in ts if anio[t]), default=None),
                            "hasta": max((anio[t] for t in ts if anio[t]), default=None),
                            "canciones": [P[t].titulo for t in sorted(ts, key=lambda t: F.clave(t, P[t]))][:12]}
                           for a, ts in top]
    solo_una = sum(1 for ts in canciones_de.values() if len(ts) == 1)

    # ── países ──
    paises = defaultdict(lambda: {"n": 0, "artistas": Counter()})
    sin_pais = Counter()
    for t, p in P.items():
        a = principal(p)
        pais = info.get(a, {}).get("pais")
        if pais:
            paises[pais]["n"] += 1
            paises[pais]["artistas"][a] += 1
        else:
            sin_pais[a] += 1
    out["paises"] = {c: {"n": v["n"], "artistas": len(v["artistas"]),
                         "top": [{"nombre": a, "n": n} for a, n in v["artistas"].most_common(5)]}
                     for c, v in paises.items()}
    out["sin_pais"] = [{"nombre": a, "n": n, "buscado": A.clave(a) in cache_mb} for a, n in sin_pais.most_common()]

    # ── personas / grupos, género, edad al publicar ──
    tipos, generos_p = Counter(), Counter()
    gen_dec = defaultdict(Counter)
    edades = []
    for t, p in P.items():
        primero = (_artistas(p) or [""])[0]  # quien firma la canción (en colaboraciones, el primero)
        i = info.get(primero, {})
        tipo = {"Person": "Solista", "Group": "Grupo", "Orchestra": "Orquesta", "Choir": "Coro",
                "Character": "Personaje"}.get(i.get("tipo"), "Sin dato")
        tipos[tipo] += 1
        if i.get("tipo") == "Person":
            g = {"male": "Hombre", "female": "Mujer"}.get(i.get("genero"), "Otro / sin dato")
            generos_p[g] += 1
            if anio[t]:
                gen_dec[_decada(anio[t])][g] += 1
            nac = (i.get("inicio") or "")[:4]
            if nac.isdigit() and anio[t] and 10 <= anio[t] - int(nac) <= 95:
                edades.append((anio[t] - int(nac), t, primero))
    out["tipos"] = [{"nombre": k, "n": n} for k, n in tipos.most_common()]
    out["genero_artista"] = [{"nombre": k, "n": n} for k, n in generos_p.most_common()]
    out["genero_por_decada"] = {"decadas": decadas, "series": [
        {"nombre": g, "valores": [gen_dec[d].get(g, 0) for d in decadas]} for g in ("Hombre", "Mujer", "Otro / sin dato")]}
    if edades:
        edades.sort()
        hist = Counter(e // 5 * 5 for e, _, _ in edades)
        out["edad"] = {"media": round(mean(e for e, _, _ in edades), 1), "n": len(edades),
                       "hist": [{"desde": k, "n": hist.get(k, 0)} for k in range(min(hist), max(hist) + 5, 5)],
                       "jovenes": [_pista(t, P[t], anio[t], edad=e, artista=a) for e, t, a in edades[:5]],
                       "mayores": [_pista(t, P[t], anio[t], edad=e, artista=a) for e, t, a in edades[::-1][:5]]}

    # ── sonido (características de audio de Exportify) ──
    con_audio = [t for t in ids if P[t].energia is not None and P[t].valencia is not None]
    if con_audio:
        def extremo(campo, alto=True, n=5):
            ts = sorted((t for t in ids if getattr(P[t], campo) is not None), key=lambda t: getattr(P[t], campo), reverse=alto)
            return [_pista(t, P[t], anio[t], v=round(getattr(P[t], campo), 2)) for t in ts[:n]]
        bpm = Counter(int(P[t].bpm // 10 * 10) for t in ids if P[t].bpm)
        out["audio"] = {
            "puntos": [[round(P[t].valencia, 3), round(P[t].energia, 3), P[t].etiqueta(), t] for t in con_audio],
            "medias": {k: round(_media(getattr(P[t], k) for t in con_audio if getattr(P[t], k) is not None), 2)
                       for k in ("valencia", "energia", "bailable", "acustica")},
            "bpm": [{"desde": k, "n": bpm.get(k, 0)} for k in range(min(bpm), max(bpm) + 10, 10)] if bpm else [],
            "bpm_medio": round(mean(P[t].bpm for t in ids if P[t].bpm)) if bpm else None,
            "extremos": {"Más alegre": extremo("valencia"), "Más triste": extremo("valencia", False),
                         "Más enérgica": extremo("energia"), "Más tranquila": extremo("energia", False),
                         "Más bailable": extremo("bailable"), "Más rápida (BPM)": extremo("bpm"),
                         "Más lenta (BPM)": extremo("bpm", False), "Más acústica": extremo("acustica")},
            "animo_por_decada": [{"decada": d, **{k: round(_media(getattr(P[t], k) for t in con_audio
                                                                         if anio[t] and _decada(anio[t]) == d and getattr(P[t], k) is not None), 2)
                                                  for k in ("valencia", "energia", "bailable")}}
                                 for d in decadas if any(anio[t] and _decada(anio[t]) == d for t in con_audio)],
        }
        tonos = Counter(f"{TONOS[P[t].tono]} {'mayor' if P[t].modo == 1 else 'menor'}" for t in ids
                        if P[t].tono is not None and 0 <= P[t].tono < 12 and P[t].modo is not None)
        out["tonalidades"] = [{"nombre": k, "n": n} for k, n in tonos.most_common(12)]
        out["modo"] = {"mayor": sum(1 for t in ids if P[t].modo == 1), "menor": sum(1 for t in ids if P[t].modo == 0)}

    # ── popularidad y duración ──
    con_pop = sorted((t for t in ids if P[t].popularidad is not None), key=lambda t: P[t].popularidad)
    out["popularidad"] = {
        "mainstream": [_pista(t, P[t], anio[t], v=P[t].popularidad) for t in con_pop[::-1][:8]],
        # ≤ 5 suele ser una copia duplicada de un éxito (ver aviso "copia poco escuchada"), no una joya
        "joyas": [_pista(t, P[t], anio[t], v=P[t].popularidad) for t in con_pop if P[t].popularidad > 5][:8],
        "hist": [{"desde": k, "n": sum(1 for t in con_pop if k <= P[t].popularidad < k + 10 or (k == 90 and P[t].popularidad == 100))}
                 for k in range(0, 100, 10)]}
    con_dur = sorted((t for t in ids if P[t].duracion), key=lambda t: P[t].duracion)
    out["duracion"] = {
        "largas": [_pista(t, P[t], anio[t], v=round(P[t].duracion / 1000)) for t in con_dur[::-1][:5]],
        "cortas": [_pista(t, P[t], anio[t], v=round(P[t].duracion / 1000)) for t in con_dur[:5]],
        "por_decada": [{"decada": d, "seg": round(mean(P[t].duracion for t in con_dur if anio[t] and _decada(anio[t]) == d) / 1000)}
                       for d in decadas if any(anio[t] and _decada(anio[t]) == d for t in con_dur)]}

    # ── cuándo añades música (fecha de añadido de las listas de idioma, que conservan el histórico) ──
    # las listas que conservan su historial (idiomas, Liked_Songs) usan su propia fecha de añadido;
    # el resto (reordenadas o rehechas) la de las listas de idioma
    anadida = {}
    propia = l.solo_lectura or norm(l.nombre) in {norm(n) for n in R.get("no_reordenar", [])}
    historicas = [x for x in (buscar(listas, n) for n in R.get("no_reordenar", [])) if x]
    for li in ([l] if propia or not historicas else historicas):
        if li:
            for t, f in li.anadidas.items():
                if f and t in P:
                    anadida[t] = min(anadida.get(t, f), f)
    if anadida:
        meses, calor, edad_add = Counter(), Counter(), []
        for t, a in anadida.items():
            try:
                d = datetime.fromisoformat(a.replace("Z", "+00:00")).astimezone()
            except ValueError:
                continue
            meses[d.strftime("%Y-%m")] += 1
            calor[(d.weekday(), d.hour)] += 1
            if anio[t]:
                edad_add.append(d.year - anio[t])
        ms = sorted(meses) or [datetime.now().strftime("%Y-%m")]  # por si ninguna fecha se pudo leer
        todos, (y, m) = [], map(int, ms[0].split("-"))
        while f"{y:04d}-{m:02d}" <= ms[-1]:
            todos.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        acum, serie = 0, []
        for k in todos:
            acum += meses.get(k, 0)
            serie.append({"mes": k, "n": meses.get(k, 0), "total": acum})
        out["anadidas"] = {"meses": serie, "calor": [[calor.get((d, h), 0) for h in range(24)] for d in range(7)],
                           "edad_media": round(mean(edad_add), 1) if edad_add else None,
                           "nuevas_pct": round(100 * sum(1 for e in edad_add if e <= 1) / len(edad_add)) if edad_add else None}

    # ── curiosidades ──
    cur = []
    if con_anio:
        orden = sorted(con_anio, key=lambda t: F.clave(t, P[t]))
        cur.append({"t": "La más antigua", "v": P[orden[0]].etiqueta(), "d": F.info(orden[0], P[orden[0]])[0], "id": orden[0]})
        cur.append({"t": "La más reciente", "v": P[orden[-1]].etiqueta(), "d": F.info(orden[-1], P[orden[-1]])[0], "id": orden[-1]})
        a_top = max(por_anio.items(), key=lambda kv: len(kv[1]))
        cur.append({"t": "Tu año favorito", "v": str(a_top[0]), "d": f"{len(a_top[1])} canciones"})
    carreras = [(max(anio[t] for t in ts if anio[t]) - min(anio[t] for t in ts if anio[t]), a)
                for a, ts in canciones_de.items() if sum(1 for t in ts if anio[t]) >= 2]
    if carreras:
        span, a = max(carreras)
        ts = [anio[t] for t in canciones_de[a] if anio[t]]
        cur.append({"t": "Artista con más años de carrera en tus listas", "v": a, "d": f"{min(ts)}–{max(ts)} ({span} años)"})
    titulos = [(len(re.sub(r"\s*[-(\[].*", "", P[t].titulo)), t) for t in ids]
    if titulos:
        lt = max(titulos)[1]
        ct = min((x for x in titulos if x[0] > 0), default=titulos[0])[1]
        cur.append({"t": "Título más largo", "v": P[lt].etiqueta(), "id": lt})
        cur.append({"t": "Título más corto", "v": P[ct].etiqueta(), "id": ct})
    palabras = Counter(w for p in P.values() for w in set(re.findall(r"[a-záéíóúñü']+", re.sub(r"\s*[-(\[].*", "", p.titulo).casefold()))
                       if w not in VACIAS and len(w) > 2)
    if palabras:
        cur.append({"t": "Palabras que más se repiten en los títulos",
                    "v": ", ".join(f"{w} ({n})" for w, n in palabras.most_common(6))})
    colab = [t for t in ids if len(_artistas(P[t])) > 1]
    cur.append({"t": "Colaboraciones", "v": f"{round(100 * len(colab) / max(1, len(ids)))} %",
                "d": f"{len(colab)} canciones con más de un artista"})
    colabora = Counter(a for t in colab for a in _artistas(P[t]))
    if colabora:
        a, n = colabora.most_common(1)[0]
        cur.append({"t": "Quien más colabora", "v": a, "d": f"{n} colaboraciones"})
    cur.append({"t": "Artistas con una sola canción", "v": f"{round(100 * solo_una / max(1, len(canciones_de)))} %",
                "d": f"{solo_una} de {len(canciones_de)}"})
    dias = Counter(datetime.strptime(F.info(t, P[t])[0], "%Y-%m-%d").weekday() for t in ids
                   if re.match(r"^\d{4}-\d{2}-\d{2}$", F.info(t, P[t])[0] or "") and F.info(t, P[t])[0][5:7] != "00")
    if dias:
        d, n = dias.most_common(1)[0]
        cur.append({"t": "Día de la semana en que más salieron", "v": DIAS[d],
                    "d": f"{round(100 * n / sum(dias.values()))} % de las que tienen fecha exacta"})
    mes = Counter(int(F.info(t, P[t])[0][5:7]) for t in ids if re.match(r"^\d{4}-(0[1-9]|1[0-2])", F.info(t, P[t])[0] or ""))
    if mes:
        m, n = mes.most_common(1)[0]
        cur.append({"t": "Mes con más lanzamientos", "v": MESES[m - 1], "d": f"{n} canciones"})
    sellos = Counter(p.sello for p in P.values() if p.sello)
    if sellos:
        cur.append({"t": "Discográficas que más aparecen", "v": ", ".join(f"{s} ({n})" for s, n in sellos.most_common(4))})
    if dec:
        d, n = dec.most_common(1)[0]
        cur.append({"t": "Tu década favorita", "v": f"los {d[2:] if d < '2000s' else d}", "d": f"{n} canciones ({round(100 * n / len(con_anio))} %)"})
    propias_l = [x for x in listas.values() if not x.solo_lectura and not x.ajena]
    en_listas = Counter(t for x in propias_l for t in set(x.pistas) if t in P)
    if en_listas:
        t, n = max(en_listas.items(), key=lambda kv: (kv[1], P[kv[0]].popularidad or 0))
        cur.append({"t": "La que está en más listas tuyas", "v": P[t].etiqueta(), "id": t,
                    "d": ", ".join(x.nombre for x in propias_l if t in x.pistas)})
    if ids:
        t = max(ids, key=lambda t: (len(_artistas(P[t])), P[t].popularidad or 0))
        cur.append({"t": "La canción con más artistas", "v": P[t].titulo, "id": t,
                    "d": f"{len(_artistas(P[t]))} artistas: {', '.join(_artistas(P[t]))}"})
    decadas_de = {a: {_decada(anio[t]) for t in ts if anio[t]} for a, ts in canciones_de.items()}
    if decadas_de:
        a = max(decadas_de, key=lambda a: (len(decadas_de[a]), len(canciones_de[a])))
        cur.append({"t": "Artista presente en más décadas", "v": a, "d": ", ".join(sorted(decadas_de[a]))})
    cur.append({"t": "Canciones explícitas", "v": f"{out['resumen']['explicitas']} %",
                "d": f"{sum(1 for p in P.values() if p.explicita)} con la etiqueta E"})
    if anadida:
        primera, ultima = min(anadida, key=anadida.get), max(anadida, key=anadida.get)
        cur.append({"t": "La primera que guardaste", "v": P[primera].etiqueta(), "id": primera, "d": anadida[primera][:10]})
        cur.append({"t": "La última que has añadido", "v": P[ultima].etiqueta(), "id": ultima, "d": anadida[ultima][:10]})
    if anios:
        vacios = [a for a in range(min(anios), max(anios) + 1) if a not in por_anio]
        cur.append({"t": "Años sin ninguna canción", "v": str(len(vacios)) if vacios else "ninguno",
                    "d": ", ".join(map(str, vacios[:12])) + (" …" if len(vacios) > 12 else "") if vacios else "todos los años tienen alguna"})
    out["curiosidades"] = cur

    # ── lo más de nicho: oyentes de cada artista en ListenBrainz (la popularidad de Spotify es por copia de
    # la canción: una reedición poco escuchada de un éxito sale con 5/100, no sirve para esto) ──
    oy = A.oyentes()
    con_oy = {a: oy[info[a]["mbid"]] for a in canciones_de if info.get(a, {}).get("mbid") in oy and oy[info[a]["mbid"]] > 0}
    gen_n = Counter(g for p in P.values() for g in set(p.generos))
    gen_ej = {}
    for p in P.values():
        for g in p.generos:
            gen_ej.setdefault(g, p.etiqueta())
    if con_oy:
        orden_oy = sorted(con_oy, key=lambda a: (con_oy[a], a.casefold()))
        out["nicho"] = {
            "artistas": [{"nombre": a, "oyentes": con_oy[a], "n": len(canciones_de[a]), "ej": P[canciones_de[a][0]].titulo}
                         for a in orden_oy[:10]],
            "famosos": [{"nombre": a, "oyentes": con_oy[a], "n": len(canciones_de[a])} for a in orden_oy[::-1][:5]],
            "mediana": round(median(con_oy.values())), "con_dato": len(con_oy), "total": len(canciones_de),
            "pct_nicho": round(100 * sum(1 for v in con_oy.values() if v < 1000) / len(con_oy)),
            "generos": [{"nombre": g, "n": n, "ej": gen_ej[g]} for g, n in sorted(gen_n.items(), key=lambda kv: (kv[1], kv[0]))[:10]],
        }

    out["anios"] = tu_anio(P, anio, anadida, canciones_de, info, principal, listas, R, F)
    return out


def tu_anio(P, anio, anadida, canciones_de, info, principal, listas, R, F):
    """Resumen de cada año según lo que añadiste ese año (tipo Wrapped, pero de tu colección)."""
    cuando = {}
    for t, a in anadida.items():
        try:
            cuando[t] = datetime.fromisoformat(a.replace("Z", "+00:00")).astimezone()
        except ValueError:
            pass
    if not cuando:
        return {}
    primera_vez = {}  # año en que añadiste por primera vez algo de cada artista / país
    for t in sorted(cuando, key=cuando.get):
        for a in _artistas(P[t]):
            primera_vez.setdefault(("a", a), cuando[t].year)
        pais = info.get(principal(P[t]), {}).get("pais")
        if pais:
            primera_vez.setdefault(("p", pais), cuando[t].year)
    generos = [buscar(listas, g) for g in R.get("generos", [])]
    out = {}
    for y in sorted({d.year for d in cuando.values()}):
        ts = sorted((t for t, d in cuando.items() if d.year == y), key=cuando.get)
        arts = Counter(a for t in ts for a in _artistas(P[t]))
        meses = Counter(cuando[t].month for t in ts)
        dec = Counter(_decada(anio[t]) for t in ts if anio[t])
        gen = Counter(g.nombre for t in ts for g in generos if g and t in g.pistas)
        con_anio = sorted((t for t in ts if anio[t]), key=lambda t: F.clave(t, P[t]))
        mes, n_mes = meses.most_common(1)[0]
        out[y] = {
            "n": len(ts), "minutos": round(sum(P[t].duracion or 0 for t in ts) / 60000),
            "artistas": [{"nombre": a, "n": n} for a, n in arts.most_common(8)],
            "nuevos_artistas": sorted({k[1] for k, v in primera_vez.items() if k[0] == "a" and v == y}, key=lambda a: -arts[a])[:8],
            "n_nuevos_artistas": sum(1 for k, v in primera_vez.items() if k[0] == "a" and v == y),
            "nuevos_paises": sorted(k[1] for k, v in primera_vez.items() if k[0] == "p" and v == y),
            "generos": [{"nombre": g, "n": n} for g, n in gen.most_common(4)],
            "decadas": [{"decada": d, "n": n} for d, n in sorted(dec.items())],
            "mes": {"nombre": MESES[mes - 1], "n": n_mes},
            "por_mes": [meses.get(m, 0) for m in range(1, 13)],
            "primera": {"id": ts[0], "t": P[ts[0]].etiqueta(), "d": cuando[ts[0]].strftime("%d/%m")},
            "ultima": {"id": ts[-1], "t": P[ts[-1]].etiqueta(), "d": cuando[ts[-1]].strftime("%d/%m")},
            "antigua": con_anio and {"id": con_anio[0], "t": P[con_anio[0]].etiqueta(), "anio": anio[con_anio[0]]},
            "reciente": con_anio and {"id": con_anio[-1], "t": P[con_anio[-1]].etiqueta(), "anio": anio[con_anio[-1]]},
            "del_anio": sum(1 for t in ts if anio[t] and anio[t] >= y - 1),  # salidas ese año o el anterior
        }
    return out


def guardar_foto(s, carpeta):
    """Una foto al mes de las cifras de la colección (para ver cómo cambia). No pisa la del mes si ya existe."""
    import json
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / f"{datetime.now():%Y-%m}.json"
    if s.get("error") or f.exists():
        return
    r = s["resumen"]
    foto = {"fecha": f"{datetime.now():%Y-%m-%d}", "canciones": r["canciones"], "artistas": r["artistas"],
            "horas": r["horas"], "paises": len(s["paises"]), "anio_mediana": r["anio_mediana"],
            "popularidad": r["popularidad"], "por_decada": {d["decada"]: d["n"] for d in s["por_decada"]},
            "top_artistas": [a["nombre"] for a in s["top_artistas"][:10]]}
    f.write_text(json.dumps(foto, ensure_ascii=False), encoding="utf-8")


def evolucion(carpeta):
    import json
    if not carpeta.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(carpeta.glob("*.json"))]
