"""Web API de Spotify con app propia (OAuth PKCE: solo Client ID, sin secreto).

Desde feb-2026 el modo desarrollo exige Premium en la cuenta dueña de la app y ya no hay endpoints en lote,
pero leer y reordenar listas propias sigue disponible. El token se guarda en cache/spotify_token.json.
"""
import base64
import hashlib
import json
import secrets
import time
import bisect
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.config import cache_json, env, save_cache
from core.red import abrir as _abrir

AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
SCOPES = ("playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public "
          "user-library-read user-read-private")  # user-read-private: saber si la cuenta es Premium
CUENTA_CACHE = "spotify_cuenta.json"
SIN_PREMIUM = ("Spotify solo deja usar su API a apps cuyo dueño tiene Premium (modo desarrollo, desde feb-2026). "
               "Sin Premium Chronify funciona igual con el zip de Exportify: ordenas copiando el txt en Spotify del PC.")
NO_AUTORIZADA = ("Tu cuenta no está autorizada en esa app de Spotify. Crea tu propia app en developer.spotify.com "
                 "(pasos en el README) y pon su Client ID en Ajustes, o pide al dueño de la app que te añada en "
                 "User Management.")
TOKEN_CACHE = "spotify_token.json"
BLOQUEO_CACHE = "spotify_bloqueo.json"
# Ritmo mínimo entre peticiones: Spotify castiga las ráfagas en modo desarrollo con bloqueos de ~24 h
PAUSA = {"GET": 0.25, "escritura": 1.0}
_ULTIMA = [0.0]
ESPERA_MAX = 60  # si Spotify pide esperar más que esto, se corta con un error claro en vez de quedarse colgado


CUPO_CACHE = "spotify_cupo.json"
# Spotify castiga con ~24 h de bloqueo al pasar de unas 600 escrituras al día (observado nov-2026).
# La app se para antes, en este límite (configurable con SPOTIFY_CUPO en .env), y se sigue al día siguiente.
CUPO_DIA = 450  # margen para las lecturas: el 11-nov Spotify bloqueó tras 500 escrituras + lecturas
DIA = 24 * 3600


class SpotifyBloqueado(RuntimeError):
    pass


class SpotifyNoDisponible(RuntimeError):
    """La cuenta no puede usar la API (sin Premium o no autorizada en la app): no es un fallo de Chronify."""


class SpotifyCupo(RuntimeError):
    """Se ha llegado al límite diario propio de escrituras (no es un bloqueo de Spotify)."""


def _escrituras():
    ahora = time.time()
    return [t for t in cache_json(CUPO_CACHE).get("escrituras", []) if t > ahora - DIA]


def cupo():
    """Escrituras hechas en las últimas 24 h, límite, libres y cuándo se libera la más antigua."""
    usadas = _escrituras()
    limite = int(env("SPOTIFY_CUPO") or CUPO_DIA)
    return {"usadas": len(usadas), "limite": limite, "libres": max(0, limite - len(usadas)),
            "libera": min(usadas) + DIA if usadas else None}


def _apuntar_escritura():
    usadas = _escrituras()
    save_cache(CUPO_CACHE, {"escrituras": usadas + [time.time()]})


def _msg_cupo(c):
    cuando = time.strftime("%d/%m %H:%M", time.localtime(c["libera"])) if c["libera"] else "mañana"
    return (f"Límite diario alcanzado ({c['usadas']}/{c['limite']} cambios en 24 h) para que Spotify no bloquee "
            f"la app. Se puede seguir a partir de {cuando} (el cupo se va liberando poco a poco).")


def bloqueado_hasta():
    """Timestamp hasta el que Spotify ha bloqueado la app (o None)."""
    hasta = cache_json(BLOQUEO_CACHE).get("hasta", 0)
    return hasta if hasta > time.time() else None


def _msg_bloqueo(hasta):
    return ("Spotify ha bloqueado la app temporalmente por demasiadas peticiones seguidas. "
            f"Se podrá volver a usar a partir de {time.strftime('%d/%m %H:%M', time.localtime(hasta))}. "
            "Mientras tanto puedes usar el zip de Exportify (lo que ya está hecho en tus listas se queda bien).")
