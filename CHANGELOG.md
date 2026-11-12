# Cambios

## v1.6.0 — 2026-11-12

- **Versión web** (iPhone, iPad, Mac, Linux y cualquier navegador): la misma app, sin instalar nada, en
  https://anxobt.github.io/chronify/. El mismo código Python funciona dentro del navegador (Pyodide); tus datos se
  guardan en ese navegador, funciona sin conexión y se puede añadir a la pantalla de inicio. Progreso y cancelar en
  las tareas largas, pantalla encendida mientras trabajan.
- **Cualquier cuenta de Spotify**: si la cuenta no tiene Premium o no está autorizada en la app de Spotify, Chronify
  lo explica (en vez de un error 403) y no intenta leer de la API; todo lo demás sigue con Exportify.
- **Restaurar copia** (Ajustes): también sirve para pasar tus datos entre dispositivos (PC ↔ web). En la web la copia
  se descarga.
- En el móvil, **desliza a izquierda o derecha para cambiar de pestaña**.
- Mac y Linux: `Abrir Chronify.command` y ventana propia con Chrome/Edge/Chromium.
- Las actualizaciones ya no necesitan token de GitHub (repo público).
- **Seguridad**: el servidor local del PC y de Android rechaza peticiones de otras webs (Host, Origin y cabecera
  propia en cada cambio) y, en Android, de otras apps (clave secreta por arranque). Restaurar una copia solo escribe
  tus datos (nunca código ni fuera de su carpeta) y limita el tamaño. La web sirve Pyodide desde la propia web,
  verificado con su firma, en vez de una CDN.
- Sincronizar con el móvil funciona aunque haya también un emulador conectado.
- README en inglés y español, plantillas de incidencias y publicación automática de la web.

## v1.5.0 — 2026-11-11

- **Sirve para cualquiera**: sin configurar nada ordena cualquier lista por fecha real. **Ajustes → Tus listas**
  para decir qué es cada lista (Mix y las que lo forman, épocas con sus años, géneros, no reordenar, ignorar) y
  activar las comprobaciones entre listas. Tus listas y excepciones (`rules.json`) ya no van en el repo: son tuyas.
- **Conocimiento compartido**: cada versión trae las fechas verificadas, los países de los artistas y los datos de
  MusicBrainz/ListenBrainz ya buscados (`conocimiento/`); se añaden a lo tuyo sin pisarlo. Lo que corriges tú manda.
- README nuevo para instalar y empezar (PC y móvil), con los pasos para conectar tu propia app de Spotify.
- **Lee de Spotify al abrir** (si está conectado) y solo descarga las listas que han cambiado desde la última vez
  (cada lista trae una marca de versión; las canciones que te gustan se comparan por las últimas añadidas). Sin
  cambios tarda un segundo. El zip de Exportify sigue sirviendo para géneros y datos de audio.
- **Copia de seguridad** (Ajustes del PC): .env, caché, zips de Exportify y la clave de firma del APK en
  Documentos/Chronify copias. Se hace sola cada semana; se guardan las 5 últimas. Restaurar:
  `python -m core.copia restaurar <zip>`.
- Límite diario propio de 450 cambios (antes 500): Spotify también cuenta las lecturas. Con el cupo gastado no
  se lee sola al abrir.
- Al ordenar, el registro ya no pierde los mensajes de "ordenada" tras la primera lista.
- La interfaz se ha partido en varios archivos (estilos y JS por partes): mismo aspecto, más fácil de mantener.

## v1.4.0 — 2026-11-11

- **Versión para Android (APK)**: la misma app en el móvil, con la interfaz adaptada (pestañas desplazables,
  tarjetas en dos columnas, gráficas legibles, zoom del mapa con dos dedos). Login de Spotify por el navegador,
  enlaces a canciones en la app de Spotify, pantalla encendida mientras haya una tarea larga e icono negro.
- **Sincronizar PC ↔ móvil por USB** (Ajustes del PC): fechas, reglas, excepciones, países de artistas, ajustes,
  sesión de Spotify, límite diario, historial y fotos mensuales. Le pasa al móvil el zip de Exportify más
  reciente y le instala la versión nueva de Chronify si la del PC es más nueva. Tus datos no pasan por internet.
- **Importar zip…**: elegir el zip de Exportify desde cualquier carpeta (en el móvil es la forma de cargarlo).
- Cada release trae el zip del PC y el APK del móvil.
- Arreglado: al fusionar reglas el texto de las excepciones se partía en letras.

## v1.3.0 — 2026-11-11

