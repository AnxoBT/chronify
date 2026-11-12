// Utilidades comunes: $, el() (construir DOM sin innerHTML), api(), toast(), pestañas
const $ = s => document.querySelector(s);
function el(tag, props = {}, ...kids) {
  const e = Object.assign(document.createElement(tag), props);
  for (const k of kids) e.append(k instanceof Node ? k : document.createTextNode(k ?? ""));
  return e;
}
const api = async (url, body) => {
  const r = await fetch(url, body ? {method:"POST", headers:{"Content-Type":"application/json", "X-Chronify":"1"}, body:JSON.stringify(body)} : {});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
  return (r.headers.get("Content-Type") || "").includes("json") ? r.json() : r.text();
};
function toast(m) { const t = $("#toast"); t.textContent = m; t.style.display = "block"; clearTimeout(t._h); t._h = setTimeout(() => t.style.display = "none", 2500); }
const link = id => el("a", {href:`https://open.spotify.com/track/${id}`, target:"_blank", rel:"noopener"}, "abrir");

document.querySelectorAll("#nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("#nav button, section").forEach(x => x.classList.remove("on"));
  b.classList.add("on"); $("#" + b.dataset.s).classList.add("on");
  if (b.dataset.s === "fechas") cargarFechas();
  if (b.dataset.s === "stats") cargarStats();
  if (b.dataset.s === "historial") cargarHistorial();
});

// Móvil: deslizar a la izquierda / derecha para cambiar de pestaña, como en las redes sociales: la pestaña sigue al
// dedo, la de al lado asoma por el borde y al soltar termina la transición (o vuelve si no se ha deslizado bastante).
// No se activa sobre el mapa (zoom y arrastre), campos de texto o algo que se desplace en horizontal.
(() => {
  const DURACION = matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 230;
  let g = null;  // gesto en curso
  const bloquea = e => {
    if (!(e instanceof Element) || e.closest(".mapa, input, select, textarea")) return true;
    for (let n = e; n && n !== document.body; n = n.parentElement)
      if (n.scrollWidth > n.clientWidth + 2 && /(auto|scroll)/.test(getComputedStyle(n).overflowX)) return true;
    return false;
  };
  const botones = () => [...document.querySelectorAll("#nav button")].filter(b => b.offsetParent !== null);
  const poner = (el, x, transicion) => {
    el.style.transition = transicion ? `transform ${DURACION}ms cubic-bezier(.2,.7,.2,1)` : "none";
    el.style.transform = x ? `translate3d(${x}px,0,0)` : "";
  };
  const limpiar = el => { if (el) { el.style.transition = el.style.transform = ""; el.classList.remove("asomando"); el.style.top = ""; } };

  function vecina(lado) {  // lado: +1 la siguiente (a la derecha), -1 la anterior
    const bs = botones(), i = bs.findIndex(b => b.classList.contains("on")), b = bs[i + lado];
    return b ? {boton: b, seccion: $("#" + b.dataset.s)} : null;
  }
  function asomar(lado) {  // coloca la pestaña de al lado justo al borde, a la altura de lo que se ve ahora
    if (g.lado === lado) return;
    if (g.v) limpiar(g.v.seccion);
    g.lado = lado;
    g.v = vecina(lado);
    if (!g.v) return;
    const s = g.v.seccion;
    s.classList.add("asomando");
    s.style.top = scrollY + "px";  // a la altura de la vista: al cambiar se sube arriba del todo y no salta
  }

  addEventListener("touchstart", ev => {
    if (g && g.animando) return;
    g = null;
    if (ev.touches.length !== 1 || bloquea(ev.target)) return;
    const sec = document.querySelector("section.on");
    if (!sec) return;
    g = {x0: ev.touches[0].clientX, y0: ev.touches[0].clientY, t0: Date.now(), sec, dir: null, dx: 0, lado: 0, v: null,
         ancho: sec.parentElement.clientWidth};
  }, {passive: true});

  addEventListener("touchmove", ev => {
    if (!g || g.animando) return;
    const t = ev.touches[0], dx = t.clientX - g.x0, dy = t.clientY - g.y0;
    if (!g.dir) {  // primero se decide si el gesto es horizontal (pestañas) o vertical (desplazar la página)
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      g.dir = Math.abs(dx) > Math.abs(dy) * 1.3 ? "h" : "v";
      if (g.dir === "h") document.body.classList.add("deslizando");
    }
    if (g.dir !== "h") return;
    ev.preventDefault();  // horizontal: la página no se mueve en vertical mientras tanto
    asomar(dx < 0 ? 1 : -1);
    g.dx = g.v ? dx : dx * 0.3;  // sin pestaña a ese lado: resistencia
    poner(g.sec, g.dx);
    if (g.v) poner(g.v.seccion, g.dx + (dx < 0 ? g.ancho : -g.ancho));
  }, {passive: false});

  addEventListener("touchend", () => {
    if (!g || g.dir !== "h" || g.animando) { g = null; return; }
    const {sec, v, dx, ancho} = g, rapido = Math.abs(dx) / Math.max(1, Date.now() - g.t0) > 0.45;
    const cambia = v && (Math.abs(dx) > ancho * 0.35 || (rapido && Math.abs(dx) > 40));
    g.animando = true;
    const lado = dx < 0 ? -1 : 1;
    poner(sec, cambia ? lado * ancho : 0, true);
    if (v) poner(v.seccion, cambia ? 0 : -lado * ancho, true);
    const acabar = () => {
      limpiar(sec);
      if (v) limpiar(v.seccion);
      document.body.classList.remove("deslizando");
      if (cambia) {
        v.boton.click();
        v.boton.scrollIntoView({inline: "center", block: "nearest"});
        scrollTo({top: 0});
      }
      g = null;
    };
    if (DURACION) setTimeout(acabar, DURACION + 20); else acabar();
  });
  addEventListener("touchcancel", () => {
    if (!g || g.animando) return;
    limpiar(g.sec); if (g.v) limpiar(g.v.seccion);
    document.body.classList.remove("deslizando");
    g = null;
  });
})();
