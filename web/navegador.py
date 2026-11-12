"""Chronify en el navegador (versión web: iPhone, Mac, Linux, cualquier móvil). Solo se usa dentro de Pyodide.

El worker (web/js/trabajador.js) carga Python, pone el código en /app y los datos del usuario en /datos (IndexedDB:
se quedan en ese navegador), y llama a `iniciar()` y después a `despachar()` por cada petición que haría la
página al servidor local. Lo que cambia respecto al PC:

- red: no hay sockets → XMLHttpRequest síncrono (se puede dentro de un Web Worker) con la misma interfaz que urlopen;
- hilos: no hay → las tareas largas (ordenar en Spotify, MusicBrainz…) se apuntan y se ejecutan al acabar la
  petición que las lanza (`hay_tareas()` / `ejecutar_tareas()`); mientras, la página enseña su progreso con las
  fotos de estado que se envían desde `time.sleep` (todas las tareas esperan entre peticiones);
- time.sleep: con memoria compartida (página aislada por el service worker, sw.js) se espera con Atomics.wait sin
  gastar CPU, y la página puede pedir "cancelar" aunque Python esté ocupado; sin ella, espera activa.
"""
import email.message
import io
import json
import os
import threading
import time
import traceback
from urllib.error import HTTPError, URLError

TAREAS = []
_ENVIAR = [None]  # función JS que manda a la página las fotos de estado
_COMPARTIDA = [None]  # Int32Array sobre SharedArrayBuffer: [0] = la página pide cancelar, [1] = para esperar
_ULTIMA_FOTO = [0.0]
ESTADOS = {"/api/spotify": "SP", "/api/mb": "MB", "/api/artistas": "ART"}  # ruta → estado de la tarea en web/server.py
_dormir_real = time.sleep


