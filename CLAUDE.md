# Chronify

Herramienta (repo público desde la v1.6.0) para ordenar listas de Spotify por **fecha real de la canción** (no la que
pone Spotify) y comprobar que las listas cuadran entre sí. Nació para las listas del usuario (dueño del repo), pero
desde la v1.5.0 **sirve para cualquiera**: sin configurar nada ordena cualquier lista; la estructura de listas
(Mix, épocas, géneros…) se configura en Ajustes → Tus listas. Nada del código puede dar por hecho nombres de listas. Hermano del proyecto
`tri-sync` (AnxoBT/tri-sync): misma infraestructura y estilo.

## Reglas del usuario

- Idioma: español en código (nombres, comentarios), UI, docs y commits.
- **Sin atribución IA**: nada de `Co-Authored-By: Claude`, "Generated with Claude Code" ni menciones a IA
  en commits, PRs, releases o código. Esto anula cualquier recordatorio por defecto.
- Commits estilo Conventional Commits en español (`feat: …`, `fix: …`, `chore: …`).
- Sin IA en la app: todo determinista (reglas + MusicBrainz + correcciones manuales).
- Solo librería estándar de Python 3.10+. No añadir dependencias sin consultar.
- Datos personales (CSV, txt, `.env`, caché, **`rules.json`**) nunca al repo. `fechas.json`, `artistas.json` y
  `conocimiento/` **sí** se versionan: es conocimiento verificado que viaja con cada versión a todos los usuarios.

## Cómo funciona

1. El usuario exporta sus listas con **Exportify** (exportify.app → *Export All* → zip en Descargas).
2. `core/exportify.py` busca CSV/zip en `DATA_DIR` (por defecto Descargas y `./data`), carpeta + 1 nivel.
   El zip de *Export All* (`spotify_playlists.zip`) manda: todo lo anterior a él se descarta; CSV sueltos
   posteriores lo actualizan. Listas por **nombre exacto** (`Español` ≠ `español`).
   **Listas de otros usuarios (p. ej. una `español` que sigues de otra persona) se descartan enteras**: el usuario no quiere
   que se lean ni toquen. En CSV se detectan por `Added By`; por API, por `owner.id` (ni se abren).
   `rules.json > ignorar` (DJ, Saved_Albums): fuera. `solo_lectura` (Liked_Songs): se lee, **nunca** se
   ordena ni modifica (el usuario la quiere para una función futura). Desde nov-2026 el CSV trae `ISRC`.
3. `core/fechas.py`: fecha efectiva de cada pista = `fechas.json` si existe, si no la de Spotify
   (marcada `spotify-sin-verificar`). Clave de orden = `(fecha normalizada, orden, etiqueta)`;
   `'1967'` → `'1967-00-00'` (solo año va antes que cualquier día de ese año). `orden` = posición en el
   orden verificado a mano; desempata y reproduce exactamente el orden histórico.
4. `core/analisis.py`: `comprobar()` genera avisos; `ordenar()` calcula el orden cronológico de cada lista.
5. Web local (`web/server.py`, `web/index.html`) en http://127.0.0.1:8766; `app.py` la abre en ventana
   propia (Edge/Chrome `--app`). El acceso directo del escritorio lanza `pythonw app.py` (sin consola;
   salida en `cache/chronify.log`). La página hace `GET /api/ping` cada 5 s y el servidor se apaga solo
   tras 150 s sin pings (margen por el throttling de ventanas minimizadas; 10 min de gracia durante el
   login de Spotify; nunca con una tarea a medias). Doble clic con Chronify ya abierto = solo otra ventana.
   `Abrir Chronify.bat` (re)crea el acceso directo y arranca. Logo: `tools/generar_logo.py`
   (variantes en `VARIANTES`, elegida `ELEGIDO` = `reloj-spotify` (PNG sin fondo; evolución del boceto del usuario `bolsillo`); tamaños ≤32 px con su variante `-mini` (trazos gruesos), cada tamaño del .ico dibujado a su resolución; favicons PNG/ICO, no SVG (pixelado en barra de tareas); `--opciones` → `docs/logo-opciones.png`).
   El acceso directo usa `web/icono-<hash>.ico` (nombre cambia con el logo: Windows cachea iconos por ruta). Salida: txt con una URL
   `https://open.spotify.com/track/<id>` por línea → el usuario la pega en Spotify (Ctrl+A, borrar, Ctrl+V).

