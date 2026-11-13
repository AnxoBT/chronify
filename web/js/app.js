// Resumen, comprobaciones, orden, fechas, Spotify, ajustes, sincronización e historial
let E = null;
async function cargar(recargar) {
  $("#hstat").textContent = "Leyendo…";
  try { E = await api("/api/estado" + (recargar ? "?recargar=1" : "")); }
  catch (e) { $("#hstat").textContent = "Error: " + e.message; toast("Error al leer: " + e.message); return; }
  if (recargar) {
    const zips = [...new Set(E.listas.map(l => l.origen.split(":")[0]))];
    toast(E.listas.length ? `Leídas ${E.listas.length} listas de ${zips.join(", ")}` : "No he encontrado ningún zip/CSV de Exportify en " + E.carpetas.join(" ; "));
  }
  const nErr = E.avisos.filter(a => a.gravedad === "error").length;
  $("#hstat").textContent = `${E.fuente} · ${E.cargado}`;
  $("#cards").replaceChildren(
    card("Listas", E.listas.length), card("Canciones", E.fechas.total),
    card("Fechas por revisar", E.fechas.aprox), card("Errores", nErr, nErr ? "error" : "ok"),
    card("Listas a reordenar", E.orden.filter(o => !o.fija && !o.ordenada).length));
  $("#tlistas").replaceChildren(...E.listas.map(l => el("tr", {}, el("td", {}, l.nombre), el("td", {}, l.pistas),
    el("td", {className:"muted small"}, l.origen), el("td", {className:"muted small"}, l.fecha))));
  $("#carpetas").textContent = "Busca en: " + E.carpetas.join(" ; ");
  $("#bienvenida").style.display = E.listas.length ? "none" : "";  // primera vez: cómo empezar
  if (E.android) modoAndroid();
  if (E.web) modoWeb();
  pintarAvisos(); pintarOrden(); pintarPendiente(E.pendiente, E.cupo);
}

// Versión web (iPhone, Mac, cualquier navegador): sin carpetas, sin actualizador ni USB; los datos viven en el navegador
function modoWeb() {
  if (document.body.classList.contains("web")) return;
  document.body.classList.add("web");
  $("#recargar").style.display = "none";
  $("#importar").className = "pri";
  $("#carpetas").style.display = "none";
  for (const id of ["#dataDir", "#verBuscar", "#sincAhora"]) { const b = $(id) && $(id).closest(".box"); if (b) b.style.display = "none"; }
  $("#guardarTxt").style.display = "none";  // cada txt se descarga o se copia desde su lista
  $("#copiaAhora").textContent = "Descargar copia";
  $("#copiaBox").querySelector(".ayuda").textContent = "Tus datos (fechas, tus listas, excepciones, sesión de Spotify, " +
    "países…) se guardan en este navegador. Descarga una copia de vez en cuando: si borras los datos del navegador o " +
    "cambias de dispositivo, la restauras. También sirve una copia del PC. Tiene datos privados: no la subas a ningún sitio público.";
}

// En el móvil la app no puede leer la carpeta Descargas: el zip se elige con "Importar zip"
function modoAndroid() {
  document.body.classList.add("android");
  $("#recargar").style.display = "none";
  $("#importar").className = "pri";
  $("#carpetas").style.display = "none";
  const exp = $("#dataDir") && $("#dataDir").closest(".box");
  if (exp) exp.style.display = "none";
  // la app de Spotify del móvil no deja seleccionar todo y pegar: los txt no sirven, se ordena por la API
  $("#guardarTxt").closest(".box").style.display = "none";
  $("#copiaBox").style.display = "none";  // la copia se hace en el PC
}

