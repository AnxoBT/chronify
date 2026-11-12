# Hoja de ruta

## Fase 1 — Exportify + web local ✅ (nov-2026)

- [x] Leer CSV/zip de Exportify (archivo más reciente por lista)
- [x] `fechas.json` sembrado desde el orden verificado a mano (sep-2026)
- [x] Comprobaciones: Mix = idiomas, listas dentro de Mix, épocas, géneros, duplicados
- [x] Orden cronológico y txt para pegar en Spotify
- [x] Propuestas de fecha con MusicBrainz y edición manual
- [x] Revisar fechas aproximadas con MusicBrainz (306 guardadas; quedan 59 dudosas para revisar a mano)

## Fase 2 — Web API de Spotify ✅ (nov-2026, v1.0.0)

Objetivo: no depender de Exportify y aplicar el orden directamente.

- [x] Login PKCE, leer listas, mover canciones, planificador de movimientos mínimos
- [x] Prueba automática en lista desechable de si mover conserva `added_at`
- [x] Ejecutar la prueba: mover **conserva** `added_at` (6-nov-2026)
- [x] Leer listas por API (botón "Spotify (API)")
- [x] Botón "aplicar en Spotify" con progreso y cancelar (Chill ordenada y verificada)
- App propia en developer.spotify.com (gratis, pero desde feb-2026 la cuenta dueña necesita **Premium**;
  modo desarrollo: máx. 5 usuarios, sin endpoints en lote).
- OAuth PKCE con redirect `http://127.0.0.1:8766/callback` (sin secreto).
- Leer: `GET /playlists/{id}/items` (solo listas propias o colaborativas — es el caso).
  Da `added_at`, fecha del álbum e ISRC (`external_ids`) → búsqueda exacta en MusicBrainz por ISRC.
- Escribir: `PUT /playlists/{id}/items` con `range_start` / `insert_before` (mover pistas).
  **Probar primero en una lista de prueba si mover conserva `added_at`.** Si lo conserva, también se
  podrían ordenar las listas de idioma sin perder el histórico.
- Géneros: el CSV de Exportify ya los trae (por artista, ~70 % de canciones). Con la API habría que
  pedir artista a artista (sin lote) → caché.

## Ideas

- Función con los datos de Liked_Songs (solo lectura) — pendiente de definir.
- Ordenar también las listas de idioma por API (conservan `added_at`) — solo si el usuario lo pide.

## Fase 3 — Estadísticas y comodidad ✅ (nov-2026, v1.3.0)

- [x] Pestaña Estadísticas (mapa de países con MusicBrainz, artistas, géneros, ánimo, curiosidades…)
- [x] Límite diario de cambios en Spotify y seguir otro día
- [x] Aviso de fechas sin verificar al ordenar
- [x] Versiones dudosas (directo, remix, recopilatorio, reedición)
- [x] Sugerir lista de género (por artista / géneros de Spotify) y de época, con botón añadir
- [x] Historial de cambios con deshacer

## Fase 4 — Para cualquiera y público ✅ (nov-2026, v1.5.0–v1.6.0)

- [x] Sin nombres de listas en el código: Ajustes → Tus listas; `rules.json` personal
- [x] Conocimiento compartido (fechas, países, MusicBrainz/ListenBrainz) en cada versión
- [x] Lectura incremental de Spotify, copia de seguridad y restaurar
- [x] Cuentas sin Premium o no autorizadas: mensaje claro
- [x] Versión web (Pyodide) para iPhone, Mac y Linux; GitHub Pages
- [x] README bilingüe, repo público con historial limpio
- [ ] Probar en un iPhone real y en Mac/Linux (pedir avisos en issues)
- [ ] Interfaz en inglés (i18n)