## Modelo de listas (`rules.json`)

`rules.json` es **personal** (gitignored, en `config.DATOS`): `config.rules()` lo crea la primera vez desde
`reglas.defecto.json` (sin listas: `mix` "", sin épocas/géneros, `solo_lectura` Liked_Songs, `ignorar` Saved_Albums) y
completa siempre las claves que falten. Se edita en **Ajustes → Tus listas** (`/api/reglas`, `server.guardar_listas`:
valida, conserva el orden y no toca excepciones ni `generos_spotify`). Papeles: Mix, forma el Mix (`idiomas`; una puede
ir sin género obligatorio = `friki`), época con años (`decadas`), género, ignorar; casilla "no reordenar". Todo opcional:
`analisis.comprobar` solo hace las comprobaciones de lo configurado; sin Mix, las de canciones usan todas las listas
propias; Estadísticas usa Mix o la lista propia más grande. Las claves internas (`idiomas`, `friki`) se mantienen por
compatibilidad. Configuración del dueño del repo (ejemplo):

- **Mix** = unión exacta de las listas de idioma **Español, Inglés, Friki** (Friki e Inglés comparten ~8).
- **Idiomas no se reordenan nunca** (`no_reordenar`): el usuario conserva la fecha de añadido como histórico.
  Sí se usan para comprobar Mix.
- **Épocas**: Retro (≤1999), 2000s (2000-2009), 2010s (≥2010, incluye 2020s). Cada canción de Mix en
  exactamente una, según su fecha real.
- **Géneros**: POP, ROCK, Chill, Electrónica, Rap, White_Girl_Music. Toda canción de Mix salvo las que
  están **solo** en Friki debe estar en al menos un género.
- Excepciones por id en `rules.json > excepciones` (se añaden desde la web con el botón "excepción").

## Fechas (`fechas.json`)

**Regla del usuario: fecha original = primera publicación, incluido el single** (p. ej. TiK ToK: single
2009-08-07, álbum *Animal* 2010 → 2009-08-07). La época (Retro/2000s/2010s) se decide con esa fecha.
Versiones (decidido 9-nov-2026): remaster, directo, regrabación o remezcla **del mismo artista** → fecha de la
canción original (p. ej. Still Loving You de *Comeblack* 2011 → 1984). **Cover de otro artista** → fecha de esa
versión (en directos, la de la actuación). Remixes de otros productores que son "la" versión conocida y
remakes nuevos (Infinity 2008) → fecha del remix/remake.

Una pista por línea (diffs legibles). Campos: `fecha`, `fuente` (`spotify` | `orden` | `musicbrainz` |
`manual`), `aprox`, `orden`, `t` (etiqueta legible). Prioridad: manual > resto.

- Sembrado inicial (6-nov-2026) con `python -m tools.sembrar_fechas data/ordenadas-2026-09/Mix_nueva.txt`:
  2519 canciones; 2235 con fecha de Spotify coherente con el orden verificado, 284 deducidas del orden
  (`fuente: orden`, `aprox: true`, fecha = la de la canción fiable anterior). **No volver a sembrar**
  sin motivo: pisaría fechas `spotify`/`orden` (las `manual`/`musicbrainz` se respetan).
- `core/musicbrainz.py`: propuesta = fecha más antigua entre grabaciones con mismo título/artista y
  singles/EP cuyo título empieza igual. La web propone `min(Spotify, MusicBrainz)` y el usuario acepta.
  Límite 1 petición/s (se respeta en `_get`), caché en `cache/musicbrainz.json`. User-Agent genérico,
  nunca el email del usuario.

