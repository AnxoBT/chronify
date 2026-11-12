"""Genera la versión web de Chronify (para GitHub Pages o cualquier hosting estático): salida/web/.

Es la misma interfaz que en el PC; Python (core/ + web/server.py) se ejecuta en el navegador con Pyodide
(web/js/trabajador.js + web/navegador.py). Funciona en iPhone, Mac, Linux y cualquier móvil, y se puede añadir a la
pantalla de inicio. Los datos de cada persona se quedan en su navegador (con copia descargable).

Pyodide se sirve desde la propia web (no de una CDN): se descarga del registro de npm comprobando su firma sha512
(`dist.integrity`), y se guarda en salida/cache-pyodide para no bajarlo cada vez.

Uso: python -m tools.generar_web [carpeta]      # por defecto salida/web
Probar en local: python -m http.server 8790 -d salida/web  →  http://127.0.0.1:8790/
(Spotify: la Redirect URI de tu app tiene que ser la URL exacta de la web, p. ej. https://usuario.github.io/chronify/)
"""
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.version import VERSION  # noqa: E402

WEB = ROOT / "web"
PYODIDE = "314.0.7"  # Python 3.14, como el APK. Al cambiarla, cambiar también la ruta en web/js/trabajador.js
PYODIDE_ARCHIVOS = ("pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")
PY_INCLUIR = ["core/*.py", "web/server.py", "web/navegador.py", "fechas.json", "artistas.json", "reglas.defecto.json",
              "conocimiento/*.json"]
ESTATICOS = ["estilos.css", "mundo.json", "logo.png", "logo-32.png", "logo.svg", "icono-180.png", "icono-192.png",
             "icono-512.png"]

SW = """// Service worker de Chronify web (generado por tools/generar_web.py).
// - Aísla la página (COOP/COEP): así hay memoria compartida para cancelar tareas y esperar sin gastar batería.
// - Funciona sin conexión: la web, red primero con copia en caché; Pyodide (pyodide/<versión>/, inmutable), caché primero.
const CACHE = "chronify-__HUELLA__";
const ARCHIVOS = __ARCHIVOS__;

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ARCHIVOS)).catch(() => {}));
});
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k.startsWith("chronify-") && k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));

const aislar = res => {
  if (!res || res.status === 0 || res.type === "opaqueredirect") return res;
  const h = new Headers(res.headers);
  h.set("Cross-Origin-Embedder-Policy", "require-corp");
  h.set("Cross-Origin-Opener-Policy", "same-origin");
  h.set("Cross-Origin-Resource-Policy", "same-origin");
  return new Response(res.body, {status: res.status, statusText: res.statusText, headers: h});
};

self.addEventListener("fetch", e => {
  const r = e.request;
  const u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    if (u.pathname.includes("/pyodide/")) {
      const guardado = await c.match(r);
      if (guardado) return aislar(guardado);
      const res = await fetch(r);
      if (res.ok) c.put(r, res.clone());
      return aislar(res);
    }
    const clave = r.mode === "navigate" ? "./" : r;
    try {
      const res = await fetch(r);
      if (res.ok) c.put(clave, res.clone());
      return aislar(res);
    } catch (err) {
      return aislar((await c.match(clave, {ignoreSearch: true})) || Response.error());
    }
  })());
});
"""

