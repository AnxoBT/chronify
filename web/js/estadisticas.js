// Pestaña Estadísticas: tarjetas, Tu año, evolución, países sin buscar
let ST = null;
async function cargarStats(silencioso = false) {  // silencioso: se queda lo de antes hasta tener lo nuevo (sin saltos)
  const sel = $("#stLista");
  if (!silencioso) $("#stCuerpo").replaceChildren(el("div", {className:"muted"}, "Calculando…"));
  try { ST = await api("/api/estadisticas" + (sel.value ? "?lista=" + encodeURIComponent(sel.value) : "")); }
  catch (e) { $("#stCuerpo").replaceChildren(el("div", {className:"error"}, "Error: " + e.message)); return; }
  if (ST.error) { $("#stCuerpo").replaceChildren(el("div", {className:"error"}, ST.error)); return; }
  sel.replaceChildren(...ST.listas.map(x => el("option", {value:x.nombre, selected:x.nombre === ST.lista},
    `${x.favoritas ? "♥ Canciones que te gustan" : x.nombre} (${fmt(x.n)})`)));
  vigilarArtistas();
  vigilarDiscos();
  const s = ST, r = s.resumen, out = [];
  // cifras grandes
  const heroe = (v, k) => el("div", {className:"hero"}, el("div", {className:"v"}, v), el("div", {className:"k"}, k));
  out.push(el("div", {className:"heroes"},
    heroe(fmt(r.canciones), "canciones"), heroe(fmt(r.artistas), "artistas"), heroe(fmt(Math.round(r.horas)) + " h", `de música (${(r.horas / 24).toFixed(1)} días)`),
    heroe(fmt(Object.keys(s.paises).length), "países"), heroe(`${r.anio_max - r.anio_min} años`, `de música, de ${r.anio_min} a ${r.anio_max}`),
    heroe(String(r.anio_mediana), "año mediano"), heroe(r.duracion_media ? mmss(r.duracion_media) : "–", "duración media"),
    heroe(r.popularidad != null ? r.popularidad + "/100" : "–", "popularidad media")));
  const grid = el("div", {className:"st-grid"});
  out.push(grid);
  // línea temporal
  const cada = s.por_anio.length > 40 ? (MOVIL() ? 10 : 5) : s.por_anio.length > 20 ? (MOVIL() ? 5 : 2) : 1;
  grid.append(ancho(tarjeta("Tu música en el tiempo", `Canciones por año de la fecha real (${TACTIL ? "toca" : "pasa el ratón por"} una barra para ver las más conocidas de ese año)`,
    barrasV(s.por_anio.map(d => ({x: d.anio % cada === 0 ? String(d.anio) : "", n:d.n,
      tip:[el("b", {}, `${d.anio} · ${fmt(d.n)} canciones`), ...d.ejemplos.map(e => el("div", {className:"muted"}, e))]})), {alto:220}),
    el("div", {className:"leyenda", style:"margin-top:10px"}, ...s.por_decada.map(d => el("span", {}, el("b", {style:"color:var(--text)"}, d.decada), ` ${fmt(d.n)} (${Math.round(100 * d.n / r.canciones)} %)`))))));
  // mapa
  const [svgMapa, leyMapa] = await mapa(s.paises);
  const ranking = Object.entries(s.paises).sort((a, b) => b[1].n - a[1].n);
  const conPais = ranking.reduce((x, [, d]) => x + d.n, 0);
  grid.append(ancho(tarjeta("De dónde es tu música", `País de origen del artista principal (MusicBrainz). ${fmt(conPais)} de ${fmt(r.canciones)} canciones con país conocido.`,
    svgMapa, leyMapa,
    el("div", {className:"cols2", style:"margin-top:12px"},
      el("div", {}, el("div", {className:"sub"}, "Ranking de países"), hbar(ranking.slice(0, 15).map(([c, d]) => ({nombre:nombrePais(c), n:d.n,
        extra:`${d.artistas} art.`, tip:[el("b", {}, nombrePais(c)), ...d.top.map(a => el("div", {}, `${a.nombre} (${a.n})`))]})))),
      el("div", {}, el("div", {className:"sub"}, `Artistas sin país (${fmt(s.sin_pais.length)}) · corrige o completa a mano con el código de 2 letras`),
        sinPais(s.sin_pais))))));
  // artistas
  grid.append(tarjeta("Tus artistas", "Más canciones en la lista (cuenta también las colaboraciones)",
    hbar(s.top_artistas.map(a => ({nombre:a.nombre, n:a.n, extra:[a.pais ? nombrePais(a.pais) : "", a.desde ? (a.desde === a.hasta ? a.desde : `${a.desde}–${a.hasta}`) : ""].filter(Boolean).join(" · "),
      tip:[el("b", {}, `${a.nombre} · ${a.n} canciones`), el("div", {className:"muted"}, a.canciones.join(" · ") + (a.n > a.canciones.length ? " …" : ""))]})))));
  const tipos = s.tipos.filter(t => t.nombre !== "Sin dato"), sinTipo = (s.tipos.find(t => t.nombre === "Sin dato") || {}).n || 0;
  grid.append(tarjeta("Quién canta", `Artista principal: solista o grupo, y mujer u hombre en solistas${sinTipo ? ` · ${fmt(sinTipo)} canciones sin dato todavía` : ""}`,
    hbar(tipos), el("div", {style:"height:12px"}),
    s.genero_artista.length ? hbar(s.genero_artista, {color:"var(--s2)"}) : "",
    el("div", {className:"sub", style:"margin-top:14px"}, "Solistas por década"),
    leyenda(s.genero_por_decada.series.map(x => x.nombre).slice(0, 2), SERIES),
    apiladas(s.genero_por_decada.decadas.map(d => d.slice(2)), s.genero_por_decada.series.slice(0, 2), SERIES, {alto:200, W:440})));
  if (s.edad) grid.append(tarjeta("Edad del artista al sacar la canción", `Media: ${s.edad.media} años (${fmt(s.edad.n)} canciones de solistas con fecha de nacimiento)`,
    barrasV(s.edad.hist.map(d => ({x:`${d.desde}`, n:d.n, tip:[el("b", {}, `${d.desde}–${d.desde + 4} años`), `${fmt(d.n)} canciones`]})), {alto:190, W:440}),
    el("div", {className:"cols2", style:"margin-top:10px"},
      el("div", {}, el("div", {className:"sub"}, "Los más jóvenes"), el("ul", {className:"lista-mini"}, ...s.edad.jovenes.map(p => pistaLi(p, p => `${p.edad} años`)))),
      el("div", {}, el("div", {className:"sub"}, "Los más veteranos"), el("ul", {className:"lista-mini"}, ...s.edad.mayores.map(p => pistaLi(p, p => `${p.edad} años`)))))));
  // géneros
  grid.append(tarjeta("Tus listas de género por década", "Cuántas canciones de cada lista de género hay en cada década",
    calor(s.generos_listas.filas.map(f => ({nombre:`${f.nombre} (${fmt(f.n)})`, valores:f.valores})), s.generos_listas.decadas.map(d => d.slice(2)))));
  grid.append(tarjeta("Géneros según Spotify", `Los 25 más frecuentes de ${fmt(s.generos_spotify_total)} géneros distintos (por artista)`,
    hbar(s.generos_spotify)));
  grid.append(tarjeta("Lo más de nicho", s.nicho
      ? `Oyentes de tus artistas en ListenBrainz (la comunidad de MusicBrainz). Mediana: ${fmt(s.nicho.mediana)} · ${s.nicho.pct_nicho} % tienen menos de 1.000 oyentes (${fmt(s.nicho.con_dato)} de ${fmt(s.nicho.total)} artistas con dato).`
      : "Pulsa «Buscar en MusicBrainz» arriba para saber cuántos oyentes tiene cada artista.",
    s.nicho ? el("div", {}, el("div", {className:"sub"}, "Los artistas menos escuchados que tienes"),
      hbar(s.nicho.artistas.map(a => ({nombre:a.nombre, n:a.oyentes, extra:a.ej,
        tip:[el("b", {}, a.nombre), `${fmt(a.oyentes)} oyentes en ListenBrainz · ${a.n} canción${a.n > 1 ? "es" : ""} en la lista`]})), {color:"var(--s3)"}),
      el("div", {className:"sub", style:"margin-top:14px"}, "Los más escuchados que tienes"),
      hbar(s.nicho.famosos.map(a => ({nombre:a.nombre, n:a.oyentes})), {color:"var(--s1)"}),
      el("div", {className:"sub", style:"margin-top:14px"}, "Los géneros más raros de tu música"),
      el("ul", {className:"lista-mini"}, ...s.nicho.generos.map(g => el("li", {}, el("b", {}, g.nombre),
        el("span", {className:"muted"}, ` · ${g.n} canción${g.n > 1 ? "es" : ""} · ${g.ej}`))))) : ""));
  if (s.idiomas.series.length) grid.append(ancho(tarjeta("Listas de la general por década", "Canciones de cada lista que forma la lista general según la década de la canción",
    leyenda(s.idiomas.series.map(x => `${x.nombre} (${fmt(x.n)})`), SERIES), apiladas(s.idiomas.decadas, s.idiomas.series, SERIES, {alto:200}))));
  // sonido
  if (s.audio) {
    const a = s.audio;
    grid.append(ancho(tarjeta("El ánimo de tu música", `Cada punto es una canción: alegría (valencia) y energía según Spotify. Media: alegría ${Math.round(a.medias.valencia * 100)}, energía ${Math.round(a.medias.energia * 100)}, bailable ${Math.round(a.medias.bailable * 100)}.`,
      animo(a.puntos))));
    grid.append(tarjeta("Ritmo", `BPM (pulsaciones por minuto). Media: ${a.bpm_medio} BPM`,
      barrasV(a.bpm.map(d => ({x:String(d.desde), n:d.n, tip:[el("b", {}, `${d.desde}–${d.desde + 9} BPM`), `${fmt(d.n)} canciones`]})), {alto:190, cada:2, W:440})));
    grid.append(tarjeta("Tonalidades", s.modo ? `Mayor ${Math.round(100 * s.modo.mayor / (s.modo.mayor + s.modo.menor))} % · menor ${Math.round(100 * s.modo.menor / (s.modo.mayor + s.modo.menor))} %` : "",
      hbar(s.tonalidades, {color:"var(--s1)"})));
    grid.append(ancho(tarjeta("Cómo ha cambiado el ánimo por década", "Media de alegría, energía y lo bailable de tus canciones de cada década (0–100)",
      calor([["Alegría", "valencia"], ["Energía", "energia"], ["Bailable", "bailable"]].map(([n, k]) => ({nombre:n, valores:a.animo_por_decada.map(d => Math.round(d[k] * 100))})),
        a.animo_por_decada.map(d => d.decada.slice(2)), {tip:(f, i, v) => [el("b", {}, `${f.nombre} · ${a.animo_por_decada[i].decada}`), `${v}/100`]}))));
    grid.append(ancho(tarjeta("Récords de sonido", "",
      el("div", {className:"curios"}, ...Object.entries(a.extremos).map(([k, ps]) => el("div", {className:"curio"}, el("div", {className:"k"}, k),
        el("ul", {className:"lista-mini", style:"margin-top:6px"}, ...ps.slice(0, 3).map(p => pistaLi(p, k.includes("BPM") ? (p => `${Math.round(p.v)} BPM`) : (p => `${Math.round(p.v * 100)}`))))))))));
  }
  // popularidad y duración
  grid.append(tarjeta("Mainstream o joyas ocultas", "Popularidad actual en Spotify (0–100) de tus canciones",
    barrasV(s.popularidad.hist.map(d => ({x:String(d.desde), n:d.n, tip:[el("b", {}, `${d.desde}–${d.desde + 9}`), `${fmt(d.n)} canciones`]})), {alto:180, W:440}),
    el("div", {className:"cols2", style:"margin-top:10px"},
      el("div", {}, el("div", {className:"sub"}, "Las más populares"), el("ul", {className:"lista-mini"}, ...s.popularidad.mainstream.map(p => pistaLi(p, p => p.v)))),
      el("div", {}, el("div", {className:"sub"}, "Joyas ocultas"), el("ul", {className:"lista-mini"}, ...s.popularidad.joyas.map(p => pistaLi(p, p => p.v)))))));
  grid.append(tarjeta("Duración", "Duración media de tus canciones de cada década",
    barrasV(s.duracion.por_decada.map(d => ({x:d.decada.slice(2), n:d.seg, tip:[el("b", {}, d.decada), `media ${mmss(d.seg)}`]})), {alto:180, formatoY:mmss, W:440}),
    el("div", {className:"cols2", style:"margin-top:10px"},
      el("div", {}, el("div", {className:"sub"}, "Las más largas"), el("ul", {className:"lista-mini"}, ...s.duracion.largas.map(p => pistaLi(p, p => mmss(p.v))))),
      el("div", {}, el("div", {className:"sub"}, "Las más cortas"), el("ul", {className:"lista-mini"}, ...s.duracion.cortas.map(p => pistaLi(p, p => mmss(p.v))))))));
  // discos
  if (s.discos) grid.append(...tarjetasDiscos(s.discos));
  // cuándo añades música
  if (s.anadidas) {
    const ad = s.anadidas, cadaM = MOVIL() ? (ad.meses.length > 36 ? 12 : 6) : ad.meses.length > 36 ? 6 : 3;
    grid.append(ancho(tarjeta("Cuándo añades música", `Fecha de añadido en las listas que no se reordenan (conservan el histórico). Edad media de la canción al añadirla: ${ad.edad_media} años · ${ad.nuevas_pct} % las añadiste el mismo año o el siguiente de salir.`,
      el("div", {className:"sub"}, "Canciones añadidas cada mes"),
      barrasV(ad.meses.map((m, i) => ({x: i % cadaM === 0 ? m.mes.slice(2).replace("-", "/") : "", n:m.n,
        tip:[el("b", {}, m.mes), `${fmt(m.n)} añadidas · ${fmt(m.total)} en total`]})), {alto:170}),
      el("div", {className:"sub", style:"margin-top:12px"}, "Total acumulado"),
      barrasV(ad.meses.map((m, i) => ({x: i % cadaM === 0 ? m.mes.slice(2).replace("-", "/") : "", n:m.total,
        tip:[el("b", {}, m.mes), `${fmt(m.total)} canciones en total`]})), {alto:130, color:"var(--s1)"}),
      el("div", {className:"sub", style:"margin-top:12px"}, "Día y hora a la que añades canciones"),
      calor((IDIOMA === "en" ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  // "mar" sería también marzo
        : ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]).map((d, i) => ({nombre:d, valores:ad.calor[i]})),
        [...Array(24).keys()].map(h => h % 3 === 0 ? String(h) : ""),
        {tip:(f, h, v) => [el("b", {}, `${f.nombre} de ${h}:00 a ${h}:59`), `${fmt(v)} canciones`]}))));
  }
  // tu año (según lo que añadiste cada año) + evolución mes a mes
  const anios = Object.keys(s.anios || {});
  if (anios.length) grid.append(ancho(tuAnio(s, anios)));
  // curiosidades
  grid.append(ancho(tarjeta("Curiosidades", "",
    el("div", {className:"curios"}, ...s.curiosidades.slice(0, Math.floor(s.curiosidades.length / 4) * 4).map(c => el("div", {className:"curio"}, el("div", {className:"k"}, c.t),
      el("div", {className:"v"}, c.id ? enlaceSpotify("track", c.id, c.v) : c.v),
      c.d ? el("div", {className:"d"}, c.d) : ""))))));
  $("#stCuerpo").replaceChildren(...out);
}
$("#stLista").onchange = cargarStats;