- **Estadísticas**: pestaña nueva con cifras clave, canciones por año, mapa del mundo por país del artista
  (con ranking y corrección a mano), top artistas, solistas/grupos y mujeres/hombres, edad al sacar la
  canción, géneros por década, idiomas, ánimo (alegría × energía), ritmo, tonalidades, popularidad, duración,
  cuándo añades música, lo más de nicho (oyentes de cada artista en ListenBrainz) y curiosidades. Se puede
  ver por lista. País del artista = lugar de nacimiento o de formación (MusicBrainz), con desempate de
  artistas con el mismo nombre por tus canciones y búsqueda también por alias (Kanye West → Ye).
- **Límite diario** de cambios en Spotify (500 en 24 h) para que no bloquee la app; al llegar se para y el
  aviso *Seguir* continúa otro día desde donde se quedó. Botón *Ordenar todas en Spotify* con estimación de días.
- Ordenar avisa de canciones con la fecha de Spotify **sin verificar** y no las coloca salvo que lo pidas.
- **Versiones dudosas**: avisa de directos, remixes/edits, recopilatorios, reediciones y copias poco
  escuchadas (popularidad 0–5: Spotify tiene otra copia de la canción) (botón *es la buena*).
- **Sugerencias** de lista de género (según dónde están otras canciones del artista) y de época, con botón
  *añadir a …*.
- **Historial** de cambios (fechas, países, excepciones, Spotify) con *deshacer*.
- **Copias poco escuchadas → versión buena**: busca en Spotify (por ISRC y por título) la copia principal de
  la canción y la cambia en todas tus listas, en el mismo sitio, conservando su fecha verificada (respeta el
  límite diario y se sigue otro día).
- Aviso de **la misma canción dos veces** en Mix con ids distintos (mismo ISRC o mismo artista y título).
- **Tu año**: resumen de cada año según lo que añadiste (canciones, artistas y países que descubriste, mes a
  mes, décadas, géneros, primera y última). **Evolución mes a mes**: una foto de tus cifras cada mes.

## v1.2.0 — 2026-11-09

- **Fechas revisadas**: comprobadas una a una todas las canciones (web + Wikipedia/Discogs); ~470
  corregidas a mano. Criterio: remaster, directo, regrabación o remezcla del mismo artista → fecha de la
  canción original; cover de otro artista → fecha de esa versión.
- **Mover de época**: en Comprobaciones, botón *mover a …* que pasa una canción a la lista de época que
  le toca (la añade en su sitio cronológico y la quita de la otra). Solo leyendo de Spotify.
- **Protección contra bloqueos de Spotify**: peticiones espaciadas (1/s al escribir), y si Spotify bloquea
  la app se para con un aviso de hasta cuándo en vez de quedarse colgada. Las listas leídas a medias dan
  error en vez de usarse.
- Ordenar mueve bloques de canciones seguidas en una sola petición cuando puede.
- Nueva lista de género **Jazz**.
- Logo nuevo sin fondo: reloj de bolsillo con el disco y las ondas de Spotify.

## v1.1.0 — 2026-11-09

- **Actualizaciones**: aviso de versión nueva con novedades y botón *Actualizar ahora* (descarga la
  release, instala conservando `.env`, caché, fechas y excepciones, y se reinicia). Con `git clone` usa
  `git pull`. Token de GitHub en Ajustes si el PC no tiene Git/GitHub CLI con la cuenta.
- Las barras de progreso (MusicBrainz, ordenar en Spotify) salen al instante, sin recargar; al acabar
  de ordenar la lista se refresca sola. El progreso de ordenar también se ve en la pestaña Ordenar.
- Ajustes muestra el último error al conectar con Spotify (antes solo salía en la página de vuelta).

## v1.0.0 — 2026-11-06

Primera versión.

- Lectura del zip *Export All* de Exportify (o CSV sueltos) desde Descargas; listas de otros usuarios
  descartadas; `DJ` y `Saved_Albums` ignoradas; `Liked_Songs` solo lectura.
- Lectura directa por la Web API de Spotify (OAuth PKCE, solo Client ID).
- Comprobaciones: Mix = idiomas, épocas, géneros, duplicados, fechas sin verificar; excepciones.
- Orden cronológico por fecha real (`fechas.json`), txt para pegar en Spotify y **aplicar en Spotify**
  moviendo canciones (movimientos mínimos; conserva la fecha de añadido, verificado con lista desechable).
- Propuestas de fecha original con MusicBrainz (ISRC, título, singles), con aviso de propuestas dudosas.
- Pestaña Ajustes: Client ID, conectar/desconectar, prueba, carpetas.
- Ventana propia sin consola, se apaga sola al cerrarla; acceso directo con logo.
- Instalador `Abrir Chronify.bat`: instala Python con winget si falta y crea el acceso directo.