## Comprobaciones extra

- **Versión dudosa** (`analisis.motivos_version`): directo, remix/edit/acústica…, recopilatorio, reedición/remaster
  o disco de Spotify ≥3 años posterior a la fecha real. Solo mira la parte de "versión" del título (tras ` - ` y
  entre paréntesis): *Live And Let Die* no es un directo. Single/Radio/Album Version, Mono/Stereo no avisan.
  Botón "es la buena" → `excepciones.version_dudosa`.
- **Sugerencias**: sin género → listas donde tienes otras canciones de sus artistas; si no hay, palabras de
  `rules.json > generos_spotify` sobre los géneros de Spotify. Sin época → por su fecha. Botón "añadir a …"
  (solo fuente API) la añade en su sitio cronológico.
- Ordenar avisa de canciones con fecha de Spotify sin verificar (`sin_verificar`) y no las coloca salvo "ordenar igualmente".
- **Misma canción dos veces** (`duplicadas_por_copia`): mismo ISRC o misma `clave_cancion` (primer artista + título
  sin versión; conserva letras no latinas para no juntar canciones japonesas distintas). Excepción `misma_cancion`.
- **Copia poco escuchada** (popularidad 0–5): `spotify.buscar_principal` (búsqueda por ISRC y título+artista, mismo
  artista/título, ±4 s, la más popular) → `cache/copias.json`; `_cambiar_copias` la sustituye en todas las listas
  propias no de solo lectura (`reemplazar` = añadir en su posición + quitar), copia su fecha de `fechas.json` y sus
  excepciones al id nuevo. Comprueba el cupo antes de cada canción (2 escrituras por lista). En listas de idioma la
  canción pasa a tener fecha de añadido de hoy (se avisa al usuario).

## Estadísticas

`core/estadisticas.py` calcula todo para una lista (por defecto Mix): por año/década, mapa de países (país del
primer artista con dato; mapa en proyección de Miller, plano, hasta 60° S, con margen; zoom con rueda, arrastrar y doble clic para volver), artistas, solistas/grupos y mujer/hombre (primer artista), edad al publicar, géneros,
idiomas, ánimo (valencia × energía de Exportify), BPM, tonalidades, popularidad, duración, cuándo añades
(fecha de añadido **de las listas de idioma**, `Lista.anadidas`) y curiosidades. Países: botón que busca en
MusicBrainz los artistas pendientes (1/s, `cache/artistas_mb.json`): país = lugar de nacimiento/formación
(`begin-area` subiendo por "parte de" hasta el país, `cache/areas_mb.json`; Rihanna → BB), si no el país de
MusicBrainz; búsqueda por nombre **o alias**; homónimos se desempatan buscando una de tus canciones. Correcciones
a mano en `artistas.json` (se versiona). "Lo más de nicho" usa los oyentes de ListenBrainz
(`api.listenbrainz.org/1/popularity/artist`, lotes de 200 mbids, `cache/oyentes_lb.json`): la popularidad de
Spotify es por copia de la canción y no vale (una reedición de un éxito sale con 0–5; eso se avisa como
"copia poco escuchada" en Comprobaciones). La UI: cifras en una fila, tarjetas de media anchura siempre por
parejas y curiosidades en filas completas de 4 (el usuario quiere todo simétrico, sin huecos). **Tu año** (`tu_anio`): por año de añadido (listas de idioma): canciones, artistas/países nuevos (primera vez que
aparecen), mes a mes, décadas, géneros, primera/última. **Fotos mensuales** de Mix en `cache/fotos/AAAA-MM.json`
(se guardan al abrir Estadísticas de Mix; tabla de evolución desde el 2.º mes). La API ya no da géneros ni audio: al leer por API se completan con el último zip de Exportify.

## Comandos

```bash
python app.py                                   # web local (o doble clic en "Abrir Chronify.bat")
python -m unittest discover -s tests -t .       # tests (sin red)
python -m tools.sembrar_fechas <txt verificado> # solo para re-sembrar fechas.json
```