// Aviso arriba si un orden en Spotify se quedó a medias (cupo diario, bloqueo o cancelado)
function pintarPendiente(p, c) {
  const box = $("#pend");
  if (!p || !p.listas || !p.listas.length || SP_ACTIVO) { box.style.display = "none"; return; }
  box.style.display = "block";
  const libres = c && !E.bloqueado ? c.libres : 0;
  box.replaceChildren(el("div", {className:"row"},
    el("b", {}, `Ordenar en Spotify quedó a medias (${p.t}): ${p.listas.join(", ")}`),
    libres ? el("button", {className:"pri", onclick: spTarea("/api/spotify/seguir")}, `Seguir ahora (quedan ${libres} cambios hoy)`)
           : el("span", {className:"tag aviso"}, E.bloqueado ? `Spotify bloqueado hasta ${E.bloqueado}` : `Cupo de hoy gastado: se libera a partir de ${horaCupo(c)}`)),
    el("div", {className:"muted small", style:"margin-top:6px"},
      "Lo que ya está hecho se queda bien. Al seguir se vuelve a leer cada lista y se calcula lo que falta."));
}
const horaCupo = c => c && c.libera ? new Date(c.libera * 1000).toLocaleString(LOCALE, {day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"}) : "mañana";
const card = (t, v, cls = "") => el("div", {className:"box card"}, el("div", {className:"muted small"}, t), el("div", {className:"v " + cls}, String(v)));

const EXC = {sin_genero:"sin_genero", sin_decada:"sin_decada", fuera_de_mix:"fuera_de_mix", falta_en_mix:"fuera_de_mix",
  decada_distinta:"decada_distinta", version_dudosa:"version_dudosa", misma_cancion:"misma_cancion"};
const AVISOS_ABIERTOS = new Set();  // avisos largos desplegados (se conserva al repintar)
function pintarAvisos() {
  if (!E.avisos.length) { $("#avisos").replaceChildren(el("div", {className:"box"}, el("span", {className:"tag ok"}, "Todo cuadra"))); return; }
  $("#avisos").replaceChildren(...E.avisos.map(a => {
    const clave = a.tipo + a.texto + a.lista, abierto = AVISOS_ABIERTOS.has(clave) || a.pistas.length <= 15;
    const ver = abierto ? a.pistas : a.pistas.slice(0, 10);
    return el("div", {className:"box av"},
    el("div", {className:"row"}, el("span", {className:"tag " + a.gravedad}, a.gravedad), el("h3", {}, `${a.texto}${a.lista ? " · " + a.lista : ""}`),
      el("span", {className:"muted"}, a.pistas.length ? `(${a.pistas.length})` : "")),
    el("ul", {}, ...ver.map(p => el("li", {}, `${p.t} · ${p.fecha || "?"} `,
      el("span", {className:"muted small"}, `(${p.fuente}${p.spotify && p.spotify !== p.fecha ? ", Spotify " + p.spotify : ""}) `),
      p.motivos && p.motivos.length ? el("span", {className:"aviso small"}, p.motivos.join(" · ") + " ") : "",
      p.principal ? el("span", {className:"ok small"}, `→ buena: ${p.principal.album}${p.principal.popularidad != null ? ` (${p.principal.popularidad}/100)` : ""} `)
        : p.principal === false ? el("span", {className:"muted small"}, "(no hay otra copia más escuchada) ") : "",
      link(p.id), " ",
      EXC[a.tipo] ? el("button", {className:"mini", title:"No volver a avisar de esta canción", onclick: async () => {
        await api("/api/excepcion", {tipo:EXC[a.tipo], id:p.id}); toast("Añadida a excepciones en rules.json"); cargar(); }},
        a.tipo === "version_dudosa" ? "es la buena" : a.tipo === "misma_cancion" ? "son distintas" : "excepción") : "",
      " ", el("button", {className:"mini", onclick: () => editarFecha(p)}, "fecha"),
      p.destino ? " " : "", p.destino ? botonMoverEpoca(p, a.lista) : "",
      ...(p.sugeridas || []).filter(s => s.lista).map(s => [" ", botonAnadir(p, s)]).flat()))),
    abierto ? "" : el("button", {className:"mini", style:"margin-top:6px", onclick: () => { AVISOS_ABIERTOS.add(clave); pintarAvisos(); }},
      `ver las ${a.pistas.length}`),
    a.categoria === "copia" ? accionesCopias(a) : "");
  }));
}

// Copias poco escuchadas: buscar en Spotify la versión principal y cambiarla en todas tus listas
function accionesCopias(a) {
  const sinBuscar = a.pistas.filter(p => p.principal === undefined), conBuena = a.pistas.filter(p => p.principal);
  if (E.fuente !== "Spotify (API)")
    return el("div", {className:"muted small", style:"margin-top:8px"}, "Para buscar y cambiar las copias por la versión buena, pulsa 'Spotify (API)' en Resumen.");
  return el("div", {className:"row", style:"margin-top:10px"},
    sinBuscar.length ? el("button", {className:"mini pri", onclick: async () => {
      try { await api("/api/spotify/buscar_copias", {ids:sinBuscar.map(p => p.id)}); toast("Buscando…"); pintarSpotify(); } catch (e) { toast(e.message); } }},
      `Buscar la versión buena (${sinBuscar.length}, solo lectura)`) : "",
    conBuena.length ? el("button", {className:"mini pri", onclick: async () => {
      if (!confirm(`¿Cambiar ${conBuena.length} canciones por su versión buena en todas tus listas donde estén?\n\n` +
        "Cada una se pone en el mismo sitio y se quita la copia. Su fecha verificada se conserva. En las listas que no se " +
        "reordenan (las que guardan el orden en que añades) esas canciones pasarán a tener fecha de añadido de hoy.\n\n" +
        `Son unos ${conBuena.length * 6} cambios en Spotify: se para al llegar al límite diario y sigues otro día con este mismo botón.`)) return;
      try { await api("/api/spotify/cambiar_copias", {ids:conBuena.map(p => p.id)}); toast("Cambiando…"); pintarSpotify(); } catch (e) { toast(e.message); } }},
      `Cambiar por la buena (${conBuena.length})`) : "",
    el("span", {className:"muted small"}, "Cambiar gasta cupo de Spotify: unas 2 peticiones por lista en la que esté cada canción."));
}

// Añade la canción a la lista propuesta (género por sus artistas / época por su fecha), en su sitio cronológico
function botonAnadir(p, s) {
  if (E.fuente !== "Spotify (API)")
    return el("span", {className:"muted small", title:s.motivo + " · Pulsa 'Spotify (API)' en Resumen para añadirla desde aquí"}, `→ ¿${s.lista}?`);
  return el("button", {className:"mini pri", title:s.motivo, onclick: async () => {
    if (!confirm(`¿Añadir "${p.t}" a ${s.lista}?\n\n(${s.motivo}). Se coloca en su sitio cronológico.`)) return;
    try { await api("/api/spotify/anadir_a", {id:p.id, hacia:s.lista}); toast("Añadiendo…"); pintarSpotify(); }
    catch (e) { toast(e.message); } }}, `añadir a ${s.lista}`);
}

// Pasa la canción a la lista de época que le toca (solo leyendo de Spotify): se añade en su sitio y se quita de la otra
function botonMoverEpoca(p, desde) {
  if (E.fuente !== "Spotify (API)")
    return el("span", {className:"muted small", title:"Pulsa 'Spotify (API)' en Resumen para poder moverla desde aquí"}, `→ va en ${p.destino}`);
  return el("button", {className:"mini pri", onclick: async () => {
    if (!confirm(`¿Mover "${p.t}" de ${desde} a ${p.destino}?

Se añade a ${p.destino} en su sitio cronológico (allí su fecha de añadido será la de hoy) y se quita de ${desde}.`)) return;
    try { await api("/api/spotify/cambiar_epoca", {id:p.id, desde, hacia:p.destino}); toast("Moviendo…"); pintarSpotify(); }
    catch (e) { toast(e.message); } }}, `mover a ${p.destino}`);
}

// Si hay canciones con la fecha de Spotify sin verificar, avisa: ordenar las colocaría según esa fecha
function confirmarSinVerificar(n, quien) {
  if (!n) return {forzar:false};
  const r = prompt(`${quien} tiene ${n} canciones nuevas con la fecha de Spotify sin verificar: se colocarían según esa fecha, que puede estar mal.\n\n` +
    `Escribe 1 para revisarlas antes (Fechas → Nuevas), o 2 para ordenar igualmente.`, "1");
  if (r === "2") return {forzar:true};
  if (r === "1") { document.querySelector('#nav button[data-s="fechas"]').click(); $("#filtro").value = "nuevas"; cargarFechas(); }
  return null;
}
const dias = n => Math.max(1, Math.ceil(n / (E.cupo ? E.cupo.limite : 500)));

function pintarOrden() {
  const api_ = E.fuente === "Spotify (API)";
  $("#tordenar").replaceChildren(...E.orden.map(o => el("tr", {},
    el("td", {}, o.lista === "Liked_Songs" ? "Canciones que te gustan" : o.lista),
    el("td", {}, o.fija ? el("span", {className:"tag info"}, o.solo_lectura ? "solo lectura" : "no se reordena")
      : o.ordenada ? el("span", {className:"tag ok"}, "ya ordenada") : el("span", {className:"tag aviso"}, `${o.movidas} posiciones cambian`),
      !o.fija && !o.ordenada && o.peticiones != null ? el("span", {className:"muted small"}, ` · ${o.peticiones} cambios en Spotify${o.peticiones > (E.cupo ? E.cupo.limite : 500) ? ` (~${dias(o.peticiones)} días)` : ""}`) : "",
      !o.fija && o.sin_verificar ? el("span", {className:"tag aviso", style:"margin-left:6px", title:"Fecha de Spotify sin revisar: ordenar las colocaría según esa fecha"}, `${o.sin_verificar} sin verificar`) : ""),
    el("td", {className:"row"},
      E.android ? "" : el("button", {className:"mini", onclick: async () => { await navigator.clipboard.writeText(await api("/api/txt?lista=" + encodeURIComponent(o.clave))); toast(`Copiadas ${o.pistas} canciones de ${o.lista}`); }}, "copiar"),
      E.android ? "" : el("a", {href:"/api/txt?lista=" + encodeURIComponent(o.clave), download:o.lista + ".txt"}, "descargar"),
      api_ && o.en_lista_nueva ? el("button", {className:"mini pri", title:"Crea (o actualiza) en Spotify una lista con estas canciones ordenadas por fecha real",
        onclick: async () => {
          try { await api("/api/spotify/crear_ordenada", {lista:o.clave, idioma:IDIOMA}); toast("Creando la lista…"); pintarSpotify(); }
          catch (e) { toast(e.message); } }}, "crear lista ordenada") : "",
      api_ && !o.fija && !o.ordenada && !o.en_lista_nueva ? el("button", {className:"mini pri", onclick: async () => {
        const f = confirmarSinVerificar(o.sin_verificar, o.lista); if (!f) return;
        if (!f.forzar && !confirm(`¿Ordenar ${o.lista} en Spotify? Se moverán ${o.movidas} canciones (no se borra ninguna).` +
          (o.peticiones > E.cupo.libres ? `\n\nSon ${o.peticiones} cambios y hoy quedan ${E.cupo.libres}: se para al llegar al límite y sigues otro día.` : ""))) return;
        try { await api("/api/spotify/aplicar", {lista:o.clave, forzar:f.forzar}); toast("Ordenando…"); pintarSpotify(); }
        catch (e) { toast(e.message); } }}, "aplicar en Spotify") : ""))));
  // ordenar todas de una vez (se para sola al llegar al cupo diario y se sigue otro día)
  const pend = E.orden.filter(o => !o.fija && !o.ordenada && !o.en_lista_nueva), total = pend.reduce((s, o) => s + (o.peticiones || 0), 0);
  const sinVer = pend.reduce((s, o) => s + o.sin_verificar, 0), c = E.cupo || {libres:0, limite:500, usadas:0};
  $("#ordTodas").replaceChildren(
    el("div", {className:"row"}, el("b", {}, pend.length ? `${pend.length} listas por ordenar · ${total} cambios en Spotify` : "Todas las listas están ordenadas"),
      pend.length ? el("span", {className:"muted small"}, `(~${dias(total)} día${dias(total) > 1 ? "s" : ""} con el límite de ${c.limite}/día)`) : "",
      pend.length && E.bloqueado ? el("span", {className:"tag aviso"}, `Spotify bloqueado hasta ${E.bloqueado}`) : "",
      pend.length ? el("button", {className:"pri", disabled:!c.libres || !!E.bloqueado, onclick: async () => {
        const f = confirmarSinVerificar(sinVer, "Alguna lista"); if (!f) return;
        if (!f.forzar && !confirm(`¿Ordenar en Spotify ${pend.map(o => o.lista).join(", ")}?\n\nHoy caben ${c.libres} cambios; lo que no quepa queda apuntado para seguir otro día con un botón.` +
          (api_ ? "" : "\n\nAntes se leerán las listas de Spotify."))) return;
        try { await api("/api/spotify/ordenar_todas", {forzar:f.forzar}); toast("Ordenando…"); pintarSpotify(); } catch (e) { toast(e.message); } }},
        "Ordenar todas en Spotify") : ""),
    el("div", {className:"muted small", style:"margin-top:6px"},
      `Límite diario para que Spotify no bloquee la app: ${c.usadas}/${c.limite} cambios en las últimas 24 h` +
      (c.libres ? ` · quedan ${c.libres}` : ` · se libera a partir de ${horaCupo(c)}`) +
      ". Las canciones con fecha sin verificar se saltan salvo que digas ordenar igualmente."));
}
$("#guardarTxt").onclick = async () => { const r = await api("/api/guardar_txt", {}); toast(r.listas.length ? `Guardadas ${r.listas.length} en ${r.carpeta}` : "Nada que guardar: todo ordenado"); };
$("#recargar").onclick = () => cargar(true);
$("#importar").onclick = () => $("#importarArchivo").click();
$("#importarArchivo").onchange = async ev => {
  const f = ev.target.files[0]; ev.target.value = "";
  if (!f) return;
  toast(`Importando ${f.name}…`);
  try {
    const r = await fetch("/api/importar", {method:"POST", headers:{"X-Chronify":"1", "X-Nombre":encodeURIComponent(f.name)}, body:f});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.status);
    toast(`Importado ${j.nombre}: ${j.listas} listas`); cargar();
  } catch (e) { toast("No se pudo importar: " + e.message); }
};

async function editarFecha(p) {
  const f = prompt(`Fecha original de\n${p.t}\n(AAAA, AAAA-MM o AAAA-MM-DD)`, p.fecha || "");
  if (f === null || !/^\d{4}(-\d{2}(-\d{2})?)?$/.test(f.trim())) { if (f !== null) toast("Formato no válido"); return; }
  await api("/api/fecha", {id:p.id, fecha:f.trim()}); toast("Fecha guardada"); cargar(); if ($("#fechas").classList.contains("on")) cargarFechas();
}

let FECHAS = [];
async function cargarFechas() {
  FECHAS = await api("/api/fechas?filtro=" + $("#filtro").value);
  $("#tfechas").replaceChildren(...FECHAS.slice(0, 1500).map(p => el("tr", {},
    el("td", {}, p.t, el("div", {className:"muted small"}, p.album)),
    el("td", {}, p.fecha || "?"), el("td", {className:"muted small"}, p.fuente + (p.aprox ? " · aprox" : "")),
    el("td", {className:"muted small"}, p.spotify),
    el("td", {className:"row"}, el("button", {className:"mini", onclick: () => editarFecha(p)}, "editar"),
      el("button", {className:"mini", title:"La fecha actual es correcta", onclick: async () => {
        await api("/api/fecha", {id:p.id, fecha:p.fecha}); toast("Marcada como verificada"); cargar(); cargarFechas(); }}, "es correcta"), link(p.id)))));
}
$("#filtro").onchange = cargarFechas;

$("#mbBuscar").onclick = async () => {
  if (!FECHAS.length) return toast("No hay canciones en la tabla");
  if (FECHAS.length > 300 && !confirm(`Son ${FECHAS.length} canciones (~${Math.ceil(FECHAS.length * 2.3 / 60)} min). ¿Seguir?`)) return;
  await api("/api/mb", {ids: FECHAS.map(p => p.id)}); vigilarMB();
};
$("#mbCancelar").onclick = () => api("/api/mb", {cancelar:true});
let MB_T0 = null;  // [instante, hechos] al empezar a vigilar, para estimar el tiempo restante
async function vigilarMB() {
  let m;
  try { m = await api("/api/mb"); } catch (e) { return setTimeout(vigilarMB, 3000); }
  $("#mbCancelar").disabled = !m.activo; $("#mbBuscar").disabled = m.activo;
  $("#mbProg").textContent = m.error ? "Error: " + m.error : "";
  const pct = m.total ? Math.round(100 * m.hechos / m.total) : 0;
  $("#mbBarra").style.display = m.activo || m.total ? "block" : "none";
  $("#mbRelleno").style.width = pct + "%";
  $("#mbTitulo").textContent = m.activo ? `Buscando en MusicBrainz… ${m.hechos}/${m.total} (${pct}%)`
    : m.total ? `MusicBrainz terminado: ${m.hechos}/${m.total}` : "";
  $("#mbActual").textContent = m.activo ? "Ahora: " + m.actual : "Revisa abajo las propuestas y pulsa Guardar.";
  if (m.activo) {
    if (!MB_T0 || m.hechos < MB_T0[1]) MB_T0 = [Date.now(), m.hechos];
    const hechos = m.hechos - MB_T0[1], seg = (Date.now() - MB_T0[0]) / 1000;
    const resto = hechos > 2 ? (m.total - m.hechos) * seg / hechos : (m.total - m.hechos) * 3.5;  // ~3 peticiones/canción a 1/s
    $("#mbQueda").textContent = `· quedan ~${Math.max(1, Math.round(resto / 60))} min (puedes usar otras pestañas)`;
  } else { MB_T0 = null; $("#mbQueda").textContent = ""; }
  $("#mbInd").textContent = m.activo ? `${pct}%` : "";  // indicador en la pestaña Fechas
  pintarMB(m.propuestas);
  if (m.activo) setTimeout(vigilarMB, 1500);
}
// Elección del usuario por id (true/false); se conserva aunque la lista se repinte mientras busca
const MB_ELEGIDAS = new Map();
const anioDe = f => parseInt((f || "").slice(0, 4)) || 0;
// Dudosa: retrasa la fecha actual más de 2 años (MusicBrainz suele fallar con recopilatorios/regrabaciones),
// o la propuesta sale de Spotify y MusicBrainz dice otro año (Spotify a veces trae fechas anteriores erróneas)
const dudosa = p => (p.actual && anioDe(p.propuesta) - anioDe(p.actual) > 2) || (p.mb && anioDe(p.propuesta) !== anioDe(p.mb));
const marcada = p => MB_ELEGIDAS.has(p.id) ? MB_ELEGIDAS.get(p.id) : !dudosa(p);
function pintarMB(props) {
  const cambian = props.filter(p => p.cambia);
  if (!props.length) { $("#mbRes").style.display = "none"; return; }
  $("#mbRes").style.display = "block";
  const nDudosas = cambian.filter(dudosa).length;
  $("#mbRes").replaceChildren(
    el("div", {className:"row"}, el("b", {}, `${cambian.length} propuestas cambian de año`), el("span", {className:"muted small"}, `(${props.length - cambian.length} confirman el año actual)`),
      el("button", {className:"pri mini", onclick: async () => {
        const items = props.filter(p => !p.cambia || marcada(p)).filter(p => p.propuesta).map(p => ({id:p.id, fecha:p.propuesta, fuente:"musicbrainz"}));
        await api("/api/fecha", {items}); toast(`Guardadas ${items.length} fechas`); MB_ELEGIDAS.clear(); cargar(); cargarFechas(); }}, "Guardar marcadas + confirmadas")),
    nDudosas ? el("div", {className:"aviso small", style:"margin-top:6px"}, `${nDudosas} dudosas (en naranja, desmarcadas): retrasan la fecha más de 2 años o Spotify y MusicBrainz no coinciden; revísalas con "abrir" antes de marcarlas.`) : "",
    el("table", {}, el("tbody", {}, ...cambian.map(p => el("tr", {},
      el("td", {}, el("input", {type:"checkbox", checked:marcada(p), onchange: e => MB_ELEGIDAS.set(p.id, e.target.checked)})),
      el("td", {style: dudosa(p) ? "color:var(--warn)" : ""}, p.t), el("td", {className:"muted small"}, `ahora ${p.actual || "?"}`),
      el("td", {}, el("b", {style: dudosa(p) ? "color:var(--warn)" : ""}, p.propuesta)), el("td", {className:"muted small"}, `MB ${p.mb || "-"} · Spotify ${p.spotify}`), el("td", {}, link(p.id)))))));
}

const spTarea = (url, body) => async () => { try { await api(url, body || {}); } catch (e) { toast(e.message); } pintarSpotify(); };

async function pintarSpotify() {
  let s;
  try { s = await api("/api/spotify"); } catch (e) { $("#spEstado").textContent = "Error: " + e.message; return; }
  // Al abrir: si Spotify está conectado se lee de ahí (solo las listas que han cambiado desde la última vez)
  if (AUTO_LEER && E) {
    AUTO_LEER = false;
    // con el cupo del día gastado no se lee: Spotify también cuenta las lecturas y bloquearía la app 24 h
    if (s.conectado && !(s.cuenta && s.cuenta.error) && !s.bloqueado && !s.activo && E.fuente !== "Spotify (API)" && (!E.cupo || E.cupo.libres > 0)) {
      try { await api("/api/spotify/leer", {}); } catch (e) { /* se queda con el zip */ }
      return pintarSpotify();
    }
  }
  // Resumen: botón de leer y progreso de la tarea en curso
  if (s.bloqueado) {  // Spotify ha castigado a la app por exceso de peticiones: no se puede usar hasta esa hora
    $("#leerSp").replaceChildren(el("span", {className:"tag aviso", title:"Usa el zip de Exportify mientras tanto"},
      `Spotify bloqueado hasta ${s.bloqueado} (demasiadas peticiones)`));
  } else $("#leerSp").replaceChildren(s.conectado
    ? el("button", {className:"pri", disabled:s.activo, onclick:spTarea("/api/spotify/leer")}, "Spotify (API)")
    : el("span", {className:"muted small"}, "Spotify: sin conectar (Ajustes)"),
    s.activo ? el("span", {className:"tag info", style:"margin-left:8px"}, s.tarea + "…") : "",
    s.activo && s.tarea === "aplicar" ? el("button", {className:"mini", style:"margin-left:8px", onclick:spTarea("/api/spotify/cancelar")}, "Cancelar") : "");
  const logSp = () => [
    s.activo ? el("span", {className:"tag info"}, (s.tarea === "aplicar" ? "Ordenando en Spotify" : s.tarea) + "…") : "",
    s.activo && s.tarea === "aplicar" ? el("button", {className:"mini", style:"margin-left:8px", onclick:spTarea("/api/spotify/cancelar")}, "Cancelar") : "",
    s.error ? el("div", {className:"error small", style:"margin-top:8px"}, "Spotify: " + s.error) : "",
    s.log.length ? el("pre", {className:"muted small", style:"white-space:pre-wrap;margin:8px 0 0"}, s.log.join("\n")) : ""];
  $("#spLog").replaceChildren(...logSp().slice(2));
  $("#spLogOrd").replaceChildren(...logSp());
  $("#spLogOrd").style.display = s.activo || ((s.error || s.log.length) && s.tarea === "aplicar") ? "block" : "none";
  $("#spLoginError").textContent = s.login_error && !s.conectado ? "Último error al conectar: " + s.login_error : "";
  // Ajustes
  $("#cid").placeholder = s.client_id ? `guardado: ${s.client_id_corto}` : "pega aquí el Client ID de tu app";
  $("#redirect").textContent = s.redirect;
  $("#spEstado").replaceChildren(!s.client_id ? el("span", {className:"tag aviso"}, "falta el Client ID")
    : s.bloqueado ? el("span", {className:"tag aviso"}, `bloqueado por Spotify hasta ${s.bloqueado}`)
    : s.conectado && s.cuenta && s.cuenta.error ? el("span", {}, el("span", {className:"tag aviso"}, "conectado, pero sin acceso a la API"),
        el("div", {className:"muted small", style:"margin-top:6px"}, s.cuenta.error))
    : s.conectado ? el("span", {className:"tag ok"}, "conectado") : el("span", {className:"tag"}, "sin conectar"));
  $("#spConectar").style.display = s.client_id && !s.conectado ? "" : "none";
  $("#spDesconectar").style.display = s.conectado ? "" : "none";
  $("#spProbar").disabled = !s.conectado || s.activo;
  const p = s.prueba;
  $("#spPrueba").replaceChildren(s.activo && s.tarea === "probar" ? el("span", {className:"tag info"}, "probando…")
    : p ? el("span", {className:"tag " + (p.conserva_added_at ? "ok" : "error")},
        (p.conserva_added_at ? "OK: mover conserva la fecha de añadido" : "Mover CAMBIA la fecha de añadido") + ` (${p.fecha || ""})`)
    : el("span", {className:"muted small"}, "sin hacer"));
  if (s.activo) { SP_ACTIVO = true; setTimeout(pintarSpotify, 1500); }
  else if (SP_ACTIVO) {  // al acabar leer/aplicar/mover, refresca todo
    SP_ACTIVO = false;
    if (s.error) toast("Spotify: " + s.error);
    else { cargar(); if (s.tarea === "cambiar_epoca" || s.tarea === "anadir_a") toast(s.log[s.log.length - 1] ? "Hecho: " + s.log[0] : "Hecho"); }
  }
}
let SP_ACTIVO = false, AUTO_LEER = true;

$("#cidGuardar").onclick = async () => {
  const v = $("#cid").value.trim();
  if (!v) return toast("Pega el Client ID");
  try { await api("/api/spotify/client_id", {client_id:v}); $("#cid").value = ""; toast("Client ID guardado"); } catch (e) { toast(e.message); }
  pintarSpotify();
};
$("#redirectCopiar").onclick = () => navigator.clipboard.writeText($("#redirect").textContent).then(() => toast("Copiada"));
$("#spDesconectar").onclick = async () => { await api("/api/spotify/desconectar", {}); toast("Desconectado"); pintarSpotify(); };
$("#spProbar").onclick = spTarea("/api/spotify/probar");
$("#dataGuardar").onclick = async () => {
  try { await api("/api/ajustes", {data_dir:$("#dataDir").value}); toast("Guardado"); cargar(true); } catch (e) { toast(e.message); }
};
async function cargarAjustes() {
  const a = await api("/api/ajustes"); $("#dataDir").value = a.data_dir;
  $("#ghToken").placeholder = a.github_token ? "guardado (pega otro para cambiarlo)" : "github_pat_…";
}
$("#ghGuardar").onclick = async () => {
  try { await api("/api/ajustes", {github_token:$("#ghToken").value.trim()}); $("#ghToken").value = ""; toast("Token guardado"); }
  catch (e) { toast(e.message); }
  cargarAjustes(); comprobarVersion(true);
};
$("#verBuscar").onclick = () => comprobarVersion(true);

async function pintarSinc(comprobarMovil) {
  let x;
  try { x = await api("/api/sincronizar" + (comprobarMovil ? "?movil=1" : "")); } catch (e) { return; }
  if (x.android) {  // en el móvil no hay botón: se sincroniza desde el PC
    $("#sincAhora").style.display = "none";
    $("#sincAyuda").textContent = "Se sincroniza desde el Chronify del PC: conecta el móvil por USB (con la depuración USB activada) " +
      "y pulsa allí «Sincronizar con el móvil». Va por el cable: tus datos no salen de tus dispositivos.";
  }
  const cambios = u => u && u.length ? u.join(", ") : "nada";
  $("#sincEstado").replaceChildren(x.activo ? el("span", {className:"tag info"}, x.paso || "sincronizando…")
    : x.error ? el("span", {className:"tag aviso"}, x.error)
    : x.ultima ? el("span", {}, el("span", {className:"tag ok"}, `sincronizado ${x.ultima.t}`),
        el("span", {className:"muted"}, ` · al PC: ${cambios(x.ultima.pc)} · al móvil: ${cambios(x.ultima.movil)}`))
    : el("span", {className:"muted"}, x.motivo ? x.motivo : "todavía no"),
    !x.activo && x.conectado === false && x.ultima ? el("span", {className:"muted"}, ` · ahora: ${x.motivo}`) : "");
  $("#sincAhora").disabled = x.activo;
  if (x.activo) { SINC_ACTIVA = true; setTimeout(pintarSinc, 1000); }
  else if (SINC_ACTIVA) { SINC_ACTIVA = false; if (!x.error) { toast("Sincronizado con el móvil"); cargar(); } }
}
let SINC_ACTIVA = false;
$("#sincAhora").onclick = async () => { try { await api("/api/sincronizar", {}); } catch (e) { toast(e.message); } pintarSinc(); };
document.querySelector('#nav button[data-s="ajustes"]').addEventListener("click", () => { pintarSinc(true); cargarTusListas(); });  // ¿hay móvil?

async function comprobarVersion(forzar) {
  let u;
  try { u = await api("/api/actualizacion" + (forzar ? "?forzar=1" : "")); } catch (e) { return; }
  $("#verActual").textContent = "v" + u.actual;
  $("#verEstado").replaceChildren(u.error ? el("span", {className:"tag aviso"}, u.error)
    : u.hay ? el("span", {className:"tag ok"}, `hay una versión nueva: v${u.ultima}`)
    : el("span", {className:"tag"}, "tienes la última" + (forzar ? " (comprobado ahora)" : "")));
  pintarUpd(u);
  if (forzar && !u.error && !u.hay) toast("Ya tienes la última versión");
}
function pintarUpd(u) {
  const box = $("#upd");
  if (!u.hay && !u.activo && !u.hecho && !u.error_aplicar) { box.style.display = "none"; return; }
  box.style.display = "block";
  if (u.activo || u.hecho) {
    box.replaceChildren(el("b", {}, u.hecho ? `Actualizado a v${u.hecho}. Reiniciando…` : "Actualizando Chronify…"),
      el("pre", {className:"muted small", style:"white-space:pre-wrap;margin:8px 0 0"}, (u.log || []).join("\n")),
      el("div", {className:"barra"}, el("div", {style:`width:${u.hecho ? 100 : 50}%`})));
    if (u.hecho && u.instalacion === "apk") location.href = "/android/instalar";  // instalador de Android
    else if (u.hecho) esperarReinicio(u.hecho); else setTimeout(async () => pintarUpd(await api("/api/actualizacion")), 1000);
    return;
  }
  const notas = el("pre", {className:"small", style:"white-space:pre-wrap;display:none;margin:10px 0 0;max-height:300px;overflow:auto"}, u.notas || "");
  box.replaceChildren(
    el("div", {className:"row"}, el("b", {}, `Nueva versión de Chronify: v${u.ultima}`), el("span", {className:"muted small"}, `(tienes v${u.actual})`),
      el("button", {className:"mini", onclick: () => notas.style.display = notas.style.display ? "" : "none"}, "ver novedades"),
      el("button", {className:"pri", onclick: actualizarYa}, "Actualizar ahora")),
    el("div", {className:"muted small", style:"margin-top:6px"}, u.instalacion === "apk"
      ? "Se descarga el APK nuevo y Android te pide instalarlo. Tus datos se conservan."
      : u.instalacion === "git"
      ? "Se hará git pull. Tus fechas y ajustes se conservan."
      : "Se descarga e instala sola. Se conservan tu .env, la caché, tus fechas y tus excepciones; Chronify se reinicia al acabar."),
    u.error_aplicar ? el("div", {className:"error small", style:"margin-top:6px"}, "Error al actualizar: " + u.error_aplicar) : "",
    notas);
}
async function actualizarYa() {
  if (!confirm("¿Actualizar Chronify ahora? Tarda unos segundos y se reinicia solo.")) return;
  try { await api("/api/actualizacion/aplicar", {}); } catch (e) { return toast(e.message); }
  pintarUpd(await api("/api/actualizacion"));
}
async function esperarReinicio(nueva) {  // la instancia nueva arranca en el mismo puerto; al responder, recarga
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try { const v = await api("/api/version"); if (v.version === nueva) return location.reload(); } catch (e) {}
  }
  toast("No ha vuelto a arrancar: cierra la ventana y abre Chronify con el acceso directo");
}
// ───────────────────────── Historial ─────────────────────────
const TIPOS_HIST = {fecha:"fecha", artista:"país", excepcion:"excepción", spotify:"Spotify", listas:"listas"};
async function cargarHistorial() {
  const h = await api("/api/historial");
  $("#thist").replaceChildren(...(h.length ? h.map(e => el("tr", {style: e.deshecha ? "opacity:.5" : ""},
    el("td", {className:"muted small", style:"white-space:nowrap"}, e.t),
    el("td", {}, el("span", {className:"tag", style:"margin-right:6px"}, TIPOS_HIST[e.tipo] || e.tipo), e.texto,
      e.deshecha ? el("span", {className:"muted small"}, " (deshecho)") : ""),
    el("td", {}, (e.tipo === "fecha" || e.tipo === "artista") && !e.deshecha && !e.deshace
      ? el("button", {className:"mini", onclick: async () => {
          try { await api("/api/historial/deshacer", {uid:e.uid}); toast("Deshecho"); cargarHistorial(); cargar(); } catch (x) { toast(x.message); } }}, "deshacer")
      : ""))) : [el("tr", {}, el("td", {className:"muted", colSpan:3}, "Todavía no hay cambios apuntados."))]));
}