let ANIO_ELEGIDO = null;
function tuAnio(s, anios) {
  if (!ANIO_ELEGIDO || !s.anios[ANIO_ELEGIDO]) ANIO_ELEGIDO = anios[anios.length - 1];
  const caja = tarjeta("Tu año", "Lo que añadiste a tus listas cada año: artistas, países y décadas que descubriste");
  const pintar = () => {
    const a = s.anios[ANIO_ELEGIDO], y = Number(ANIO_ELEGIDO);
    const chips = el("div", {className:"row", style:"margin-bottom:12px"}, ...anios.map(x => el("button",
      {className: x === ANIO_ELEGIDO ? "pri mini" : "mini", onclick: () => { ANIO_ELEGIDO = x; pintar(); }}, x)));
    const heroe = (v, k) => el("div", {className:"hero"}, el("div", {className:"v"}, v), el("div", {className:"k"}, k));
    const cancion = (k, p, extra) => el("div", {className:"curio"}, el("div", {className:"k"}, k),
      el("div", {className:"v"}, enlaceSpotify("track", p.id, p.t)),
      el("div", {className:"d"}, extra));
    const M = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
    caja.replaceChildren(caja.firstChild, caja.children[1], chips,
      el("div", {className:"heroes", style:"grid-template-columns:repeat(4,minmax(0,1fr))"},
        heroe(fmt(a.n), "canciones añadidas"), heroe(fmt(Math.round(a.minutos / 60)) + " h", "de música nueva"),
        heroe(fmt(a.n_nuevos_artistas), "artistas que descubriste"), heroe(fmt(a.nuevos_paises.length), "países nuevos")),
      el("div", {className:"cols2"},
        el("div", {}, el("div", {className:"sub"}, "Los artistas que más añadiste"), hbar(a.artistas)),
        el("div", {}, el("div", {className:"sub"}, `Mes a mes (el que más: ${a.mes.nombre}, ${fmt(a.mes.n)})`),
          barrasV(a.por_mes.map((n, i) => ({x:M[i], n, tip:[el("b", {}, `${M[i]} ${y}`), `${fmt(n)} canciones`]})), {alto:170, W:440}))),
      el("div", {className:"cols2", style:"margin-top:14px"},
        el("div", {}, el("div", {className:"sub"}, "De qué décadas eran"), hbar(a.decadas.map(d => ({nombre:d.decada, n:d.n})), {color:"var(--s1)"})),
        el("div", {}, el("div", {className:"sub"}, "A qué listas de género fueron"), hbar(a.generos, {color:"var(--s2)"}),
          el("div", {className:"sub", style:"margin-top:14px"}, "Descubrimientos"),
          el("div", {className:"small"}, a.nuevos_artistas.length ? "Artistas: " + a.nuevos_artistas.join(", ") + (a.n_nuevos_artistas > a.nuevos_artistas.length ? "…" : "") : ""),
          el("div", {className:"small", style:"margin-top:4px"}, a.nuevos_paises.length ? "Países: " + a.nuevos_paises.map(nombrePais).join(", ") : "Ningún país nuevo"))),
      el("div", {className:"curios", style:"margin-top:14px"},
        cancion("La primera que añadiste", a.primera, a.primera.d), cancion("La última", a.ultima, a.ultima.d),
        a.antigua ? cancion("La más antigua que añadiste", a.antigua, String(a.antigua.anio)) : "",
        a.reciente ? cancion("La más nueva que añadiste", a.reciente, `${a.reciente.anio} · ${fmt(a.del_anio)} salieron ese año o el anterior`) : ""),
      evolucionTabla(s.evolucion || []));
  };
  pintar();
  return caja;
}

