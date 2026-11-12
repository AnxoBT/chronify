"""Configuración: .env, rutas, reglas (rules.json) y fechas verificadas (fechas.json)."""
import json
import os
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # código (en Android es de solo lectura)
# Datos que la app modifica (fechas, reglas, artistas, .env, caché, salida). En el PC = la carpeta del
# programa, como siempre; en Android, la carpeta privada de la app (CHRONIFY_DATOS la pone el lanzador).
DATOS = Path(os.environ.get("CHRONIFY_DATOS") or ROOT)
CACHE = DATOS / "cache"
SALIDA = DATOS / "salida"
FECHAS = DATOS / "fechas.json"
RULES = DATOS / "rules.json"  # tus listas y excepciones: personal, no va en el repo (se crea desde reglas.defecto.json)
REGLAS_DEFECTO = ROOT / "reglas.defecto.json"
SEMILLAS = ("fechas.json", "artistas.json")  # conocimiento verificado que viene con la app


def _sembrar():
    """Primera vez con una carpeta de datos aparte: copia ahí las fechas, reglas y artistas que trae la app."""
    if DATOS == ROOT:
        return
    import shutil
    DATOS.mkdir(parents=True, exist_ok=True)
    for n in SEMILLAS:
        if not (DATOS / n).exists() and (ROOT / n).exists():
            shutil.copyfile(ROOT / n, DATOS / n)


_sembrar()


def _load_env():
    env = {}
    p = DATOS / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = _load_env()


def guardar_env(key, valor):
    """Cambia o añade una clave en .env conservando el resto del archivo."""
    ENV[key] = valor
    p = DATOS / ".env"
    lineas = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    hecho = False
    for i, l in enumerate(lineas):
        if l.split("=", 1)[0].strip() == key:
            lineas[i], hecho = f"{key}={valor}", True
    if not hecho:
        lineas.append(f"{key}={valor}")
    p.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def borrar_cache(nombre):
    (CACHE / nombre).unlink(missing_ok=True)


def env(key, default=""):
    return ENV.get(key) or os.environ.get(key) or default


def export_dirs():
    """Carpetas donde buscar exports de Exportify (DATA_DIR, separadas por ';'). Por defecto: Descargas y ./data."""
    raw = env("DATA_DIR") or f"{Path.home() / 'Downloads'};data"
    out = []
    for x in raw.split(";"):
        x = x.strip()
        if x:
            d = Path(x)
            out.append(d if d.is_absolute() else DATOS / d)
    return out


def norm(nombre):
    """Nombre de lista comparable: sin tildes, sin mayúsculas, '_' = espacio. 'Electrónica' == 'electronica'."""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return " ".join(s.replace("_", " ").casefold().split())


def _read_json(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _write_json(p, data, indent=None):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(p)  # escritura atómica: si se corta no deja el archivo a medias


def rules():
    """rules.json del usuario completado con las claves que falten de reglas.defecto.json (la primera vez, todas)."""
    defecto = _read_json(REGLAS_DEFECTO, {})
    r = _read_json(RULES, None)
    if r is None:
        r = defecto
        guardar_reglas(r)
    out = {**defecto, **r}
    out["excepciones"] = {**defecto.get("excepciones", {}), **(r.get("excepciones") or {})}
    return out


def guardar_reglas(r):
    DATOS.mkdir(parents=True, exist_ok=True)
    tmp = RULES.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(RULES)


def fechas():
    return _read_json(FECHAS, {"_info": "", "pistas": {}})


def guardar_fechas(data):
    # una pista por línea: diffs de git legibles
    pistas = data.get("pistas", {})
    cuerpo = ",\n".join(f"    {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}" for k, v in pistas.items())
    txt = "{\n" + f'  "_info": {json.dumps(data.get("_info", ""), ensure_ascii=False)},\n' + '  "pistas": {\n' + cuerpo + "\n  }\n}\n"
    tmp = FECHAS.with_suffix(".json.tmp")
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(FECHAS)


def cache_json(name, default=None):
    return _read_json(CACHE / name, {} if default is None else default)


def save_cache(name, data):
    CACHE.mkdir(exist_ok=True)
    _write_json(CACHE / name, data)
