"""Tests sin red ni archivos reales: python -m unittest discover -s tests"""
import json
import unittest

from core import analisis
from core.config import norm
from core.exportify import Lista, Pista
from core.fechas import Fechas, normalizar
from core.musicbrainz import elegir, limpiar
from tools.sembrar_fechas import fiables

R = {"mix": "Mix", "idiomas": ["Español", "Inglés", "Friki"], "friki": "Friki",
     "decadas": {"Retro": [None, 1999], "2000s": [2000, 2009], "2010s": [2010, None]},
     "generos": ["POP", "ROCK"], "no_reordenar": ["Español", "Inglés", "Friki"], "excepciones": {}}


def P(tid, fecha):
    return Pista(id=tid, titulo=tid, artistas="A", album="", fecha_spotify=fecha)


def listas(**kw):
    return {norm(k): Lista(nombre=k, origen="", mtime=0, pistas=v) for k, v in kw.items()}


class TestFechas(unittest.TestCase):
    def test_normalizar_solo_anio_va_primero(self):
        self.assertLess(normalizar("1967"), normalizar("1967-01-01"))
        self.assertLess(normalizar("1967-01"), normalizar("1967-01-04"))
        self.assertEqual(normalizar(""), "9999-99-99")

    def test_fecha_verificada_gana_a_spotify(self):
        F = Fechas({"pistas": {"a": {"fecha": "1954", "fuente": "manual"}}})
        self.assertEqual(F.info("a", P("a", "2016-01-29"))[0], "1954")
        self.assertEqual(F.info("b", P("b", "2001"))[1], "spotify-sin-verificar")

    def test_orden_desempata_misma_fecha(self):
        F = Fechas({"pistas": {"x": {"fecha": "1966", "orden": 5}, "y": {"fecha": "1966", "orden": 2}}})
        self.assertEqual(sorted(["x", "y"], key=F.clave), ["y", "x"])

    def test_fiables_subsecuencia_no_decreciente(self):
        self.assertEqual(fiables(["1959", "2016", "1962", "1963", None, "1964"]), {0, 2, 3, 5})


class TestAnalisis(unittest.TestCase):
    def setUp(self):
        self.cat = {t: P(t, f) for t, f in [("a", "1970"), ("b", "2005"), ("c", "2015"), ("f", "2001"), ("n", "1980")]}
        self.F = Fechas({"pistas": {}})

    def tipos(self, L):
        return {a["tipo"]: [p["id"] for p in a["pistas"]] for a in analisis.comprobar(L, self.cat, self.F, R)}

    def test_todo_cuadra(self):
        L = listas(Mix=["a", "b", "c", "f"], Español=["a"], Inglés=["b", "c"], Friki=["f"],
                   Retro=["a"], **{"2000s": ["b"], "2010s": ["c"]}, POP=["a", "b"], ROCK=["c"])
        t = self.tipos(L)
        t.pop("fecha_sin_verificar")
        self.assertEqual(t, {})

    def test_detecta_fallos(self):
        L = listas(Mix=["a", "b", "c"], Español=["a", "n"], Inglés=["b", "c"], Friki=[],
                   Retro=["a", "b"], **{"2000s": [], "2010s": ["c"]}, POP=["a"], ROCK=[])
        t = self.tipos(L)
        self.assertEqual(t["falta_en_mix"], ["n"])
        self.assertEqual(t["sin_genero"], ["b", "c"])
        self.assertEqual(t["decada_aprox"], ["b"])  # fecha de Spotify sin verificar: solo info
        self.F.fijar("b", "2005", "manual")
        self.assertEqual(self.tipos(L)["decada_distinta"], ["b"])  # verificada: error

    def test_ordenar_respeta_fijas_y_quita_duplicados(self):
        L = listas(Mix=["c", "a", "b", "a"], Español=["b", "a"])
        o = {x["lista"]: x for x in analisis.ordenar(L, self.cat, self.F, R)}
        self.assertEqual(o["Mix"]["orden"], ["a", "b", "c"])
        self.assertTrue(o["Español"]["fija"])


class TestSpotifyPlan(unittest.TestCase):
    """Simula la semántica de PUT /playlists/{id}/items (range_start, insert_before)."""

    def aplicar(self, actual, plan):
        cur = list(actual)
        for j, b, k in plan:
            self.assertFalse(j < b <= j + k, "insert_before no puede caer dentro del bloque")
            bloque = cur[j:j + k]
            del cur[j:j + k]
            d = b - k if b > j else b
            cur[d:d] = bloque
        return cur

    def test_aleatorio(self):
        import random
        from core.spotify import plan_movimientos
        rnd = random.Random(1)
        for n in (0, 1, 2, 7, 60):
            for _ in range(50):
                obj = list(range(n)); act = obj[:]; rnd.shuffle(act)
                self.assertEqual(self.aplicar(act, plan_movimientos(act, obj)), obj)

    def test_minimo_para_nuevas_al_final(self):
        from core.spotify import plan_movimientos
        obj = list(range(100)); act = [x for x in obj if x not in (5, 50)] + [5, 50]
        self.assertEqual(len(plan_movimientos(act, obj)), 2)

    def test_bloques_ahorran_peticiones(self):
        from core.spotify import plan_movimientos
        obj = list(range(100))
        act = obj[:10] + obj[40:70] + obj[10:40] + obj[70:]  # un bloque de 30 fuera de sitio
        plan = plan_movimientos(act, obj)
        self.assertEqual(self.aplicar(act, plan), obj)
        self.assertEqual(len(plan), 1)

    def test_rechaza_duplicados(self):
        from core.spotify import plan_movimientos
        with self.assertRaises(ValueError):
            plan_movimientos([1, 1, 2], [1, 2])