PKCE_CACHE = "spotify_pkce.json"  # en disco: en la versión web el login recarga la página (se pierde la memoria)


def redirect_uri(puerto=8766):
    """PC/Android: el servidor local. Web: la propia página (CHRONIFY_WEB_URL), que recoge ?code=…"""
    import os
    return os.environ.get("CHRONIFY_WEB_URL") or f"http://127.0.0.1:{puerto}/callback"


def url_login(puerto=8766):
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(16)
    pk = {s: v for s, v in (cache_json(PKCE_CACHE) or {}).items() if time.time() - v[1] < 1800}  # 30 min
    pk[state] = [verifier, time.time()]
    save_cache(PKCE_CACHE, pk)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return AUTH + "?" + urlencode({"client_id": env("SPOTIFY_CLIENT_ID"), "response_type": "code",
                                   "redirect_uri": redirect_uri(puerto), "scope": SCOPES, "state": state,
                                   "code_challenge_method": "S256", "code_challenge": challenge})


def _token_request(datos):
    req = Request(TOKEN, data=urlencode(datos).encode(), method="POST",
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with _abrir(req) as r:
            tok = json.loads(r.read())
    except HTTPError as e:  # p. ej. invalid_grant / invalid_client: que se vea el motivo
        raise RuntimeError(f"Spotify rechazó el login ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}")
    tok["expira"] = time.time() + tok.get("expires_in", 3600) - 60
    viejo = cache_json(TOKEN_CACHE)
    tok.setdefault("refresh_token", viejo.get("refresh_token"))  # el refresh a veces no devuelve uno nuevo
    save_cache(TOKEN_CACHE, tok)
    return tok


def callback(code, state, puerto=8766):
    pk = cache_json(PKCE_CACHE) or {}
    verifier = (pk.pop(state, None) or [None])[0]
    save_cache(PKCE_CACHE, pk)
    if not verifier:
        raise ValueError("Login caducado: vuelve a pulsar Conectar")
    tok = _token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(puerto),
                          "client_id": env("SPOTIFY_CLIENT_ID"), "code_verifier": verifier})
    try:
        comprobar_cuenta()
    except Exception:  # sin red, etc.: se sabrá al usarla
        pass
    return tok


def conectado():
    return bool(cache_json(TOKEN_CACHE).get("refresh_token"))


def _token():
    tok = cache_json(TOKEN_CACHE)
    if not tok.get("refresh_token"):
        raise RuntimeError("Spotify no conectado")
    if time.time() > tok.get("expira", 0):
        tok = _token_request({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                              "client_id": env("SPOTIFY_CLIENT_ID")})
    return tok["access_token"]


def call(method, path, body=None, params=None):
    url = (path if path.startswith("http") else API + path) + ("?" + urlencode(params) if params else "")
    hasta = bloqueado_hasta()
    if hasta:
        raise SpotifyBloqueado(_msg_bloqueo(hasta))
    if method != "GET":
        c = cupo()
        if c["libres"] <= 0:
            raise SpotifyCupo(_msg_cupo(c))
    for intento in range(6):
        pausa = PAUSA["GET"] if method == "GET" else PAUSA["escritura"]
        falta = _ULTIMA[0] + pausa - time.time()
        if falta > 0:
            time.sleep(falta)
        _ULTIMA[0] = time.time()
        h = {"Authorization": "Bearer " + _token()}
        if method != "GET":
            _apuntar_escritura()  # cuenta también los intentos fallidos: Spotify los cuenta igual
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        try:
            with _abrir(Request(url, data=data, method=method, headers=h)) as r:
                raw = r.read()
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            if e.code == 429:  # límite de peticiones: Spotify dice cuánto esperar
                espera = int(e.headers.get("Retry-After") or 5)
                if espera > ESPERA_MAX or intento >= 5:
                    hasta = time.time() + espera
                    save_cache(BLOQUEO_CACHE, {"hasta": hasta, "desde": time.time()})
                    raise SpotifyBloqueado(_msg_bloqueo(hasta))
                time.sleep(espera + 1)
                continue
            if e.code in (500, 502, 503) and intento < 5:
                time.sleep(3 * (intento + 1))
                continue
            texto = e.read().decode("utf-8", "replace")[:300]
            if e.code == 403 and _no_disponible(texto):
                save_cache(CUENTA_CACHE, {"premium": None, "error": _no_disponible(texto), "t": time.time()})
                raise SpotifyNoDisponible(_no_disponible(texto))
            raise RuntimeError(f"Spotify {method} {path}: {e.code} {texto}")


