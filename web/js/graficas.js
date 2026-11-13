// Gráficas SVG de Estadísticas: barras, apiladas, calor, mapa del mundo (zoom) y ánimo
const NS = "http://www.w3.org/2000/svg";
function sv(tag, attrs = {}, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
  for (const k of kids) e.append(k instanceof Node ? k : document.createTextNode(k ?? ""));
  return e;
}
const fmt = n => (n ?? 0).toLocaleString(LOCALE);
const mmss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const TIP = $("#tip");
// tooltip que sigue al ratón; contenido = array de nodos/textos (o función que lo devuelve)
function conTip(node, contenido) {
  node.addEventListener("mousemove", ev => {
    TIP.replaceChildren(...(typeof contenido === "function" ? contenido() : contenido));
    TIP.style.display = "block";
    const w = TIP.offsetWidth, h = TIP.offsetHeight;
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
    if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
    TIP.style.left = x + "px"; TIP.style.top = y + "px";
  });
  node.addEventListener("mouseleave", () => TIP.style.display = "none");
  return node;
}
// escala secuencial de un solo tono (verde Spotify): bajo = oscuro, cerca del fondo; alto = brillante
const RAMPA = [[22, 58, 38], [27, 110, 62], [30, 170, 82], [30, 215, 96], [150, 240, 180]];
function verde(t) {
  t = Math.max(0, Math.min(1, t)) * (RAMPA.length - 1);
  const i = Math.min(RAMPA.length - 2, Math.floor(t)), f = t - i, a = RAMPA[i], b = RAMPA[i + 1];
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
}
const SERIES = ["var(--s1)", "var(--s2)", "var(--s3)"];
const tarjeta = (titulo, sub, ...kids) => el("div", {className:"st"}, el("h2", {}, titulo), sub ? el("div", {className:"sub"}, sub) : "", ...kids);
const ancho = n => (n.classList.add("ancho"), n);
const leyenda = (series, colores) => el("div", {className:"leyenda"}, ...series.map((s, i) =>
  el("span", {}, el("i", {style:`background:${colores[i]}`}), s)));
const pistaLi = (p, extra) => el("li", {}, el("a", {href:`https://open.spotify.com/track/${p.id}`, target:"_blank", rel:"noopener"}, p.t),
  el("span", {className:"muted"}, ` · ${p.anio || "?"}${extra ? " · " + extra(p) : ""}`));

// barras verticales (una serie): datos [{x, n, tip}]
// en el móvil las gráficas se dibujan a escala estrecha para que el texto se lea
const MOVIL = () => innerWidth < 700;
const TACTIL = matchMedia("(pointer:coarse)").matches;
function barrasV(datos, {alto = 200, cada = 1, color = "var(--acc)", formatoY = fmt, W = 800} = {}) {
  if (MOVIL()) {  // si quien llama ya ha elegido qué etiquetas poner (las demás vacías), se respetan
    W = Math.min(W, 440);
    if (datos.every(d => d.x !== "")) cada = Math.max(cada, Math.ceil(datos.length / 9));
  }
  const ml = 38, mb = 22, mt = 6, H = alto, max = Math.max(1, ...datos.map(d => d.n));
  const bw = (W - ml) / datos.length, g = sv("svg", {viewBox:`0 0 ${W} ${H}`, class:"graf"});
  const y = v => mt + (H - mt - mb) * (1 - v / max);
  for (let k = 0; k <= 4; k++) {
    const v = max * k / 4;
    g.append(sv("line", {x1:ml, x2:W, y1:y(v), y2:y(v), class:k ? "rej" : "eje"}),
             sv("text", {x:ml - 6, y:y(v) + 4, "text-anchor":"end"}, formatoY(Math.round(v))));
  }
  datos.forEach((d, i) => {
    const x = ml + i * bw, h = H - mb - y(d.n), w = Math.max(1, bw - 2);
    // extremo superior redondeado, base recta sobre el eje
    const r = Math.min(3, w / 2, h);
    if (d.n) g.append(sv("path", {fill:color,
      d:`M${x + 1},${H - mb}V${y(d.n) + r}q0,${-r} ${r},${-r}h${w - 2 * r}q${r},0 ${r},${r}V${H - mb}Z`}));
    if (i % cada === 0) g.append(sv("text", {x:x + bw / 2, y:H - 6, "text-anchor":"middle"}, d.x));
    g.append(conTip(sv("rect", {x, y:mt, width:bw, height:H - mt - mb, fill:"transparent"}), d.tip || [el("b", {}, d.x), fmt(d.n)]));
  });
  return g;
}