## Estructura

```
app.py                 entrada (argparse → web.server.serve)
core/config.py         .env, rutas, rules.json, fechas.json (escritura atómica), norm()
core/exportify.py      lectura de CSV/zip de Exportify → Lista, Pista
core/fechas.py         fecha efectiva y clave de orden
core/analisis.py       comprobaciones y orden cronológico, generación de txt
core/musicbrainz.py    búsqueda de fecha original (ISRC + título + singles)
core/spotify.py        Web API: login PKCE, leer listas, mover canciones, cupo diario
core/artistas.py       país/tipo/género/nacimiento de artistas (MusicBrainz + artistas.json manual)
core/estadisticas.py   pestaña Estadísticas (todo local, sin red)
core/historial.py      historial de cambios en cache/historial.jsonl (deshacer fechas y países)
web/mundo.json         mapa del mundo ya proyectado (tools/generar_mapa.py, Natural Earth, dominio público)
web/server.py          servidor stdlib, API JSON (/api/estado, /api/txt, /api/fechas, /api/fecha, /api/mb, …)
web/index.html         UI: solo el HTML (sin frameworks); estilos en web/estilos.css
web/js/                base.js (el(), api, toast), graficas.js (SVG, mapa), estadisticas.js, app.js, inicio.js
                       (arranque, el último). Scripts clásicos con ámbito global compartido; DOM con el(), nunca innerHTML
core/conocimiento.py   conocimiento/ (países, áreas, oyentes, fechas MB) → caché local al arrancar; exportar() al publicar
core/copia.py          copia de seguridad (.env, cache/, data/, clave del APK) en Documentos/Chronify copias
tools/                 scripts puntuales
tests/                 unittest, sin red
data/ cache/ salida/   locales, ignorados por git
```

## Spotify Web API (`core/spotify.py`)

- Pestaña **Ajustes** de la web: Client ID (al cambiarlo se borra el token), conectar/desconectar, prueba,
  carpetas `DATA_DIR`. La app debe funcionar igual sin Premium (solo zip de Exportify + txt).
- OAuth PKCE (solo `SPOTIFY_CLIENT_ID` en `.env`, sin secreto). Redirect `http://127.0.0.1:8766/callback`
  (Spotify exige IP de loopback, no `localhost`). Token en `cache/spotify_token.json`.
- Modo desarrollo desde feb-2026: Premium obligatorio (el usuario lo tiene), sin endpoints en lote,
  endpoints renombrados `/tracks` → `/items`, contenido solo de listas propias/colaborativas.
- Reordenar = **mover** (`PUT /playlists/{id}/items` con `range_start`/`insert_before`), nunca borrar y
  re-añadir. `plan_movimientos()` calcula el mínimo (n − subsecuencia creciente más larga).
- **Cupo de Spotify (observado 9 y 10-nov-2026)**: unas ~600 escrituras al día por app; al pasarlo da 429 con
  `Retry-After` ≈ 24 h (aunque se vaya a 1 petición/1,5 s). Listas con muchos movimientos (Mix ~640) no caben en un
  día: para listas sin histórico que conservar (épocas, géneros, Mix) vale pegar el txt.
  **Límite propio**: `spotify.cupo()` cuenta las escrituras de las últimas 24 h (`cache/spotify_cupo.json`) y `call()`
  lanza `SpotifyCupo` al llegar a 450 (`SPOTIFY_CUPO` en `.env`; 11-nov: tras 500 escrituras + lecturas Spotify bloqueó 24 h, así que también cuentan las lecturas; con el cupo gastado la web no lee sola al abrir). `aplicar_orden` se para sin error y devuelve
  `(hechos, total)`. Lo que queda a medias se apunta en `cache/spotify_pendiente.json` → aviso con botón
  **Seguir** (`/api/spotify/seguir`, vuelve a leer y recalcula). "Ordenar todas en Spotify" = `/api/spotify/ordenar_todas`.