// ───────────────────────── Estadísticas ─────────────────────────

async function pintarCopia() {
  if (document.body.classList.contains("web")) { $("#copiaEstado").textContent = "en este navegador"; return; }
  let c;
  try { c = await api("/api/copia"); } catch (e) { return; }
  $("#copiaEstado").replaceChildren(c.ultima
    ? el("span", {title:c.ultima.ruta}, c.ultima.fecha + " ", el("span", {className:"muted"}, "en " + c.carpeta))
    : el("span", {className:"tag aviso"}, "ninguna todavía"));
}
$("#copiaRestaurar").onclick = () => $("#copiaArchivo").click();
$("#copiaArchivo").onchange = async ev => {
  const f = ev.target.files[0];
  ev.target.value = "";
  if (!f || !confirm(`¿Restaurar la copia ${f.name}? Sustituye tus datos actuales de este dispositivo ` +
    "(fechas, tus listas, excepciones, sesión de Spotify, cachés) por los de la copia.")) return;
  try {
    const r = await fetch("/api/copia/restaurar", {method:"POST", headers:{"X-Chronify":"1"}, body:f});
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
    toast("Copia restaurada"); cargar(); pintarSpotify();
  } catch (e) { toast("No se pudo restaurar: " + e.message); }
};
$("#copiaAhora").onclick = async () => {
  if (document.body.classList.contains("web")) {  // web: la copia se descarga
    const r = await fetch("/api/copia", {method:"POST", headers:{"Content-Type":"application/json", "X-Chronify":"1"}, body:"{}"});
    if (!r.ok) return toast("No se pudo hacer la copia");
    const nombre = ((r.headers.get("Content-Disposition") || "").match(/filename="(.+)"/) || [])[1] || "chronify-copia.zip";
    return descargarArchivo(await r.blob(), nombre);
  }
  $("#copiaAhora").disabled = true;
  try { const r = await api("/api/copia", {}); toast(`Copia hecha: ${r.archivos} archivos, ${fmt(r.kb)} KB`); }
  catch (e) { toast(e.message); }
  $("#copiaAhora").disabled = false;
  pintarCopia();
};

