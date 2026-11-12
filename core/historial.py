"""Historial de cambios (fechas, excepciones, artistas, acciones en Spotify) en cache/historial.jsonl.

Cada línea: {uid, t, tipo, texto, id?, antes?, despues?}. Los cambios de fecha se pueden deshacer
(se restaura 'antes'); las acciones en Spotify solo se apuntan.
"""
import json
import secrets
import time

from core.config import CACHE

ARCHIVO = CACHE / "historial.jsonl"


def registrar(tipo, texto, **extra):
    CACHE.mkdir(exist_ok=True)
    # uid único aunque se registren muchos en el mismo instante (p. ej. "guardar marcadas" de MusicBrainz)
    e = {"uid": f"{time.time_ns()}-{secrets.token_hex(3)}", "t": time.strftime("%Y-%m-%d %H:%M:%S"), "tipo": tipo, "texto": texto, **extra}
    with open(ARCHIVO, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e


def leer(n=500):
    """Últimas n entradas, la más reciente primero. Marca las ya deshechas."""
    if not ARCHIVO.exists():
        return []
    todas = [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]
    deshechas = {e.get("deshace") for e in todas if e.get("deshace")}
    for e in todas:
        e["deshecha"] = e["uid"] in deshechas
    return todas[::-1][:n]


def buscar(uid):
    return next((e for e in leer(10 ** 9) if e["uid"] == uid), None)