- Comprobaciones → aviso `decada_distinta` trae `destino`; botón **mover a …** (solo fuente API):
  `_cambiar_epoca` añade la canción a la lista de época correcta en su sitio cronológico
  (`posicion_cronologica`, `anadir`) y la quita de la otra (`quitar`). Solo entre listas de época.
- `spotify.cargar()` lee todas las listas propias + Liked (solo lectura) → mismo modelo que Exportify,
  con `Lista.spotify_id`. **Lectura incremental** (`cache/spotify_listas.json`): solo se descargan las listas cuyo
  `snapshot_id` cambió; Liked se compara por total + primera canción y solo se leen las nuevas por arriba. La web
  lee de Spotify sola al abrir si está conectado (el usuario no quiere que se relea todo cada vez). Botón "aplicar en Spotify" solo si la fuente es la API y la lista no es fija.
  La API ya no da géneros en lote ni audio-features; para las comprobaciones no hacen falta.
- `tools/probar_spotify.py` (botón en la web): crea lista desechable, comprueba si mover conserva
  `added_at`, la borra. Resultado en `cache/prueba_spotify.json`. **No aplicar orden a listas reales sin
  que esa prueba haya dado `conserva_added_at: true`** (y nunca a las de idioma sin preguntar).

## Versiones y actualizaciones

- `core/version.py`: `VERSION` y `REPO`. `tools.publicar` además exporta la caché de MusicBrainz/ListenBrainz de este PC a
  `conocimiento/` (`core/conocimiento.exportar`) y la commitea si cambió; al arrancar, `conocimiento.sembrar()` añade a la
  caché local lo que falte (lo local manda; solo trabaja si cambia la huella de `conocimiento/`). Release = sincronizar con el móvil (para que `fechas.json` lleve lo cambiado
  allí), subir `VERSION`, entrada en CHANGELOG, commit y **`python -m tools.publicar`** (tests, APK firmado, tag,
  `git archive` del zip y `gh release create` con el zip del PC y el APK del móvil).
- `core/actualizar.py`: consulta `releases/latest` (repo privado: token de `.env GITHUB_TOKEN`, `gh auth token`
  o `git credential fill` sin ventanas). Instala el zip encima sin tocar `.env`, `cache/`, `data/`, `salida/`
  ni `rules.json` (personal); fusiona `fechas.json` (local manda salvo fuente más fiable) y `artistas.json` (lo manual
  local manda). Carpeta con `.git` → `git pull --ff-only`. Luego `server.reiniciar()` lanza `app.py --reinicio`
  (espera a que se libere el puerto, sin abrir ventana) y la página se recarga al ver la versión nueva.
- Tareas en segundo plano (MB, Spotify, actualización): marcar `activo` **antes** de lanzar el hilo, si no la
  página consulta antes de que empiece y deja de vigilar.
- `core/red.py`: `abrir()` = urlopen con reintento si Windows no tiene aún el certificado raíz.

## Android (`android/`)

- APK = la misma app: **Chaquopy 17.2** (Python 3.14) + AGP 8.7.2/Gradle 8.9 (como `AnxoBT/wallpaper-editor`).
  `MainActivity` (Kotlin, `Activity` sin androidx salvo `FileProvider`) arranca `chronify_android.arrancar()` →
  `web.server.serve(8766, auto_apagar=False)` y lo enseña en un `WebView`. Lo que no es 127.0.0.1 se abre fuera
  (login de Spotify en el navegador → vuelve a `127.0.0.1:8766/callback`, mismo redirect que en el PC).
- Compilar: `cd android && ./gradlew assembleDebug` (necesita `local.properties` con `sdk.dir`). Instalar:
  `adb install -r app/build/outputs/apk/debug/app-debug.apk`. Para probar el servidor del móvil desde el PC:
  `adb forward tcp:8780 tcp:8766`. Firma: clave propia `~/.android/chronify-release.jks` (datos en
  `android/keystore.properties`, ignorado por git; **hay que conservarla**: con otra clave el móvil no instala
  la actualización encima y habría que desinstalar). Debug y release firman igual.