// ── Ajustes → Tus listas: qué papel tiene cada lista (rules.json) ──
// Nombres generales (cada uno organiza sus listas a su manera); las claves de rules.json se mantienen por compatibilidad
const PAPELES = [["", "Normal: se ordena por fecha"], ["mix", "General: une otras listas"], ["base", "Parte de la general"],
  ["base-libre", "Parte de la general, sin género obligatorio"], ["epoca", "Época (por años)"], ["genero", "Género o estilo"],
  ["ignorar", "Ignorar: no se lee"]];
// Canciones que te gustan: Spotify no deja reordenarlas (van por fecha de añadido); como mucho, en una lista nueva
const PAPELES_LIKED = [["", "Solo lectura: no se toca"], ["nueva", "Ordenar en una lista nueva"], ["ignorar", "Ignorar: no se lee"]];
let TL = null;
async function cargarTusListas() {
  try { TL = await api("/api/reglas"); } catch (e) { $("#tlEstado").textContent = "Error: " + e.message; return; }
  const papel = n => n === TL.mix ? "mix" : TL.idiomas.includes(n) ? (n === TL.friki ? "base-libre" : "base")
    : n in TL.decadas ? "epoca" : TL.generos.includes(n) ? "genero" : TL.ignorar.includes(n) ? "ignorar" : "";
  if (!TL.listas.length) {
    $("#tlListas").replaceChildren(el("tr", {}, el("td", {colSpan:5, className:"muted"}, "Primero carga tus listas (Resumen).")));
    return;
  }
  $("#tlListas").replaceChildren(...TL.listas.map(l => {
    if (l.solo_lectura) {
      const sel = el("select", {title:"Spotify no deja reordenar las canciones que te gustan: se pueden ordenar en una lista nueva"},
        ...PAPELES_LIKED.map(([v, t]) => el("option", {value:v}, t)));
      sel.value = TL.ignorar.includes(l.nombre) ? "ignorar" : TL.liked_ordenar ? "nueva" : "";
      const tr = el("tr", {}, el("td", {}, l.nombre === "Liked_Songs" ? "Canciones que te gustan" : l.nombre),
        el("td", {}, l.n == null ? "—" : fmt(l.n)), el("td", {colSpan:3}, sel));
      tr._leer = () => ({nombre:l.nombre, papel:sel.value === "ignorar" ? "ignorar" : "", liked:sel.value});
      return tr;
    }
    const sel = el("select", {}, ...PAPELES.map(([v, t]) => el("option", {value:v}, t)));
    sel.value = papel(l.nombre);
    const rango = TL.decadas[l.nombre] || [null, null];
    const desde = el("input", {type:"number", placeholder:"desde", value:rango[0] ?? "", style:"width:80px"});
    const hasta = el("input", {type:"number", placeholder:"hasta", value:rango[1] ?? "", style:"width:80px"});
    const anios = el("span", {}, desde, " – ", hasta);
    const fija = el("input", {type:"checkbox", checked:TL.no_reordenar.includes(l.nombre)});
    const ver = () => { anios.style.visibility = sel.value === "epoca" ? "visible" : "hidden"; };
    sel.onchange = () => { ver(); if (sel.value === "mix") [...$("#tlListas").querySelectorAll("select")].forEach(s => { if (s !== sel && s.value === "mix") s.value = ""; }); };
    ver();
    const tr = el("tr", {}, el("td", {}, l.nombre), el("td", {}, l.n == null ? "—" : fmt(l.n)), el("td", {}, sel), el("td", {}, anios), el("td", {}, fija));
    tr._leer = () => ({nombre:l.nombre, papel:sel.value, desde:desde.value, hasta:hasta.value, fija:fija.checked});
    return tr;
  }));
  const vacio = !TL.mix && !TL.idiomas.length && !Object.keys(TL.decadas).length && !TL.generos.length;
  $("#tlEstado").textContent = vacio ? "Sin configurar: se puede ordenar cualquier lista, pero no se comprueba nada entre listas." : "";
}
$("#tlGuardar").onclick = async () => {
  const filas = [...$("#tlListas").querySelectorAll("tr")].filter(tr => tr._leer).map(tr => tr._leer());
  const de = p => filas.filter(f => f.papel === p).map(f => f.nombre);
  const cuerpo = {liked_ordenar:filas.some(f => f.liked === "nueva"),
    mix:(filas.find(f => f.papel === "mix") || {}).nombre || "", idiomas:[...de("base"), ...de("base-libre")],
    friki:de("base-libre")[0] || "", generos:de("genero"), ignorar:de("ignorar"), no_reordenar:filas.filter(f => f.fija).map(f => f.nombre),
    decadas:Object.fromEntries(filas.filter(f => f.papel === "epoca").map(f => [f.nombre, [f.desde || null, f.hasta || null]]))};
  if (de("base-libre").length > 1) return toast("Solo una lista puede ir sin género obligatorio");
  try {
    const r = await api("/api/reglas", cuerpo);
    toast("Guardado");
    if (r.recargar) {  // ignorar/dejar de ignorar: hay que volver a leer las listas
      if (E && E.fuente === "Spotify (API)") { if (!E.cupo || E.cupo.libres > 0) { await api("/api/spotify/leer", {}).catch(() => {}); pintarSpotify(); } }
      else await cargar(true);
    } else await cargar();
    cargarTusListas();
  } catch (e) { toast(e.message); }
};

