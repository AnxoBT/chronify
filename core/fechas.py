"""Fecha "real" de cada canción y clave de orden cronológico.

fechas.json guarda, por id de Spotify:
  fecha   'AAAA', 'AAAA-MM' o 'AAAA-MM-DD' (la mejor conocida de la versión original)
  fuente  'spotify' (coincide con lo que dice Spotify), 'orden' (deducida del orden verificado a mano),
          'musicbrainz', 'manual'
  aprox   true si es una estimación que conviene revisar
  orden   posición en el orden verificado (desempata canciones con la misma fecha)
  t       "Artista - Título" para que el archivo sea legible
  m       cuándo se cambió por última vez (al sincronizar PC y móvil gana el cambio más reciente)

Prioridad: manual > musicbrainz/orden/spotify guardado > fecha que da Spotify en el CSV.
"""
import re
import time

from core.config import fechas

SIN_ORDEN = 10 ** 9


def normalizar(f):
    """'1967' -> '1967-00-00' para que una fecha solo con año vaya antes que cualquier día de ese año."""
    f = (f or "").strip()
    if not re.match(r"^\d{4}", f):
        return "9999-99-99"
    partes = (f.split("-") + ["00", "00"])[:3]
    return "-".join(p.zfill(2) for p in partes)


def anio(f):
    return int(f[:4]) if f and f[:4].isdigit() else None


class Fechas:
    def __init__(self, data=None):
        self.data = data if data is not None else fechas()
        self.pistas = self.data.setdefault("pistas", {})

    def info(self, tid, pista=None):
        """(fecha, fuente, aprox) efectiva de una pista."""
        e = self.pistas.get(tid)
        if e and e.get("fecha"):
            return e["fecha"], e.get("fuente", "?"), bool(e.get("aprox"))
        if pista and pista.fecha_spotify:
            return pista.fecha_spotify, "spotify-sin-verificar", True
        return "", "desconocida", True

    def clave(self, tid, pista=None):
        f, _, _ = self.info(tid, pista)
        e = self.pistas.get(tid, {})
        return normalizar(f), e.get("orden", SIN_ORDEN), (pista.etiqueta().casefold() if pista else tid)

    def anio(self, tid, pista=None):
        return anio(self.info(tid, pista)[0])

    def fijar(self, tid, fecha, fuente="manual", pista=None, aprox=False):
        e = self.pistas.setdefault(tid, {})
        e.update(fecha=fecha, fuente=fuente, m=int(time.time()))  # m: cuándo (para sincronizar entre PC y móvil)
        if aprox:
            e["aprox"] = True
        else:
            e.pop("aprox", None)
        if pista:
            e["t"] = pista.etiqueta()
        return e
