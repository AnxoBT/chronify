# Cambios

## v1.1.1 — 2026-11-17

- La lista "Canciones que te gustan · por fecha" se renombra en Spotify al cambiar el idioma de la app, y las listas
  que crea Chronify no cuentan en Estadísticas aunque las renombres o vengan con su nombre anterior en un zip viejo.
- Crear listas en Spotify usa el método alternativo solo cuando el normal no está disponible; los errores de sesión,
  de límite o del servidor de Spotify se avisan tal cual.
- Más avisos traducidos al inglés (errores de sincronización y por Wi-Fi, contador de canciones).
- Seguridad: política para avisar de fallos en privado y avisos automáticos de dependencias.

## v1.1.0 — 2026-11-16

- **Versión buena**: en Comprobaciones, las canciones en directo, remezcladas, de recopilatorio o reediciones dicen cuál es
  el disco original (según MusicBrainz, gratis y sin cuenta) y, si lees por la API, cuál es esa versión en Spotify, con
  botón para escucharla y para cambiarla en todas tus listas (mismo sitio y misma fecha). Sin la API, enlace para
  buscarla en Spotify. Lo ya buscado no se vuelve a buscar.
- **Canciones que ya no están en Spotify** (salen en gris): nuevo aviso en Comprobaciones (leyendo por la API).
  Si Spotify cambió tu copia por otra que sí suena, se sigue reconociendo la tuya.
- Los enlaces a canciones abren la **app de Spotify** del PC si la tienes instalada.
- "La misma canción dos veces" detecta también títulos con el nombre alternativo entre paréntesis
  (p. ej. *Bang A Gong (Get It On)* y *Get It On*).

## v1.0.1 — 2026-11-13

- Al corregir el país de un artista en Estadísticas, el mapa y los rankings se actualizan solos (sin salir de la
  pestaña ni perder la posición). Al marcar una fecha como correcta se actualizan también Comprobaciones y Resumen.
- La lista "Canciones que te gustan · por fecha" se crea con el nombre en el idioma de la app ("Liked Songs · by date")
  y ya no se cuenta como una lista más (no duplica canciones en Estadísticas ni en Comprobaciones).
- Listas ignoradas: se reconocen aunque el nombre del CSV de Exportify lleve guiones bajos o sin tildes.
- Crear listas en Spotify solo usa el método antiguo si el nuevo no existe.

## v1.0.0 — 2026-11-13

Primera versión pública.

- **Sincronizar por Wi-Fi** (Ajustes), en casa y sin cable: uno de los dos espera y enseña su dirección y un código, y
  el otro se conecta. Hace lo mismo que por USB: junta los datos de los dos en ambos sentidos, pasa el zip de Exportify
  más nuevo y la versión nueva de la app al móvil. Todo va cifrado con el código, que solo sirve una vez y 2 minutos.
- **Novedades al actualizar**: la primera vez que abres Chronify después de una actualización, una ventana resume
  qué ha cambiado desde tu versión.
- **Guía de inicio**: cuatro pasos la primera vez que abres Chronify en cada dispositivo, con selector de idioma; se
  puede volver a ver en Ajustes.
- **Ordenar por fecha real** cualquier lista de Spotify: copiar y pegar en el Spotify del PC o (con Premium)
  aplicarlo por la API, que *mueve* las canciones sin borrarlas y conserva la fecha en que las añadiste.
- **Comprobaciones**: repetidas, la misma canción en ediciones distintas, directos, remixes, recopilatorios y copias
  poco escuchadas, con botón para cambiarlas por la principal.
- **Tus listas**: Mix formado por otras listas, épocas, géneros, listas fijas o ignoradas, con sugerencias y arreglos
  de un toque. **Canciones que te gustan** ordenadas por fecha en una lista nueva.
- **Fechas** propuestas por MusicBrainz para canciones sin fecha verificada, y **conocimiento compartido** (fechas y
  países) que viene con cada versión; lo que corriges tú siempre manda.
- **Estadísticas**: mapa, años, décadas, artistas, géneros, ánimo, ritmo, tonalidades, popularidad, artistas de
  nicho, "tu año" y evolución mensual.
- **Historial** con deshacer, **copia de seguridad** y sincronización PC ↔ móvil por USB.
- En **Windows, macOS y Linux** (Python), **Android** y en el **navegador** (también iPhone), en español e inglés,
  con bienvenida para empezar y aviso de versiones nuevas.
