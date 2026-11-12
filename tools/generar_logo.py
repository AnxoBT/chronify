"""Genera el logo de Chronify: web/logo.svg, web/logo.png y web/logo.ico (para el acceso directo).

El logo se describe con primitivas sencillas (círculos, arcos, líneas) en un lienzo de 64x64 y se dibuja
igual en SVG (web) y con Pillow (png/ico). Pillow solo hace falta para regenerarlo; la app no lo usa.

    python -m tools.generar_logo            # genera el logo elegido
    python -m tools.generar_logo --opciones # además docs/logo-opciones.png con todas las variantes
"""
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
VERDE, VERDE_OSC, BLANCO, NEGRO = "#1ed760", "#169c46", "#ffffff", "#121212"



def ola(cx, y, medio, flecha, w, c):
    """Arco tipo onda: cuerda de ancho 2*medio a la altura y, curvado hacia arriba 'flecha' unidades."""
    r = (medio ** 2 + flecha ** 2) / (2 * flecha)
    th = math.degrees(math.asin(medio / r))
    return ("arc", cx, y - flecha + r, r, w, 270 - th, 270 + th, c)


# ángulos en grados, 0 = derecha, sentido horario (eje y hacia abajo, como en pantalla)
VARIANTES = {
    # Reloj verde con tres ondas saliendo a la derecha (como un altavoz)
    "reloj": [
        ("circle", 32, 32, 30, NEGRO),
        ("ring", 27, 32, 17, 5, VERDE),
        ("line", 27, 32, 27, 22, 4, VERDE),
        ("line", 27, 32, 34, 36, 4, VERDE),
        ("arc", 27, 32, 23, 4, -40, 40, VERDE),
        ("arc", 27, 32, 29, 4, -35, 35, VERDE),
    ],
    # Igual pero en los colores de Spotify: disco verde, reloj y ondas en negro
    "reloj-verde": [
        ("circle", 32, 32, 30, VERDE),
        ("ring", 27, 32, 15, 5, NEGRO),
        ("line", 27, 32, 27, 23, 4, NEGRO),
        ("line", 27, 32, 33, 35, 4, NEGRO),
        ("arc", 27, 32, 22, 4, -38, 38, NEGRO),
        ("arc", 27, 32, 28, 4, -30, 30, NEGRO),
    ],
    # Disco verde con tres ondas en curva (cada vez más cortas) y un reloj pequeño abajo a la derecha
    "insignia": [
        ("circle", 30, 30, 28, VERDE),
        ("arc", 28, 76, 60, 6, 252, 288, NEGRO),
        ("arc", 28, 81, 56, 5, 254.5, 285.5, NEGRO),
        ("arc", 28, 86, 52, 4, 257, 283, NEGRO),
        ("circle", 49, 49, 14, NEGRO),
        ("ring", 49, 49, 9, 3, VERDE),
        ("line", 49, 49, 49, 43, 3, VERDE),
        ("line", 49, 49, 53, 51, 3, VERDE),
    ],
    # Modelo del usuario: reloj de bolsillo blanco sobre verde, ondas dentro y una flecha que cierra la esfera
    "bolsillo": [
        ("rrect", 0, 0, 64, 64, 14, VERDE),
        ("ering", 32, 9, 6.5, 4, 2.6, BLANCO),
        ("line", 32, 13, 32, 15.5, 3, BLANCO),
        ("arc", 32, 36, 19.5, 3, 108, 432, BLANCO),
        ("arrow", 32, 36, 19.5, 432, 6.5, 4.2, BLANCO),
        ola(32, 30, 11, 4, 3.4, BLANCO),
        ola(32, 37, 8.5, 3.2, 3.2, BLANCO),
        ola(32, 43.5, 6, 2.4, 3, BLANCO),
    ],
    # Versión para tamaños pequeños (barra de tareas, 16-32 px): menos margen, trazos gruesos, dos ondas
    "bolsillo-mini": [
        ("rrect", 0, 0, 64, 64, 14, VERDE),
        ("ering", 32, 7.5, 6, 3.6, 4, BLANCO),
        ("arc", 32, 36, 22, 5.5, 112, 428, BLANCO),
        ("arrow", 32, 36, 22, 428, 8.5, 6.5, BLANCO),
        ola(32, 32, 13, 5, 6, BLANCO),
        ola(32, 43, 8, 3.2, 6, BLANCO),
    ],
    # Sin fondo (PNG transparente): reloj de bolsillo verde con esfera negra y ondas verdes
    "reloj-oscuro": [
        ("ering", 32, 7.2, 6, 3.6, 2.8, VERDE),
        ("line", 32, 11, 32, 14.5, 3.2, VERDE),
        ("circle", 32, 37, 18.5, NEGRO),
        ("arc", 32, 37, 21, 4, 112, 428, VERDE),
        ("arrow", 32, 37, 21, 428, 7, 5, VERDE),
        ola(32, 31.5, 10.5, 4, 3.6, VERDE),
        ola(32, 38.5, 8, 3.1, 3.4, VERDE),
        ola(32, 45, 5.5, 2.2, 3.2, VERDE),
    ],
    "reloj-oscuro-mini": [
        ("ering", 32, 6.5, 6, 3.4, 4, VERDE),
        ("circle", 32, 37, 19, NEGRO),
        ("arc", 32, 37, 23, 6, 114, 426, VERDE),
        ("arrow", 32, 37, 23, 426, 9, 7, VERDE),
        ola(32, 33, 12, 4.6, 6, VERDE),
        ola(32, 44, 7, 2.8, 6, VERDE),
    ],
    # Sin fondo: disco verde tipo Spotify con ondas negras dentro de un aro de reloj verde
    "reloj-spotify": [
        ("ering", 32, 7.2, 6, 3.6, 2.8, VERDE),
        ("line", 32, 11, 32, 14.5, 3.2, VERDE),
        ("circle", 32, 37, 17, VERDE),
        ("arc", 32, 37, 21.5, 3.4, 112, 428, VERDE),
        ("arrow", 32, 37, 21.5, 428, 6.5, 4.6, VERDE),
        ola(32, 31.5, 10, 4, 3.6, NEGRO),
        ola(32, 38.3, 7.6, 3, 3.4, NEGRO),
        ola(32, 44.5, 5.2, 2.1, 3.2, NEGRO),
    ],
    "reloj-spotify-mini": [
        ("ering", 32, 6.5, 6, 3.4, 4, VERDE),
        ("circle", 32, 37, 17.5, VERDE),
        ("arc", 32, 37, 23, 5, 114, 426, VERDE),
        ("arrow", 32, 37, 23, 426, 8.5, 6.5, VERDE),
        ola(32, 33, 11, 4.4, 5.6, NEGRO),
        ola(32, 43.5, 6.5, 2.6, 5.6, NEGRO),
    ],
}
ELEGIDO = "reloj-spotify"
# variante que se usa en el .ico para tamaños <= 32 px
PEQUENO = {"bolsillo": "bolsillo-mini", "reloj-oscuro": "reloj-oscuro-mini", "reloj-spotify": "reloj-spotify-mini"}