class TestMusicBrainz(unittest.TestCase):
    def test_elegir_ignora_fecha_suelta(self):
        self.assertEqual(elegir(["1965", "1970-01-01", "1970-03", "1971"]), "1970-01-01")
        self.assertEqual(elegir(["1982-11-19"]), "1982-11-19")
        self.assertIsNone(elegir([None, ""]))

    def test_limpiar_titulo(self):
        self.assertEqual(limpiar("Hey Jude - Remastered 2015"), "Hey Jude")
        self.assertEqual(limpiar("Wiggle (feat. Snoop Dogg)"), "Wiggle")
        self.assertEqual(limpiar("Sweat (A La La La La Long)"), "Sweat (A La La La La Long)")



class TestActualizar(unittest.TestCase):
    def test_version(self):
        from core.actualizar import version_tupla
        self.assertEqual(version_tupla("v1.2"), (1, 2, 0))
        self.assertGreater(version_tupla("1.10.0"), version_tupla("1.9.3"))
        self.assertEqual(version_tupla("1.1.0"), version_tupla("v1.1.0"))

    def test_fusionar_fechas(self):
        from core.actualizar import _fusionar_fechas
        local = {"a": {"fecha": "2000", "fuente": "manual"}, "b": {"fecha": "1999", "fuente": "spotify"},
                 "c": {"fecha": "1980", "fuente": "musicbrainz"}}
        nueva = {"a": {"fecha": "2001", "fuente": "musicbrainz"}, "b": {"fecha": "1970", "fuente": "manual"},
                 "c": {"fecha": "1981", "fuente": "musicbrainz"}, "d": {"fecha": "2010", "fuente": "spotify"}}
        r = _fusionar_fechas(local, nueva)
        self.assertEqual(r["a"]["fecha"], "2000")  # manual local manda
        self.assertEqual(r["b"]["fecha"], "1970")  # la release trae una más fiable
        self.assertEqual(r["c"]["fecha"], "1980")  # empate: lo local
        self.assertIn("d", r)

    def test_fusionar_reglas(self):
        from core.actualizar import _fusionar_reglas
        r = _fusionar_reglas({"mix": "Mix", "excepciones": {"sin_genero": ["x"]}},
                             {"mix": "Otro", "nueva": 1, "excepciones": {"sin_genero": ["y"], "fuera_de_mix": ["z"]}})
        self.assertEqual(r["mix"], "Mix")
        self.assertEqual(r["nueva"], 1)
        self.assertEqual(r["excepciones"], {"sin_genero": ["x", "y"], "fuera_de_mix": ["z"]})
        # el texto "_info" no se trata como lista (antes quedaba partido en letras)
        r = _fusionar_reglas({"excepciones": {"_info": "Ids…", "a": ["x"]}}, {"excepciones": {"_info": "Ids…", "a": ["y"]}})
        self.assertEqual(r["excepciones"], {"_info": "Ids…", "a": ["x", "y"]})
        r = _fusionar_reglas({"excepciones": {"_info": ["I", "d"]}}, {"excepciones": {"_info": "Ids"}})
        self.assertEqual(r["excepciones"]["_info"], "Ids")  # repara el que ya estuviera partido

    def test_sincro_fechas_gana_el_mas_reciente(self):
        from core.sincro import fusionar_fechas
        pc = {"a": {"fecha": "1980", "fuente": "manual", "m": 100}, "b": {"fecha": "1990", "fuente": "spotify"}}
        movil = {"a": {"fecha": "1981", "fuente": "manual", "m": 200}, "b": {"fecha": "1991", "fuente": "manual"},
                 "c": {"fecha": "2000", "fuente": "spotify"}}
        r = fusionar_fechas(pc, movil)
        self.assertEqual((r["a"]["fecha"], r["b"]["fecha"], r["c"]["fecha"]), ("1981", "1991", "2000"))


class TestVersiones(unittest.TestCase):
    def motivos(self, titulo, album="", spotify="2000", real=""):
        p = Pista(id="x", titulo=titulo, artistas="A", album=album, fecha_spotify=spotify)
        return [c for c, _ in analisis.motivos_version(p, real)]

    def test_directo_solo_en_la_version(self):
        self.assertEqual(self.motivos("Live And Let Die"), [])
        self.assertEqual(self.motivos("Heaven - Live"), ["directo"])
        self.assertEqual(self.motivos("Played-A-Live (The Bongo Song) - Radio Edit", "Played-A-Live (The Bongo Song)"), [])
        self.assertEqual(self.motivos("Stars", "Tonight At The Opera (Live)"), ["directo"])

    def test_versiones_buenas_no_avisan(self):
        for t in ("California Dreamin' - Single Version", "Satisfaction - Mono", "Feel So Close - Radio Edit"):
            self.assertEqual(self.motivos(t), [], t)
        self.assertEqual(self.motivos("Aqualung - Steven Wilson Stereo Remix"), ["version"])

    def test_recopilatorio_y_reedicion(self):
        self.assertEqual(self.motivos("Jump", "Best of Volume 1"), ["recopilatorio"])
        self.assertEqual(self.motivos("Twist And Shout - Remastered 2009"), ["reedicion"])
        self.assertEqual(self.motivos("Sh-Boom", spotify="2016-01-29", real="1954"), ["reedicion"])


