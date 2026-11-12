// Versión web (solo en el build de tools/generar_web.py, se carga antes que los demás scripts).
// Las peticiones que en el PC van al servidor local (/api/…, /spotify/login, /callback) las contesta Python en
// un Web Worker (js/trabajador.js). Así el resto de la página es la misma que en el PC y en Android.
(() => {
  const VERSION = document.documentElement.dataset.version || "";
  const BASE = new URL(".", location.href);  // p. ej. https://usuario.github.io/chronify/
  const URL_APP = BASE.href;                  // redirect de Spotify: vuelve aquí con ?code=…
  const DINAMICO = /^\/(api\/|spotify\/login|callback)/;
  const ESTADOS = ["/api/spotify", "/api/mb", "/api/artistas"];

  // memoria compartida (solo si el service worker ha aislado la página): cancelar y esperas sin gastar batería
  const compartida = self.crossOriginIsolated ? new SharedArrayBuffer(8) : null;
  const banderas = compartida ? new Int32Array(compartida) : null;

  const W = new Worker(new URL("js/trabajador.js?v=" + VERSION, BASE), {type: "module"});
  W.postMessage({tipo: "iniciar", url: URL_APP, compartida, version: VERSION});

  const esperando = new Map(), fotos = {}, ultimosGet = new Map(), avisarFoto = [];
  let n = 0, ocupado = false, listo = false, bloqueo = null;

  // ── carga inicial (la primera vez descarga Python, ~13 MB; luego va de la caché) ──
  const aviso = document.createElement("div");
  aviso.id = "cargandoWeb";
  aviso.textContent = "Preparando Chronify… (la primera vez tarda un poco: descarga Python)";
  document.addEventListener("DOMContentLoaded", () => document.body.append(aviso));

  W.onmessage = ev => {
    const m = ev.data;
    if (m.tipo === "fotos") {  // progreso de la tarea en marcha (las de antes o de fuera de una tarea no valen)
      if (ocupado) { Object.assign(fotos, JSON.parse(m.fotos)); avisarFoto.splice(0).forEach(f => f()); }
      return;
    }
    if (m.tipo === "progreso") { aviso.textContent = m.texto; return; }
    if (m.tipo === "listo") { listo = true; aviso.remove(); return; }
    if (m.tipo === "error") { aviso.textContent = "No se pudo cargar Chronify: " + m.texto; aviso.classList.add("error"); return; }
    if (m.tipo === "libre") {
      ocupado = false;
      if (banderas) Atomics.store(banderas, 0, 0);  // un "cancelar" que llegó tarde no vale para la próxima tarea
      for (const k in fotos) delete fotos[k];
      ultimosGet.clear();
      avisarFoto.splice(0).forEach(f => f());  // quien esperaba progreso pide ya la respuesta real
      pantalla(false);
      return;
    }
    if (m.ocupado) {  // esta respuesta lanza una tarea larga: a partir de aquí el progreso sale de las fotos
      ocupado = true;
      for (const k in fotos) delete fotos[k];
      ESTADOS.forEach(e => ultimosGet.delete(e));
      pantalla(true);
    }
    const fin = esperando.get(m.id);
    esperando.delete(m.id);
    if (fin) fin(m);
  };

  const pedir = (metodo, ruta, cabeceras, cuerpo) => new Promise(ok => {
    const id = ++n;
    esperando.set(id, ok);
    W.postMessage({id, metodo, ruta, cabeceras, cuerpo}, cuerpo ? [cuerpo] : []);
  }).then(m => new Response(m.codigo === 302 ? null : m.cuerpo, {status: m.codigo, headers: m.cabeceras}));

  const json = (o, status = 200) => new Response(JSON.stringify(o), {status, headers: {"Content-Type": "application/json"}});

  // ── fetch: lo dinámico al worker; lo estático (mundo.json…) relativo a la carpeta de la web ──
  const fetchReal = window.fetch.bind(window);
  window.fetch = async (url, op = {}) => {
    const u = new URL(url, location.href);
    if (u.origin !== location.origin) return fetchReal(url, op);
    if (!DINAMICO.test(u.pathname)) {
      return fetchReal(u.pathname.startsWith(BASE.pathname) ? u : new URL(u.pathname.slice(1) + u.search, BASE), op);
    }
    const ruta = u.pathname + u.search, metodo = (op.method || "GET").toUpperCase();
    if (u.pathname === "/api/ping") return json({ok: true, app: "chronify"});
    if (ocupado) {
      // con una tarea en marcha Python no atiende: progreso desde las fotos, lo demás desde la última respuesta
      if (metodo === "GET" && ESTADOS.includes(u.pathname)) {  // el progreso real (nunca una respuesta vieja)
        if (!fotos[u.pathname]) await new Promise(ok => avisarFoto.push(ok));
        if (fotos[u.pathname]) return json(JSON.parse(fotos[u.pathname]));
      }
      if (metodo === "GET" && ultimosGet.has(ruta)) return ultimosGet.get(ruta).clone();
      if (metodo === "POST" && /cancelar|"cancelar":true/.test(u.pathname + (op.body || ""))) {
        if (banderas) { Atomics.store(banderas, 0, 1); Atomics.notify(banderas, 1); return json({ok: true}); }
        return json({error: "Este navegador no deja cancelar a medias: espera a que termine o recarga la página"}, 409);
      }
      if (metodo === "POST") return json({error: "Hay una tarea en marcha: espera a que termine"}, 409);
    }
    const cab = {};
    new Headers(op.headers || {}).forEach((v, k) => cab[k] = v);
    let cuerpo = null;
    if (op.body != null) cuerpo = typeof op.body === "string" ? new TextEncoder().encode(op.body).buffer : await new Response(op.body).arrayBuffer();
    const r = await pedir(metodo, ruta, cab, cuerpo);
    if (metodo === "GET" && r.ok) ultimosGet.set(ruta, r.clone());
    return r;
  };

  // ── enlaces que en el PC abre el servidor: descargas (txt, copia) y el login de Spotify ──
  document.addEventListener("click", async ev => {
    const a = ev.target instanceof Element && ev.target.closest("a[href]");
    if (!a) return;
    const u = new URL(a.getAttribute("href"), location.origin);
    if (u.origin !== location.origin || !DINAMICO.test(u.pathname)) return;
    ev.preventDefault();
    const r = await fetch(u.pathname + u.search);
    if (u.pathname === "/spotify/login") { location.href = r.headers.get("Location"); return; }
    descargar(await r.blob(), a.getAttribute("download") || "chronify.txt");
  }, true);

  window.descargarArchivo = descargar;
  function descargar(blob, nombre) {
    const a = Object.assign(document.createElement("a"), {href: URL.createObjectURL(blob), download: nombre});
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 30000);
  }

  // ── vuelta del login de Spotify: ?code=…&state=… ──
  const q = new URLSearchParams(location.search);
  if (q.has("state") && (q.has("code") || q.has("error"))) {
    history.replaceState(null, "", BASE.pathname);
    fetch("/callback?" + q.toString()).then(r => r.text()).then(t => {
      const msg = new DOMParser().parseFromString(t, "text/html").body.textContent.replace("Volver", "").trim();
      if (window.toast) toast(msg);
      if (window.pintarSpotify) pintarSpotify();
    });
  }

  // ── pantalla encendida durante las tareas largas (si se apaga, el navegador pausa la web) ──
  async function pantalla(si) {
    try {
      if (si && !bloqueo && navigator.wakeLock) bloqueo = await navigator.wakeLock.request("screen");
      if (!si && bloqueo) { await bloqueo.release(); bloqueo = null; }
    } catch (e) { /* sin permiso o no disponible */ }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && ocupado) { bloqueo = null; pantalla(true); } });

  // ── service worker: funciona sin conexión y aísla la página (memoria compartida) ──
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(new URL("sw.js", BASE)).then(() => {
      // la primera vez la página no estaba controlada: recargar una vez para que quede aislada
      if (!navigator.serviceWorker.controller && !sessionStorage.getItem("chronifySw")) {
        try { sessionStorage.setItem("chronifySw", "1"); } catch (e) { return; }
        navigator.serviceWorker.ready.then(() => location.reload());
      }
    }).catch(() => {});
  }
})();