// barras apiladas por categoría (pocas series, con hueco de 2px entre segmentos)
function apiladas(cats, series, colores, {alto = 200, W = 800} = {}) {
  if (MOVIL()) W = Math.min(W, 440);
  const ml = 38, mb = 22, mt = 6, H = alto;
  const tot = cats.map((_, i) => series.reduce((s, x) => s + x.valores[i], 0)), max = Math.max(1, ...tot);
  const bw = (W - ml) / cats.length, g = sv("svg", {viewBox:`0 0 ${W} ${H}`, class:"graf"});
  const esc = v => (H - mt - mb) * v / max;
  for (let k = 0; k <= 4; k++) {
    const v = max * k / 4, yy = H - mb - esc(v);
    g.append(sv("line", {x1:ml, x2:W, y1:yy, y2:yy, class:k ? "rej" : "eje"}), sv("text", {x:ml - 6, y:yy + 4, "text-anchor":"end"}, fmt(Math.round(v))));
  }
  cats.forEach((c, i) => {
    let base = H - mb;
    const x = ml + i * bw + bw * .18, w = bw * .64;
    series.forEach((s, j) => {
      const h = esc(s.valores[i]);
      if (h > 0) { g.append(sv("rect", {x, y:base - h, width:w, height:Math.max(0, h - 2), rx:2, fill:colores[j]})); base -= h; }
    });
    g.append(sv("text", {x:ml + i * bw + bw / 2, y:H - 6, "text-anchor":"middle"}, c));
    g.append(conTip(sv("rect", {x:ml + i * bw, y:mt, width:bw, height:H - mt - mb, fill:"transparent"}),
      () => [el("b", {}, `${c} · ${fmt(tot[i])}`), ...series.map((s, j) => el("div", {}, el("span", {style:`color:${colores[j]}`}, "■ "),
        `${s.nombre}: ${fmt(s.valores[i])}${tot[i] ? ` (${Math.round(100 * s.valores[i] / tot[i])} %)` : ""}`))]));
  });
  return g;
}

// barras horizontales en HTML (rankings): items [{nombre, n, extra, tip}]
function hbar(items, {color = "var(--acc)", valor = d => fmt(d.n)} = {}) {
  const max = Math.max(1, ...items.map(d => d.n));
  return el("div", {className:"hb"}, ...items.flatMap(d => {
    const fila = [el("div", {className:"nom", title:d.nombre}, d.nombre, d.extra ? el("span", {className:"muted small"}, " " + d.extra) : ""),
      el("div", {}, el("div", {className:"bar", style:`width:${100 * d.n / max}%;background:${color}`})), el("div", {className:"num"}, valor(d))];
    if (d.tip) fila.forEach(n => conTip(n, d.tip));
    return fila;
  }));
}

// mapa de calor: filas [{nombre, valores}] × columnas
function calor(filas, cols, {tip} = {}) {
  const max = Math.max(1, ...filas.flatMap(f => f.valores));
  return el("div", {className:"calor", style:`grid-template-columns:minmax(70px,auto) repeat(${cols.length}, minmax(0,1fr))`},
    el("div", {}), ...cols.map(c => el("div", {style:"text-align:center"}, c)),
    ...filas.flatMap(f => [el("div", {style:"align-self:center"}, f.nombre), ...f.valores.map((v, i) =>
      conTip(el("div", {className:"c", style: v ? `background:${verde(0.12 + 0.88 * v / max)}` : ""}),
        tip ? tip(f, i, v) : [el("b", {}, `${f.nombre} · ${cols[i]}`), `${fmt(v)} canciones`]))]));
}