def _no_disponible(texto):
    """Mensaje claro para los 403 de cuenta (no de lista): sin Premium o usuario no añadido a la app."""
    t = texto.casefold()
    if "premium" in t:
        return SIN_PREMIUM
    if "regist" in t or "user management" in t or "not allowed" in t:
        return NO_AUTORIZADA
    return ""


def comprobar_cuenta():
    """Tras conectar: ¿esta cuenta puede usar la API? Guarda {premium, error} en cache/spotify_cuenta.json."""
    try:
        me = yo()
        producto = me.get("product")  # "premium" | "free" | "open" (None si el token no tiene user-read-private)
        info = {"premium": None if producto is None else producto == "premium",
                "error": SIN_PREMIUM if producto in ("free", "open") else None}
    except SpotifyNoDisponible as e:
        info = {"premium": None, "error": str(e)}
    info["t"] = time.time()
    save_cache(CUENTA_CACHE, info)
    return info


def yo():
    return call("GET", "/me")


def mis_listas():
    out, url = [], "/me/playlists"
    params = {"limit": 50}
    while url:
        d = call("GET", url, params=params)
        out += d.get("items", [])
        url, params = d.get("next"), None
    return out


def items(playlist_id):
    """[{id, added_at, uri}] en orden. Solo listas propias o colaborativas (limitación del modo desarrollo)."""
    out, url, total = [], f"/playlists/{playlist_id}/items", None
    params = {"limit": 100, "additional_types": "track"}
    while url:
        d = call("GET", url, params=params)
        total = d.get("total", total)
        out += [_item(it) for it in d.get("items", [])]
        url, params = d.get("next"), None
    if total is not None and len(out) != total:  # nunca trabajar con una lista leída a medias
        raise RuntimeError(f"Spotify devolvió {len(out)} de {total} canciones de una lista: vuelve a leer más tarde")
    return [x for x in out if x["id"]]  # pistas locales / episodios no tienen id de canción


def _item(it):
    t = it.get("item") or it.get("track") or {}
    if t.get("type", "track") != "track":
        t = {}
    alb = t.get("album") or {}
    return {"id": t.get("id"), "uri": t.get("uri"), "added_at": it.get("added_at"), "nombre": t.get("name", ""),
            "artistas": ";".join(a.get("name", "") for a in t.get("artists", [])), "album": alb.get("name", ""),
            "fecha": alb.get("release_date", ""), "isrc": (t.get("external_ids") or {}).get("isrc", ""),
            "duracion": t.get("duration_ms"), "popularidad": t.get("popularity"), "explicita": bool(t.get("explicit")),
            "album_tipo": alb.get("album_type", "")}


def guardadas(limite=None):
    """Canciones que te gustan (solo lectura), de la más reciente a la más antigua."""
    out, url, params, total = [], "/me/tracks", {"limit": limite or 50}, None
    while url:
        d = call("GET", url, params=params)
        total = d.get("total", total)
        out += [_item(it) for it in d.get("items", [])]
        if limite:
            return total, [x for x in out if x["id"]]
        url, params = d.get("next"), None
    if total is not None and len(out) != total:
        raise RuntimeError(f"Spotify devolvió {len(out)} de {total} canciones guardadas: vuelve a leer más tarde")
    return [x for x in out if x["id"]]


LECTURA_CACHE = "spotify_listas.json"


