"""Peticiones HTTPS (compartido por Spotify, MusicBrainz, ListenBrainz y las actualizaciones).

En el PC y Android: urlopen, con un reintento en Windows si falta el certificado raíz.
En la versión web (Pyodide, en el navegador) no hay sockets: `web/navegador.py` pone en TRANSPORTE una función
que hace la petición con XMLHttpRequest síncrono (dentro de un Web Worker) y devuelve lo mismo que urlopen.
"""
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen

TRANSPORTE = [None]  # versión web: función (req, timeout) → respuesta tipo urlopen


def _raiz_windows(url):
    """Windows descarga los certificados raíz bajo demanda, pero Python solo ve los que ya están en el almacén.

    accounts.spotify.com usa una CA (Certainly) que puede no estar todavía: una petición con PowerShell
    (que usa el verificador de Windows) hace que Windows la instale y Python ya la encuentra al reintentar.
    """
    if sys.platform != "win32":
        return False
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Invoke-WebRequest -UseBasicParsing -Method Head -TimeoutSec 20 -Uri '{url}' | Out-Null"],
                       capture_output=True, timeout=40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def abrir(req, timeout=30):
    """urlopen con un reintento si falla el certificado (ver _raiz_windows)."""
    if TRANSPORTE[0]:
        return TRANSPORTE[0](req, timeout)
    try:
        return urlopen(req, timeout=timeout)
    except URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e) or not _raiz_windows(req.full_url.split("?")[0]):
            raise
        return urlopen(req, timeout=timeout)
