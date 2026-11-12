"""Prueba en una lista desechable si REORDENAR con la API conserva la fecha de añadido (added_at).

Crea la lista privada 'Chronify prueba', añade 4 canciones de una en una (con pausa para que cada una
tenga una fecha distinta), las desordena y ordena moviéndolas, compara added_at y borra la lista.
Uso: python -m tools.probar_spotify   (o el botón de la web). Necesita Spotify conectado.
"""
import time

from core import spotify
from core.config import save_cache

PISTAS = ["2QfiRTz5Yc8DdShCxG1tB2", "5ZBeML7Lf3FMEVviTyvi8l", "7jmHyHMEqm9MJWiMAneF05", "0pYDUAXXUanILl4FrDtdIt"]


def probar(log=print):
    me = spotify.yo()
    log(f"Conectado como {me.get('display_name') or me.get('id')} ({me.get('product', '?')})")
    try:
        pl = spotify.call("POST", "/me/playlists", {"name": "Chronify prueba", "public": False,
                                                    "description": "Prueba temporal, se borra sola"})
    except RuntimeError:
        pl = spotify.call("POST", f"/users/{me['id']}/playlists", {"name": "Chronify prueba", "public": False})
    pid = pl["id"]
    log(f"Lista de prueba creada ({pid})")
    try:
        for t in PISTAS:  # orden de añadido = PISTAS; luego se invierte para tener algo que ordenar
            spotify.call("POST", f"/playlists/{pid}/items", {"uris": [f"spotify:track:{t}"], "position": 0})
            time.sleep(2)
        antes = {x["id"]: x["added_at"] for x in spotify.items(pid)}
        orden_antes = [x["id"] for x in spotify.items(pid)]
        log(f"Añadidas 4 canciones. Orden actual (invertido): {orden_antes}")
        n = spotify.aplicar_orden(pid, PISTAS)
        despues_items = spotify.items(pid)
        despues = {x["id"]: x["added_at"] for x in despues_items}
        orden_ok = [x["id"] for x in despues_items] == PISTAS
        fechas_ok = antes == despues
        for t in PISTAS:
            log(f"  {t}: antes {antes[t]}  después {despues.get(t)}")
        res = {"movimientos": n, "orden_ok": orden_ok, "conserva_added_at": fechas_ok, "antes": antes, "despues": despues,
               "fecha": time.strftime("%Y-%m-%d %H:%M")}
        save_cache("prueba_spotify.json", res)
        log(f"{n} movimientos · orden correcto: {orden_ok} · conserva fecha de añadido: {fechas_ok}")
        return res
    finally:
        spotify.call("DELETE", f"/playlists/{pid}/followers")
        log("Lista de prueba borrada")


if __name__ == "__main__":
    probar()
