// Versión web: Python (Pyodide) en un Web Worker hace de "servidor" de Chronify (web/navegador.py).
// La página le manda cada petición /api/… y él contesta igual que el servidor del PC.
// Código en /app (chronify-py.zip, generado por tools/generar_web.py); tus datos en /datos (IndexedDB del navegador).
// Worker de tipo módulo (importScripts no vale en una página aislada con COEP). Pyodide se sirve desde la propia web,
// verificado al generarla (tools/generar_web.py, PYODIDE): misma versión aquí.
import { loadPyodide } from "../pyodide/314.0.7/pyodide.mjs";

let py = null, nav = null, inicio = null;

const guardar = () => new Promise(ok => py.FS.syncfs(false, e => { if (e) console.error("No se pudo guardar", e); ok(); }));

async function iniciar({url, compartida, version}) {
  py = await loadPyodide({indexURL: new URL("../pyodide/314.0.7/", import.meta.url).href});
  postMessage({tipo: "progreso", texto: "Cargando Chronify…"});
  const FS = py.FS;
  FS.mkdirTree("/datos");
  FS.mount(FS.filesystems.IDBFS, {}, "/datos");
  await new Promise((ok, mal) => FS.syncfs(true, e => e ? mal(e) : ok()));
  const zip = await (await fetch(new URL("../chronify-py.zip?v=" + version, import.meta.url))).arrayBuffer();
  py.unpackArchive(zip, "zip", {extractDir: "/app"});
  py.globals.set("URL_APP", url);
  py.runPython(`
import os, sys
os.environ.update(CHRONIFY_DATOS="/datos", CHRONIFY_WEB="1", CHRONIFY_WEB_URL=URL_APP)
sys.path.insert(0, "/app")
`);
  nav = py.pyimport("web.navegador");
  nav.iniciar(fotos => postMessage({tipo: "fotos", fotos}), compartida ? new Int32Array(compartida) : null);
  await guardar();
  postMessage({tipo: "listo"});
}

async function atender({id, metodo, ruta, cabeceras, cuerpo}) {
  await inicio;
  const r = nav.despachar(metodo, ruta, py.toPy(cabeceras || {}), cuerpo ? new Uint8Array(cuerpo) : null);
  const [codigo, cab, datos] = r.toJs({dict_converter: Object.fromEntries});
  r.destroy();
  const ocupado = nav.hay_tareas();  // lanza una tarea larga: la página lo sabe antes de pedir el progreso
  await guardar();  // antes de responder: p. ej. el login de Spotify sale de la página nada más recibir la respuesta
  const buf = datos.slice().buffer;
  postMessage({id, codigo, cabeceras: cab, cuerpo: buf, ocupado}, [buf]);
  if (ocupado) {  // ordenar, MusicBrainz…: el progreso va a la página con las "fotos"
    try { nav.ejecutar_tareas(); } finally {
      await guardar();
      postMessage({tipo: "libre"});
    }
  }
}

let cola = Promise.resolve();
onmessage = ev => {
  const m = ev.data;
  if (m.tipo === "iniciar") {
    inicio = iniciar(m).catch(e => { postMessage({tipo: "error", texto: String(e && e.message || e)}); throw e; });
    return;
  }
  cola = cola.then(() => atender(m)).catch(e => {
    const buf = new TextEncoder().encode(JSON.stringify({error: String(e && e.message || e)})).buffer;
    postMessage({id: m.id, codigo: 500, cabeceras: {"Content-Type": "application/json"}, cuerpo: buf}, [buf]);
  });
};
