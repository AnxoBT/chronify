"""Arranque de Chronify en Android (lo llama MainActivity a través de Chaquopy).

Los datos que la app modifica (fechas, reglas, artistas, .env, caché, zip importado) van en la carpeta
privada de la app: el código viene dentro del APK y se reemplaza en cada actualización.
"""
import os
import threading

ARRANCADO = threading.Event()


def arrancar(datos, puerto=8766, secreto=""):
    if ARRANCADO.is_set():
        return
    os.environ["CHRONIFY_DATOS"] = datos  # antes de importar core.config
    os.environ["CHRONIFY_ANDROID"] = "1"
    os.environ["CHRONIFY_SECRETO"] = secreto  # el servidor solo contesta a quien la tenga (web/server.py)
    from core import actualizar
    actualizar.fusionar_semillas()  # fechas y artistas que trae esta versión del APK
    from web import server
    threading.Thread(target=server.serve, args=(puerto, False), daemon=True, name="chronify").start()
    ARRANCADO.set()
