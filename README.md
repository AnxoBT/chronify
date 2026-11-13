<p align="center">
  <img src="web/logo.png" width="112" alt="Chronify">
</p>

<h1 align="center">Chronify</h1>

<p align="center">
  <a href="https://github.com/AnxoBT/chronify/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/AnxoBT/chronify?style=flat-square&color=1ED760"></a>
  <a href="https://anxobt.github.io/chronify/"><img alt="Web" src="https://img.shields.io/badge/Web-iPhone%20·%20Mac%20·%20Linux-1ED760?style=flat-square&logo=googlechrome&logoColor=white"></a>
  <img alt="Windows" src="https://img.shields.io/badge/Windows-10%2B-0078D4?style=flat-square&logo=windows&logoColor=white">
  <img alt="Android 8.0+" src="https://img.shields.io/badge/Android-8.0%2B-34A853?style=flat-square&logo=android&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-stdlib_only-3776AB?style=flat-square&logo=python&logoColor=white">
</p>

<br>

<details open>
<summary><b>English</b></summary>

<br>

<p align="center">Sort your Spotify playlists by the <b>real</b> release date of every song, and check that your playlists add up.</p>

<p align="center"><a href="https://anxobt.github.io/chronify/"><b>Open the web app</b></a> · <a href="https://github.com/AnxoBT/chronify/releases/latest"><b>Download</b></a> (Windows / Mac / Linux zip · Android APK)</p>

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>📅 Real dates</h3>
      Spotify shows the date of the remaster or compilation you saved. Chronify uses the date the song first came out (single included), from verified dates and MusicBrainz, and sorts your playlists by it.
    </td>
    <td width="33%" valign="top">
      <h3>✅ Playlists that add up</h3>
      Tell it what each playlist is (an "everything" mix, eras, genres) and it finds what is missing, duplicated, in the wrong era, or a live/remix version you didn't mean to save.
    </td>
    <td width="33%" valign="top">
      <h3>📊 Your music, in numbers</h3>
      World map of your artists, years and decades, top artists, genres, mood, tempo, "your year" and how your collection changes month by month.
    </td>
  </tr>
</table>

> The interface is in English and Spanish: it follows your system language and can be changed in Settings.

### Features

- **Sort by real date** any playlist: copy-paste a list into Spotify desktop, or (Premium) apply it through
  the Spotify API, which *moves* songs without deleting them, so your "date added" is kept
- **Checks**: duplicates, the same song saved twice from different editions, live versions, remixes,
  compilations and barely-played copies (with a button to swap them for the main one)
- **Your playlists** (optional): a mix made of other playlists, eras with year ranges, genres, playlists
  never to reorder, playlists to ignore. Suggestions and one-tap fixes ("add to…", "move to…")
- **Liked Songs** can't be reordered in Spotify, but you can get them sorted by real date into a new playlist (one tap)
- **Dates**: proposals from MusicBrainz for songs without a verified date; you decide
- **Statistics**: map, years, decades, artists, solo/groups, genres, mood, tempo, keys, popularity,
  length, niche artists (ListenBrainz listeners), "your year", monthly evolution
- **History** with undo, **backup** and restore (also to move your data between devices)
- **Sync PC ↔ phone** over USB or **over Wi-Fi** at home (a one-time code, everything encrypted)
- **What's new**: after an update, a short summary of the changes ([CHANGELOG.en.md](CHANGELOG.en.md))
- Swipe left/right on the phone to change tab
- **Shared knowledge**: verified dates and artist countries ship with every version, so nobody starts from
  scratch. What you correct always wins over what a new version brings

### Where it runs