class _HiloWeb:
    """Sustituye a threading.Thread: la tarea se ejecuta cuando la página ya tiene su respuesta."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **_):
        self._f, self._a, self._k = target, args, kwargs or {}

    def start(self):
        TAREAS.append(self)

    def run(self):
        self._f(*self._a, **self._k)


def _dormir(segundos):
    fin = time.time() + max(0.0, segundos)
    while True:
        _foto()
        if time.time() >= fin:
            return
        trozo = min(0.2, fin - time.time())
        if _COMPARTIDA[0] is not None:
            from js import Atomics
            Atomics.wait(_COMPARTIDA[0], 1, 0, max(1, int(trozo * 1000)))
        else:
            t = time.time()
            while time.time() - t < trozo:  # espera activa a trozos, enviando el progreso entre medias
                pass


def _foto(forzar=False):
    """Manda a la página el estado de las tareas (como si hubiera consultado /api/spotify, /api/mb…)."""
    if _COMPARTIDA[0] is not None and _COMPARTIDA[0][0]:  # la página ha pulsado "cancelar"/"parar"
        from js import Atomics
        Atomics.store(_COMPARTIDA[0], 0, 0)
        from web import server
        for d in (server.SP, server.MB, server.ART):
            if d.get("activo"):
                d["cancelar"] = True
    if not _ENVIAR[0] or (not forzar and time.time() - _ULTIMA_FOTO[0] < 1.0):
        return
    _ULTIMA_FOTO[0] = time.time()
    from web import server
    fotos = {}
    for ruta, nombre in ESTADOS.items():
        if not getattr(server, nombre).get("activo"):  # solo las tareas en marcha (las demás no cambian)
            continue
        codigo, _, cuerpo = despachar("GET", ruta, {}, b"")
        if codigo == 200:
            fotos[ruta] = cuerpo.decode("utf-8")
    _ENVIAR[0](json.dumps(fotos))


class _Respuesta(io.BytesIO):
    def __init__(self, url, codigo, cabeceras, cuerpo):
        super().__init__(cuerpo)
        self.url, self.status, self.code, self.headers = url, codigo, codigo, cabeceras

    def getcode(self):
        return self.status


def _transporte(req, timeout=30):
    """urlopen hecho con XMLHttpRequest síncrono. Las webs a las que llama Chronify (Spotify, MusicBrainz,
    ListenBrainz) permiten CORS. El navegador pone su propio User-Agent (no se puede cambiar)."""
    from js import Uint8Array, XMLHttpRequest
    from pyodide.ffi import to_js
    x = XMLHttpRequest.new()
    x.open(req.get_method(), req.full_url, False)
    x.responseType = "arraybuffer"
    x.timeout = int(timeout * 1000)
    for k, v in req.header_items():
        if k.lower() not in ("user-agent", "content-length", "host", "connection"):
            x.setRequestHeader(k, v)
    try:
        x.send(to_js(req.data) if req.data else None)
    except Exception as e:  # sin conexión, CORS, tiempo agotado
        raise URLError(f"sin conexión con {req.host} ({e})")
    if x.status == 0:
        raise URLError(f"sin conexión con {req.host}")
    cab = email.message.Message()
    for linea in (x.getAllResponseHeaders() or "").splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            cab[k.strip()] = v.strip()
    cuerpo = bytes(Uint8Array.new(x.response).to_py()) if x.response else b""
    if x.status >= 400:
        raise HTTPError(req.full_url, x.status, x.statusText, cab, io.BytesIO(cuerpo))
    return _Respuesta(req.full_url, x.status, cab, cuerpo)


def iniciar(enviar_foto, compartida=None):
    """Una vez, con /app (código) y /datos (IndexedDB) ya montados y CHRONIFY_* en el entorno."""
    threading.Thread = _HiloWeb
    time.sleep = _dormir
    _ENVIAR[0], _COMPARTIDA[0] = enviar_foto, compartida
    from core import actualizar, conocimiento, red
    red.TRANSPORTE[0] = _transporte
    actualizar.fusionar_semillas()  # fechas y países que trae esta versión, fusionados con los tuyos
    conocimiento.sembrar()
    from web import server  # noqa: F401  (carga el estado)


def despachar(metodo, ruta, cabeceras, cuerpo):
    """Una petición de la página → (código, cabeceras, cuerpo en bytes), igual que la respondería el PC."""
    from web.server import H
    if hasattr(cuerpo, "to_bytes"):  # Uint8Array de JS
        cuerpo = cuerpo.to_bytes()

    class Peticion(H):
        def __init__(self):  # sin socket: no se llama al constructor de BaseHTTPRequestHandler
            self.command, self.path = metodo, ruta
            self.headers = email.message.Message()
            for k, v in dict(cabeceras or {}).items():
                self.headers[k] = v
            del self.headers["Content-Length"]
            self.headers["Content-Length"] = str(len(cuerpo or b""))
            self.rfile = io.BytesIO(bytes(cuerpo or b""))
            self.resultado = (500, {}, b"")

        def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
            if not isinstance(body, bytes):
                body = (json.dumps(body, ensure_ascii=False) if ctype.startswith("application/json") else body).encode("utf-8")
            self.resultado = (code, {"Content-Type": ctype, **(extra or {})}, body)

    p = Peticion()
    try:
        (p.do_POST if metodo == "POST" else p.do_GET)()
    except Exception as e:  # el servidor del PC devolvería un 500: aquí se explica
        p.resultado = (500, {"Content-Type": "application/json"}, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())
    return p.resultado


def hay_tareas():
    return bool(TAREAS)


def ejecutar_tareas():
    """Ejecuta las tareas lanzadas (una tras otra) mandando el progreso. Devuelve cuántas se han hecho."""
    if _COMPARTIDA[0] is not None:  # un "cancelar" de antes no vale para esta tarea
        from js import Atomics
        Atomics.store(_COMPARTIDA[0], 0, 0)
    n = 0
    _foto(forzar=True)  # la página tiene el estado de la tarea desde el primer momento
    while TAREAS:
        try:  # como un hilo en el PC: si una falla, se apunta y siguen las demás
            TAREAS.pop(0).run()
        except Exception:
            traceback.print_exc()
        n += 1
        _foto(forzar=True)
    return n