class TestSugerencias(unittest.TestCase):
    def test_genero_por_artista_y_por_spotify(self):
        cat = {"a": Pista(id="a", titulo="a", artistas="Queen", album="", fecha_spotify="1975"),
               "b": Pista(id="b", titulo="b", artistas="Queen;David Bowie", album="", fecha_spotify="1981"),
               "c": Pista(id="c", titulo="c", artistas="Otro", album="", fecha_spotify="1990", generos=["hard rock"])}
        L = listas(ROCK=["b"], POP=[])
        r = {**R, "generos_spotify": {"ROCK": ["rock"], "POP": ["pop"]}}
        self.assertEqual([g for g, _ in analisis.sugerir_generos("a", L, cat, r)], ["ROCK"])
        self.assertEqual([g for g, _ in analisis.sugerir_generos("c", L, cat, r)], ["ROCK"])


class TestCupo(unittest.TestCase):
    def test_para_al_llegar_al_limite(self):
        from unittest import mock
        from core import spotify
        llamadas = []
        with mock.patch.object(spotify, "items", return_value=[{"id": t} for t in "cba"]), \
             mock.patch.object(spotify, "mover", side_effect=lambda *a, **k: llamadas.append(a) if len(llamadas) < 1
                               else (_ for _ in ()).throw(spotify.SpotifyCupo("x"))):
            hechos, total = spotify.aplicar_orden("pl", ["a", "b", "c"])
        self.assertEqual((hechos, total), (1, 2))

    def test_cupo_cuenta_24h(self):
        import time
        from unittest import mock
        from core import spotify
        ahora = time.time()
        with mock.patch.object(spotify, "cache_json", return_value={"escrituras": [ahora - 90000, ahora - 100, ahora - 50]}), \
             mock.patch.object(spotify, "env", return_value="3"):
            c = spotify.cupo()
        self.assertEqual((c["usadas"], c["libres"]), (2, 1))
        self.assertAlmostEqual(c["libera"], ahora - 100 + 86400, delta=1)


class TestEstadisticas(unittest.TestCase):
    def test_calcula_sin_red(self):
        from unittest import mock
        from core import estadisticas
        cat = {t: Pista(id=t, titulo=t, artistas=a, album="", fecha_spotify=f, duracion=200000, popularidad=50,
                        energia=.5, valencia=.7, bpm=120, tono=0, modo=1)
               for t, a, f in [("a", "Queen", "1975"), ("b", "Queen", "1981"), ("c", "Estopa", "1999-10-04")]}
        L = listas(Mix=["a", "b", "c"], Español=["c"], Inglés=["a", "b"], Friki=[])
        L[norm("Español")].anadidas = {"c": "2022-05-30T10:00:00Z"}
        with mock.patch.object(estadisticas, "cache_json", return_value={"queen": {"pais": "GB", "tipo": "Group"}}), \
             mock.patch.object(estadisticas.A, "manuales", return_value={"Estopa": {"pais": "ES"}}):
            s = estadisticas.calcular(L, cat, Fechas({"pistas": {}}), R)
        self.assertEqual(s["resumen"]["canciones"], 3)
        self.assertEqual({k: v["n"] for k, v in s["paises"].items()}, {"GB": 2, "ES": 1})
        self.assertEqual(s["top_artistas"][0]["nombre"], "Queen")
        self.assertEqual(s["anadidas"]["meses"][0]["n"], 1)


class TestOrdenarVarias(unittest.TestCase):
    """Ordenar varias listas en Spotify (simulado): lo no hecho queda apuntado para 'Seguir'."""

    def preparar(self, mover):
        import random
        from unittest import mock
        from core import config, spotify
        from web import server as S
        cat = {f"t{i}": Pista(id=f"t{i}", titulo=f"t{i}", artistas="A", album="", fecha_spotify=str(1960 + i)) for i in range(20)}
        random.seed(3)
        self.remoto = {}
        listas_ = {}
        for n in ("POP", "Mix"):
            ids = list(cat); random.shuffle(ids); self.remoto[n] = ids
            listas_[n] = Lista(nombre=n, origen="Spotify API", mtime=0, pistas=list(ids), spotify_id=n)
        S.ESTADO.update(listas=listas_, cat=cat, fuente="Spotify (API)", cargado="x")
        self.guardado = {}
        F = Fechas({"pistas": {t: {"fecha": cat[t].fecha_spotify} for t in cat}})
        parches = [
            mock.patch.object(spotify, "items", lambda pid: [{"id": t} for t in self.remoto[pid]]),
            mock.patch.object(spotify, "mover", mover),
            mock.patch.object(spotify, "cupo", lambda: {"libres": 500, "usadas": 0, "limite": 500, "libera": None}),
            mock.patch.object(config, "cache_json", lambda n, d=None: {"conserva_added_at": True} if n == "prueba_spotify.json"
                              else self.guardado.get(n, {})),
            mock.patch.object(config, "save_cache", lambda n, d: self.guardado.__setitem__(n, d)),
            mock.patch.object(config, "borrar_cache", lambda n: self.guardado.pop(n, None)),
            mock.patch("core.analisis.Fechas", lambda: F),
            mock.patch.object(S.historial, "registrar", lambda *a, **k: None),
        ]
        for p in parches:
            p.start()
            self.addCleanup(p.stop)
        return S

    def test_error_cualquiera_deja_pendiente(self):
        n = [0]

        def mover(pid, j, b, snap=None, largo=1):
            n[0] += 1
            if n[0] > 3:
                raise RuntimeError("Spotify PUT: 502")
            l = self.remoto[pid]; blo = l[j:j + largo]; del l[j:j + largo]; d = b - largo if b > j else b; l[d:d] = blo
        S = self.preparar(mover)
        with self.assertRaises(RuntimeError):
            S._ordenar(["POP", "Mix"])(lambda m: None)
        self.assertEqual(self.guardado[S.PENDIENTE]["listas"], ["POP", "Mix"])