// fotos mensuales de Mix (o de la lista principal): cómo cambia la colección (aparece a partir del segundo mes)
function evolucionTabla(fotos) {
  if (fotos.length < 2) return el("div", {className:"muted small", style:"margin-top:14px"},
    "Evolución mes a mes: cada mes se guarda una foto de tus cifras; a partir del mes que viene verás aquí cómo cambian.");
  const dif = (a, b) => { const d = a - b; return d ? ` (${d > 0 ? "+" : ""}${fmt(Math.round(d * 10) / 10)})` : ""; };
  return el("div", {style:"margin-top:14px"}, el("div", {className:"sub"}, "Evolución mes a mes"),
    el("table", {}, el("thead", {}, el("tr", {}, ...["Mes", "Canciones", "Artistas", "Horas", "Países", "Año mediano"].map(h => el("th", {}, h)))),
      el("tbody", {}, ...fotos.map((f, i) => { const p = fotos[i - 1] || f; return el("tr", {},
        el("td", {}, f.fecha.slice(0, 7)), el("td", {}, fmt(f.canciones) + dif(f.canciones, p.canciones)),
        el("td", {}, fmt(f.artistas) + dif(f.artistas, p.artistas)), el("td", {}, fmt(f.horas) + dif(f.horas, p.horas)),
        el("td", {}, fmt(f.paises) + dif(f.paises, p.paises)), el("td", {}, String(f.anio_mediana))); }))));
}

