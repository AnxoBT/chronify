"""Chronify: ordena tus listas de Spotify por fecha real y comprueba que cuadran entre sí.

Es una web local que se abre en su propia ventana (Edge/Chrome/Chromium en modo app; si no hay, en el navegador).
Windows, Mac y Linux. Con el acceso directo
se ejecuta con pythonw (sin consola) y el servidor se apaga solo al cerrar la ventana.

Uso:
    python app.py                 # ventana propia
    python app.py --navegador     # pestaña normal del navegador
    python app.py --no-navegador  # solo el servidor (no se apaga solo)
    python app.py --puerto 8770
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
NAVEGADORES = [  # cualquiera con modo --app sirve (ventana sin barra de direcciones)
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),  # Mac
    Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
]
EN_PATH = ("msedge", "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")


def abrir(url, modo_app=True):
    if modo_app:
        exe = next((str(p) for p in NAVEGADORES if p.is_file()), None) or next(filter(None, map(shutil.which, EN_PATH)), None)
        if exe:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1200,860"])
            return
    webbrowser.open(url)


def ya_abierto(puerto):
    try:
        with urlopen(f"http://127.0.0.1:{puerto}/api/ping", timeout=2) as r:
            return json.loads(r.read()).get("app") == "chronify"
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-navegador", action="store_true")
    ap.add_argument("--navegador", action="store_true", help="pestaña normal en vez de ventana propia")
    ap.add_argument("--puerto", type=int, default=8766)
    ap.add_argument("--reinicio", action="store_true", help="tras actualizar: espera a que se cierre la anterior, sin abrir ventana")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.puerto}"

    if sys.stdout is None:  # pythonw (sin consola): la salida y los errores van a un archivo
        (ROOT / "cache").mkdir(exist_ok=True)
        sys.stdout = sys.stderr = open(ROOT / "cache" / "chronify.log", "a", encoding="utf-8", buffering=1)

    if args.reinicio:  # la instancia vieja se está apagando; la ventana abierta se recarga sola
        import time
        for _ in range(40):
            if not ya_abierto(args.puerto):
                break
            time.sleep(0.5)
        time.sleep(0.5)
        from web.server import serve
        print("Reiniciado tras actualizar")
        return serve(args.puerto, auto_apagar=True)

    if ya_abierto(args.puerto):  # doble clic con Chronify ya en marcha: solo abre otra ventana
        abrir(url, not args.navegador)
        return

    from threading import Timer
    from web.server import serve
    if not args.no_navegador:
        Timer(1.0, abrir, args=(url, not args.navegador)).start()
    serve(args.puerto, auto_apagar=not args.no_navegador)


if __name__ == "__main__":
    main()
