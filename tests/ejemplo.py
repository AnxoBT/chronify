"""Zip de Exportify inventado: otra persona, con sus propias listas, para probar Chronify sin datos reales.

- "Mis favoritas": canciones que Chronify ya conoce (fechas.json) y una desconocida, desordenadas, una repetida.
- "Rock": subconjunto.
- "Liked_Songs": canciones que te gustan (solo lectura).
- "Lista de otro": añadida por otra cuenta (se descarta entera).
Uso: python -m tests.ejemplo salida/ejemplo_exportify.zip
"""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLUMNAS = ["Track URI", "ISRC", "Track Name", "Album Name", "Artist Name(s)", "Release Date", "Duration (ms)",
            "Popularity", "Explicit", "Added By", "Added At", "Genres", "Record Label", "Danceability", "Energy", "Key",
            "Loudness", "Mode", "Speechiness", "Acousticness", "Instrumentalness", "Liveness", "Valence", "Tempo",
            "Time Signature"]
YO, OTRO = "spotify:user:persona_de_prueba", "spotify:user:otra_persona"


def _conocidas(n):
    """Canciones de fechas.json con fecha verificada (las de cualquier usuario que coincidan se benefician)."""
    pistas = json.loads((ROOT / "fechas.json").read_text(encoding="utf-8"))["pistas"]
    out = []
    for tid, v in pistas.items():
        if v.get("fuente") in ("manual", "musicbrainz") and " - " in v.get("t", ""):
            artista, titulo = v["t"].split(" - ", 1)
            out.append((tid, titulo, artista, v["fecha"]))
        if len(out) == n:
            break
    return out


def _fila(tid, titulo, artista, fecha, autor, i):
    return {"Track URI": f"spotify:track:{tid}", "ISRC": "", "Track Name": titulo, "Album Name": titulo,
            "Artist Name(s)": artista, "Release Date": fecha[:4] + "-01-01", "Duration (ms)": 200000 + i * 1000,
            "Popularity": 50, "Explicit": "false", "Added By": autor, "Added At": f"2025-0{1 + i % 9}-1{i % 9}T10:00:00Z",
            "Genres": "rock,pop", "Record Label": "", "Danceability": 0.5, "Energy": 0.6, "Key": i % 12,
            "Loudness": -6, "Mode": 1, "Speechiness": 0.05, "Acousticness": 0.1, "Instrumentalness": 0,
            "Liveness": 0.1, "Valence": 0.5, "Tempo": 120, "Time Signature": 4}


def _csv(filas):
    b = io.StringIO()
    w = csv.DictWriter(b, COLUMNAS)
    w.writeheader()
    w.writerows(filas)
    return b.getvalue()


def zip_ejemplo():
    con = _conocidas(12)
    nueva = ("0000000000000000000000", "Canción Nueva Inventada", "Artista Inventado", "2024")
    favs = [*reversed(con[:10]), nueva, con[0]]  # al revés (desordenada), una desconocida y una repetida
    listas = {
        "Mis favoritas": [_fila(*c, YO, i) for i, c in enumerate(favs)],
        "Rock": [_fila(*c, YO, i) for i, c in enumerate(con[2:6])],
        "Liked_Songs": [_fila(*c, YO, i) for i, c in enumerate(con[5:12])],
        "Lista de otro": [_fila(*c, OTRO, i) for i, c in enumerate(con[:4])],
    }
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for nombre, filas in listas.items():
            z.writestr(nombre + ".csv", _csv(filas))
    return b.getvalue()


if __name__ == "__main__":
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "salida" / "spotify_playlists.zip")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(zip_ejemplo())
    print(destino)