// tras corregir países: se recalcula todo (mapa, rankings…) al poco de la última corrección, sin perder la posición
let REFRESCO_STATS = null;
function refrescarStatsLuego() {
  clearTimeout(REFRESCO_STATS);
  REFRESCO_STATS = setTimeout(async () => {
    if (!$("#stats").classList.contains("on")) return;  // al volver a la pestaña ya se recalcula
    const y = scrollY;
    await cargarStats(true);
    scrollTo(0, y);
  }, 1500);
}

function sinPais(lista) {
  const caja = el("div", {style:"max-height:330px;overflow:auto"});
  caja.append(...lista.slice(0, 150).map(a => {
    const inp = el("input", {size:3, maxLength:2, placeholder:"ES", style:"width:46px;padding:3px 6px"});
    const guardar = async () => {
      try { await api("/api/artista", {nombre:a.nombre, pais:inp.value}); toast(`${a.nombre}: ${inp.value.toUpperCase()}`); fila.style.opacity = .4; refrescarStatsLuego(); }
      catch (e) { toast(e.message); } };
    inp.onkeydown = e => { if (e.key === "Enter") guardar(); };
    const fila = el("div", {className:"row", style:"gap:6px;margin:3px 0;font-size:13px"}, inp, el("button", {className:"mini", onclick:guardar}, "ok"),
      el("span", {}, a.nombre), el("span", {className:"muted small"}, `${a.n} canc.${a.buscado ? "" : " · sin buscar aún"}`));
    return fila;
  }));
  return caja;
}