def _liked_nuevas(previas, total, sin_id=0):
    """Liked solo crece por arriba: se leen páginas hasta llegar a la que era la primera y se pega lo de antes.
    Si no cuadra con el total (has quitado alguna), se lee entera. 'sin_id': pistas locales o no disponibles que
    había antes (Spotify las cuenta en el total, pero no se guardan)."""
    if previas:
        nuevas, url, params = [], "/me/tracks", {"limit": 50}
        while url and len(nuevas) <= total:
            d = call("GET", url, params=params)
            pag = [_item(it) for it in d.get("items", [])]
            k = next((i for i, x in enumerate(pag) if x["id"] == previas[0]["id"]), None)
            if k is not None:
                arriba = nuevas + pag[:k]
                if len(arriba) + len(previas) + sin_id == total:
                    return [x for x in arriba if x["id"]] + previas
                break
            nuevas += pag
            url, params = d.get("next"), None
    return guardadas()


def _lectura_incremental(fuentes, progreso=None):
    """Lee solo lo que ha cambiado desde la última vez: cada lista trae su `snapshot_id` (cambia con cualquier
    modificación) y Liked se compara por total + última canción (solo se añade por arriba).

    fuentes: [(nombre, playlist_id | None para Liked, snapshot)]. Devuelve ({nombre: items}, n releídas)."""
    previa = cache_json(LECTURA_CACHE) or {}
    nueva, out, leidas = {}, {}, 0
    for n, (nombre, pid, snap) in enumerate(fuentes, 1):
        clave = pid or "_liked"
        antes = previa.get(clave) or {}
        if pid:
            firma = snap
        else:
            total, primeras = guardadas(limite=1)
            firma = f"{total}:{primeras[0]['id'] if primeras else ''}"
        if firma and antes.get("firma") == firma and isinstance(antes.get("items"), list):
            its = antes["items"]
        else:
            if progreso:
                progreso(f"Leyendo {nombre} ({n}/{len(fuentes)})")
            its = items(pid) if pid else _liked_nuevas(antes.get("items"), total, antes.get("sin_id", 0))
            leidas += 1
        out[nombre] = its
        nueva[clave] = {"firma": firma, "nombre": nombre, "items": its}
        if not pid:
            nueva[clave]["sin_id"] = max(0, total - len(its))
    save_cache(LECTURA_CACHE, nueva)
    return out, leidas


def cargar(ignorar=(), solo_lectura=(), progreso=None):
    """Como exportify.cargar() pero leyendo de Spotify. Las listas de otros usuarios ni se abren.
    Solo se descargan las listas que han cambiado desde la última lectura (cache/spotify_listas.json)."""
    from core.exportify import Lista, Pista
    yo_id = yo()["id"]
    listas, catalogo = {}, {}
    propias = [pl for pl in mis_listas() if pl and (pl.get("owner") or {}).get("id") == yo_id
               and pl.get("name") not in ignorar]
    fuentes = [(pl["name"], pl["id"], pl.get("snapshot_id")) for pl in propias]
    if "Liked_Songs" not in ignorar:  # canciones que te gustan: siempre de solo lectura
        fuentes.append(("Liked_Songs", None, None))
    leido, releidas = _lectura_incremental(fuentes, progreso)
    for nombre, pid, _ in fuentes:
        its = leido[nombre]
        for x in its:
            catalogo[x["id"]] = Pista(id=x["id"], titulo=x["nombre"], artistas=x["artistas"], album=x["album"],
                                      fecha_spotify=x["fecha"], isrc=x["isrc"], anadida=x["added_at"] or "",
                                      duracion=x["duracion"], popularidad=x["popularidad"],
                                      explicita=x["explicita"], album_tipo=x["album_tipo"])
        listas[nombre] = Lista(nombre=nombre, origen="Spotify API", mtime=time.time(), pistas=[x["id"] for x in its],
                               autor=yo_id, solo_lectura=not pid or nombre in solo_lectura, spotify_id=pid or "",
                               anadidas={x["id"]: x["added_at"] or "" for x in reversed(its)})
    if progreso and releidas < len(fuentes):
        progreso(f"Solo {releidas} de {len(fuentes)} listas tenían cambios")
    return listas, catalogo