| Version | Devices | Install |
|---|---|---|
| **Web** | iPhone, iPad, Mac, Linux, Android, Windows (any modern browser) | Nothing: open [anxobt.github.io/chronify](https://anxobt.github.io/chronify/). On iPhone: Share → *Add to Home Screen* |
| **Desktop** | Windows 10+, macOS, Linux | `Chronify-vX.Y.Z.zip` → `Abrir Chronify.bat` (Windows) or `Abrir Chronify.command` (Mac/Linux). Needs Python 3.10+ (installed automatically on Windows) |
| **Android** | Android 8.0+ (arm64) | `Chronify-vX.Y.Z.apk` from the release |

All versions are the same app with the same features. The web version runs the same Python code inside your
browser ([Pyodide](https://pyodide.org)); the first visit downloads ~13 MB once (served from the same site, verified when it is built) and then it also works offline.
Your data stays on your device: in the browser (web), in the program folder (desktop) or in the app (Android).
Desktop and Android can be synced with a USB cable.

### Getting started

1. **Load your playlists**, either way:
   - **Exportify** (free, no Premium): [exportify.app](https://exportify.app) → *Export All* → zip → **Importar zip…**
     (on Windows it is picked up from Downloads automatically).
   - **Spotify API** (Premium): see below. Once connected, Chronify reads your playlists on start and only downloads
     the ones that changed.
2. **Ordenar** (Sort): each playlist in real-date order. With the API, **aplicar en Spotify**; without it, copy the
   list and paste it into the playlist in Spotify desktop (`Ctrl+A`, `Delete`, `Ctrl+V`).
3. Optional, **Ajustes → Tus listas**: tell Chronify what each playlist is to turn on the checks between them.

### Spotify accounts: Premium or not

| | Free account | Premium account |
|---|---|---|
| Load playlists (Exportify zip) | ✓ | ✓ |
| Checks, dates, statistics, history | ✓ | ✓ |
| Sort: copy and paste in Spotify desktop | ✓ (the "date added" becomes today) | ✓ |
| Sort/fix directly in Spotify, keeping "date added" | | ✓ |
| Read playlists without Exportify | | ✓ |

Spotify only lets apps whose owner has Premium use its API (development mode, since February 2026), so each
person creates their own free Spotify app (5 minutes):

1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → *Create app* (Web API).
2. Redirect URI: the one shown in Chronify → **Ajustes** (`http://127.0.0.1:8766/callback` on desktop/Android,
   `https://anxobt.github.io/chronify/` on the web; you can add both).
3. Paste its **Client ID** in Ajustes → **Conectar con Spotify** → **Probar en lista desechable** (a safety test on a
   throwaway playlist; sorting stays locked until it passes).

If your account can't use the API (no Premium, or not allowed in that app), Chronify says so clearly and
everything else keeps working with Exportify. Spotify blocks apps for 24 h after too many changes in a day, so
Chronify stops at 450 and offers **Seguir** (continue) the next day; a big, very unsorted playlist can take a
couple of days.

### Privacy

- No account, no server, no tracking. Chronify only talks to Spotify (your own app), MusicBrainz, ListenBrainz and
  GitHub (update check), straight from your device.
- Your playlists, settings, corrections and Spotify session never leave your device. The backup zip contains
  them, so don't share it.
- The shared knowledge in this repo (dates, artist countries) is public music metadata.
- The desktop/Android local server only answers the app itself: requests from other websites are refused, and on
  Android other apps need a secret key that changes every time the app starts.

### Compatibility

| Platform | Device | Status |
|---|---|---|
| Windows | Windows 11 | Tested daily |
| Android | vivo V2337, Android 16 | Tested daily, sorting in Spotify included |
| Web | Chromium (desktop and phone-size viewport, touch) | Tested: load, checks, sort, statistics, backup, MusicBrainz, cancel |
| Web | iPhone (Safari) | **Not tested on a real iPhone yet**: uses only features Safari supports (Web Workers, IndexedDB, WebAssembly) |
| macOS / Linux desktop | — | **Not tested yet** (plain Python + browser) |

Reports are welcome: [open an issue](https://github.com/AnxoBT/chronify/issues/new/choose) with the device, browser
or Android version, what you did and what happened.

### Build

Python 3.10+, standard library only.

```sh
python app.py                                   # desktop (own window; --navegador for a normal tab)
python -m unittest discover -s tests -t .       # tests (offline)
python -m tools.generar_web                     # web version in salida/web (python -m http.server -d salida/web)
cd android && ./gradlew assembleRelease         # Android APK (JDK 17 + Android SDK)
python -m tools.publicar                        # release: tests, APK, shared knowledge, tag, zip, GitHub release
```

The web version is published to GitHub Pages by `.github/workflows/web.yml` on every release.

### How it works

- **Real date** = first release, single included (e.g. *TiK ToK*: single 2009, album 2010 → 2009). Remasters, live
  or re-recorded versions by the same artist take the original date; covers by other artists take their own.
- **Sorting** moves the fewest songs possible (n − longest increasing subsequence).
- **Artist country** = birthplace or where the band was formed (MusicBrainz, walking up to the country), with
  manual corrections in `artistas.json`.
- **Web version**: the same Python runs in a Web Worker with Pyodide; your data is saved in IndexedDB; a service
  worker makes it work offline and isolates the page so long tasks can be cancelled.

### Credits

[Pyodide](https://pyodide.org) (MPL-2.0) · map from [Natural Earth](https://www.naturalearthdata.com) (public domain) ·
dates and artists from [MusicBrainz](https://musicbrainz.org) (CC0) · listeners from
[ListenBrainz](https://listenbrainz.org) · playlist export by [Exportify](https://exportify.app). Not affiliated with
Spotify.

### License

Copyright © 2026 AnxoBT. Licensed under the [GNU General Public License v3.0](LICENSE): you can
use, study, share and modify it, but anything you distribute that is based on this code must be
released under the same licence, with its source code.

</details>

<details>
<summary><b>Español</b></summary>

<br>

<p align="center">Ordena tus listas de Spotify por la fecha <b>real</b> de cada canción y comprueba que tus listas cuadran.</p>

<p align="center"><a href="https://anxobt.github.io/chronify/"><b>Abrir la web</b></a> · <a href="https://github.com/AnxoBT/chronify/releases/latest"><b>Descargar</b></a> (zip de Windows / Mac / Linux · APK de Android)</p>

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>📅 Fechas reales</h3>
      Spotify enseña la fecha del remaster o del recopilatorio que guardaste. Chronify usa la de la primera publicación (incluido el single), de fechas verificadas y MusicBrainz, y ordena tus listas por ella.
    </td>
    <td width="33%" valign="top">
      <h3>✅ Listas que cuadran</h3>
      Dile qué es cada lista (un Mix con todo, épocas, géneros) y encuentra lo que falta, lo repetido, lo que está en la época equivocada o una versión en directo o remix que no querías.
    </td>
    <td width="33%" valign="top">
      <h3>📊 Tu música en cifras</h3>
      Mapa del mundo de tus artistas, años y décadas, artistas, géneros, ánimo, ritmo, "tu año" y cómo cambia tu colección mes a mes.
    </td>
  </tr>
</table>

### Funciones

- **Ordenar por fecha real** cualquier lista: copiar y pegar en Spotify del PC o (Premium) aplicarlo por la API de
  Spotify, que *mueve* las canciones sin borrarlas y conserva la fecha en que las añadiste
- **Comprobaciones**: repetidas, la misma canción guardada dos veces de ediciones distintas, directos, remixes,
  recopilatorios y copias poco escuchadas (con botón para cambiarlas por la principal)
- **Tus listas** (opcional): un Mix formado por otras listas, épocas con sus años, géneros, listas que no se
  reordenan nunca, listas a ignorar. Sugerencias y arreglos con un toque ("añadir a…", "mover a…")
- **Canciones que te gustan**: Spotify no deja reordenarlas, pero puedes tenerlas ordenadas por fecha real en una lista nueva (un toque)
- **Fechas**: propuestas de MusicBrainz para canciones sin fecha verificada; decides tú
- **Estadísticas**: mapa, años, décadas, artistas, solistas/grupos, géneros, ánimo, ritmo, tonalidades, popularidad,
  duración, artistas de nicho (oyentes en ListenBrainz), "tu año", evolución mensual
- **Historial** con deshacer, **copia de seguridad** y restaurar (también para pasar tus datos de un dispositivo a otro)
- **Sincronizar PC ↔ móvil** por USB o **por Wi-Fi** en casa (con un código de un solo uso, todo cifrado)
- **Novedades**: tras actualizar, un resumen corto de los cambios ([CHANGELOG.md](CHANGELOG.md))
- En el móvil, desliza a izquierda o derecha para cambiar de pestaña
- **Conocimiento compartido**: las fechas verificadas y los países de los artistas vienen con cada versión, así que
  nadie empieza de cero. Lo que corriges tú siempre manda sobre lo que traiga una versión nueva

### Dónde funciona

| Versión | Dispositivos | Instalación |
|---|---|---|
| **Web** | iPhone, iPad, Mac, Linux, Android, Windows (cualquier navegador actual) | Nada: abre [anxobt.github.io/chronify](https://anxobt.github.io/chronify/). En iPhone: Compartir → *Añadir a pantalla de inicio* |
| **Escritorio** | Windows 10+, macOS, Linux | `Chronify-vX.Y.Z.zip` → `Abrir Chronify.bat` (Windows) o `Abrir Chronify.command` (Mac/Linux). Necesita Python 3.10+ (en Windows se instala solo) |
| **Android** | Android 8.0+ (arm64) | `Chronify-vX.Y.Z.apk` de la release |

Todas son la misma app con las mismas funciones. La web ejecuta el mismo código Python dentro del navegador
([Pyodide](https://pyodide.org)); la primera vez descarga ~13 MB (desde la propia web, verificados al generarla) y después funciona también sin conexión. Tus datos se
quedan en tu dispositivo: en el navegador (web), en la carpeta del programa (escritorio) o en la app (Android). El PC
y el móvil Android se sincronizan por cable USB.

### Primeros pasos

1. **Carga tus listas**, de una de estas formas:
   - **Exportify** (gratis, sin Premium): [exportify.app](https://exportify.app) → *Export All* → zip → **Importar zip…**
     (en Windows se coge solo de Descargas).
   - **API de Spotify** (Premium): ver abajo. Una vez conectada, Chronify lee tus listas al abrirse y solo descarga
     las que han cambiado.
2. **Ordenar**: cada lista por fecha real. Con la API, **aplicar en Spotify**; sin ella, copia la lista y pégala en la
   lista de Spotify del PC (`Ctrl+A`, `Supr`, `Ctrl+V`).
3. Opcional, **Ajustes → Tus listas**: dile qué es cada lista para activar las comprobaciones entre listas.

### Cuentas de Spotify: con Premium o sin él

| | Cuenta gratis | Cuenta Premium |
|---|---|---|
| Cargar listas (zip de Exportify) | ✓ | ✓ |
| Comprobaciones, fechas, estadísticas, historial | ✓ | ✓ |
| Ordenar copiando y pegando en Spotify del PC | ✓ (la fecha de añadido pasa a ser hoy) | ✓ |
| Ordenar y arreglar directamente en Spotify, conservando la fecha de añadido | | ✓ |
| Leer las listas sin Exportify | | ✓ |

Spotify solo deja usar su API a apps cuyo dueño tiene Premium (modo desarrollo, desde febrero de 2026), así que cada
persona crea su propia app de Spotify, gratis (5 minutos):

1. [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → *Create app* (Web API).
2. Redirect URI: la que enseña Chronify en **Ajustes** (`http://127.0.0.1:8766/callback` en escritorio/Android,
   `https://anxobt.github.io/chronify/` en la web; puedes poner las dos).
3. Pega su **Client ID** en Ajustes → **Conectar con Spotify** → **Probar en lista desechable** (una prueba de
   seguridad en una lista desechable; hasta que no da OK no se deja ordenar).

Si tu cuenta no puede usar la API (sin Premium o no autorizada en esa app), Chronify lo explica y todo lo demás sigue
funcionando con Exportify. Spotify bloquea 24 h a las apps que hacen demasiados cambios en un día, así que Chronify se
para en 450 y ofrece **Seguir** al día siguiente; una lista grande muy desordenada puede tardar un par de días.

### Privacidad

- Sin cuentas, sin servidor, sin seguimiento. Chronify solo habla con Spotify (tu propia app), MusicBrainz,
  ListenBrainz y GitHub (para avisar de versiones nuevas), directamente desde tu dispositivo.
- Tus listas, ajustes, correcciones y sesión de Spotify no salen de tu dispositivo. La copia de seguridad los
  contiene: no la compartas.
- El conocimiento compartido del repo (fechas, países de artistas) son datos públicos de música.
- El servidor local del PC y de Android solo atiende a la propia app: rechaza peticiones de otras webs y, en Android,
  otras apps necesitan una clave secreta que cambia cada vez que se abre la app.

### Compatibilidad

| Plataforma | Dispositivo | Estado |
|---|---|---|
| Windows | Windows 11 | Probado a diario |
| Android | vivo V2337, Android 16 | Probado a diario, incluido ordenar en Spotify |
| Web | Chromium (escritorio y tamaño de móvil, táctil) | Probado: cargar, comprobaciones, ordenar, estadísticas, copia, MusicBrainz, cancelar |
| Web | iPhone (Safari) | **Aún sin probar en un iPhone real**: solo usa funciones que Safari tiene (Web Workers, IndexedDB, WebAssembly) |
| Escritorio macOS / Linux | — | **Aún sin probar** (Python normal + navegador) |

Se agradecen los avisos: [abre una incidencia](https://github.com/AnxoBT/chronify/issues/new/choose) con el
dispositivo, navegador o versión de Android, qué hiciste y qué pasó.

### Compilar

Python 3.10+, solo librería estándar.

```sh
python app.py                                   # escritorio (ventana propia; --navegador para una pestaña normal)
python -m unittest discover -s tests -t .       # tests (sin red)
python -m tools.generar_web                     # versión web en salida/web (python -m http.server -d salida/web)
cd android && ./gradlew assembleRelease         # APK de Android (JDK 17 + Android SDK)
python -m tools.publicar                        # release: tests, APK, conocimiento compartido, tag, zip, release de GitHub
```

La web se publica en GitHub Pages con `.github/workflows/web.yml` en cada release.

### Cómo funciona

- **Fecha real** = primera publicación, incluido el single (p. ej. *TiK ToK*: single 2009, álbum 2010 → 2009).
  Remasters, directos o regrabaciones del mismo artista llevan la fecha original; las versiones de otros artistas, la suya.
- **Ordenar** mueve el mínimo de canciones posible (n − subsecuencia creciente más larga).
- **País del artista** = lugar de nacimiento o de formación del grupo (MusicBrainz, subiendo hasta el país), con
  correcciones a mano en `artistas.json`.
- **Versión web**: el mismo Python en un Web Worker con Pyodide; tus datos en IndexedDB; un service worker hace que
  funcione sin conexión y aísla la página para poder cancelar las tareas largas.

### Créditos

[Pyodide](https://pyodide.org) (MPL-2.0) · mapa de [Natural Earth](https://www.naturalearthdata.com) (dominio público) ·
fechas y artistas de [MusicBrainz](https://musicbrainz.org) (CC0) · oyentes de [ListenBrainz](https://listenbrainz.org) ·
exportación de listas con [Exportify](https://exportify.app). Sin relación con Spotify.

### Licencia

Copyright © 2026 AnxoBT. Con licencia [GNU General Public License v3.0](LICENSE): puedes usarla,
estudiarla, compartirla y modificarla, pero lo que distribuyas basado en este código tiene que
publicarse con la misma licencia y con su código fuente.

</details>
