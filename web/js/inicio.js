// Arranque: se carga el último (usa funciones de los demás archivos)
comprobarVersion(false);
cargarAjustes();
pintarSinc();
pintarCopia();
// Android: pantalla encendida mientras haya alguna tarea larga en marcha (si se apaga, la app se pausa)
if (window.ChronifyAndroid) {
  let encendida = false;
  setInterval(async () => {
    try {
      const [s, m, a] = await Promise.all([api("/api/spotify"), api("/api/mb"), api("/api/artistas")]);
      const activa = s.activo || m.activo || a.activo;
      if (activa !== encendida) { encendida = activa; window.ChronifyAndroid.mantenerPantalla(activa); }
    } catch (e) {}
  }, 4000);
}
vigilarMB();  // si hay una búsqueda en marcha (p. ej. al reabrir la ventana), enseña su progreso

cargar().then(pintarSpotify);
// latido: si se cierra la ventana, el servidor se apaga solo al rato
const latido = () => fetch("/api/ping").catch(() => {});
latido(); setInterval(latido, 5000);