// ── bienvenida (primera vez) e idioma ──
$("#bvImportar").onclick = () => $("#importarArchivo").click();
const irA = (s, foco) => { document.querySelector(`#nav button[data-s="${s}"]`).click(); if (foco) setTimeout(() => $(foco).scrollIntoView({block:"start"}), 50); };
$("#bvSpotify").onclick = () => irA("ajustes", "#cid");
$("#bvListas").onclick = () => irA("ajustes", "#tusListas");
document.querySelectorAll(".selIdioma").forEach(s => { s.value = IDIOMA; s.onchange = () => cambiarIdioma(s.value); });

// ── guía de inicio: 4 pasos la primera vez en cada dispositivo; se puede volver a ver desde Ajustes ──
let GUIA = 0;
const PASOS_GUIA = document.querySelectorAll("#guia .gpaso").length;
function pintarGuia() {
  document.querySelectorAll("#guia .gpaso").forEach((p, i) => p.classList.toggle("on", i === GUIA));
  $("#gPuntos").replaceChildren(...[...Array(PASOS_GUIA)].map((_, i) => el("i", {className: i === GUIA ? "on" : ""})));
  $("#gAtras").style.visibility = GUIA ? "visible" : "hidden";
  $("#gSig").textContent = traducirTexto(GUIA === PASOS_GUIA - 1 ? "Empezar" : "Siguiente");
  document.querySelectorAll("#guia [data-idioma]").forEach(b => b.classList.toggle("on", b.dataset.idioma === IDIOMA));
}
function abrirGuia(i = 0) { GUIA = i; $("#guia").classList.add("on"); pintarGuia(); }
function cerrarGuia() {
  $("#guia").classList.remove("on");
  try { localStorage.setItem("chronify_guia", "1"); } catch (e) {}
}
$("#gSig").onclick = () => { if (GUIA === PASOS_GUIA - 1) return cerrarGuia(); GUIA++; pintarGuia(); };
$("#gAtras").onclick = () => { GUIA = Math.max(0, GUIA - 1); pintarGuia(); };
$("#gSaltar").onclick = ev => { ev.preventDefault(); cerrarGuia(); };
$("#verGuia").onclick = () => abrirGuia(0);
document.querySelectorAll("#guia [data-idioma]").forEach(b => b.onclick = () => {
  if (b.dataset.idioma !== IDIOMA) { try { sessionStorage.setItem("chronify_guia_abierta", "1"); } catch (e) {} cambiarIdioma(b.dataset.idioma); }
});
(() => {  // primera vez en este dispositivo (o vuelve tras cambiar de idioma desde la propia guía)
  let vista = null, seguir = null;
  try { vista = localStorage.getItem("chronify_guia"); seguir = sessionStorage.getItem("chronify_guia_abierta"); sessionStorage.removeItem("chronify_guia_abierta"); } catch (e) {}
  if (!vista || seguir) abrirGuia(0);
})();

