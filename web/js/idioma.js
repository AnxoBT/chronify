// Idioma de la interfaz. El código y los mensajes del servidor están en español; en inglés se traduce en la página:
// todo texto que aparece (HTML, lo que pinta el JS, avisos y registros del servidor, title/placeholder, confirm) se busca
// en el catálogo de js/idioma-en.js (texto exacto o patrón con números/nombres). Así sirve igual en PC, Android y web.
// Elección: la guardada en Ajustes; si no, la del sistema (español → español; cualquier otro → inglés).
const IDIOMA = (() => {
  try { const g = localStorage.getItem("chronify_idioma"); if (g === "es" || g === "en") return g; } catch (e) {}
  return /^es\b/i.test(navigator.language || "es") ? "es" : "en";
})();
const LOCALE = IDIOMA === "en" ? "en-US" : "es";

function cambiarIdioma(nuevo) {
  try { localStorage.setItem("chronify_idioma", nuevo); } catch (e) {}
  location.reload();
}

// Traduce un texto (o lo devuelve igual). En los patrones, lo capturado también se traduce: "Spotify: <error>".
// porLineas: registros (<pre>), una línea por mensaje.
let traducirTexto = (t, porLineas) => t;

(() => {
  document.documentElement.lang = IDIOMA;
  if (IDIOMA !== "en" || typeof IDIOMA_EN === "undefined") return;
  const SALTO = "\n";
  const plano = t => t.replace(/\s+/g, " ").trim();  // el HTML parte las frases en varias líneas del código
  const exactos = new Map();
  for (const [es, en] of Object.entries(IDIOMA_EN.exactos)) { exactos.set(es, en); exactos.set(plano(es), en); }
  const patrones = IDIOMA_EN.patrones.map(([re, s]) => [new RegExp(re), s]);
  const LETRAS = /[A-Za-zÁÉÍÓÚáéíóúÑñ]{2}/;
  const cache = new Map();

  function patron(k) {
    for (const [re, s] of patrones) {
      const m = k.match(re);
      if (m) return s.replace(/\$(\d)/g, (_, i) => traducirTexto(m[+i] ?? ""));
    }
    return undefined;
  }
  const lineas = k => k.split(SALTO).map(l => traducirTexto(l)).join(SALTO);
  function una(k, porLineas) {
    const clave = (porLineas ? "L:" : "T:") + k;
    if (cache.has(clave)) return cache.get(clave);
    let r;
    if (porLineas && k.includes(SALTO)) r = lineas(k);
    else {
      const p = plano(k);
      r = exactos.get(k) ?? exactos.get(p) ?? patron(k) ?? (p !== k ? patron(p) : undefined);
      if (r === undefined && k.includes(SALTO)) r = lineas(k);
      for (const sep of [" · ", ", "]) {  // listas unidas (motivos, países…): pieza a pieza
        if (r !== undefined || !p.includes(sep)) continue;
        const piezas = p.split(sep), trad = piezas.map(x => traducirTexto(x));
        if (trad.some((x, i) => x !== piezas[i])) r = trad.join(sep);
      }
    }
    if (cache.size < 5000) cache.set(clave, r ?? null);
    return r ?? null;
  }

  traducirTexto = (t, porLineas = false) => {
    const k = String(t).trim();
    if (!k || !LETRAS.test(k)) return t;
    const r = una(k, porLineas);
    return r == null ? t : String(t).replace(k, () => r);  // conserva los espacios de alrededor
  };

  const ATRIBUTOS = ["title", "placeholder", "aria-label"];
  const fuera = n => !!(n && n.closest && n.closest("script, style, code, textarea, [data-sin-traducir]"));
  function nodo(n) {
    if (n.nodeType === 3) {
      if (fuera(n.parentElement)) return;
      const v = n.nodeValue, t = traducirTexto(v, !!(n.parentElement && n.parentElement.closest("pre")));
      if (t !== v) n.nodeValue = t;
    } else if (n.nodeType === 1 && !fuera(n)) {
      for (const a of ATRIBUTOS) {
        const v = n.getAttribute(a);
        if (v) { const t = traducirTexto(v); if (t !== v) n.setAttribute(a, t); }
      }
      for (const h of n.childNodes) nodo(h);
    }
  }
  nodo(document.body);
  new MutationObserver(cambios => {
    for (const c of cambios) {
      if (c.type === "childList") c.addedNodes.forEach(nodo);
      else nodo(c.target);  // texto o atributo cambiado
    }
  }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATRIBUTOS});
  for (const f of ["confirm", "alert", "prompt"]) {
    const original = window[f].bind(window);
    window[f] = (m, ...resto) => original(traducirTexto(String(m ?? "")), ...resto);
  }
})();