async function vigilarArtistas() {
  let a;
  try { a = await api("/api/artistas"); } catch (e) { return; }
  $("#stArt").replaceChildren(a.activo
    ? el("span", {}, el("span", {className:"tag info"}, `Buscando países en MusicBrainz ${a.hechos}/${a.total}`),
        el("span", {className:"muted"}, ` ~${Math.ceil((a.total - a.hechos) * 1.1 / 60)} min · ${a.actual} `),
        el("button", {className:"mini", onclick: () => api("/api/artistas", {cancelar:true})}, "parar"))
    : a.pendientes ? el("span", {}, el("span", {className:"muted"}, `${fmt(a.pendientes)} artistas sin buscar país `),
        el("button", {className:"mini pri", onclick: async () => { try { await api("/api/artistas", {}); vigilarArtistas(); } catch (e) { toast(e.message); } }},
          `Buscar en MusicBrainz (~${Math.ceil(a.pendientes * 1.1 / 60)} min)`))
    : el("span", {className:"muted"}, "Países de todos los artistas buscados en MusicBrainz"),
    a.error ? el("span", {className:"error"}, " Error: " + a.error) : "");
  if (a.activo) { ART_ACTIVO = true; setTimeout(vigilarArtistas, 3000); }
  else if (ART_ACTIVO) { ART_ACTIVO = false; if ($("#stats").classList.contains("on")) cargarStats(); }
}
let ART_ACTIVO = false;