// ── novedades tras actualizar: cambios desde la última versión que se abrió en este dispositivo (CHANGELOG) ──
const tuplaVersion = v => String(v).replace(/^v/i, "").split(".").map(x => parseInt(x) || 0);
const masNueva = (a, b) => { const x = tuplaVersion(a), y = tuplaVersion(b); for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0); return false; };
function textoConNegritas(t) {  // **así** → <b> (sin innerHTML)
  return t.replace(/`/g, "").split("**").map((trozo, i) => i % 2 ? el("b", {}, trozo) : trozo.replace(/\*([^*]+)\*/g, "$1"));
}
async function mostrarNovedades() {
  let actual;
  try { actual = (await api("/api/version")).version; } catch (e) { return; }
  let vista = null;
  try { vista = localStorage.getItem("chronify_version"); localStorage.setItem("chronify_version", actual); } catch (e) { return; }
  if (!vista || !masNueva(actual, vista) || $("#guia").classList.contains("on")) return;  // instalación nueva: ya está la guía
  let lista;
  try { lista = await api(`/api/novedades?desde=${encodeURIComponent(vista)}&idioma=${IDIOMA}`); } catch (e) { return; }
  if (!lista.length) return;
  $("#nvTitulo").textContent = traducirTexto(`Novedades de la versión ${actual}`);
  $("#nvLista").replaceChildren(...lista.slice(0, 4).flatMap(v => [
    lista.length > 1 ? el("h4", {}, `v${v.version}` + (v.fecha ? ` · ${v.fecha}` : "")) : "",
    v.intro ? el("p", {className:"muted small", style:"margin:0 0 6px"}, v.intro) : "",
    el("ul", {}, ...v.puntos.map(p => el("li", {}, ...textoConNegritas(p))))]));
  $("#novedades").classList.add("on");
}
$("#nvCerrar").onclick = () => $("#novedades").classList.remove("on");
mostrarNovedades();

// ── sincronizar por Wi-Fi (core/wifi.py): uno espera con dirección + código, el otro conecta ──
let WIFI_VIGILAR = false;
async function pintarWifi() {
  let w;
  try { w = await api("/api/wifi"); } catch (e) { return; }
  if (w.web) { $("#wifiBox").style.display = "none"; return; }
  $("#wfEsperar").textContent = traducirTexto(w.esperando ? "Cancelar" : "Esperar conexión (2 min)");
  $("#wfEsperar").className = w.esperando ? "" : "pri";
  $("#wfEspera").replaceChildren(w.esperando ? el("div", {className:"codigoWifi"},
    el("div", {}, el("span", {className:"muted small"}, "Dirección"), el("b", {}, w.direccion)),
    el("div", {}, el("span", {className:"muted small"}, "Código"), el("b", {}, w.codigo)),
    el("div", {className:"muted small"}, traducirTexto(`Escríbelos en el otro dispositivo · quedan ${w.quedan} s`))) : "");
  $("#wfConectar").disabled = w.conectando || w.esperando;
  const res = w.resultado;
  $("#wfEstado").replaceChildren(
    w.conectando ? el("span", {className:"tag info"}, "Sincronizando…") : "",
    w.log.length && (w.conectando || w.error) ? el("pre", {className:"muted small", style:"white-space:pre-wrap;margin:6px 0 0"}, w.log.join("\n")) : "",
    w.error ? el("div", {className:"error"}, w.error) : "",
    res && !w.conectando ? el("div", {}, el("span", {className:"tag ok"}, "Sincronizado"), ` ${res.t} · `,
      traducirTexto(`aquí: ${res.aqui.length ? res.aqui.join(", ") : "nada nuevo"} · allí: ${res.alli.length ? res.alli.join(", ") : "nada nuevo"}`)) : "",
    w.apk_listo && E && E.android ? el("div", {style:"margin-top:8px"}, el("button", {className:"pri", onclick: () => { location.href = "/android/instalar"; }},
      traducirTexto(`Instalar Chronify v${w.apk_listo}`))) : "");
  const vivo = w.esperando || w.conectando;
  if (vivo) { WIFI_VIGILAR = true; setTimeout(pintarWifi, 1000); }
  else if (WIFI_VIGILAR) { WIFI_VIGILAR = false; if (res) { cargar(); toast(traducirTexto("Sincronizado por Wi-Fi")); } }
}
$("#wfEsperar").onclick = async () => {
  try {
    const w = await api("/api/wifi");
    await api(w.esperando ? "/api/wifi/parar" : "/api/wifi/esperar", {});
  } catch (e) { toast(e.message); }
  pintarWifi();
};
$("#wfConectar").onclick = async () => {
  const direccion = $("#wfDir").value.trim(), codigo = $("#wfCodigo").value.trim();
  try { localStorage.setItem("chronify_wifi_dir", direccion); } catch (e) {}
  try { await api("/api/wifi/conectar", {direccion, codigo}); $("#wfCodigo").value = ""; } catch (e) { toast(e.message); }
  pintarWifi();
};
try { $("#wfDir").value = localStorage.getItem("chronify_wifi_dir") || ""; } catch (e) {}
document.querySelector('#nav button[data-s="ajustes"]').addEventListener("click", pintarWifi);