def crear_o_rellenar(nombre, ids, pid=None, descripcion=""):
    """Lista propia con esas canciones en ese orden (p. ej. Liked por fecha). Si 'pid' es una lista tuya que sigue
    existiendo, la reemplaza; si no, crea una privada. Escrituras: 1 + una por cada 100 canciones. Devuelve su id."""
    uris = [f"spotify:track:{t}" for t in ids]
    if pid and pid not in {pl["id"] for pl in mis_listas() if pl}:
        pid = None  # la borraste: se crea otra
    if pid:
        call("PUT", f"/playlists/{pid}/items", {"uris": uris[:100]})  # reemplaza todo con las 100 primeras
    else:
        cuerpo = {"name": nombre, "public": False, "description": descripcion}
        try:
            pid = call("POST", "/me/playlists", cuerpo)["id"]
        except RuntimeError:  # endpoint antiguo
            pid = call("POST", f"/users/{yo()['id']}/playlists", cuerpo)["id"]
        if uris:
            call("POST", f"/playlists/{pid}/items", {"uris": uris[:100]})
    for i in range(100, len(uris), 100):
        call("POST", f"/playlists/{pid}/items", {"uris": uris[i:i + 100]})
    return pid


def mover(playlist_id, desde, antes_de, snapshot=None, largo=1):
    body = {"range_start": desde, "insert_before": antes_de, "range_length": largo}
    if snapshot:
        body["snapshot_id"] = snapshot
    return call("PUT", f"/playlists/{playlist_id}/items", body).get("snapshot_id")


def anadir(playlist_id, track_id, posicion=None):
    """Añade una canción (su fecha de añadido en esa lista será la de hoy)."""
    body = {"uris": [f"spotify:track:{track_id}"]}
    if posicion is not None:
        body["position"] = posicion
    return call("POST", f"/playlists/{playlist_id}/items", body).get("snapshot_id")


def quitar(playlist_id, track_id):
    """Quita una canción de la lista (todas sus apariciones)."""
    uri = f"spotify:track:{track_id}"
    try:
        return call("DELETE", f"/playlists/{playlist_id}/items", {"items": [{"uri": uri}]}).get("snapshot_id")
    except RuntimeError as e:  # formato antiguo del cuerpo ("tracks") por si la API aún lo pide
        if " 400 " not in str(e):
            raise
        return call("DELETE", f"/playlists/{playlist_id}/items", {"tracks": [{"uri": uri}]}).get("snapshot_id")


def buscar_principal(pista):
    """Copia principal de una canción en Spotify (la que escucha la gente) cuando la tuya es una copia
    duplicada poco escuchada. Busca por ISRC y por título + artista; se queda con las del mismo artista,
    mismo título y duración parecida, y elige la más popular (a igualdad, la de un álbum que no sea
    recopilatorio). Devuelve {id, album, fecha, popularidad, album_tipo} o None. Solo lecturas."""
    from core.analisis import clave_cancion
    from core.exportify import Pista
    from core.musicbrainz import limpiar
    artista = (pista.artistas or "").split(";")[0]
    consultas = [f'track:"{limpiar(pista.titulo)}" artist:"{artista}"']
    if pista.isrc:
        consultas.insert(0, f"isrc:{pista.isrc}")
    vistos, cands = set(), []
    for q in consultas:
        for t in (call("GET", "/search", params={"q": q, "type": "track", "limit": 10}).get("tracks") or {}).get("items", []):
            if not t or t.get("id") in vistos or t.get("id") == pista.id:
                continue
            vistos.add(t["id"])
            otra = Pista(id=t["id"], titulo=t.get("name", ""), artistas=";".join(a.get("name", "") for a in t.get("artists", [])),
                         album="", fecha_spotify="")
            dur = t.get("duration_ms") or 0
            if clave_cancion(otra) == clave_cancion(pista) and (not pista.duracion or abs(dur - pista.duracion) <= 4000):
                alb = t.get("album") or {}
                cands.append({"id": t["id"], "album": alb.get("name", ""), "fecha": alb.get("release_date", ""),
                              "popularidad": t.get("popularity"), "album_tipo": alb.get("album_type", "")})
    if not cands:
        return None
    mejor = max(cands, key=lambda c: (c["popularidad"] or -1, c["album_tipo"] == "album", c["album_tipo"] != "compilation"))
    if mejor["popularidad"] is not None and pista.popularidad is not None and mejor["popularidad"] <= pista.popularidad:
        return None  # ninguna copia es más escuchada que la tuya
    return mejor


