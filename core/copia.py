"""Copia de seguridad de lo que no está en GitHub: .env, caché (token, MusicBrainz, historial…), data/, las fechas,
reglas y artistas locales y la clave de firma del APK (sin ella no se puede actualizar la app del móvil).

Se guarda en Documentos/Chronify copias (o COPIAS_DIR en .env), se conservan las últimas 5 y se hace sola cada
7 días al abrir Chronify en el PC. Contiene datos privados (token de Spotify, contraseña de la clave): no subirla
a ningún sitio público.

Restaurar: python -m core.copia restaurar <zip>
"""
import sys
import time
import zipfile
from pathlib import Path

from core import config

CADA = 7 * 24 * 3600
MAX_RESTAURAR = 400_000_000  # bytes descomprimidos: una copia normal ocupa unos pocos MB
RESTAURABLES = (".env", "fechas.json", "rules.json", "artistas.json", "cache/", "data/")
GUARDAR = 5
CLAVE = Path.home() / ".android" / "chronify-release.jks"
SALTAR = {"actualizacion", "chronify.log"}
LEEME = """Copia de seguridad de Chronify ({fecha}).

Restaurar: copia esta carpeta encima de la de Chronify o ejecuta en ella
    python -m core.copia restaurar "<ruta de este zip>"
La clave del APK (android-clave/chronify-release.jks) va en ~/.android/ y keystore.properties en android/.

Contiene datos privados (token de Spotify, contraseña de la clave): no la subas a ningún sitio público.
"""


def carpeta():
    return Path(config.env("COPIAS_DIR") or Path.home() / "Documents" / "Chronify copias")


def _archivos():
    """[(ruta en disco, ruta en el zip)]"""
    out = [(config.DATOS / n, n) for n in (".env", "fechas.json", "rules.json", "artistas.json")]
    for sub in ("cache", "data"):
        base = config.DATOS / sub
        for p in sorted(base.rglob("*")) if base.exists() else ():
            rel = p.relative_to(config.DATOS)
            if p.is_file() and not (set(rel.parts) & SALTAR) and p.suffix != ".tmp":
                out.append((p, rel.as_posix()))
    out += [(CLAVE, "android-clave/" + CLAVE.name), (config.ROOT / "android" / "keystore.properties",
                                                    "android/keystore.properties")]
    return [(p, n) for p, n in out if p.is_file()]


def _escribir(f):
    archivos = _archivos()
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEEME.txt", LEEME.format(fecha=time.strftime("%d/%m/%Y %H:%M")))
        for p, n in archivos:
            z.write(p, n)
    return archivos


def en_memoria():
    """Versión web: la copia se descarga (los datos viven en el navegador). Devuelve (nombre, bytes)."""
    import io
    b = io.BytesIO()
    _escribir(b)
    return time.strftime("chronify-copia-%Y-%m-%d-%H%M%S.zip"), b.getvalue()


def crear(destino=None):
    """Crea la copia y borra las antiguas. Devuelve {ruta, archivos, kb}."""
    destino = Path(destino or carpeta())
    destino.mkdir(parents=True, exist_ok=True)
    zipf = destino / time.strftime("chronify-copia-%Y-%m-%d-%H%M%S.zip")
    tmp = zipf.with_suffix(".zip.tmp")
    with open(tmp, "wb") as f:
        archivos = _escribir(f)
    tmp.replace(zipf)
    for viejo in sorted(destino.glob("chronify-copia-*.zip"))[:-GUARDAR]:
        viejo.unlink()
    return {"ruta": str(zipf), "archivos": len(archivos), "kb": zipf.stat().st_size // 1024}


def ultima():
    zips = sorted(carpeta().glob("chronify-copia-*.zip")) if carpeta().exists() else []
    return {"ruta": str(zips[-1]), "t": zips[-1].stat().st_mtime} if zips else None


def automatica():
    """Al abrir en el PC: una copia si la última tiene más de 7 días. Nunca falla (solo avisa en el log)."""
    try:
        u = ultima()
        if not u or time.time() - u["t"] > CADA:
            r = crear()
            print(f"Copia de seguridad: {r['ruta']} ({r['archivos']} archivos)")
    except Exception as e:
        print(f"No se pudo hacer la copia de seguridad: {e}")


def restaurar(zipf):
    """Devuelve cada archivo a su sitio (zipf: ruta o archivo abierto). Lo que haya ahora se guarda antes en otra
    copia, por si acaso. En la web la clave del APK no se restaura (no hay APK que firmar)."""
    import os
    web = bool(os.environ.get("CHRONIFY_WEB"))
    if not web:
        crear(carpeta() / "antes-de-restaurar")
    with zipfile.ZipFile(zipf) as z:
        if "LEEME.txt" not in z.namelist():
            raise ValueError("Ese zip no es una copia de Chronify")
        if sum(i.file_size for i in z.infolist()) > MAX_RESTAURAR:
            raise ValueError("La copia es demasiado grande")
        for n in z.namelist():
            if n.endswith("/") or n == "LEEME.txt":
                continue
            # solo los sitios que crea una copia (nunca código ni rutas absolutas)
            if n == "android-clave/" + CLAVE.name and not web:
                base, rel = CLAVE.parent, n.split("/", 1)[1]
            elif n == "android/keystore.properties" and not web:
                base, rel = config.ROOT / "android", "keystore.properties"
            elif n.startswith(RESTAURABLES) or n in RESTAURABLES:
                base, rel = config.DATOS, n
            else:
                continue
            destino = (base / rel).resolve()
            if "\\" in n or ":" in n or not destino.is_relative_to(base.resolve()):
                raise ValueError("Ruta no válida en la copia: " + n)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(z.read(n))
            print("restaurado", n)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "restaurar":
        restaurar(sys.argv[2])
    else:
        print(crear()["ruta"])