class TestCopias(unittest.TestCase):
    def test_duplicada_por_copia(self):
        cat = {"a": Pista(id="a", titulo="Enjoy the Silence", artistas="Depeche Mode", album="Violator", fecha_spotify="1990"),
               "b": Pista(id="b", titulo="Enjoy the Silence - 2006 Remaster", artistas="Depeche Mode", album="Singles", fecha_spotify="1998"),
               "c": Pista(id="c", titulo="ウィーアー!", artistas="Kitadani", album="", fecha_spotify="1999"),
               "d": Pista(id="d", titulo="ウィーゴー！", artistas="Kitadani", album="", fecha_spotify="2011")}
        self.assertEqual(analisis.duplicadas_por_copia(cat, cat), [["a", "b"]])  # el japonés no se junta

    def test_buscar_principal(self):
        from unittest import mock
        from core import spotify
        mia = Pista(id="x", titulo="Skinny Love", artistas="Bon Iver", album="For Emma", fecha_spotify="2008",
                    isrc="US1", duracion=238000, popularidad=0)
        res = {"tracks": {"items": [
            {"id": "x", "name": "Skinny Love", "artists": [{"name": "Bon Iver"}], "duration_ms": 238000, "popularity": 0, "album": {}},
            {"id": "y", "name": "Skinny Love", "artists": [{"name": "Bon Iver"}], "duration_ms": 238500, "popularity": 80,
             "album": {"name": "For Emma, Forever Ago", "album_type": "album", "release_date": "2008-02-19"}},
            {"id": "z", "name": "Skinny Love", "artists": [{"name": "Birdy"}], "duration_ms": 201000, "popularity": 90, "album": {}}]}}
        with mock.patch.object(spotify, "call", return_value=res):
            self.assertEqual(spotify.buscar_principal(mia)["id"], "y")  # Birdy es otra artista (cover): fuera

    def test_cambiar_en_todas_las_listas_y_heredar_fecha(self):
        from unittest import mock
        from core import config, spotify
        from web import server as S
        cat = {t: Pista(id=t, titulo=t, artistas="A", album="", fecha_spotify="2000") for t in ("x", "o1", "o2")}
        L = {"Mix": Lista(nombre="Mix", origen="", mtime=0, pistas=["o1", "x", "o2"], spotify_id="m"),
             "Inglés": Lista(nombre="Inglés", origen="", mtime=0, pistas=["x"], spotify_id="i"),
             "Liked_Songs": Lista(nombre="Liked_Songs", origen="", mtime=0, pistas=["x"], solo_lectura=True)}
        S.ESTADO.update(listas=L, cat=cat, fuente="Spotify (API)", cargado="x")
        guardado = {S.COPIAS: {"x": {"propuesta": {"id": "y", "album": "Buena", "fecha": "2000", "popularidad": 80,
                                                   "album_tipo": "album"}, "hecho": False}}}
        F = Fechas({"pistas": {"x": {"fecha": "1999-05-01", "fuente": "manual"}}})
        llamadas = []
        with mock.patch.object(spotify, "anadir", lambda pid, t, pos=None: llamadas.append(("+", pid, t, pos))), \
             mock.patch.object(spotify, "quitar", lambda pid, t: llamadas.append(("-", pid, t))), \
             mock.patch.object(spotify, "cupo", lambda: {"libres": 500, "usadas": 0, "limite": 500, "libera": None}), \
             mock.patch.object(config, "cache_json", lambda n, d=None: guardado.get(n, {})), \
             mock.patch.object(config, "save_cache", lambda n, d: guardado.__setitem__(n, d)), \
             mock.patch.object(config, "guardar_fechas"), mock.patch.object(config, "rules", lambda: {"excepciones": {}}), \
             mock.patch.object(S, "Fechas", lambda: F), mock.patch.object(S.historial, "registrar", lambda *a, **k: None):
            S._cambiar_copias(["x"])(lambda m: None)
        self.assertEqual(L["Mix"].pistas, ["o1", "y", "o2"])  # en el mismo sitio
        self.assertEqual(L["Inglés"].pistas, ["y"])
        self.assertEqual(L["Liked_Songs"].pistas, ["x"])  # solo lectura: no se toca
        self.assertIn(("+", "m", "y", 1), llamadas)
        self.assertEqual(F.pistas["y"]["fecha"], "1999-05-01")  # hereda la fecha verificada
        self.assertTrue(guardado[S.COPIAS]["x"]["hecho"])

    def test_para_si_no_cabe_en_el_cupo(self):
        from unittest import mock
        from core import config, spotify
        from web import server as S
        L = {"Mix": Lista(nombre="Mix", origen="", mtime=0, pistas=["x"], spotify_id="m"),
             "Inglés": Lista(nombre="Inglés", origen="", mtime=0, pistas=["x"], spotify_id="i")}
        S.ESTADO.update(listas=L, cat={}, fuente="Spotify (API)", cargado="x")
        guardado = {S.COPIAS: {"x": {"propuesta": {"id": "y", "album": "B", "fecha": "", "popularidad": 1, "album_tipo": ""}, "hecho": False}}}
        with mock.patch.object(spotify, "anadir", side_effect=AssertionError), mock.patch.object(spotify, "quitar", side_effect=AssertionError), \
             mock.patch.object(spotify, "cupo", lambda: {"libres": 3, "usadas": 497, "limite": 500, "libera": 0}), \
             mock.patch.object(config, "cache_json", lambda n, d=None: guardado.get(n, {})), \
             mock.patch.object(S, "Fechas", lambda: Fechas({"pistas": {}})), mock.patch.object(config, "rules", lambda: {}):
            r = S._cambiar_copias(["x"])(lambda m: None)  # necesita 4 cambios y quedan 3: ni empieza
        self.assertEqual(r["cambiadas"], 0)
        self.assertEqual(L["Mix"].pistas, ["x"])


