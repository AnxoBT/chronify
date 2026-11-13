"""Servidor web local (solo librería estándar). Solo escucha en 127.0.0.1."""
import dataclasses
import hmac
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core import analisis, config, exportify, historial
from core.version import VERSION
from core.fechas import Fechas, normalizar

WEB = Path(__file__).resolve().parent
LOCK = threading.Lock()
ES_WEB = bool(os.environ.get("CHRONIFY_WEB"))  # versión web (Pyodide en el navegador): web/navegador.py
ESTADO = {"listas": {}, "cat": {}, "cargado": None, "fuente": ""}
# Seguridad del servidor local: otras webs abiertas en el navegador pueden hacer peticiones a 127.0.0.1.
# - Host tiene que ser 127.0.0.1/localhost (frena el "DNS rebinding": una web que se hace pasar por 127.0.0.1).
# - Los POST llevan la cabecera X-Chronify: otra web no puede ponerla sin preflight (que este servidor no acepta).
# - Android: otras apps del móvil también llegan a 127.0.0.1 → clave secreta por arranque (CHRONIFY_SECRETO): la
#   pantalla de la app la recibe en ?k= y la guarda en una cookie; la sincronización por USB la lee con adb.
HOST_LOCAL = re.compile(r"^(127\.0\.0\.1|localhost)(:\d+)?$")
ORIGEN_LOCAL = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$")
SECRETO = os.environ.get("CHRONIFY_SECRETO", "")
SIN_CLAVE = {"/callback", "/api/ping"}  # /callback lo abre el navegador al volver de Spotify (protegido por "state")
PUERTO = [8766]
# apagado automático: la página hace ping cada pocos segundos; sin pings (ventana cerrada) se apaga.
# Margen amplio: con la ventana minimizada el navegador solo deja ejecutar temporizadores 1 vez/minuto.
VIDA = {"ultimo": None, "margen": 150}
SP = {"activo": False, "tarea": "", "log": [], "error": None, "resultado": None, "cancelar": False}
UPD = {"activo": False, "log": [], "error": None, "hecho": None}  # actualización en curso
LOGIN = {"error": None}  # último error al conectar con Spotify (se enseña en Ajustes)
SRV = [None]
MB = {"activo": False, "hechos": 0, "total": 0, "actual": "", "propuestas": [], "error": None, "cancelar": False}
SINC = {"activo": False, "error": None, "paso": ""}  # sincronización PC ↔ móvil por USB (core/sincro.py)
ART = {"activo": False, "hechos": 0, "total": 0, "actual": "", "error": None, "cancelar": False}  # países de artistas
PENDIENTE = "spotify_pendiente.json"  # listas que se quedaron a medias de ordenar (cupo, bloqueo, cancelar)


def pendiente():
    """Lo que queda a medias de ordenar, o None (el archivo con listas vacías = "ya no queda nada")."""
    p = config.cache_json(PENDIENTE)
    return p if p.get("listas") else None