// Discos: canciones que tienes de cada disco; total de canciones y duración del disco entero, de MusicBrainz
function tarjetasDiscos(d) {
  const r = d.resumen, sinDatos = !r.con_total;
  const heroe = (v, k) => el("div", {className:"hero"}, el("div", {className:"v"}, v), el("div", {className:"k"}, k));
  const disco = x => enlaceSpotify("search", `${x.artista === "Varios artistas" ? "" : x.artista + " "}${x.disco}`, x.disco);
  const li = (x, extra) => el("li", {}, disco(x), el("span", {className:"muted"}, ` · ${x.artista} · ${x.anio || "?"} · ${extra(x)}`));
  const lista = (xs, extra, vacio = "Sin datos todavía") => xs.length ? el("ul", {className:"lista-mini"}, ...xs.map(x => li(x, extra)))
    : el("div", {className:"muted small"}, vacio);
  const aviso = "Pulsa «Buscar discos en MusicBrainz» arriba para saber cuántas canciones tiene cada disco y cuánto dura.";
  const minutos = ms => `${Math.round(ms / 60000)} min`;
  const tips = x => [el("b", {}, `${x.artista} - ${x.disco}`), el("div", {className:"muted"}, x.titulos.join(" · ") + (x.n > x.titulos.length ? " …" : ""))];
  const out = [];
  out.push(ancho(tarjeta("Tus discos", `Canciones de la lista agrupadas por disco y artista (los singles y EP, aparte). El total de canciones y la duración de cada disco salen de MusicBrainz: ${fmt(r.con_total)} de ${fmt(r.discos)} discos con dato.`,
    el("div", {className:"heroes", style:"grid-template-columns:repeat(4,minmax(0,1fr))"},
      heroe(fmt(r.discos), "discos distintos"), heroe(r.media != null ? fmt(r.media) : "–", "canciones por disco de media"),
      heroe(fmt(r.completos), "discos completos"), heroe(r.edad_media != null ? `${r.edad_media} años` : "–", "edad media de tus discos")),
    sinDatos ? el("div", {className:"muted small"}, aviso) : "")));
  out.push(tarjeta("Discos de los que más canciones tienes", "Sin contar singles ni EP",
    hbar(d.mas_canciones.map(x => ({nombre:x.disco, n:x.n, total:x.total, extra:x.artista, tip:tips(x)})),
      {valor: x => x.total ? `${x.n}/${x.total}` : fmt(x.n)})));
  out.push(tarjeta("Cuánto te falta para completar cada disco", "Discos que tienes a medias, los más cerca de estar completos primero: 6/8 = tienes 6 de sus 8 canciones (discos de 5 canciones o más con dato de MusicBrainz, de los que tienes al menos 2)",
    d.mas_completos.length ? hbar(d.mas_completos.map(x => ({nombre:x.disco, n:x.pct, extra:x.artista, tienes:x.n, total:x.total,
      tip:[...tips(x), el("div", {}, x.total - x.n === 1 ? "Te falta 1 canción" : `Te faltan ${x.total - x.n} canciones`)]})),
      {color:"var(--s1)", max:100, valor: x => `${x.n} % · ${x.tienes}/${x.total}`})
      : el("div", {className:"muted small"}, sinDatos ? aviso : "Ninguno a medias"),
    el("div", {className:"sub", style:"margin-top:14px"}, `Discos completos (${fmt(r.completos)})`),
    lista(d.completos, x => `${x.total} canciones`, sinDatos ? "Sin datos todavía" : "Ninguno todavía")));
  out.push(tarjeta("Los discos más largos y más cortos", "Duración del disco entero (álbumes según MusicBrainz: sin singles, EP ni recopilatorios de varios artistas)",
    el("div", {className:"cols2"},
      el("div", {}, el("div", {className:"sub"}, "Los más largos"), lista(d.largos, x => minutos(x.ms))),
      el("div", {}, el("div", {className:"sub"}, "Los más cortos"), lista(d.cortos, x => minutos(x.ms))))));
  out.push(tarjeta("Discos con más y menos canciones", "Canciones del disco entero (álbumes según MusicBrainz)",
    el("div", {className:"cols2"},
      el("div", {}, el("div", {className:"sub"}, "Con más canciones"), lista(d.mas_pistas, x => `${x.total} canciones`)),
      el("div", {}, el("div", {className:"sub"}, "Con menos canciones"), lista(d.menos_pistas, x => `${x.total} canciones`)))));
  out.push(tarjeta("Tus discos por década", "Discos distintos según el año en que salió el disco",
    barrasV(d.por_decada.map(x => ({x:x.decada.slice(2), n:x.n, tip:[el("b", {}, x.decada), `${fmt(x.n)} discos`]})), {alto:190, W:440})));
  out.push(tarjeta("Artistas con más discos", "De cuántos discos distintos tienes canciones",
    d.artistas.length ? hbar(d.artistas.map(a => ({nombre:a.nombre, n:a.n, tip:[el("b", {}, a.nombre), el("div", {className:"muted"}, a.discos.join(" · "))]})), {color:"var(--s2)"})
      : el("div", {className:"muted small"}, "Ningún artista con más de un disco")));
  const cur = d.curiosidades.slice(0, Math.floor(d.curiosidades.length / 4) * 4);
  if (cur.length) out.push(ancho(tarjeta("Curiosidades de tus discos", "",
    el("div", {className:"curios"}, ...cur.map(c => el("div", {className:"curio"}, el("div", {className:"k"}, c.t),
      el("div", {className:"v"}, c.buscar ? enlaceSpotify("search", c.buscar, c.v) : c.v), c.d ? el("div", {className:"d"}, c.d) : ""))))));
  return out;
}

