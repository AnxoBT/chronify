"""Actualizaciones desde las releases de GitHub (repo público: sin token; con token, más margen de peticiones).

Token opcional, por orden: GITHUB_TOKEN en .env (pestaña Ajustes), `gh auth token`, o el guardado por Git
(`git credential fill`, sin abrir ventanas). Nunca se escribe en el repo ni se envía a otro sitio que no sea
api.github.com.

Instalación:
- carpeta con `.git` → `git pull --ff-only`;
- carpeta del zip → se descarga el zip de la release y se copian sus archivos encima. Nunca se tocan
  `.env`, `cache/`, `data/`, `salida/` ni `rules.json` (tus listas); `fechas.json` y `artistas.json` se fusionan
  (lo local manda salvo que la release traiga una fecha más fiable).
"""
import io
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from core import config
from core.red import abrir
from core.version import REPO, VERSION

API = "https://api.github.com"
NO_TOCAR = {".env", "cache", "data", "salida", ".git", "fechas.json", "rules.json", "artistas.json"}
CARPETAS_CODIGO = ("core", "web", "tools", "tests", "docs")  # aquí se borran archivos que ya no existan
PRIORIDAD = {"manual": 3, "musicbrainz": 2}
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CACHE = {"t": 0, "info": None}


def version_tupla(v):
    out = []
    for x in str(v).lstrip("vV").split("."):
        num = "".join(ch for ch in x if ch.isdigit())
        out.append(int(num or 0))
    return tuple(out + [0] * (3 - len(out)))


ANDROID = bool(os.environ.get("CHRONIFY_ANDROID"))  # APK: se actualiza instalando el APK nuevo


def es_git():
    return (config.ROOT / ".git").exists()


def _token():
    if config.env("GITHUB_TOKEN"):
        return config.env("GITHUB_TOKEN"), "Ajustes"
    if ANDROID:  # en el móvil no hay gh ni git (y Android no deja lanzar programas)
        return "", ""
    entorno = dict(os.environ, GCM_INTERACTIVE="never", GIT_TERMINAL_PROMPT="0")
    for cmd, origen, entrada in ((["gh", "auth", "token"], "GitHub CLI", None),
                                 (["git", "credential", "fill"], "Git", "protocol=https\nhost=github.com\n\n")):
        try:
            r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=15, env=entorno,
                               creationflags=_SIN_VENTANA)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode:
            continue
        if entrada is None:
            tok = r.stdout.strip()
        else:
            tok = next((l.split("=", 1)[1] for l in r.stdout.splitlines() if l.startswith("password=")), "")
        if tok:
            return tok, origen
    return "", ""


def _get(url, token, binario=False):
    req = Request(url, headers={"User-Agent": "Chronify", "X-GitHub-Api-Version": "2022-11-28",
                                "Accept": "application/octet-stream" if binario else "application/vnd.github+json"})
    if token:
        req.add_unredirected_header("Authorization", "Bearer " + token)  # no se reenvía al servidor de descargas
    with abrir(req, timeout=120 if binario else 20) as r:
        datos = r.read()
    return datos if binario else json.loads(datos)


def comprobar(forzar=False):
    """{actual, ultima, hay, notas, url, error, token, instalacion}. Cachea 6 h."""
    if not forzar and _CACHE["info"] and time.time() - _CACHE["t"] < 6 * 3600:
        return _CACHE["info"]
    if os.environ.get("CHRONIFY_WEB"):  # la web siempre es la última versión publicada
        return {"actual": VERSION, "ultima": VERSION, "hay": False, "notas": "", "url": "", "error": None,
                "token": "", "instalacion": "web"}
    info = {"actual": VERSION, "ultima": None, "hay": False, "notas": "", "url": "", "error": None,
            "token": "", "instalacion": "apk" if ANDROID else "git" if es_git() else "zip"}
    token, info["token"] = _token()
    try:  # repo público: funciona sin token (60 consultas/hora por IP, de sobra)
        rel = _get(f"{API}/repos/{REPO}/releases/latest", token)
        info.update(ultima=rel.get("tag_name", "").lstrip("v"), notas=rel.get("body") or "",
                    url=rel.get("html_url", ""))
        info["hay"] = version_tupla(info["ultima"]) > version_tupla(VERSION)
        zips = [a for a in rel.get("assets", []) if a.get("name", "").endswith(".apk" if ANDROID else ".zip")]
        info["_asset"] = zips[0]["url"] if zips else ""
    except HTTPError as e:
        info["error"] = {401: "token no válido o caducado", 403: "GitHub limita las consultas: prueba más tarde",
                         404: "no hay versiones publicadas"}.get(e.code, f"GitHub {e.code}")
    except OSError as e:
        info["error"] = f"sin conexión con GitHub ({e})"
    _CACHE.update(t=time.time(), info=info)
    return info


def publico(info):
    return {k: v for k, v in info.items() if not k.startswith("_")}


# ---------- aplicar ----------

def _fusionar_fechas(local, nueva):
    """Lo local manda, salvo que la release traiga una fuente más fiable (manual > musicbrainz > resto)."""
    out = dict(nueva)
    for tid, x in local.items():
        y = nueva.get(tid)
        if y is None or PRIORIDAD.get(x.get("fuente"), 0) >= PRIORIDAD.get(y.get("fuente"), 0):
            out[tid] = x
    return out