def _pt(cx, cy, r, ang):
    a = math.radians(ang)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def _flecha(cx, cy, r, ang, largo, ancho):
    """Punta de flecha al final de un arco recorrido en sentido horario (apunta hacia donde avanza)."""
    a = math.radians(ang)
    px, py = cx + r * math.cos(a), cy + r * math.sin(a)
    dx, dy = -math.sin(a), math.cos(a)  # tangente (sentido horario en pantalla)
    nx, ny = math.cos(a), math.sin(a)   # normal hacia fuera
    return [(px + dx * largo, py + dy * largo), (px + nx * ancho, py + ny * ancho), (px - nx * ancho, py - ny * ancho)]


def svg(prims):
    out = []
    for p in prims:
        k = p[0]
        if k == "circle":
            _, cx, cy, r, c = p
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>')
        elif k == "ring":
            _, cx, cy, r, w, c = p
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{c}" stroke-width="{w}"/>')
        elif k == "ering":
            _, cx, cy, rx, ry, w, c = p
            out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="none" stroke="{c}" stroke-width="{w}"/>')
        elif k == "rrect":
            _, x0, y0, x1, y1, rad, c = p
            out.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="{rad}" fill="{c}"/>')
        elif k == "arrow":
            pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in _flecha(*p[1:7]))
            out.append(f'<polygon points="{pts}" fill="{p[7]}" stroke="{p[7]}" stroke-width="1" stroke-linejoin="round"/>')
        elif k == "arc":
            _, cx, cy, r, w, a0, a1, c = p
            x0, y0 = _pt(cx, cy, r, a0)
            x1, y1 = _pt(cx, cy, r, a1)
            grande = 1 if (a1 - a0) % 360 > 180 else 0
            out.append(f'<path d="M{x0:.2f} {y0:.2f}A{r} {r} 0 {grande} 1 {x1:.2f} {y1:.2f}" fill="none" '
                       f'stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>')
        elif k == "line":
            _, x0, y0, x1, y1, w, c = p
            out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{c}" stroke-width="{w}" '
                       'stroke-linecap="round"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' + "".join(out) + "</svg>\n"