def reemplazar(playlist_id, viejo, nuevo, actual):
    """Pone 'nuevo' en el sitio de 'viejo' (añadir en su posición + quitar). 'actual' = ids de la lista en orden."""
    pos = actual.index(viejo)
    anadir(playlist_id, nuevo, pos)
    quitar(playlist_id, viejo)
    return [nuevo if x == viejo else x for x in actual]


def posicion_cronologica(actual, objetivo, track_id):
    """Dónde insertar track_id en 'actual' para que quede justo detrás de su predecesora en 'objetivo'."""
    i = objetivo.index(track_id)
    previas = [t for t in objetivo[:i] if t in actual]
    return actual.index(previas[-1]) + 1 if previas else 0


def plan_movimientos(actual, objetivo):
    """Movimientos (range_start, insert_before, range_length) para pasar de 'actual' a 'objetivo'.

    Se quedan quietas las canciones de la subsecuencia creciente más larga; el resto se mueve detrás de su
    predecesora en el objetivo. Las canciones que ya van seguidas y en orden se mueven juntas en un solo
    bloque (menos peticiones a Spotify). Requiere ids únicos y el mismo conjunto en ambas listas.
    """
    if len(set(actual)) != len(actual) or set(actual) != set(objetivo):
        raise ValueError("La lista tiene duplicados o no coincide con el orden calculado: vuelve a leerla")
    pos = {t: i for i, t in enumerate(objetivo)}
    seq = [pos[t] for t in actual]
    colas, colas_i, prev = [], [], [None] * len(seq)
    for i, v in enumerate(seq):
        k = bisect.bisect_left(colas, v)
        colas[k:k + 1] = [v]
        colas_i[k:k + 1] = [i]
        prev[i] = colas_i[k - 1] if k else None
    quietas, k = set(), (colas_i[-1] if colas_i else None)
    while k is not None:
        quietas.add(actual[k]); k = prev[k]
    cur, plan, n = list(actual), [], 0
    while n < len(objetivo):
        t = objetivo[n]
        if t in quietas:
            n += 1
            continue
        j = cur.index(t)
        largo = 1  # alarga el bloque con las siguientes del objetivo que ya van detrás, en orden
        while (n + largo < len(objetivo) and j + largo < len(cur) and cur[j + largo] == objetivo[n + largo]
               and objetivo[n + largo] not in quietas):
            largo += 1
        b = cur.index(objetivo[n - 1]) + 1 if n else 0
        if b != j:  # si b == j el bloque ya está justo detrás de su predecesora
            plan.append((j, b, largo))
            bloque = cur[j:j + largo]
            del cur[j:j + largo]
            dest = b - largo if b > j else b
            cur[dest:dest] = bloque
        n += largo
    assert cur == list(objetivo)
    return plan


def aplicar_orden(playlist_id, objetivo, progreso=None, cancelar=lambda: False):
    """Reordena moviendo canciones (no las borra ni las vuelve a añadir).

    Devuelve (movimientos hechos, movimientos del plan). Si se acaba el cupo diario se para sin error:
    lo hecho se queda bien y la próxima vez el plan se recalcula desde cómo esté la lista.
    """
    actual = [x["id"] for x in items(playlist_id)]
    plan = plan_movimientos(actual, objetivo)
    snap, hechos = None, 0
    for n, (j, b, largo) in enumerate(plan, 1):
        if cancelar():
            break
        try:
            snap = mover(playlist_id, j, b, snap, largo)
        except SpotifyCupo:
            break
        hechos = n
        if progreso:
            progreso(n, len(plan))
    return hechos, len(plan)