let MUNDO = null;
async function mapa(paises) {
  MUNDO = MUNDO || await api("/mundo.json");
  const max = Math.max(1, ...Object.values(paises).map(p => p.n)), L = Math.log1p(max);
  const color = n => verde(0.1 + 0.9 * Math.log1p(n) / L);
  // margen alrededor para que no se corte el borde (Tierra del Fuego, Alaska…)
  const M = 8, base = {x:-M, y:-M, w:MUNDO.w + 2 * M, h:MUNDO.h + 2 * M};
  const g = sv("svg", {viewBox:`${base.x} ${base.y} ${base.w} ${base.h}`, class:"graf mapa", style:"cursor:grab;touch-action:none;overflow:hidden;border-radius:8px"});
  const tipPais = (m, d) => () => [el("b", {}, m.n), d ? el("div", {}, `${fmt(d.n)} canciones · ${d.artistas} artista${d.artistas > 1 ? "s" : ""}`) : el("div", {className:"muted"}, "Ninguna canción de aquí"),
    ...(d ? d.top.map(a => el("div", {className:"muted"}, `${a.nombre} (${a.n})`)) : [])];
  const puntos = [];
  for (const m of MUNDO.paises) {
    const d = paises[m.c];
    if (m.d) g.append(conTip(sv("path", {d:m.d, fill: d ? color(d.n) : "var(--sindato)", "vector-effect":"non-scaling-stroke"}), tipPais(m, d)));
    if (m.p && (d || !m.d)) {
      const c = sv("circle", {cx:m.p[0], cy:m.p[1], r: d ? 3.2 : 1.4, fill: d ? color(d.n) : "#3a444e",
        stroke: d ? "#0f1317" : "none", "stroke-width":.8, "vector-effect":"non-scaling-stroke"});
      c.dataset.r = d ? 3.2 : 1.4;
      puntos.push(c);
      g.append(conTip(c, tipPais(m, d)));
    }
  }
  // zoom con la rueda (hacia donde apunta el ratón), arrastrar para moverse, doble clic para volver
  let vb = {...base};
  const aplicar = () => {
    const z = base.w / vb.w;
    g.setAttribute("viewBox", `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
    for (const c of puntos) c.setAttribute("r", c.dataset.r / Math.sqrt(z));  // los puntos de países pequeños no crecen tanto
    zoomTxt.textContent = z > 1.01 ? `×${z.toFixed(1)}` : "";
  };
  const limitar = () => {
    vb.w = Math.min(base.w, Math.max(base.w / 12, vb.w)); vb.h = vb.w * base.h / base.w;
    vb.x = Math.min(base.x + base.w - vb.w, Math.max(base.x, vb.x)); vb.y = Math.min(base.y + base.h - vb.h, Math.max(base.y, vb.y));
  };
  const zoom = (f, cx = .5, cy = .5) => {  // cx, cy: punto fijo en fracción del recuadro visible
    const nw = vb.w / f, nh = vb.h / f;
    vb = {x: vb.x + (vb.w - nw) * cx, y: vb.y + (vb.h - nh) * cy, w: nw, h: nh};
    limitar(); aplicar();
  };
  g.addEventListener("wheel", ev => {
    ev.preventDefault();
    const r = g.getBoundingClientRect();
    zoom(ev.deltaY < 0 ? 1.25 : 1 / 1.25, (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
  }, {passive:false});
  // un dedo / ratón: arrastrar; dos dedos: pellizcar para acercar o alejar (móvil)
  let arrastre = null;
  const dedos = new Map();
  let pellizco = null;
  const distancia = () => { const [a, b] = [...dedos.values()]; return Math.hypot(a.x - b.x, a.y - b.y); };
  const centro = () => { const [a, b] = [...dedos.values()]; return {x:(a.x + b.x) / 2, y:(a.y + b.y) / 2}; };
  g.addEventListener("pointerdown", ev => {
    dedos.set(ev.pointerId, {x:ev.clientX, y:ev.clientY});
    g.setPointerCapture(ev.pointerId);
    if (dedos.size === 2) { pellizco = {d:distancia()}; arrastre = null; }
    else { arrastre = {x:ev.clientX, y:ev.clientY, vb:{...vb}}; g.style.cursor = "grabbing"; }
  });
  g.addEventListener("pointermove", ev => {
    if (!dedos.has(ev.pointerId)) return;
    dedos.set(ev.pointerId, {x:ev.clientX, y:ev.clientY});
    const r = g.getBoundingClientRect();
    if (pellizco && dedos.size === 2) {
      const d = distancia(), c = centro();
      if (d > 0 && pellizco.d > 0) zoom(d / pellizco.d, (c.x - r.left) / r.width, (c.y - r.top) / r.height);
      pellizco.d = d;
      return;
    }
    if (!arrastre) return;
    vb.x = arrastre.vb.x - (ev.clientX - arrastre.x) * vb.w / r.width;
    vb.y = arrastre.vb.y - (ev.clientY - arrastre.y) * vb.h / r.height;
    limitar(); aplicar();
  });
  const soltar = ev => {
    dedos.delete(ev.pointerId);
    if (dedos.size < 2) pellizco = null;
    if (dedos.size === 1) { const [p] = [...dedos.values()]; arrastre = {x:p.x, y:p.y, vb:{...vb}}; }  // sigue arrastrando con el otro dedo
    else if (!dedos.size) { arrastre = null; g.style.cursor = "grab"; }
  };
  g.addEventListener("pointerup", soltar); g.addEventListener("pointercancel", soltar);
  g.addEventListener("dblclick", () => { vb = {...base}; aplicar(); });
  const zoomTxt = el("span", {className:"muted small"});
  const controles = el("div", {className:"row", style:"gap:6px"},
    el("button", {className:"mini", title:"Acercar", onclick: () => zoom(1.5)}, "+"),
    el("button", {className:"mini", title:"Alejar", onclick: () => zoom(1 / 1.5)}, "−"),
    el("button", {className:"mini", title:"Ver el mundo entero", onclick: () => { vb = {...base}; aplicar(); }}, "mundo entero"),
    zoomTxt, el("span", {className:"muted small"}, matchMedia("(pointer:coarse)").matches
      ? "· pellizca para acercar, arrastra para moverte" : "· rueda del ratón para acercar, arrastra para moverte, doble clic para volver"));
  const grad = `linear-gradient(90deg, ${[0, .25, .5, .75, 1].map(t => verde(0.1 + 0.9 * t)).join(",")})`;
  return [g, el("div", {className:"row", style:"justify-content:space-between;margin-top:6px"},
    el("div", {className:"leyenda", style:"align-items:center;margin:0"},
      el("span", {}, el("i", {style:"background:var(--sindato);border:1px solid #3a444e"}), "sin canciones"),
      el("span", {}, "1 ", el("span", {style:`display:inline-block;width:140px;height:10px;border-radius:5px;vertical-align:-1px;background:${grad}`}), ` ${fmt(max)} canciones`)),
    controles)];
}
const nombrePais = c => (MUNDO && (MUNDO.paises.find(p => p.c === c) || {}).n) || c;

// nube de puntos alegría × energía (cuatro cuadrantes de ánimo)
function animo(puntos) {
  // los nombres de los cuadrantes van fuera del recuadro (arriba y abajo) para no tapar canciones
  const W = MOVIL() ? 440 : 800, H = MOVIL() ? 440 : 480, ml = 30, mr = 10, mt = MOVIL() ? 46 : 30, mb = MOVIL() ? 66 : 52;
  const g = sv("svg", {viewBox:`0 0 ${W} ${H}`, class:"graf"});
  const X = v => ml + (W - ml - mr) * v, Y = v => H - mb - (H - mt - mb) * v;
  g.append(sv("rect", {x:ml, y:mt, width:W - ml - mr, height:H - mt - mb, fill:"none", class:"eje"}),
    sv("line", {x1:X(.5), x2:X(.5), y1:mt, y2:H - mb, class:"eje"}), sv("line", {x1:ml, x2:W - mr, y1:Y(.5), y2:Y(.5), class:"eje"}));
  const cuad = [[0, 1, "Tensión", "tristes y enérgicas"], [1, 1, "Euforia", "alegres y enérgicas"], [0, 0, "Melancolía", "tristes y tranquilas"], [1, 0, "Calma", "alegres y tranquilas"]];
  for (const [cx, cy, nom, desc] of cuad) {
    const n = puntos.filter(p => (p[0] >= .5) === !!cx && (p[1] >= .5) === !!cy).length;
    const pct = `${fmt(n)} ${desc} (${Math.round(100 * n / puntos.length)} %)`, ancla = cx ? "end" : "start", x = cx ? W - mr : ml;
    if (MOVIL()) g.append(  // dos líneas: nombre y cifra
      sv("text", {x, y: cy ? mt - 24 : H - mb + 18, "text-anchor":ancla, style:"font-size:14px;font-weight:650;fill:var(--text)"}, nom),
      sv("text", {x, y: cy ? mt - 8 : H - mb + 34, "text-anchor":ancla}, pct));
    else g.append(sv("text", {x, y: cy ? mt - 10 : H - mb + 20, "text-anchor":ancla},
      sv("tspan", {style:"font-size:14px;font-weight:650;fill:var(--text)"}, nom), sv("tspan", {}, ` · ${pct}`)));
  }
  g.append(sv("text", {x:W / 2, y:H - 8, "text-anchor":"middle"}, "triste ← alegría → alegre"),
    sv("text", {x:12, y:(mt + H - mb) / 2, "text-anchor":"middle", transform:`rotate(-90 12 ${(mt + H - mb) / 2})`}, "tranquila ← energía → enérgica"));
  for (const p of puntos) g.append(conTip(sv("circle", {cx:X(p[0]), cy:Y(p[1]), r:3, fill:"var(--acc)", "fill-opacity":.35}),
    [el("b", {}, p[2]), `alegría ${Math.round(p[0] * 100)} · energía ${Math.round(p[1] * 100)}`]));
  return g;
}