- El APK solo lleva `core/`, `web/`, `conocimiento/`, `fechas.json`, `reglas.defecto.json`, `artistas.json` (tarea `copiarPython`): **nunca**
  `.env`, caché ni CSV. Versión = `core/version.py` (versionCode = MA*10000+MI*100+PA).
- `config.DATOS` (variable `CHRONIFY_DATOS`): carpeta de datos modificables; en el PC = la del programa, en
  Android = `files/datos`. La primera vez se siembra con los JSON del APK; en cada versión nueva
  `actualizar.fusionar_semillas()` fusiona los del APK con los del móvil.
- `CHRONIFY_ANDROID=1`: sin subprocesos (Android no deja), "Zip de Exportify" oculto (no puede leer Descargas: se usa
  **Importar zip**, `POST /api/importar`, también en el PC), actualizar = descargar el `.apk` de la release y abrir el
  instalador (`/android/instalar` lo intercepta `MainActivity`). La página pide pantalla encendida
  (`window.ChronifyAndroid.mantenerPantalla`) mientras haya una tarea larga: con la pantalla apagada se pausa.
- Interfaz móvil: `@media (max-width:700px)` en web/estilos.css; gráficas a escala estrecha (`MOVIL()`), mapa con pellizco.
  En Android no hay txt (la app de Spotify del móvil no deja seleccionar todo y pegar): se ordena por la API.
  Android 15 dibuja bajo las barras del sistema: `MainActivity` deja el hueco con los insets. Icono adaptativo
  negro (`tools/generar_icono_android.py`).

## Sincronizar PC ↔ móvil (`core/sincro.py`)

**Por USB (adb), nunca por internet**: el usuario no quiere sus datos en GitHub. Botón en Ajustes del PC:
`adb forward tcp:8781 tcp:8766`, abre la app del móvil si hace falta, `GET /api/sincro/datos` del móvil → `recibir()`
aquí → `POST /api/sincro/datos` al móvil (que fusiona igual) y, si el zip de Exportify del PC es más nuevo, se lo pasa
(`/api/importar`). Fusiona fechas.json (gana el cambio más reciente: campo `m` que pone `Fechas.fijar`), rules.json,
artistas.json, cachés de MusicBrainz/ListenBrainz y el **cupo de Spotify** (unión de escrituras: el límite es por app).
adb: `ADB` en .env, PATH o `%LOCALAPPDATA%/Android/Sdk/platform-tools`.

## Copia de seguridad (`core/copia.py`)

Lo que no está en GitHub: `.env`, `cache/` (menos `actualizacion/` y el log), `data/`, fechas/rules/artistas locales,
`~/.android/chronify-release.jks` y `android/keystore.properties`. Destino `COPIAS_DIR` (.env) o
`Documentos/Chronify copias`; automática cada 7 días al arrancar en el PC, se guardan 5. Restaurar:
`python -m core.copia restaurar <zip>` (antes guarda lo actual en `antes-de-restaurar/`). Solo en el PC.

## Versión web (`web/navegador.py`, `web/js/web.js`, `web/js/trabajador.js`, `tools/generar_web.py`)

Para iPhone y cualquier navegador, sin servidor: GitHub Pages (`.github/workflows/web.yml`, en cada release).
- `tools/generar_web.py` → `salida/web`: index.html con rutas relativas + `js/web.js` delante, `chronify-py.zip`
  (core/, web/server.py, web/navegador.py, fechas/artistas/reglas.defecto, conocimiento/), `sw.js`, manifest e iconos.
- `js/web.js` (página): sustituye `fetch` para `/api/…`, `/spotify/login`, `/callback` → worker. Mientras el worker
  ejecuta una tarea larga no atiende: los GET de estado (`/api/spotify|mb|artistas`) salen de las "fotos" que manda
  Python y el resto de GET de la última respuesta; los POST dan 409 salvo cancelar. Enlaces `/api/txt` → descarga.
  Login: el redirect es la URL de la web (`CHRONIFY_WEB_URL`); al volver con `?code&state` llama a `/callback`. PKCE
  en `cache/spotify_pkce.json` (la página se recarga). Wake Lock durante las tareas.