async function vigilarDiscos() {
  clearTimeout(DISC_TIMER);  // una sola consulta en marcha aunque se llame otra vez al recalcular la página
  const lista = $("#stLista").value || "";
  let a;
  try { a = await api("/api/discos?lista=" + encodeURIComponent(lista)); } catch (e) { return; }
  const min = n => Math.max(1, Math.ceil(n * 2.2 / 60));  // 2 peticiones por disco, 1 por segundo
  $("#stDisc").replaceChildren(a.activo
    ? el("span", {}, el("span", {className:"tag info"}, `Buscando discos en MusicBrainz ${a.hechos}/${a.total}`),
        el("span", {className:"muted"}, ` ~${min(a.total - a.hechos)} min · ${a.actual} `),
        el("button", {className:"mini", onclick: () => api("/api/discos", {cancelar:true})}, "parar"))
    : a.pendientes ? el("span", {}, el("span", {className:"muted"}, `${fmt(a.pendientes)} discos sin buscar `),
        el("button", {className:"mini pri", onclick: async () => { try { await api("/api/discos", {lista}); vigilarDiscos(); } catch (e) { toast(e.message); } }},
          `Buscar discos en MusicBrainz (~${min(a.pendientes)} min)`))
    : el("span", {className:"muted"}, "Discos buscados en MusicBrainz"),
    a.error ? el("span", {className:"error"}, " Error: " + a.error) : "");
  if (a.activo) { DISC_ACTIVO = true; DISC_VUELTAS = (DISC_VUELTAS + 1) % 10; DISC_TIMER = setTimeout(vigilarDiscos, 3000);
    // cada ~30 s se recalcula la página con lo que ya se ha encontrado (sin perder la posición)
    if (!DISC_VUELTAS) refrescarStatsLuego(); }
  else if (DISC_ACTIVO) { DISC_ACTIVO = false; refrescarStatsLuego(); }
}
let DISC_ACTIVO = false, DISC_VUELTAS = 0, DISC_TIMER = null;