def png(prims, tam):
    from PIL import Image, ImageDraw
    k = 8  # sobremuestreo para bordes suaves
    s = tam * k / 64
    img = Image.new("RGBA", (tam * k, tam * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def bolita(x, y, w, c):  # extremos redondeados
        d.ellipse([x * s - w * s / 2, y * s - w * s / 2, x * s + w * s / 2, y * s + w * s / 2], fill=c)

    for p in prims:
        kind = p[0]
        if kind == "circle":
            _, cx, cy, r, c = p
            d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=c)
        elif kind == "ring":
            _, cx, cy, r, w, c = p
            rr = r + w / 2
            d.ellipse([(cx - rr) * s, (cy - rr) * s, (cx + rr) * s, (cy + rr) * s], outline=c, width=round(w * s))
        elif kind == "ering":
            _, cx, cy, rx, ry, w, c = p
            d.ellipse([(cx - rx - w / 2) * s, (cy - ry - w / 2) * s, (cx + rx + w / 2) * s, (cy + ry + w / 2) * s],
                      outline=c, width=round(w * s))
        elif kind == "rrect":
            _, x0, y0, x1, y1, rad, c = p
            d.rounded_rectangle([x0 * s, y0 * s, x1 * s - 1, y1 * s - 1], radius=rad * s, fill=c)
        elif kind == "arrow":
            d.polygon([(x * s, y * s) for x, y in _flecha(*p[1:7])], fill=p[7])
        elif kind == "arc":
            _, cx, cy, r, w, a0, a1, c = p
            rr = r + w / 2
            d.arc([(cx - rr) * s, (cy - rr) * s, (cx + rr) * s, (cy + rr) * s], a0, a1, fill=c, width=round(w * s))
            for a in (a0, a1):
                bolita(*_pt(cx, cy, r, a), w, c)
        elif kind == "line":
            _, x0, y0, x1, y1, w, c = p
            d.line([x0 * s, y0 * s, x1 * s, y1 * s], fill=c, width=round(w * s))
            bolita(x0, y0, w, c)
            bolita(x1, y1, w, c)
    return img.resize((tam, tam), Image.LANCZOS)


def opciones():
    from PIL import Image, ImageDraw
    nombres = list(VARIANTES)
    hoja = Image.new("RGBA", (len(nombres) * 220 + 20, 290), "#2b2f36")
    d = ImageDraw.Draw(hoja)
    for i, n in enumerate(nombres):
        x = 20 + i * 220
        hoja.paste(png(VARIANTES[n], 180), (x, 20), png(VARIANTES[n], 180))
        for j, t in enumerate((48, 32, 16)):
            im = png(VARIANTES[n], t)
            hoja.paste(im, (x + j * 60, 215), im)
        d.text((x, 270), n + ("  (elegido)" if n == ELEGIDO else ""), fill="#e3e8ed")
    (ROOT / "docs").mkdir(exist_ok=True)
    hoja.save(ROOT / "docs" / "logo-opciones.png")


def icono(nombre, tams=(16, 20, 24, 32, 40, 48, 64, 128, 256)):
    """Imágenes de cada tamaño dibujadas a su resolución (no reescaladas); las pequeñas con la variante mini."""
    mini = VARIANTES[PEQUENO.get(nombre, nombre)]
    return [png(mini if t <= 32 else VARIANTES[nombre], t) for t in tams]


def guardar_ico(imgs, ruta):
    grande = imgs[-1]
    grande.save(ruta, format="ICO", sizes=[im.size for im in imgs], append_images=imgs[:-1])


def main():
    prims = VARIANTES[ELEGIDO]
    (WEB / "logo.svg").write_text(svg(prims), encoding="utf-8")
    png(prims, 256).save(WEB / "logo.png")
    imgs = icono(ELEGIDO)
    imgs[3].save(WEB / "logo-32.png")  # favicon pequeño nítido (pestaña / barra de tareas)
    guardar_ico(imgs, WEB / "logo.ico")
    # Windows cachea el icono de un acceso directo por ruta: el del escritorio usa un nombre que cambia con el logo
    for viejo in WEB.glob("icono-*.ico"):
        viejo.unlink()
    huella = hashlib.sha1((svg(prims) + svg(VARIANTES[PEQUENO.get(ELEGIDO, ELEGIDO)])).encode()).hexdigest()[:8]
    guardar_ico(imgs, WEB / f"icono-{huella}.ico")
    if "--opciones" in sys.argv:
        opciones()
    print(f"Logo '{ELEGIDO}' generado en {WEB}")


if __name__ == "__main__":
    main()