class TestLecturaIncremental(unittest.TestCase):
    def test_solo_relee_lo_cambiado(self):
        from unittest import mock
        from core import spotify
        guardado = {spotify.LECTURA_CACHE: {
            "A": {"firma": "s1", "items": [{"id": "a"}]},
            "B": {"firma": "viejo", "items": [{"id": "b"}]},
            "_liked": {"firma": "3:z", "items": [{"id": "z"}, {"id": "y"}, {"id": "x"}]}}}
        leidas = []
        liked = [{"id": "n"}, {"id": "z"}, {"id": "y"}, {"id": "x"}]  # una nueva por arriba

        def call(metodo, url, params=None, body=None):
            leidas.append(url)
            lim = (params or {}).get("limit", 50)
            return {"total": len(liked), "items": [{"track": {"id": x["id"]}} for x in liked[:lim]], "next": None}
        with mock.patch.object(spotify, "call", call),              mock.patch.object(spotify, "items", lambda pid: leidas.append(pid) or [{"id": "b2"}]),              mock.patch.object(spotify, "cache_json", lambda n, d=None: guardado.get(n, {})),              mock.patch.object(spotify, "save_cache", lambda n, d: guardado.__setitem__(n, d)):
            out, n = spotify._lectura_incremental([("A", "A", "s1"), ("B", "B", "s2"), ("Liked", None, None)])
        self.assertEqual([x["id"] for x in out["A"]], ["a"])
        self.assertEqual([x["id"] for x in out["B"]], ["b2"])
        self.assertEqual([x["id"] for x in out["Liked"]], ["n", "z", "y", "x"])
        self.assertEqual(n, 2)
        self.assertNotIn("A", leidas)
        self.assertEqual(guardado[spotify.LECTURA_CACHE]["B"]["firma"], "s2")


