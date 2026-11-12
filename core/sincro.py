"""Sincroniza el PC y el móvil por USB (adb), sin pasar por internet: tus datos no salen de tus dispositivos.

El Chronify del PC redirige un puerto al móvil (`adb forward`), abre la app del móvil si hace falta, y:
1. pide los datos del móvil (`GET /api/sincro/datos`), los fusiona con los suyos y los guarda;
2. le manda el resultado (`POST /api/sincro/datos`), que el móvil fusiona igual;
3. si el zip de Exportify del PC es más nuevo que el del móvil, se lo pasa (`POST /api/importar`).

Fusión: fechas.json → por canción gana el cambio más reciente (campo `m`; sin él, la fuente más fiable y si no
lo de este lado); rules.json → lo de aquí + claves nuevas, excepciones unidas; artistas.json y cachés de
MusicBrainz/ListenBrainz → unión; cupo de Spotify → todas las escrituras de los dos (el límite es por app).
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

from core import actualizar, artistas, config

PAQUETE = "com.anxobt.chronify"
PUERTO_MOVIL = 8766
PUERTO_LOCAL = 8781  # en el PC, redirigido al 8766 del móvil
ESTADO = "sincro.json"
CACHES = (artistas.CACHE, artistas.AREAS, artistas.OYENTES, "musicbrainz.json")
CUPO = "spotify_cupo.json"


# ---------- datos de este dispositivo (lo usan los dos lados) ----------

def zip_reciente():
    """El zip de Exportify más reciente de las carpetas de búsqueda: (ruta, mtime) o (None, 0)."""
    zips = [p for d in config.export_dirs() if d.exists() for p in [*d.glob("*.zip"), *d.glob("*/*.zip")]
            if p.name.lower().startswith("spotify_playlists")]
    p = max(zips, key=lambda p: p.stat().st_mtime, default=None)
    return (p, p.stat().st_mtime) if p else (None, 0)


def _historial():
    from core import historial
    return historial.ARCHIVO.read_text(encoding="utf-8").splitlines() if historial.ARCHIVO.exists() else []


def _fotos():
    d = config.CACHE / "fotos"
    return {f.name: json.loads(f.read_text(encoding="utf-8")) for f in d.glob("*.json")} if d.exists() else {}


def datos():
    _, mtime = zip_reciente()
    from core.version import VERSION
    return {"fechas": config.fechas().get("pistas", {}), "rules": config.rules(), "artistas": artistas.manuales(),
            "caches": {n: config.cache_json(n) for n in CACHES}, "cupo": config.cache_json(CUPO).get("escrituras", []),
            "zip": mtime, "version": VERSION,
            # ajustes y estado de Spotify (la carpeta de Descargas no: es distinta en cada dispositivo)
            "ajustes": {"SPOTIFY_CLIENT_ID": config.env("SPOTIFY_CLIENT_ID")},
            "estado": {n: config.cache_json(n) for n in ESTADOS},
            "historial": _historial(), "fotos": _fotos()}


# Estado que se comparte: sesión de Spotify, prueba de "mover conserva la fecha", bloqueo, lo pendiente de
# ordenar y las versiones buenas de copias ya buscadas
ESTADOS = ("spotify_token.json", "prueba_spotify.json", "spotify_bloqueo.json", "spotify_pendiente.json", "copias.json",
           "spotify_cuenta.json")


def _elegir_estado(nombre, aqui, otro):
    """Qué versión de un archivo de estado se queda."""
    if not otro:
        return aqui
    if not aqui:
        return otro
    if nombre == "spotify_token.json":  # la sesión renovada más recientemente
        return otro if otro.get("expira", 0) > aqui.get("expira", 0) else aqui
    if nombre == "spotify_bloqueo.json":  # el bloqueo que dure más
        return otro if otro.get("hasta", 0) > aqui.get("hasta", 0) else aqui
    if nombre == "spotify_cuenta.json":  # la comprobación más reciente de la cuenta
        return otro if otro.get("t", 0) > aqui.get("t", 0) else aqui
    if nombre == "copias.json":
        return {**otro, **{k: v for k, v in aqui.items() if v.get("hecho") or k not in otro}}
    return aqui


def fusionar_fechas(aqui, otro):
    out = dict(otro)
    for tid, x in aqui.items():
        y = otro.get(tid)
        if y is None or x == y:
            out[tid] = x
        elif x.get("m") or y.get("m"):
            out[tid] = x if (x.get("m") or 0) >= (y.get("m") or 0) else y  # el cambio más reciente
        else:
            p = actualizar.PRIORIDAD
            out[tid] = x if p.get(x.get("fuente"), 0) >= p.get(y.get("fuente"), 0) else y
    return out


def recibir(otro):
    """Fusiona los datos de otro dispositivo con los de este y guarda lo que cambie. Devuelve qué ha cambiado."""
    cambios = []
    d = config.fechas()
    junto = fusionar_fechas(d.get("pistas", {}), otro.get("fechas", {}))
    if junto != d.get("pistas", {}):
        d["pistas"] = junto
        config.guardar_fechas(d)
        cambios.append("fechas")
    reglas = config.rules()
    r = actualizar._fusionar_reglas(reglas, otro.get("rules", {}))
    if r != reglas:
        config.guardar_reglas(r)
        cambios.append("reglas")
    man = artistas.manuales()
    a = {**otro.get("artistas", {}), **man}
    if a != man:
        artistas.escribir(a)
        cambios.append("artistas")
    for n, v in (otro.get("caches") or {}).items():
        if n in CACHES:
            c = config.cache_json(n)
            junta = {**v, **c}
            if junta != c:
                config.save_cache(n, junta)
                if "cachés" not in cambios:
                    cambios.append("cachés")
    cupo = config.cache_json(CUPO).get("escrituras", [])
    todas = sorted(set(cupo) | set(otro.get("cupo") or []))
    if todas != sorted(set(cupo)):
        config.save_cache(CUPO, {"escrituras": todas})
        cambios.append("límite de Spotify")
    # ajustes: si aquí falta el Client ID de Spotify, se toma el del otro
    cid = (otro.get("ajustes") or {}).get("SPOTIFY_CLIENT_ID")
    if cid and not config.env("SPOTIFY_CLIENT_ID"):
        config.guardar_env("SPOTIFY_CLIENT_ID", cid)
        cambios.append("Client ID de Spotify")
    for n, v in (otro.get("estado") or {}).items():
        if n in ESTADOS:
            aqui = config.cache_json(n)
            nuevo = _elegir_estado(n, aqui, v)
            if nuevo != aqui:
                config.save_cache(n, nuevo)
                cambios.append({"spotify_token.json": "sesión de Spotify", "prueba_spotify.json": "prueba de Spotify",
                                "spotify_bloqueo.json": "bloqueo de Spotify", "spotify_pendiente.json": "orden pendiente",
                                "copias.json": "versiones buenas", "spotify_cuenta.json": "cuenta de Spotify"}[n])
    # historial (por uid, en orden) y fotos mensuales
    from core import historial
    lineas = _historial()
    vistos = {json.loads(l)["uid"] for l in lineas if l.strip()}
    nuevas = [l for l in otro.get("historial") or [] if l.strip() and json.loads(l)["uid"] not in vistos]
    if nuevas:
        todas_l = sorted(lineas + nuevas, key=lambda l: json.loads(l)["uid"])
        config.CACHE.mkdir(exist_ok=True)
        historial.ARCHIVO.write_text("\n".join(todas_l) + "\n", encoding="utf-8")
        cambios.append("historial")
    carpeta = config.CACHE / "fotos"
    for n, f in (otro.get("fotos") or {}).items():
        if not (carpeta / n).exists() and n.endswith(".json") and "/" not in n and "\\" not in n:
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / n).write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
            if "fotos" not in cambios:
                cambios.append("fotos")
    return cambios


# ---------- en el PC: hablar con el móvil por adb ----------

def adb():
    """Ruta de adb: ADB en .env, el PATH o el SDK de Android de Windows."""
    for c in (config.env("ADB"), shutil.which("adb"),
              str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools/adb.exe")):
        if c and Path(c).exists():
            return c
    return None


_SERIE = [None]  # dispositivo elegido (el que tiene Chronify; puede haber también un emulador conectado)
CLAVE_MOVIL = f"/sdcard/Android/data/{PAQUETE}/files/clave-sincro.txt"  # la escribe la app en cada arranque


def _adb(*args, timeout=20, todos=False):
    pre = [] if todos or not _SERIE[0] else ["-s", _SERIE[0]]
    r = subprocess.run([adb(), *pre, *args], capture_output=True, text=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout


def _clave():
    """Clave secreta del servidor del móvil (otras apps del móvil no pueden leerla; adb sí)."""
    try:
        return _adb("shell", "cat", CLAVE_MOVIL, timeout=10).strip()
    except RuntimeError:
        return ""


def _movil(ruta, cuerpo=None, cabeceras=None, timeout=60):
    h = {"X-Chronify": "1", "X-Chronify-Clave": _clave(), **(cabeceras or {})}
    req = Request(f"http://127.0.0.1:{PUERTO_LOCAL}{ruta}", method="POST" if cuerpo is not None else "GET",
                  data=cuerpo, headers=h)
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def movil_conectado():
    """(sí/no, explicación) sin hacer cambios. Para enseñarlo en Ajustes."""
    if not adb():
        return False, "no encuentro adb (Android SDK platform-tools)"
    try:
        dispositivos = [l.split()[0] for l in _adb("devices", timeout=10, todos=True).splitlines()[1:]
                        if l.strip().endswith("device")]
    except Exception as e:
        return False, f"adb no responde ({e})"
    if not dispositivos:
        return False, "no hay ningún móvil conectado por USB (con la depuración USB activada)"
    for serie in sorted(dispositivos, key=lambda s: s.startswith("emulator-")):  # primero los móviles de verdad
        _SERIE[0] = serie
        try:
            if PAQUETE in _adb("shell", "pm", "list", "packages", PAQUETE, timeout=15):
                return True, "móvil conectado"
        except RuntimeError:
            continue
    _SERIE[0] = None
    return False, "el móvil no tiene Chronify instalado"


def _abrir_app(log, forzar=False):
    """Se asegura de que Chronify está abierto en el móvil y su servidor contesta."""
    if not forzar:
        try:
            _movil("/api/ping", timeout=2)
            return
        except OSError:
            pass
    log("Abriendo Chronify en el móvil…")
    _adb("shell", "am", "start", "-n", f"{PAQUETE}/.MainActivity")
    for _ in range(60):
        time.sleep(0.5)
        try:
            _movil("/api/ping", timeout=2)
            return
        except OSError:
            continue
    raise RuntimeError("Chronify no arranca en el móvil (¿está bloqueado? desbloquéalo y vuelve a probar)")


def apk_local():
    """APK de esta versión en el PC (el de la release preparada o el último compilado), o None."""
    from core.version import VERSION
    for p in (config.ROOT / "salida" / "release" / f"Chronify-v{VERSION}.apk",
              config.ROOT / "android/app/build/outputs/apk/release/app-release.apk"):
        if p.exists():
            return p
    return None


def _instalar_si_nueva(log):
    """Si el PC tiene una versión de Chronify más nueva que la del móvil, se la instala por USB (sin token de
    GitHub ni descargas). Los datos del móvil se conservan: la app se instala encima."""
    from core.version import VERSION
    del_movil = _movil("/api/version").get("version", "0")
    apk = apk_local()
    if not apk or actualizar.version_tupla(VERSION) <= actualizar.version_tupla(del_movil):
        return None
    log(f"Instalando Chronify v{VERSION} en el móvil (tiene la v{del_movil})…")
    _adb("install", "-r", str(apk), timeout=180)
    _abrir_app(log, forzar=True)
    return VERSION


def sincronizar_movil(log=print):
    ok, motivo = movil_conectado()
    if not ok:
        raise RuntimeError(motivo.capitalize())
    _adb("forward", f"tcp:{PUERTO_LOCAL}", f"tcp:{PUERTO_MOVIL}")
    _abrir_app(log)
    instalada = _instalar_si_nueva(log)
    log("Leyendo los datos del móvil…")
    del_movil = _movil("/api/sincro/datos")
    aqui = recibir(del_movil)
    log("Pasando los datos al móvil…")
    alli = _movil("/api/sincro/datos", json.dumps(datos()).encode(), {"Content-Type": "application/json"}).get("cambios", [])
    p, mtime = zip_reciente()
    if p and mtime > (del_movil.get("zip") or 0) + 1:
        log(f"Pasando el zip de Exportify ({p.name})…")
        _movil("/api/importar", p.read_bytes(), {"X-Nombre": p.name}, timeout=300)
        alli.append("zip de Exportify")
    if instalada:
        alli.insert(0, f"Chronify v{instalada}")
    res = {"pc": aqui, "movil": alli, "t": time.strftime("%d/%m %H:%M")}
    config.save_cache(ESTADO, res)
    return res


def estado():
    return config.cache_json(ESTADO) or None