MANIFEST = {
    "name": "Chronify", "short_name": "Chronify", "lang": "es",
    "description": "Ordena tus listas de Spotify por la fecha real de cada canción",
    "start_url": "./", "scope": "./", "display": "standalone", "background_color": "#0f1317", "theme_color": "#0f1317",
    "icons": [{"src": "icono-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icono-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
}

CABECERA = """<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icono-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Chronify">
<meta name="theme-color" content="#0f1317">
<style>
  #cargandoWeb { position:fixed; inset:auto 16px 16px 16px; z-index:50; padding:12px 16px; border-radius:10px;
    background:#1c2228; color:#e8eef2; box-shadow:0 4px 18px #0008; font:14px system-ui; text-align:center; }
  #cargandoWeb.error { background:#5a1f1f; }
  body { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
</style>
"""


def _pyodide(destino):
    """Copia los archivos de Pyodide a destino/pyodide/<versión>/, del paquete de npm verificado con sha512."""
    cache = ROOT / "salida" / "cache-pyodide" / f"pyodide-{PYODIDE}.tgz"
    with urlopen(f"https://registry.npmjs.org/pyodide/{PYODIDE}", timeout=60) as r:
        dist = json.load(r)["dist"]
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(dist["tarball"], timeout=300) as r:
            cache.write_bytes(r.read())
    algoritmo, esperado = dist["integrity"].split("-", 1)
    real = base64.b64encode(hashlib.new(algoritmo, cache.read_bytes()).digest()).decode()
    if algoritmo != "sha512" or real != esperado:
        cache.unlink()
        raise SystemExit(f"Pyodide {PYODIDE}: la firma no coincide con la del registro de npm (descarga corrupta o alterada)")
    carpeta = destino / "pyodide" / PYODIDE
    carpeta.mkdir(parents=True)
    with tarfile.open(cache) as t:
        for n in PYODIDE_ARCHIVOS:
            (carpeta / n).write_bytes(t.extractfile(f"package/{n}").read())


def _zip_python():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for patron in PY_INCLUIR:
            for p in sorted(ROOT.glob(patron)):
                z.write(p, p.relative_to(ROOT).as_posix())
    return b.getvalue()


def _index(huella):
    s = (WEB / "index.html").read_text(encoding="utf-8")
    s = re.sub(r'(href|src)="/(?!/)', r'\1="', s)  # rutas relativas: la web puede vivir en /chronify/
    s = s.replace('href="spotify/login"', 'href="/spotify/login"')  # lo intercepta js/web.js
    s = s.replace('href="favicon.ico', 'href="logo-32.png').replace('sizes="16x16 24x24 32x32 48x48 64x64 128x128 256x256"', "")
    s = s.replace('<html lang="es">', f'<html lang="es" data-version="{huella}">', 1)
    s = s.replace('<link rel="stylesheet"', CABECERA + '<link rel="stylesheet"', 1)
    s = s.replace('<script src="js/base.js"></script>', '<script src="js/web.js"></script>\n<script src="js/base.js"></script>', 1)
    assert 'js/web.js' in s and "manifest.webmanifest" in s
    return s


def generar(out):
    out = Path(out)
    shutil.rmtree(out, ignore_errors=True)
    (out / "js").mkdir(parents=True)
    zpy = _zip_python()
    js = sorted((WEB / "js").glob("*.js"))
    h = hashlib.sha1(zpy + SW.encode() + PYODIDE.encode() + (WEB / "index.html").read_bytes())
    for p in js + [WEB / f for f in ESTATICOS]:
        h.update(p.read_bytes())
    huella = f"{VERSION}-{h.hexdigest()[:8]}"
    (out / "chronify-py.zip").write_bytes(zpy)
    for f in ESTATICOS:
        shutil.copyfile(WEB / f, out / f)
    for p in js:
        shutil.copyfile(p, out / "js" / p.name)
    _pyodide(out)
    (out / "index.html").write_text(_index(huella), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")
    archivos = ["./", "manifest.webmanifest", f"chronify-py.zip?v={huella}", *ESTATICOS,
                *[f"js/{p.name}" for p in js], f"js/trabajador.js?v={huella}"]
    (out / "sw.js").write_text(SW.replace("__HUELLA__", huella).replace("__ARCHIVOS__", json.dumps(archivos)),
                               encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"Web generada en {out} ({total // 1024 // 1024} MB con Pyodide, Python de Chronify {len(zpy) // 1024} KB, "
          f"versión {huella})")
    return out


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else ROOT / "salida" / "web")