def recargar():
    with LOCK:
        R = config.rules()
        ESTADO["listas"], ESTADO["cat"] = exportify.cargar(ignoradas(), R.get("mix", ""),
                                                          R.get("solo_lectura", []))
        ESTADO["cargado"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        ESTADO["fuente"] = "Exportify (CSV)"


def propias():
    """Ids de las canciones de tus listas (sin las que solo están en listas que sigues de otros)."""
    return {t for l in ESTADO["listas"].values() if not l.ajena and not l.solo_lectura for t in l.pistas}


def peticiones(o):
    """Peticiones a Spotify que costaría ordenar la lista (movimientos en bloque). None si no se puede calcular."""
    from core import spotify
    l = ESTADO["listas"].get(o["clave"])
    if not l or o["fija"] or o["ordenada"]:
        return None if not l or o["fija"] else 0
    if o.get("en_lista_nueva"):  # crear la lista + añadir de 100 en 100
        return 2 + len(o["orden"]) // 100
    try:
        return len(spotify.plan_movimientos(l.pistas, o["orden"]))
    except ValueError:  # duplicados: se calcula al aplicar
        return None


CLAVES_LISTAS = ("mix", "idiomas", "friki", "decadas", "generos", "no_reordenar", "ignorar", "liked_ordenar")
CREADAS = "listas_creadas.json"  # {lista: id de la lista nueva en Spotify} (p. ej. Liked ordenada por fecha)


def reglas_listas():
    """Para Ajustes → Tus listas: qué papel tiene cada lista y qué listas hay."""
    if not ESTADO["cargado"]:
        recargar()
    R = config.rules()
    vistas = {l.nombre: {"nombre": l.nombre, "n": len(set(l.pistas)), "solo_lectura": l.solo_lectura}
              for l in ESTADO["listas"].values() if not l.ajena}
    for n in R.get("ignorar") or []:  # las ignoradas no se cargan: se enseñan igual para poder quitarlas
        vistas.setdefault(n, {"nombre": n, "n": None, "solo_lectura": n in (R.get("solo_lectura") or [])})
    return {**{k: R.get(k) for k in CLAVES_LISTAS},
            "listas": sorted(vistas.values(), key=lambda x: (x["solo_lectura"], -(x["n"] or 0), config.norm(x["nombre"])))}


def guardar_listas(b):
    """Valida y guarda la configuración de listas (lo demás de rules.json, como excepciones, no se toca)."""
    def nombres(v):
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError("lista de nombres no válida")
        return list(dict.fromkeys(x.strip() for x in v))

    def anio(x):
        if x in (None, ""):
            return None
        x = int(x)
        if not 1800 <= x <= 2200:
            raise ValueError(f"año fuera de rango: {x}")
        return x
    nuevo = {"mix": str(b.get("mix") or "").strip(), "friki": str(b.get("friki") or "").strip(),
             "liked_ordenar": bool(b.get("liked_ordenar"))}
    for k in ("idiomas", "generos", "no_reordenar", "ignorar"):
        nuevo[k] = nombres(b.get(k) or [])
    dec = b.get("decadas") or {}
    if not isinstance(dec, dict):
        raise ValueError("épocas no válidas")
    nuevo["decadas"] = {}
    for n, rango in dec.items():
        a, z = (anio(rango[0]), anio(rango[1])) if isinstance(rango, list) and len(rango) == 2 else (None, None)
        if a is not None and z is not None and a > z:
            raise ValueError(f"{n}: el año 'desde' es mayor que 'hasta'")
        nuevo["decadas"][n.strip()] = [a, z]
    if nuevo["friki"] and nuevo["friki"] not in nuevo["idiomas"]:
        nuevo["friki"] = ""
    if nuevo["mix"] and nuevo["mix"] in nuevo["idiomas"]:
        raise ValueError("La lista general no puede formar parte de sí misma")
    R = config.rules()
    antes = {k: R.get(k) for k in CLAVES_LISTAS}
    for k in ("idiomas", "generos", "no_reordenar", "ignorar"):  # se conserva el orden que ya tenían
        viejo = list(antes.get(k) or [])
        nuevo[k].sort(key=lambda n: viejo.index(n) if n in viejo else len(viejo))
    viejo = list(antes.get("decadas") or {})
    nuevo["decadas"] = dict(sorted(nuevo["decadas"].items(), key=lambda kv: viejo.index(kv[0]) if kv[0] in viejo else len(viejo)))
    R.update(nuevo)
    config.guardar_reglas(R)
    historial.registrar("listas", "Tus listas: configuración cambiada")
    return {"recargar": sorted(antes.get("ignorar") or []) != sorted(nuevo["ignorar"])}


def resumen():
    from core import spotify
    L, C = ESTADO["listas"], ESTADO["cat"]
    F = Fechas()
    orden = analisis.ordenar(L, C, F)
    mias = propias()
    aprox = sum(1 for t in mias if F.info(t, C.get(t))[2])
    avisos = analisis.comprobar(L, C, F)
    copias = config.cache_json(COPIAS)
    for a in avisos:  # versión principal ya buscada de las copias poco escuchadas
        if a.get("categoria") == "copia":
            for p in a["pistas"]:
                if p["id"] in copias:
                    p["principal"] = copias[p["id"]].get("propuesta") or False
    return {"cargado": ESTADO["cargado"], "fuente": ESTADO["fuente"], "carpetas": [str(d) for d in config.export_dirs()],
            "listas": exportify.describir(L), "avisos": avisos,
            "orden": [{**{k: v for k, v in o.items() if k not in ("orden", "sin_verificar")},
                       "sin_verificar": len(o["sin_verificar"]), "peticiones": peticiones(o)} for o in orden],
            "fechas": {"total": len(mias), "aprox": aprox}, "cupo": spotify.cupo(),
            "pendiente": pendiente(),
            "android": bool(os.environ.get("CHRONIFY_ANDROID")), "web": ES_WEB,
            "bloqueado": (lambda h: time.strftime("%d/%m %H:%M", time.localtime(h)) if h else None)(spotify.bloqueado_hasta())}


def _tarea(nombre, fn):
    """Ejecuta una tarea de Spotify en segundo plano (una a la vez)."""
    try:
        SP["resultado"] = fn(SP["log"].append)
    except Exception as e:
        SP["error"] = str(e)
    finally:
        SP["activo"] = False


def _probar(log):
    from tools.probar_spotify import probar
    return probar(log)


def _leer(log):
    from core import spotify
    R = config.rules()
    listas, cat = spotify.cargar(ignoradas(), R.get("solo_lectura", []), progreso=log)
    try:  # la API ya no da géneros ni características de audio: se toman del último zip de Exportify si lo hay
        _, cat_csv = exportify.cargar(R.get("ignorar", []), R.get("mix", ""), R.get("solo_lectura", []))
        campos = ("generos", "sello", "bpm", "energia", "bailable", "tono", "modo", "valencia", "acustica", "habla",
                  "volumen", "popularidad")
        for t, p in cat.items():
            q = cat_csv.get(t)
            if q:
                for c in campos:
                    if getattr(p, c) in (None, [], "") and getattr(q, c) not in (None, [], ""):
                        setattr(p, c, getattr(q, c))
    except Exception as e:
        log(f"(sin datos extra de Exportify: {e})")
    with LOCK:
        ESTADO.update(listas=listas, cat=cat, fuente="Spotify (API)",
                      cargado=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    log(f"Leídas {len(listas)} listas, {len(cat)} canciones")


def _cambiar_lista(tid, desde, hacia):
    """Añade una canción a una lista de época o género en su sitio cronológico y, si se indica 'desde'
    (otra lista de época), la quita de ahí."""
    def fn(log):
        from core import spotify
        R = config.rules()
        if hacia not in (R.get("decadas") or {}) and hacia not in (R.get("generos") or []):
            raise ValueError("Solo se añaden canciones a listas de época o de género")
        if desde and (desde not in (R.get("decadas") or {}) or hacia not in (R.get("decadas") or {}) or desde == hacia):
            raise ValueError("Solo se mueven canciones entre listas de época")
        L, C = ESTADO["listas"], ESTADO["cat"]
        a, b = L.get(desde) if desde else None, L.get(hacia)
        if not b or not b.spotify_id or (desde and (not a or not a.spotify_id)):
            raise ValueError("Primero pulsa 'Spotify (API)' para leer las listas")
        if desde and tid not in a.pistas:
            raise ValueError(f"La canción ya no está en {desde}: vuelve a leer las listas")
        if spotify.cupo()["libres"] < (2 if desde else 1):  # que no quede añadida a una y sin quitar de la otra
            raise ValueError(spotify._msg_cupo(spotify.cupo()))
        p = C.get(tid)
        etiqueta = p.etiqueta() if p else tid
        log(f"{etiqueta}: {desde + ' → ' if desde else 'añadir a '}{hacia}")
        if tid not in b.pistas:
            F = Fechas()
            objetivo = sorted(set(b.pistas) | {tid}, key=lambda x: F.clave(x, C.get(x)))
            pos = spotify.posicion_cronologica(b.pistas, objetivo, tid)
            spotify.anadir(b.spotify_id, tid, pos)
            b.pistas.insert(pos, tid)
            log(f"Añadida a {hacia} en la posición {pos + 1}")
        if desde:
            spotify.quitar(a.spotify_id, tid)
            a.pistas = [x for x in a.pistas if x != tid]
            log(f"Quitada de {desde}")
        historial.registrar("spotify", f"{etiqueta}: {'de ' + desde + ' a ' if desde else 'añadida a '}{hacia}", id=tid)
        return {"id": tid, "desde": desde, "hacia": hacia}
    return fn


def creadas():
    """{lista: {"id", "nombre"}} de las listas que ha creado Chronify (p. ej. Liked por fecha)."""
    return {k: (v if isinstance(v, dict) else {"id": v, "nombre": ""}) for k, v in config.cache_json(CREADAS).items()}


def ignoradas():
    """Listas que no se leen: las de Ajustes y las que crea Chronify (son copias: contarían dos veces las canciones)."""
    R = config.rules()
    return [*(R.get("ignorar") or []), *(c["nombre"] for c in creadas().values() if c.get("nombre"))]


def _crear_ordenada(clave, idioma="es"):
    """Copia ordenada por fecha real de una lista que Spotify no deja reordenar (Liked) en una lista nueva tuya.
    La próxima vez se actualiza la misma lista (si no la has borrado)."""
    def fn(log):
        from core import spotify
        o = next((o for o in analisis.ordenar(ESTADO["listas"], ESTADO["cat"]) if o["clave"] == clave), None)
        if not o or not o["en_lista_nueva"]:
            raise ValueError("Esa lista no se ordena en una lista nueva (Ajustes → Tus listas)")
        falta = 2 + len(o["orden"]) // 100
        if spotify.cupo()["libres"] < falta:
            raise ValueError(spotify._msg_cupo(spotify.cupo()))
        en = idioma == "en"
        base = ("Liked Songs" if en else "Canciones que te gustan") if o["lista"] == "Liked_Songs" else o["lista"]
        nombre = base + (" · by date" if en else " · por fecha")
        previas = creadas()
        log(f"{nombre}: {len(o['orden'])} canciones…")
        pid = spotify.crear_o_rellenar(nombre, o["orden"], (previas.get(clave) or {}).get("id"),
                                       "Sorted by the real release date of every song (Chronify)" if en
                                       else "Ordenada por la fecha real de cada canción (Chronify)")
        nueva = (previas.get(clave) or {}).get("id") != pid
        config.save_cache(CREADAS, {**previas, clave: {"id": pid, "nombre": nombre}})
        log(f"{nombre}: {'creada' if nueva else 'actualizada'} en Spotify")
        historial.registrar("spotify", f"{nombre}: {'creada' if nueva else 'actualizada'} ({len(o['orden'])} canciones)")
        return {"id": pid, "nombre": nombre}
    return fn


def _ordenar(nombres, forzar=False):
    """Ordena en Spotify una o varias listas seguidas hasta acabar o hasta el cupo diario.

    Lo que quede a medias se apunta en cache/spotify_pendiente.json para seguir otro día con un botón.
    'forzar': ordena aunque haya canciones con la fecha de Spotify sin verificar.
    """
    def progreso(nombre, i, t):  # una línea de progreso por lista, que se actualiza (en la misma lista de log)
        linea, L = f"  {nombre} {i}/{t}", SP["log"]
        if L and L[-1].startswith(f"  {nombre} "):
            L[-1] = linea
        else:
            L.append(linea)

    def fn(log):
        from core import spotify
        if not (config.cache_json("prueba_spotify.json") or {}).get("conserva_added_at"):
            raise ValueError("Antes haz 'Probar en lista desechable' (Ajustes) y que confirme que se conserva la fecha de añadido")
        if ESTADO["fuente"] != "Spotify (API)":
            log("Leyendo las listas de Spotify…")
            _leer(lambda m: None)
        ordenes = {o["clave"]: o for o in analisis.ordenar(ESTADO["listas"], ESTADO["cat"])}
        quedan, saltadas, hechas = [], [], []
        try:
            for i, nombre in enumerate(nombres):
                o, l = ordenes.get(nombre), ESTADO["listas"].get(nombre)
                if not o or not l:
                    log(f"{nombre}: no la encuentro, la salto")
                    continue
                if o["fija"] or not l.spotify_id:  # Liked: no se puede mover; se ordena en una lista nueva
                    saltadas.append(nombre)
                    log(f"{nombre}: no se reordena aquí, la salto")
                    continue
                if o["ordenada"]:
                    log(f"{nombre}: ya está ordenada")
                    continue
                if o["sin_verificar"] and not forzar:
                    saltadas.append(nombre)
                    log(f"{nombre}: la salto, tiene {len(o['sin_verificar'])} {'canción' if len(o['sin_verificar']) == 1 else 'canciones'} con la fecha de Spotify sin verificar "
                        "(revísalas en Fechas → Nuevas o pulsa 'ordenar igualmente')")
                    continue
                if SP["cancelar"]:
                    quedan += nombres[i:]
                    break
                c = spotify.cupo()
                if not c["libres"]:
                    quedan += nombres[i:]
                    log(spotify._msg_cupo(c))
                    break
                log(f"{nombre}: ordenando ({o['movidas']} canciones fuera de sitio, quedan {c['libres']} cambios hoy)")
                try:
                    n, total = spotify.aplicar_orden(l.spotify_id, o["orden"], cancelar=lambda: SP["cancelar"],
                                                     progreso=lambda i, t, nombre=nombre: progreso(nombre, i, t))
                except ValueError as e:  # canciones repetidas o la lista cambió en Spotify: esa se salta, el resto sigue
                    saltadas.append(nombre)
                    log(f"{nombre}: la salto ({e})")
                    continue
                if n < total:
                    l.pistas = [x["id"] for x in spotify.items(l.spotify_id)]
                    quedan += nombres[i:]
                    motivo = "cancelado" if SP["cancelar"] else spotify._msg_cupo(spotify.cupo())
                    log(f"{nombre}: {n} de {total} movimientos hechos. {motivo}")
                    historial.registrar("spotify", f"{nombre}: ordenada a medias ({n}/{total} movimientos)")
                    break
                l.pistas = list(o["orden"])
                hechas.append(nombre)
                log(f"{nombre}: ordenada ({n} movimientos)")
                historial.registrar("spotify", f"{nombre}: ordenada en Spotify ({n} movimientos)")
        except Exception:  # bloqueo, red, error de Spotify…: lo que no se ha hecho queda apuntado para "Seguir"
            quedan += [n for n in nombres if n not in hechas and n not in quedan and n not in saltadas]
            for n in quedan:  # la lista pudo quedar a medias: que la web enseñe su orden real
                l = ESTADO["listas"].get(n)
                if l and l.spotify_id:
                    try:
                        l.pistas = [x["id"] for x in spotify.items(l.spotify_id)]
                    except Exception:
                        break
            raise
        finally:
            # "m": cuándo se apuntó; al sincronizar gana lo más reciente (también "ya no queda nada": listas vacías)
            config.save_cache(PENDIENTE, {"listas": list(dict.fromkeys(quedan)), "forzar": forzar, "m": time.time(),
                                          "t": datetime.now().strftime("%d/%m %H:%M")})
        return {"hechas": hechas, "quedan": quedan, "saltadas": saltadas}
    return fn


COPIAS = "copias.json"  # {id copia: {"propuesta": {...} | None, "hecho": bool}}


def _buscar_copias(ids):
    """Busca en Spotify la copia principal de cada canción (solo lecturas, no gasta cupo de escrituras)."""
    def fn(log):
        from core import spotify
        C, hechas = ESTADO["cat"], config.cache_json(COPIAS)
        encontradas = 0
        for i, t in enumerate(ids, 1):
            p = C.get(t)
            if not p or t in hechas:  # ya buscada antes
                continue
            SP["log"][:] = [f"Buscando la versión principal {i}/{len(ids)}: {p.etiqueta()}"]
            prop = spotify.buscar_principal(p)
            hechas[t] = {"propuesta": prop, "hecho": False}
            encontradas += bool(prop)
            config.save_cache(COPIAS, hechas)
        log(f"Encontrada la versión principal de {encontradas} de {len(ids)} canciones")
        return {"encontradas": encontradas}
    return fn


def _cambiar_copias(ids):
    """Sustituye cada copia por su versión principal en todas tus listas donde esté (en su misma posición).
    La fecha verificada y las excepciones pasan a la nueva. Se para al llegar al cupo diario."""
    def fn(log):
        from core import spotify
        copias, F, R = config.cache_json(COPIAS), Fechas(), config.rules()
        L, C = ESTADO["listas"], ESTADO["cat"]
        hechas = 0
        for t in ids:
            prop = (copias.get(t) or {}).get("propuesta")
            if not prop or copias[t].get("hecho"):
                continue
            nuevo = prop["id"]
            donde = [l for l in L.values() if t in l.pistas and not l.solo_lectura and not l.ajena]
            if any(not l.spotify_id for l in donde):
                raise ValueError("Primero pulsa 'Spotify (API)' para leer las listas")
            necesarias = sum(1 if nuevo in l.pistas else 2 for l in donde)
            if spotify.cupo()["libres"] < necesarias:
                log(spotify._msg_cupo(spotify.cupo()) + f" Quedan {sum(1 for x in ids if not (copias.get(x) or {}).get('hecho'))} por cambiar.")
                break
            p = C.get(t)
            for l in donde:
                if nuevo in l.pistas:  # ya estaba la buena: solo sobra la copia
                    spotify.quitar(l.spotify_id, t)
                    l.pistas = [x for x in l.pistas if x != t]
                else:
                    l.pistas = spotify.reemplazar(l.spotify_id, t, nuevo, l.pistas)
            if p:  # la canción nueva hereda los datos de la copia
                C[nuevo] = dataclasses.replace(p, id=nuevo, album=prop["album"], fecha_spotify=prop["fecha"] or p.fecha_spotify,
                                               popularidad=prop["popularidad"], album_tipo=prop["album_tipo"])
            if t in F.pistas:
                F.pistas[nuevo] = dict(F.pistas[t])
                config.guardar_fechas(F.data)
            exc = R.get("excepciones", {})
            if any(t in v for v in exc.values() if isinstance(v, list)):
                for v in exc.values():
                    if isinstance(v, list) and t in v and nuevo not in v:
                        v.append(nuevo)
                config.guardar_reglas(R)
            copias[t]["hecho"] = True
            config.save_cache(COPIAS, copias)
            hechas += 1
            historial.registrar("spotify", f"{p.etiqueta() if p else t}: cambiada por la versión principal "
                                f"({prop['album']}) en {', '.join(l.nombre for l in donde)}", id=t)
            log(f"{p.etiqueta() if p else t} → {prop['album']} ({len(donde)} listas)")
        log(f"Cambiadas {hechas} canciones")
        return {"cambiadas": hechas}
    return fn


def _sincronizar():
    """PC: sincroniza con el móvil conectado por USB (adb). En segundo plano."""
    from core import sincro
    try:
        sincro.sincronizar_movil(log=lambda m: SINC.update(paso=m))
        SINC["error"] = None
    except Exception as e:
        SINC["error"] = str(e)
    finally:
        SINC["activo"] = False


def _actualizar():
    from core import actualizar
    try:
        UPD["hecho"] = actualizar.aplicar(UPD["log"].append)
        if actualizar.ANDROID:  # la página abre el instalador de Android (/android/instalar)
            UPD["log"].append(f"Descargada v{UPD['hecho']}: abriendo el instalador…")
        else:
            UPD["log"].append(f"Instalada v{UPD['hecho']}. Reiniciando Chronify…")
            threading.Timer(1.5, reiniciar).start()  # deja tiempo a que la página lo lea
    except Exception as e:
        UPD["error"] = str(e)
    finally:
        UPD["activo"] = False


def reiniciar():
    """Arranca una instancia nueva (con el código nuevo) y apaga esta. La ventana abierta se recarga sola."""
    exe = sys.executable
    subprocess.Popen([exe, str(config.ROOT / "app.py"), "--reinicio", "--puerto", str(PUERTO[0])], cwd=config.ROOT,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     close_fds=True)
    if SRV[0]:
        SRV[0].shutdown()


def estado_spotify():
    from core import spotify
    cid = config.env("SPOTIFY_CLIENT_ID")
    return {"client_id": bool(cid), "client_id_corto": f"{cid[:4]}…{cid[-4:]}" if cid else "",
            "conectado": spotify.conectado(), "login_error": LOGIN["error"],
            "bloqueado": (lambda h: time.strftime("%d/%m %H:%M", time.localtime(h)) if h else None)(spotify.bloqueado_hasta()),
            "redirect": spotify.redirect_uri(PUERTO[0]), "prueba": config.cache_json("prueba_spotify.json") or None,
            "cupo": spotify.cupo(), "pendiente": pendiente(),
            "cuenta": config.cache_json(spotify.CUENTA_CACHE) or None,
            **{k: SP[k] for k in ("activo", "tarea", "log", "error")}}


def pendientes(filtro):
    C, F = ESTADO["cat"], Fechas()
    out = []
    for t in propias():
        p = C.get(t)
        if not p:
            continue
        fecha, fuente, aprox = F.info(t, p)
        if filtro == "todas" or (filtro == "aprox" and aprox) or (filtro == "nuevas" and t not in F.pistas):
            out.append({"id": t, "t": p.etiqueta(), "fecha": fecha, "fuente": fuente, "aprox": aprox,
                        "spotify": p.fecha_spotify, "album": p.album})
    return sorted(out, key=lambda x: F.clave(x["id"], C.get(x["id"])))


def _buscar_mb(ids):
    from core import musicbrainz
    C = ESTADO["cat"]
    try:
        F = Fechas()
        for t in ids:
            if MB["cancelar"]:
                break
            p = C.get(t)
            if not p:
                continue
            MB["actual"] = p.etiqueta()
            r = musicbrainz.buscar(p)
            actual = F.info(t, p)[0]
            cands = [f for f in (p.fecha_spotify, r and r["fecha"]) if f]
            propuesta = min(cands, key=normalizar) if cands else ""
            MB["propuestas"].append({"id": t, "t": p.etiqueta(), "actual": actual, "spotify": p.fecha_spotify,
                                     "mb": r and r["fecha"], "propuesta": propuesta,
                                     "cambia": normalizar(propuesta)[:4] != normalizar(actual)[:4]})
            MB["hechos"] += 1
    except Exception as e:  # sin conexión, MusicBrainz caído…
        MB["error"] = str(e)
    finally:
        MB["activo"] = False


def _titulos_artistas():
    """{artista: [títulos de sus canciones]} (los títulos sirven para distinguir artistas con el mismo nombre)."""
    out = {}
    for l in ESTADO["listas"].values():
        if l.ajena:
            continue
        for t in l.pistas:
            p = ESTADO["cat"].get(t)
            for a in (p.artistas.split(";") if p else []):
                if a and p.titulo not in out.setdefault(a, []):
                    out[a].append(p.titulo)
    return out


def _nombres_artistas():
    return sorted(_titulos_artistas())


def _buscar_artistas():
    """País, tipo y fecha de nacimiento de cada artista en MusicBrainz (los que no estén ya en caché)."""
    from core import artistas
    try:
        titulos, fallos = _titulos_artistas(), 0
        for n in artistas.pendientes(sorted(titulos))[:ART["total"]]:
            if ART["cancelar"]:
                break
            ART["actual"] = n
            try:
                artistas.buscar(n, titulos.get(n, []))
                fallos = 0
            except Exception as e:  # un artista que falla no para la tanda; muchos seguidos = MusicBrainz caído
                fallos += 1
                if fallos >= 5:
                    raise RuntimeError(f"MusicBrainz no responde ({e}); vuelve a intentarlo en un rato")
            ART["hechos"] += 1
        if not ART["cancelar"]:  # oyentes en ListenBrainz (para "lo más de nicho"), por lotes: unos segundos
            ART["actual"] = "oyentes en ListenBrainz"
            artistas.actualizar_oyentes([v.get("mbid") for v in config.cache_json(artistas.CACHE).values() if v])
    except Exception as e:
        ART["error"] = str(e)
    finally:
        ART["activo"] = False


def deshacer(uid):
    e = historial.buscar(uid)
    if not e or e.get("deshecha") or e["tipo"] not in ("fecha", "artista"):
        raise ValueError("Ese cambio no se puede deshacer")
    MSG_DESPUES = "Ese dato ha cambiado después: deshaz primero el cambio más reciente de esa canción o artista"
    if e["tipo"] == "fecha":
        F = Fechas()
        if F.pistas.get(e["id"]) != e.get("despues"):
            raise ValueError(MSG_DESPUES)
        if e.get("antes"):
            F.pistas[e["id"]] = e["antes"]
        else:
            F.pistas.pop(e["id"], None)
        config.guardar_fechas(F.data)
    else:
        from core import artistas
        m = artistas.manuales()
        if m.get(e["id"]) != e.get("despues"):
            raise ValueError(MSG_DESPUES)
        if e.get("antes"):
            m[e["id"]] = e["antes"]
        else:
            m.pop(e["id"], None)
        artistas.escribir(m)
    historial.registrar(e["tipo"], f"Deshecho: {e['texto']}", id=e.get("id"), deshace=uid)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if not isinstance(body, bytes):
            body = (json.dumps(body, ensure_ascii=False) if ctype.startswith("application/json") else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _importar(self):
        """Guarda en <datos>/data el zip de Exportify (o un CSV) que el usuario elige, y relee las listas.
        Hace falta en Android (la app no puede leer Descargas) y en el PC es cómodo."""
        from urllib.parse import unquote
        n = int(self.headers.get("Content-Length") or 0)
        nombre = Path(unquote(self.headers.get("X-Nombre") or "")).name
        if not n or n > 80_000_000 or Path(nombre).suffix.lower() not in (".zip", ".csv"):
            return self._send(400, {"error": "Elige el zip de Exportify (o un CSV)"})
        destino = config.DATOS / "data"
        destino.mkdir(parents=True, exist_ok=True)
        datos = self.rfile.read(n)
        tmp = destino / (nombre + ".tmp")
        tmp.write_bytes(datos)
        tmp.replace(destino / nombre)
        os.utime(destino / nombre)  # el más reciente manda
        recargar()
        return self._send(200, {"ok": True, "nombre": nombre, "listas": len(ESTADO["listas"])})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _permitido(self, u):
        if ES_WEB:  # en el navegador no hay servidor al que llegar desde fuera
            return True
        if not HOST_LOCAL.match(self.headers.get("Host", "")):
            return False
        origen = self.headers.get("Origin")
        if origen and not ORIGEN_LOCAL.match(origen):
            return False
        if self.command == "POST" and self.headers.get("X-Chronify") != "1":
            return False
        if SECRETO and u.path not in SIN_CLAVE:
            galleta = next((c.split("=", 1)[1] for c in (self.headers.get("Cookie") or "").split("; ")
                            if c.startswith("chronify=")), "")
            dada = galleta or self.headers.get("X-Chronify-Clave", "")
            return hmac.compare_digest(dada.encode(), SECRETO.encode())
        return True

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if SECRETO and u.path == "/" and hmac.compare_digest(q.get("k", "").encode(), SECRETO.encode()):
            return self._send(302, b"", extra={"Location": "/", "Set-Cookie":
                                                f"chronify={SECRETO}; Path=/; HttpOnly; SameSite=Strict"})
        if not self._permitido(u):
            return self._send(403, {"error": "petición no permitida"})
        if u.path == "/api/ping":
            VIDA["ultimo"] = max(VIDA["ultimo"] or 0, time.time())
            return self._send(200, {"ok": True, "app": "chronify"})
        if u.path in ("/", "/index.html"):
            return self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        if u.path == "/estilos.css" or (u.path.startswith("/js/") and u.path.endswith(".js")):
            f = (WEB / u.path.lstrip("/")).resolve()
            if f.parent not in (WEB.resolve(), (WEB / "js").resolve()) or not f.is_file():
                return self._send(404, {"error": "no existe"})
            tipo = "text/css" if f.suffix == ".css" else "text/javascript"
            return self._send(200, f.read_bytes(), tipo + "; charset=utf-8")
        if u.path in ("/logo.svg", "/logo.png", "/logo-32.png", "/favicon.ico"):
            f = {"/favicon.ico": "logo.ico"}.get(u.path, u.path[1:])
            tipo = {"svg": "image/svg+xml", "png": "image/png", "ico": "image/x-icon"}[f.rsplit(".", 1)[1]]
            return self._send(200, (WEB / f).read_bytes(), tipo)
        if u.path == "/api/estado":
            if q.get("recargar") or not ESTADO["cargado"]:
                recargar()
            return self._send(200, resumen())
        if u.path == "/api/txt":
            o = next((o for o in analisis.ordenar(ESTADO["listas"], ESTADO["cat"]) if o["clave"] == q.get("lista")), None)
            if not o:
                return self._send(404, {"error": "lista no encontrada"})
            return self._send(200, analisis.txt(o["orden"]), "text/plain; charset=utf-8")
        if u.path == "/api/fechas":
            return self._send(200, pendientes(q.get("filtro", "aprox")))
        if u.path == "/api/mb":
            return self._send(200, MB)
        if u.path == "/mundo.json":
            return self._send(200, (WEB / "mundo.json").read_bytes(), "application/json; charset=utf-8")
        if u.path == "/api/estadisticas":
            from core import estadisticas
            if not ESTADO["cargado"]:
                recargar()
            R = config.rules()
            st = estadisticas.calcular(ESTADO["listas"], ESTADO["cat"], Fechas(), R, q.get("lista"))
            fotos = config.CACHE / "fotos"  # una foto al mes de Mix para ver la evolución (datos personales: caché)
            if st.get("lista") == (R.get("mix") or (None if q.get("lista") else st.get("lista"))):
                estadisticas.guardar_foto(st, fotos)
            st["evolucion"] = estadisticas.evolucion(fotos)
            return self._send(200, st)
        if u.path == "/api/artistas":
            from core import artistas
            return self._send(200, {**ART, "pendientes": len(artistas.pendientes(_nombres_artistas()))})
        if u.path == "/api/historial":
            return self._send(200, historial.leer())
        if u.path == "/api/spotify":
            return self._send(200, estado_spotify())
        if u.path == "/api/wifi":  # sincronizar por Wi-Fi: espera abierta, progreso y resultado
            from core import wifi
            return self._send(200, {**wifi.estado(), "web": ES_WEB})
        if u.path == "/api/novedades":  # ?desde=1.0.0&idioma=en → cambios desde esa versión (aviso tras actualizar)
            from core import actualizar
            return self._send(200, actualizar.novedades(q.get("desde", VERSION), q.get("idioma", "es")))
        if u.path == "/api/version":
            return self._send(200, {"version": VERSION})
        if u.path == "/api/actualizacion":
            from core import actualizar
            info = actualizar.publico(actualizar.comprobar(forzar=bool(q.get("forzar"))))
            return self._send(200, {**info, **{k: UPD[k] for k in ("activo", "log", "hecho")}, "error_aplicar": UPD["error"]})
        if u.path == "/api/sincronizar":  # ?movil=1 comprueba además si hay un móvil conectado (llama a adb)
            from core import sincro
            extra = {}
            if q.get("movil") and not os.environ.get("CHRONIFY_ANDROID"):
                extra["conectado"], extra["motivo"] = sincro.movil_conectado()
            return self._send(200, {**SINC, **extra, "ultima": sincro.estado(), "android": bool(os.environ.get("CHRONIFY_ANDROID"))})
        if u.path == "/api/reglas":
            return self._send(200, reglas_listas())
        if u.path == "/api/copia":
            from core import copia
            u_ = copia.ultima()
            return self._send(200, {"carpeta": str(copia.carpeta()), "ultima": u_ and {
                "ruta": u_["ruta"], "fecha": time.strftime("%d/%m/%Y %H:%M", time.localtime(u_["t"]))}})
        if u.path == "/api/sincro/datos":  # el PC pide los datos de este dispositivo (por adb)
            from core import sincro
            return self._send(200, sincro.datos())
        if u.path == "/api/ajustes":
            return self._send(200, {"data_dir": config.env("DATA_DIR"), "github_token": bool(config.env("GITHUB_TOKEN")),
                                    "carpetas": [str(d) for d in config.export_dirs()]})
        if u.path == "/spotify/login":
            from core import spotify
            VIDA["ultimo"] = time.time() + 600  # durante el login la ventana está en spotify.com: no hay pings
            return self._send(302, b"", extra={"Location": spotify.url_login(PUERTO[0])})
        if u.path == "/callback":
            from core import spotify
            try:
                if "error" in q:
                    raise ValueError(q["error"])
                spotify.callback(q.get("code", ""), q.get("state", ""), PUERTO[0])
                LOGIN["error"] = None
                msg = "Spotify conectado." if ES_WEB else "Spotify conectado. Puedes cerrar esta pestaña y volver a Chronify."
            except Exception as e:
                print(f"Error en el login de Spotify: {e!r}")
                LOGIN["error"] = f"{datetime.now():%d/%m %H:%M} · {e}"
                msg = html.escape(f"No se pudo conectar: {e}")
            return self._send(200, f"<meta charset=utf-8><body style='font:16px system-ui;padding:40px'>{msg}"
                                   f"<p><a href='/'>Volver</a>", "text/html; charset=utf-8")
        return self._send(404, {"error": "no existe"})

    def do_POST(self):
        u = urlparse(self.path)
        if not self._permitido(u):
            return self._send(403, {"error": "petición no permitida"})
        if u.path == "/api/importar":  # cuerpo = el zip/CSV tal cual (elegido con el selector de archivos)
            return self._importar()
        if u.path == "/api/copia/restaurar":  # cuerpo = el zip de una copia (de este u otro dispositivo)
            from core import copia
            n = int(self.headers.get("Content-Length") or 0)
            if not n or n > 200_000_000:
                return self._send(400, {"error": "Elige el zip de una copia de Chronify"})
            import io
            import zipfile
            try:
                copia.restaurar(io.BytesIO(self.rfile.read(n)))
            except zipfile.BadZipFile:
                return self._send(400, {"error": "Ese archivo no es un zip"})
            except (ValueError, OSError) as e:
                return self._send(400, {"error": str(e)})
            config.ENV.clear()
            config.ENV.update(config._load_env())
            recargar()
            return self._send(200, {"ok": True})
        b = self._body()
        if u.path == "/api/fecha":  # {id, fecha}: fecha manual
            F = Fechas()
            for item in b.get("items", [b]):
                antes = dict(F.pistas[item["id"]]) if item["id"] in F.pistas else None
                p = ESTADO["cat"].get(item["id"])
                despues = dict(F.fijar(item["id"], item["fecha"].strip(), item.get("fuente", "manual"), p))
                if antes != despues:
                    historial.registrar("fecha", f"{p.etiqueta() if p else item['id']}: "
                                        f"{(antes or {}).get('fecha') or 'sin fecha'} → {despues['fecha']} ({despues['fuente']})",
                                        id=item["id"], antes=antes, despues=despues)
            config.guardar_fechas(F.data)
            return self._send(200, {"ok": True})
        if u.path == "/api/excepcion":  # {tipo, id}
            R = config.rules()
            lst = R.setdefault("excepciones", {}).setdefault(b["tipo"], [])
            if b["id"] not in lst:
                lst.append(b["id"])
            config.guardar_reglas(R)
            p = ESTADO["cat"].get(b["id"])
            historial.registrar("excepcion", f"{p.etiqueta() if p else b['id']}: excepción «{b['tipo']}»", id=b["id"])
            return self._send(200, {"ok": True})
        if u.path == "/api/historial/deshacer":  # {uid}
            try:
                deshacer(b.get("uid", ""))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            return self._send(200, {"ok": True})
        if u.path == "/api/artistas":  # {} empieza a buscar países en MusicBrainz, {cancelar:true} para
            if b.get("cancelar"):
                ART["cancelar"] = True
                return self._send(200, {"ok": True})
            if ART["activo"] or MB["activo"]:
                return self._send(409, {"error": "ya hay una búsqueda en MusicBrainz en marcha"})
            from core import artistas
            ART.update(activo=True, hechos=0, total=len(artistas.pendientes(_nombres_artistas())), actual="",
                       error=None, cancelar=False)
            threading.Thread(target=_buscar_artistas, daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path == "/api/artista":  # {nombre, pais}: corrección manual (artistas.json)
            from core import artistas
            nombre, pais = b.get("nombre", ""), "".join(ch for ch in str(b.get("pais", "")).upper() if ch.isalpha())[:2]
            if not nombre or len(pais) != 2:
                return self._send(400, {"error": "Pon el código de país de 2 letras (ES, US, GB…)"})
            antes = artistas.manuales().get(nombre)
            artistas.guardar_manual(nombre, {"pais": pais})
            historial.registrar("artista", f"{nombre}: país {(antes or {}).get('pais') or '?'} → {pais}", id=nombre,
                                antes=antes, despues=artistas.manuales().get(nombre))
            return self._send(200, {"ok": True})
        if u.path == "/api/mb":  # {ids:[...]} o {cancelar:true}
            if b.get("cancelar"):
                MB["cancelar"] = True
                return self._send(200, {"ok": True})
            if MB["activo"] or ART["activo"]:
                return self._send(409, {"error": "ya hay una búsqueda en marcha"})
            ids = b.get("ids", [])
            MB.update(activo=True, hechos=0, total=len(ids), actual="", propuestas=[], error=None, cancelar=False)
            threading.Thread(target=_buscar_mb, args=(ids,), daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path == "/api/spotify/client_id":
            cid = "".join(ch for ch in b.get("client_id", "") if ch.isalnum())
            if cid != config.env("SPOTIFY_CLIENT_ID"):
                config.borrar_cache("spotify_token.json")  # el token era de la otra app
                config.borrar_cache("spotify_cuenta.json")
            config.guardar_env("SPOTIFY_CLIENT_ID", cid)
            return self._send(200, {"ok": True})
        if u.path == "/api/spotify/desconectar":  # olvida el token (no toca nada en Spotify)
            config.borrar_cache("spotify_token.json")
            config.borrar_cache("spotify_cuenta.json")
            return self._send(200, {"ok": True})
        if u.path == "/api/reglas":  # Ajustes → Tus listas
            try:
                with LOCK:
                    return self._send(200, guardar_listas(b))
            except (ValueError, TypeError) as e:
                return self._send(400, {"error": str(e)})
        if u.path == "/api/copia":  # copia de seguridad de lo que no está en GitHub
            from core import copia
            if os.environ.get("CHRONIFY_ANDROID"):
                return self._send(400, {"error": "La copia se hace en el PC (el móvil se sincroniza con él)"})
            if ES_WEB:  # los datos están en el navegador: la copia se descarga
                nombre, datos = copia.en_memoria()
                return self._send(200, datos, "application/zip", {"Content-Disposition": f'attachment; filename="{nombre}"'})
            return self._send(200, copia.crear())
        if u.path in ("/api/wifi/esperar", "/api/wifi/parar", "/api/wifi/conectar"):
            from core import wifi
            if ES_WEB:
                return self._send(400, {"error": "En la web no se puede sincronizar por Wi-Fi: usa la copia de seguridad"})
            if u.path.endswith("/parar"):
                wifi.parar()
                return self._send(200, wifi.estado())
            if wifi.ESTADO["conectando"]:
                return self._send(409, {"error": "Ya hay una sincronización por Wi-Fi en marcha"})
            if u.path.endswith("/esperar"):
                try:
                    return self._send(200, wifi.esperar())
                except RuntimeError as e:
                    return self._send(400, {"error": str(e)})
            direccion, codigo = str(b.get("direccion") or "").strip(), str(b.get("codigo") or "")
            if not direccion or len(wifi.cifrado.normalizar(codigo)) != 10:
                return self._send(400, {"error": "Escribe la dirección y el código de 10 caracteres que enseña el otro dispositivo"})
            wifi.ESTADO.update(conectando=True, log=[], error=None, resultado=None)

            def tarea():
                try:
                    wifi.ESTADO["resultado"] = wifi.conectar(direccion, codigo, wifi.ESTADO["log"].append)
                except Exception as e:  # noqa: BLE001
                    wifi.ESTADO["error"] = str(e)
                finally:
                    wifi.ESTADO["conectando"] = False
            threading.Thread(target=tarea, daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path == "/api/sincronizar":
            if os.environ.get("CHRONIFY_ANDROID") or ES_WEB:
                return self._send(400, {"error": "Se sincroniza desde el Chronify del PC con el móvil conectado por USB"})
            if not SINC["activo"]:
                SINC.update(activo=True, error=None, paso="")
                threading.Thread(target=_sincronizar, daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path == "/api/sincro/datos":  # el PC manda sus datos: se fusionan con los de aquí
            from core import sincro
            with LOCK:
                return self._send(200, {"cambios": sincro.recibir(b)})
        if u.path == "/api/ajustes":  # {data_dir} y/o {github_token}
            if "data_dir" in b:
                config.guardar_env("DATA_DIR", " ".join(str(b["data_dir"]).split()))  # sin saltos de línea en .env
            if "github_token" in b:
                config.guardar_env("GITHUB_TOKEN", "".join(ch for ch in str(b["github_token"]) if ch.isalnum() or ch == "_"))
                from core import actualizar
                actualizar._CACHE.update(t=0, info=None)
            return self._send(200, {"ok": True})
        if u.path == "/api/actualizacion/aplicar":
            if UPD["activo"] or SP["activo"] or MB["activo"] or ART["activo"]:
                return self._send(409, {"error": "espera a que acabe la tarea en marcha"})
            UPD.update(activo=True, log=[], error=None, hecho=None)
            threading.Thread(target=_actualizar, daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path in ("/api/spotify/probar", "/api/spotify/leer", "/api/spotify/aplicar", "/api/spotify/cambiar_epoca",
                      "/api/spotify/anadir_a", "/api/spotify/ordenar_todas", "/api/spotify/seguir",
                      "/api/spotify/buscar_copias", "/api/spotify/cambiar_copias", "/api/spotify/crear_ordenada"):
            if SP["activo"]:
                return self._send(409, {"error": f"ya hay una tarea en marcha ({SP['tarea']})"})
            nombre = u.path.rsplit("/", 1)[-1]
            if nombre in ("cambiar_epoca", "anadir_a"):
                fn = _cambiar_lista(b.get("id", ""), b.get("desde") or None, b.get("hacia", ""))
            elif nombre == "buscar_copias":
                fn = _buscar_copias(list(b.get("ids", [])))
            elif nombre == "cambiar_copias":
                fn = _cambiar_copias(list(b.get("ids", [])))
            elif nombre == "aplicar":
                fn = _ordenar([b.get("lista", "")], bool(b.get("forzar")))
            elif nombre == "ordenar_todas":
                fn = _ordenar([o["clave"] for o in analisis.ordenar(ESTADO["listas"], ESTADO["cat"])
                               if not o["fija"] and not o["ordenada"] and not o["en_lista_nueva"]], bool(b.get("forzar")))
            elif nombre == "crear_ordenada":
                fn = _crear_ordenada(b.get("lista", ""), "en" if b.get("idioma") == "en" else "es")
            elif nombre == "seguir":
                p = pendiente() or {}
                if not p.get("listas"):
                    return self._send(400, {"error": "No hay nada a medias"})
                fn = _ordenar(p["listas"], bool(p.get("forzar")))
            else:
                fn = {"probar": _probar, "leer": _leer}[nombre]
            nombre = "aplicar" if nombre in ("ordenar_todas", "seguir") else nombre
            SP.update(activo=True, tarea=nombre, log=[], error=None, resultado=None, cancelar=False)
            threading.Thread(target=_tarea, args=(nombre, fn), daemon=True).start()
            return self._send(200, {"ok": True})
        if u.path == "/api/spotify/cancelar":
            SP["cancelar"] = True
            return self._send(200, {"ok": True})
        if u.path == "/api/guardar_txt":  # escribe en salida/AAAA-MM-DD/ los txt de las listas desordenadas
            carpeta = config.SALIDA / datetime.now().strftime("%Y-%m-%d")
            carpeta.mkdir(parents=True, exist_ok=True)
            hechos = []
            for o in analisis.ordenar(ESTADO["listas"], ESTADO["cat"]):
                if not o["fija"] and not o["ordenada"]:
                    (carpeta / f"{o['lista']}.txt").write_text(analisis.txt(o["orden"]), encoding="utf-8")
                    hechos.append(o["lista"])
            return self._send(200, {"carpeta": str(carpeta), "listas": hechos})
        return self._send(404, {"error": "no existe"})


def _vigilar(srv):
    """Apaga el servidor cuando la ventana lleva un rato cerrada (y no hay tareas a medias)."""
    while True:
        time.sleep(10)
        u = VIDA["ultimo"]
        if u and time.time() - u > VIDA["margen"] and not SP["activo"] and not MB["activo"] and not UPD["activo"] and not ART["activo"] and not SINC["activo"]:
            print("Ventana cerrada: apagando Chronify")
            srv.shutdown()
            return


def _ganchos_wifi():  # la sincronización por Wi-Fi usa el mismo cerrojo y recarga que el resto del servidor
    from core import wifi
    wifi.GANCHOS.update(bloqueo=LOCK, recargar=recargar)


_ganchos_wifi()


def serve(puerto, auto_apagar=True):
    PUERTO[0] = puerto
    srv = SRV[0] = ThreadingHTTPServer(("127.0.0.1", puerto), H)
    print(f"Chronify en http://127.0.0.1:{puerto}")
    if auto_apagar:
        threading.Thread(target=_vigilar, args=(srv,), daemon=True).start()
    from core import conocimiento
    try:  # países/oyentes/fechas de MusicBrainz que trae esta versión (lo local manda)
        conocimiento.sembrar()
    except Exception as e:
        print(f"No se pudo cargar el conocimiento compartido: {e}")
    if not os.environ.get("CHRONIFY_ANDROID"):
        from core import copia
        threading.Thread(target=copia.automatica, daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