class TestCopia(unittest.TestCase):
    def test_crear_y_restaurar(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from unittest import mock
        from core import config, copia
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            datos, clave = d / "datos", d / "home" / ".android" / "chronify-release.jks"
            (datos / "cache" / "actualizacion").mkdir(parents=True)
            (datos / ".env").write_text("SPOTIFY_CLIENT_ID=x")
            (datos / "cache" / "musicbrainz.json").write_text("{}")
            (datos / "cache" / "actualizacion" / "basura").write_text("x")
            clave.parent.mkdir(parents=True)
            clave.write_bytes(b"clave")
            with mock.patch.object(config, "DATOS", datos), mock.patch.object(config, "ROOT", d / "raiz"),                  mock.patch.object(copia, "CLAVE", clave), mock.patch.object(copia, "carpeta", lambda: d / "copias"):
                for _ in range(7):
                    r = copia.crear()
                    nombres = zipfile.ZipFile(r["ruta"]).namelist()
                (datos / ".env").write_text("cambiado")
                clave.unlink()
                copia.restaurar(r["ruta"])
                self.assertEqual((datos / ".env").read_text(), "SPOTIFY_CLIENT_ID=x")
                self.assertEqual(clave.read_bytes(), b"clave")
            self.assertIn("cache/musicbrainz.json", nombres)
            self.assertIn("android-clave/chronify-release.jks", nombres)
            self.assertNotIn("cache/actualizacion/basura", nombres)
            self.assertLessEqual(len(list((d / "copias").glob("chronify-copia-*.zip"))), copia.GUARDAR)


class TestParaCualquiera(unittest.TestCase):
    """La app sirve sin configurar nada (otra persona con sus propias listas)."""

    def test_reglas_por_defecto(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        from core import config
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "rules.json"
            with mock.patch.object(config, "RULES", ruta), mock.patch.object(config, "DATOS", Path(d)):
                r = config.rules()
                self.assertTrue(ruta.exists())
                self.assertEqual(r["mix"], "")
                self.assertIn("Liked_Songs", r["solo_lectura"])
                ruta.write_text(json.dumps({"mix": "Todo", "excepciones": {"sin_genero": ["x"]}}), encoding="utf-8")
                r = config.rules()  # lo tuyo manda y se completa con las claves que falten
                self.assertEqual(r["mix"], "Todo")
                self.assertEqual(r["excepciones"]["sin_genero"], ["x"])
                self.assertIn("misma_cancion", r["excepciones"])
                self.assertIn("generos_spotify", r)

    def test_comprobar_sin_configurar(self):
        cat = {t: Pista(id=t, titulo=t, artistas="A", album="", fecha_spotify="2001") for t in "abc"}
        listas = {"Cosas": Lista(nombre="Cosas", origen="", mtime=0, pistas=["a", "b", "a"]),
                  "Otra": Lista(nombre="Otra", origen="", mtime=0, pistas=["c"])}
        R = {"mix": "", "idiomas": [], "decadas": {}, "generos": [], "excepciones": {}}
        avisos = analisis.comprobar(listas, cat, Fechas({"pistas": {}}), R)
        tipos = {a["tipo"] for a in avisos}
        self.assertNotIn("faltan_listas", tipos)
        self.assertIn("duplicadas", tipos)
        nuevas = next(a for a in avisos if a["tipo"] == "fecha_sin_verificar")
        self.assertEqual({p["id"] for p in nuevas["pistas"]}, {"a", "b", "c"})  # sin Mix: todas tus listas

    def test_conocimiento_se_anade_sin_pisar(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        from core import config, conocimiento
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "con").mkdir()
            (d / "con" / "artistas_mb.json").write_text(json.dumps({"queen": {"pais": "GB"}, "abba": {"pais": "SE"}}))
            (d / "cache").mkdir()
            (d / "cache" / "artistas_mb.json").write_text(json.dumps({"queen": {"pais": "XX"}}))
            with mock.patch.object(conocimiento, "CARPETA", d / "con"), mock.patch.object(config, "CACHE", d / "cache"):
                self.assertEqual(conocimiento.sembrar(), 1)
                self.assertEqual(conocimiento.sembrar(), 0)  # sin cambios en conocimiento/ no vuelve a trabajar
                c = config.cache_json("artistas_mb.json")
        self.assertEqual(c, {"queen": {"pais": "XX"}, "abba": {"pais": "SE"}})

    def test_guardar_tus_listas(self):
        from unittest import mock
        from core import config
        from web import server as S
        guardado = {}
        actual = {"mix": "Mix", "idiomas": ["B", "A"], "generos": [], "decadas": {}, "no_reordenar": [], "ignorar": [],
                  "excepciones": {"sin_genero": ["x"]}}
        with mock.patch.object(config, "rules", lambda: dict(actual)), \
             mock.patch.object(config, "guardar_reglas", lambda r: guardado.update(r)), \
             mock.patch.object(S.historial, "registrar", lambda *a, **k: None):
            S.guardar_listas({"mix": "Mix", "idiomas": ["A", "B", "C"], "friki": "Z", "generos": ["POP"],
                              "decadas": {"Viejo": [None, "1999"]}, "no_reordenar": ["A"], "ignorar": []})
            self.assertEqual(guardado["idiomas"], ["B", "A", "C"])  # conserva el orden que tenían
            self.assertEqual(guardado["decadas"], {"Viejo": [None, 1999]})
            self.assertEqual(guardado["friki"], "")  # no forma parte del Mix: se descarta
            self.assertEqual(guardado["excepciones"], {"sin_genero": ["x"]})
            with self.assertRaises(ValueError):
                S.guardar_listas({"decadas": {"Mal": [2000, 1990]}})
            with self.assertRaises(ValueError):
                S.guardar_listas({"mix": "A", "idiomas": ["A"]})


class TestCuentasSpotify(unittest.TestCase):
    """Cuentas distintas: Premium, gratis y no autorizada en la app (simuladas: sin red)."""

    def _llamar(self, codigo, cuerpo):
        import io
        from unittest import mock
        from urllib.error import HTTPError
        from core import spotify
        guardado = {}

        def abrir(req, *a, **k):
            if codigo == 200:
                return mock.MagicMock(__enter__=lambda s: io.BytesIO(cuerpo.encode()), __exit__=lambda *a: None)
            raise HTTPError(req.full_url, codigo, "x", {}, io.BytesIO(cuerpo.encode()))
        with mock.patch.object(spotify, "_abrir", abrir), mock.patch.object(spotify, "_token", lambda: "t"), \
             mock.patch.object(spotify, "bloqueado_hasta", lambda: None), \
             mock.patch.object(spotify, "save_cache", lambda n, d: guardado.__setitem__(n, d)):
            try:
                return spotify.comprobar_cuenta(), guardado
            except Exception as e:  # noqa: BLE001
                return e, guardado

    def test_premium(self):
        info, _ = self._llamar(200, '{"id": "u", "product": "premium"}')
        self.assertEqual((info["premium"], info["error"]), (True, None))

    def test_gratis(self):
        from core import spotify
        info, _ = self._llamar(200, '{"id": "u", "product": "free"}')
        self.assertEqual(info["error"], spotify.SIN_PREMIUM)

    def test_dueno_sin_premium(self):
        from core import spotify
        info, g = self._llamar(403, '{"error": {"status": 403, "message": "Active premium subscription required for the owner of the app."}}')
        self.assertEqual(info["error"], spotify.SIN_PREMIUM)

    def test_no_autorizada(self):
        from core import spotify
        info, g = self._llamar(403, '{"error": {"status": 403, "message": "Check settings on developer.spotify.com/dashboard, the user may not be registered."}}')
        self.assertEqual(info["error"], spotify.NO_AUTORIZADA)
        self.assertEqual(g[spotify.CUENTA_CACHE]["error"], spotify.NO_AUTORIZADA)


class TestOtraPersona(unittest.TestCase):
    """De principio a fin con un zip de Exportify inventado (tests/ejemplo.py): otra cuenta, sin configurar nada."""

    def test_zip_de_otra_persona(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from core import exportify
        from tests.ejemplo import zip_ejemplo
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "spotify_playlists.zip").write_bytes(zip_ejemplo())
            with mock.patch.object(exportify, "export_dirs", lambda: [Path(d)]):
                listas, cat = exportify.cargar(["Saved_Albums"], "", ["Liked_Songs"])
        self.assertEqual(sorted(listas), ["Liked_Songs", "Mis favoritas", "Rock"])  # la de otra cuenta, fuera
        R = {"mix": "", "idiomas": [], "decadas": {}, "generos": [], "excepciones": {}, "solo_lectura": ["Liked_Songs"]}
        avisos = {a["tipo"]: a for a in analisis.comprobar(listas, cat, Fechas(), R)}
        self.assertIn("duplicadas", avisos)
        self.assertEqual([p["id"] for p in avisos["fecha_sin_verificar"]["pistas"]], ["0000000000000000000000"])
        orden = {o["lista"]: o for o in analisis.ordenar(listas, cat, Fechas(), R)}
        self.assertTrue(orden["Liked_Songs"]["fija"])
        self.assertFalse(orden["Mis favoritas"]["fija"])
        F = Fechas()
        fechas = [F.clave(t, cat[t]) for t in orden["Rock"]["orden"]]
        self.assertEqual(fechas, sorted(fechas))  # por fecha real


LOCAL = {"Host": "127.0.0.1:8766"}
POST = {**LOCAL, "X-Chronify": "1", "Content-Type": "application/json"}


class TestPuenteWeb(unittest.TestCase):
    """web/navegador.py atiende las peticiones como el servidor (lo que hace en el navegador, sin Pyodide)."""

    def test_despachar(self):
        from web import navegador
        codigo, cab, cuerpo = navegador.despachar("GET", "/api/ping", LOCAL, b"")
        self.assertEqual((codigo, json.loads(cuerpo)["app"]), (200, "chronify"))
        self.assertEqual(navegador.despachar("GET", "/no-existe", LOCAL, b"")[0], 404)
        codigo, _, cuerpo = navegador.despachar("POST", "/api/reglas", POST, b'{"decadas": {"X": [2000, 1990]}}')
        self.assertEqual(codigo, 400)  # validación igual que en el PC

    def test_pagina_y_estaticos(self):
        from web import navegador
        for ruta, tipo in (("/", "text/html"), ("/js/app.js", "text/javascript"), ("/estilos.css", "text/css"),
                           ("/mundo.json", "application/json")):
            codigo, cab, _ = navegador.despachar("GET", ruta, LOCAL, b"")
            self.assertEqual((codigo, cab["Content-Type"].split(";")[0]), (200, tipo), ruta)
        self.assertEqual(navegador.despachar("GET", "/js/../server.py", LOCAL, b"")[0], 404)

    def test_tareas_sin_hilos(self):
        from web import navegador
        hecho = []

        def falla():
            raise RuntimeError("x")
        navegador._HiloWeb(target=falla).start()
        navegador._HiloWeb(target=hecho.append, args=(1,)).start()
        self.assertTrue(navegador.hay_tareas())
        self.assertEqual(navegador.ejecutar_tareas(), 2)  # la que falla no para a las demás
        self.assertEqual(hecho, [1])
        self.assertFalse(navegador.hay_tareas())


class TestSeguridad(unittest.TestCase):
    """Otras webs (o apps del móvil) no pueden usar el servidor local."""

    def test_peticiones_de_fuera(self):
        from web import navegador
        d = navegador.despachar
        self.assertEqual(d("GET", "/api/estado", {"Host": "evil.example:8766"}, b"")[0], 403)  # DNS rebinding
        self.assertEqual(d("POST", "/api/reglas", {**LOCAL, "Content-Type": "text/plain"}, b"{}")[0], 403)  # sin cabecera
        self.assertEqual(d("POST", "/api/reglas", {**POST, "Origin": "https://evil.example"}, b"{}")[0], 403)

    def test_clave_android(self):
        from unittest import mock
        from web import navegador, server
        with mock.patch.object(server, "SECRETO", "s3creto"):
            d = navegador.despachar
            self.assertEqual(d("GET", "/api/historial", LOCAL, b"")[0], 403)  # otra app del móvil
            self.assertEqual(d("GET", "/api/ping", LOCAL, b"")[0], 200)
            codigo, cab, _ = d("GET", "/?k=s3creto", LOCAL, b"")
            self.assertEqual(codigo, 302)
            self.assertIn("HttpOnly", cab["Set-Cookie"])
            self.assertEqual(d("GET", "/api/historial", {**LOCAL, "Cookie": "chronify=s3creto"}, b"")[0], 200)
            self.assertEqual(d("GET", "/api/historial", {**LOCAL, "X-Chronify-Clave": "s3creto"}, b"")[0], 200)
            self.assertEqual(d("GET", "/api/historial", {**LOCAL, "Cookie": "chronify=otra"}, b"")[0], 403)

    def test_restaurar_no_sale_de_su_sitio(self):
        import io
        import tempfile
        import zipfile
        from pathlib import Path
        from unittest import mock
        from core import config, copia
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            datos = d / "datos"
            datos.mkdir()
            for malo in ("../fuera.txt", "cache/../../fuera.txt", "/abs.txt", "C:/abs.txt", "core/config.py"):
                b = io.BytesIO()
                with zipfile.ZipFile(b, "w") as z:
                    z.writestr("LEEME.txt", "x")
                    z.writestr(malo, "malo")
                with mock.patch.object(config, "DATOS", datos), mock.patch.object(copia, "carpeta", lambda: d / "c"):
                    try:
                        copia.restaurar(io.BytesIO(b.getvalue()))
                    except ValueError:
                        pass
            self.assertFalse((d / "fuera.txt").exists())
            self.assertFalse((datos / "core").exists())  # código: nunca se restaura
            with self.assertRaises(ValueError):  # un zip cualquiera no es una copia
                b = io.BytesIO()
                with zipfile.ZipFile(b, "w") as z:
                    z.writestr("otra.txt", "x")
                copia.restaurar(io.BytesIO(b.getvalue()))


class TestLikedConLocales(unittest.TestCase):
    def test_pista_local_no_obliga_a_releer(self):
        from unittest import mock
        from core import spotify
        previas = [{"id": "b"}, {"id": "a"}]
        pagina = [{"track": {"id": "c"}}, {"track": {"id": "b"}}]  # c nueva; antes había 1 local sin id
        llamadas = []

        def call(m, url, params=None, body=None):
            llamadas.append(url)
            return {"items": pagina, "next": None}
        with mock.patch.object(spotify, "call", call), mock.patch.object(spotify, "guardadas", side_effect=AssertionError):
            out = spotify._liked_nuevas(previas, total=4, sin_id=1)
        self.assertEqual([x["id"] for x in out], ["c", "b", "a"])
        self.assertEqual(len(llamadas), 1)


class TestPKCE(unittest.TestCase):
    def test_login_sobrevive_a_recargar(self):
        from unittest import mock
        from urllib.parse import parse_qs, urlparse
        from core import spotify
        guardado = {}
        with mock.patch.object(spotify, "cache_json", lambda n, d=None: guardado.get(n, {})), \
             mock.patch.object(spotify, "save_cache", lambda n, d: guardado.__setitem__(n, d)), \
             mock.patch.object(spotify, "env", lambda k, d="": "cid"), \
             mock.patch.object(spotify, "_token_request", lambda datos: datos), \
             mock.patch.object(spotify, "comprobar_cuenta", lambda: None):
            state = parse_qs(urlparse(spotify.url_login()).query)["state"][0]
            datos = spotify.callback("codigo", state)  # otra "página" (se lee de disco, no de memoria)
            self.assertTrue(datos["code_verifier"])
            with self.assertRaises(ValueError):  # un state solo vale una vez
                spotify.callback("codigo", state)


class TestSincroPendiente(unittest.TestCase):
    def test_gana_lo_mas_reciente(self):
        from core import sincro
        viejo = {"listas": ["Mix"], "m": 100}
        hecho = {"listas": [], "m": 200}  # ya se terminó en el otro dispositivo
        self.assertEqual(sincro._elegir_estado("spotify_pendiente.json", viejo, hecho), hecho)
        self.assertEqual(sincro._elegir_estado("spotify_pendiente.json", hecho, viejo), hecho)
        self.assertEqual(sincro._elegir_estado("spotify_pendiente.json", {"listas": ["Mix"]}, hecho), hecho)  # sin "m"


class TestLikedEnListaNueva(unittest.TestCase):
    def test_solo_si_se_pide(self):
        cat = {t: Pista(id=t, titulo=t, artistas="A", album="", fecha_spotify=f) for t, f in (("a", "2001"), ("b", "1990"))}
        listas = {"Liked_Songs": Lista(nombre="Liked_Songs", origen="", mtime=0, pistas=["a", "b"], solo_lectura=True)}
        F = Fechas({"pistas": {}})
        o = analisis.ordenar(listas, cat, F, {"excepciones": {}})[0]
        self.assertTrue(o["fija"])  # por defecto no se toca
        o = analisis.ordenar(listas, cat, F, {"excepciones": {}, "liked_ordenar": True})[0]
        self.assertFalse(o["fija"])
        self.assertTrue(o["en_lista_nueva"])
        self.assertEqual(o["orden"], ["b", "a"])

    def test_crear_o_rellenar(self):
        from unittest import mock
        from core import spotify
        llamadas = []

        def call(metodo, ruta, cuerpo=None, params=None):
            llamadas.append((metodo, ruta, len((cuerpo or {}).get("uris", []))))
            return {"id": "nueva"}
        ids = [f"t{i}" for i in range(250)]
        with mock.patch.object(spotify, "call", call), mock.patch.object(spotify, "mis_listas", lambda: [{"id": "vieja"}]):
            self.assertEqual(spotify.crear_o_rellenar("X", ids, None), "nueva")
            self.assertEqual(llamadas, [("POST", "/me/playlists", 0), ("POST", "/playlists/nueva/items", 100),
                                        ("POST", "/playlists/nueva/items", 100), ("POST", "/playlists/nueva/items", 50)])
            llamadas.clear()
            self.assertEqual(spotify.crear_o_rellenar("X", ids, "vieja"), "vieja")  # existe: se reemplaza su contenido
            self.assertEqual(llamadas[0], ("PUT", "/playlists/vieja/items", 100))
            llamadas.clear()
            spotify.crear_o_rellenar("X", ids[:5], "borrada")  # ya no está entre tus listas: se crea otra
            self.assertEqual(llamadas[0][:2], ("POST", "/me/playlists"))


class TestHistorial(unittest.TestCase):
    def test_uids_unicos_y_no_deshace_si_cambio_despues(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from core import historial
        from web import server as S
        with tempfile.TemporaryDirectory() as d, mock.patch.object(historial, "ARCHIVO", Path(d) / "h.jsonl"):
            uids = {historial.registrar("fecha", "x")["uid"] for _ in range(200)}
            self.assertEqual(len(uids), 200)
            a = historial.registrar("fecha", "A", id="t", antes={"fecha": "1984"}, despues={"fecha": "1985"})
            historial.registrar("fecha", "B", id="t", antes={"fecha": "1985"}, despues={"fecha": "1986"})
            datos = {"pistas": {"t": {"fecha": "1986"}}}
            with mock.patch.object(S, "Fechas", lambda: Fechas(datos)), mock.patch.object(S.config, "guardar_fechas") as g:
                with self.assertRaises(ValueError):  # A ya no es el estado actual: no se pisa B
                    S.deshacer(a["uid"])
                g.assert_not_called()


if __name__ == "__main__":
    unittest.main()
