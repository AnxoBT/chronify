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

// Móvil: deslizar a la izquierda / derecha cambia a la pestaña siguiente / anterior (como en Instagram).
// No se activa al deslizar sobre el mapa (zoom y arrastre), campos de texto o algo que se desplace en horizontal.
(() => {
  let x0 = null, y0 = 0, t0 = 0;
  const bloquea = e => {
    if (!(e instanceof Element) || e.closest(".mapa, input, select, textarea")) return true;
    for (let n = e; n && n !== document.body; n = n.parentElement)
      if (n.scrollWidth > n.clientWidth + 2 && /(auto|scroll)/.test(getComputedStyle(n).overflowX)) return true;
    return false;
  };
  addEventListener("touchstart", ev => {
    if (ev.touches.length !== 1 || bloquea(ev.target)) { x0 = null; return; }
    x0 = ev.touches[0].clientX; y0 = ev.touches[0].clientY; t0 = Date.now();
  }, {passive:true});
  addEventListener("touchend", ev => {
    if (x0 === null) return;
    const t = ev.changedTouches[0], dx = t.clientX - x0, dy = t.clientY - y0;
    x0 = null;
    if (Math.abs(dx) < 70 || Math.abs(dx) < 2 * Math.abs(dy) || Date.now() - t0 > 700) return;  // gesto claro y rápido
    const bs = [...document.querySelectorAll("#nav button")].filter(b => b.offsetParent !== null);
    const j = bs.findIndex(b => b.classList.contains("on")) + (dx < 0 ? 1 : -1);
    if (j < 0 || j >= bs.length) return;
    bs[j].click();
    bs[j].scrollIntoView({inline:"center", block:"nearest"});
    scrollTo({top:0});
  }, {passive:true});
})();