def _fusionar_reglas(local, nueva):
    out = dict(local)
    for k, v in nueva.items():
        if k not in out:
            out[k] = v
        elif k == "excepciones" and isinstance(v, dict):
            exc = dict(out[k])
            for tipo, ids in v.items():
                a = exc.get(tipo)
                if isinstance(a, list) and isinstance(ids, list):  # listas de ids: se unen
                    exc[tipo] = list(dict.fromkeys(a + ids))
                elif isinstance(ids, str) or a is None:  # textos como "_info" (y arregla uno partido en letras)
                    exc[tipo] = ids
            out[k] = exc
    return out


def _datos_json(ruta):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def aplicar(log=print):
    """Descarga e instala la última release. Devuelve la versión instalada."""
    info = comprobar(forzar=True)
    if info["error"]:
        raise RuntimeError("No se puede comprobar la actualización: " + info["error"])
    if not info["hay"]:
        raise RuntimeError("Ya tienes la última versión")
    if info["instalacion"] == "git":
        log("Actualizando con git pull…")
        r = subprocess.run(["git", "pull", "--ff-only"], cwd=config.ROOT, capture_output=True, text=True,
                           timeout=120, creationflags=_SIN_VENTANA)
        if r.returncode:
            raise RuntimeError("git pull falló (¿cambios locales en el mismo archivo?): " + (r.stderr or r.stdout)[-300:])
        return info["ultima"]
    if not info.get("_asset"):
        raise RuntimeError("La release no tiene " + ("APK" if ANDROID else "zip") + " adjunto")
    token, _ = _token()
    if ANDROID:  # se descarga el APK y la app abre el instalador de Android (MainActivity: /android/instalar)
        log(f"Descargando el APK de v{info['ultima']}…")
        apk = config.DATOS / "Chronify.apk"
        apk.write_bytes(_get(info["_asset"], token, binario=True))
        _CACHE.update(t=0, info=None)
        return info["ultima"]
    log(f"Descargando v{info['ultima']}…")
    zf = zipfile.ZipFile(io.BytesIO(_get(info["_asset"], token, binario=True)))
    nombres = [n for n in zf.namelist() if not n.endswith("/")]
    prefijo = nombres[0].split("/", 1)[0] + "/" if all("/" in n for n in nombres) else ""
    if prefijo + "app.py" not in nombres or prefijo + "core/version.py" not in nombres:
        raise RuntimeError("El zip de la release no parece de Chronify")

    tmp = config.CACHE / "actualizacion"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for n in nombres:
        rel = n[len(prefijo):]
        destino = (tmp / rel).resolve()
        if not str(destino).startswith(str(tmp.resolve())):  # zip con rutas raras
            raise RuntimeError("Ruta no válida en el zip: " + n)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(zf.read(n))

    log("Instalando…")
    raiz = config.ROOT
    nuevos = {p.relative_to(tmp).as_posix() for p in tmp.rglob("*") if p.is_file()}
    for rel in sorted(nuevos):
        if rel.split("/", 1)[0] in NO_TOCAR:
            continue
        (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp / rel, raiz / rel)
    for carpeta in CARPETAS_CODIGO:  # archivos que la nueva versión ya no trae
        for p in (raiz / carpeta).rglob("*") if (raiz / carpeta).exists() else ():
            rel = p.relative_to(raiz).as_posix()
            if p.is_file() and "__pycache__" not in rel and rel not in nuevos:
                p.unlink()
    local, nueva = _datos_json(raiz / "fechas.json"), _datos_json(tmp / "fechas.json")
    config.guardar_fechas({"_info": nueva.get("_info") or local.get("_info", ""),
                           "pistas": _fusionar_fechas(local.get("pistas", {}), nueva.get("pistas", {}))})
    # rules.json es personal (no viene en la release): las claves nuevas salen de reglas.defecto.json al leerlo
    from core import artistas
    artistas.escribir({**_datos_json(tmp / "artistas.json"), **artistas.manuales()})  # lo tuyo manda
    shutil.rmtree(tmp, ignore_errors=True)
    _CACHE.update(t=0, info=None)
    return info["ultima"]


def fusionar_semillas():
    """Android: cada APK trae las fechas y artistas verificados de su versión. Al arrancar una versión
    nueva se fusionan con los del móvil (lo del móvil manda salvo fuente más fiable), como al actualizar en el PC."""
    if config.DATOS == config.ROOT:
        return
    marca = config.DATOS / ".semillas"
    if marca.exists() and marca.read_text(encoding="utf-8").strip() == VERSION:
        return
    local, nueva = _datos_json(config.FECHAS), _datos_json(config.ROOT / "fechas.json")
    config.guardar_fechas({"_info": nueva.get("_info") or local.get("_info", ""),
                           "pistas": _fusionar_fechas(local.get("pistas", {}), nueva.get("pistas", {}))})
    from core import artistas
    artistas.escribir({**_datos_json(config.ROOT / "artistas.json"), **artistas.manuales()})
    marca.write_text(VERSION, encoding="utf-8")