- `js/trabajador.js` (worker **de módulo**: `importScripts` falla con COEP): Pyodide 314.0.7 **servido desde la propia
  web** (`pyodide/<versión>/`; `generar_web._pyodide` baja el paquete de npm y verifica `dist.integrity` sha512; nada de
  CDN). Código en `/app`, datos en `/datos` (IDBFS: `syncfs` **antes** de responder y tras cada tarea). La respuesta
  lleva `ocupado` si lanzó una tarea (la página lo sabe antes de pedir el progreso). Entorno `CHRONIFY_WEB=1`.
- `web/navegador.py`: `despachar()` = el handler `H` sin socket (subclase que captura `_send`); `threading.Thread` →
  cola que se ejecuta tras responder; `time.sleep` → `Atomics.wait` si hay SharedArrayBuffer (si no, espera activa) y
  envía fotos de estado; red → XHR síncrono (`core/red.TRANSPORTE`; Spotify, MusicBrainz y ListenBrainz permiten CORS).
- `sw.js`: aísla la página (COOP/COEP) → SharedArrayBuffer (cancelar y esperas sin CPU) y caché sin conexión (web: red
  primero; `pyodide/`: caché primero). Iconos `web/icono-*.png` generados una vez (Pillow solo entonces, no en el build).
- `server.WEB`: sin carpetas, actualizador ni USB; copia = descarga (`POST /api/copia` devuelve el zip) y
  `POST /api/copia/restaurar` (también en el PC).
- Probar: `python -m tools.generar_web && python -m http.server 8790 -d salida/web`; `python -m tests.ejemplo
  salida/web/prueba/spotify_playlists.zip` crea un zip de Exportify inventado (otra persona) para importarlo.

## Seguridad del servidor local (`web/server.py`, `H._permitido`)

Otras webs del navegador y otras apps del móvil pueden llegar a 127.0.0.1. Por eso: `Host` tiene que ser
127.0.0.1/localhost (DNS rebinding); `Origin`, si viene, local; **todo POST lleva `X-Chronify: 1`** (base.js `api()` y
los `fetch` de importar/restaurar/copia; sincro también) → otra web necesitaría preflight y no lo hay. Android:
`CHRONIFY_SECRETO` (aleatorio por arranque, `MainActivity.SECRETO`): la pantalla entra con `/?k=` → cookie HttpOnly
SameSite=Strict; la sincronización la lee por adb de `/sdcard/Android/data/<paquete>/files/clave-sincro.txt` (solo
Android 11+; otras apps no pueden leerla) y la manda en `X-Chronify-Clave`. Libres: `/callback` (state PKCE) y
`/api/ping`. `copia.restaurar`: solo `.env`, fechas/rules/artistas, `cache/`, `data/` (y la clave del APK fuera de la
web), rutas resueltas dentro de su carpeta, máx. 400 MB descomprimidos. Tests en `TestSeguridad`. Sincro elige el
dispositivo con Chronify (puede haber un emulador conectado).

## Cuentas de Spotify

`spotify.comprobar_cuenta()` tras el login (scope `user-read-private` → `product`) y los 403 de cuenta
(`_no_disponible`: "premium" → `SIN_PREMIUM`, "registered" → `NO_AUTORIZADA`) lanzan `SpotifyNoDisponible` y guardan
`cache/spotify_cuenta.json`; la web lo enseña en Ajustes y no lee sola al abrir. Sin Premium: Exportify + txt.

## Publicar

Repo público. **Nada personal en el repo**: ni `rules.json`, ni caché, ni nombres de otras personas; commits con el
email noreply de GitHub. Móvil: deslizar a los lados cambia de pestaña (`base.js`, no en el mapa ni en tablas
desplazables).

## Hoja de ruta

Ver `docs/ROADMAP.md`.
