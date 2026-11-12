"""Iconos del APK a partir de web/logo.png: fondo negro y el logo en el centro.

- Icono adaptativo (Android 8+): fondo negro + primer plano con el logo dentro de la zona segura. El móvil
  le pone su forma (cuadrado con esquinas redondeadas, como el resto de apps).
- Iconos clásicos (mipmap-*/ic_launcher.png): cuadrado negro con esquinas redondeadas ya dibujado.

Uso puntual (con Pillow, solo para desarrollo): python -m tools.generar_icono_android
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android/app/src/main/res"
DENSIDADES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
NEGRO = (0, 0, 0, 255)


def _logo(lado):
    return Image.open(ROOT / "web" / "logo.png").convert("RGBA").resize((lado, lado), Image.LANCZOS)


def main():
    for nombre, f in DENSIDADES.items():
        carpeta = RES / f"mipmap-{nombre}"
        carpeta.mkdir(parents=True, exist_ok=True)
        # primer plano del adaptativo: lienzo de 108 dp, zona segura de 66 dp en el centro
        t = round(108 * f)
        fg = Image.new("RGBA", (t, t), (0, 0, 0, 0))
        lado = round(t * 0.56)
        fg.alpha_composite(_logo(lado), ((t - lado) // 2, (t - lado) // 2))
        fg.save(carpeta / "ic_launcher_foreground.png")
        # clásico: 48 dp, cuadrado negro redondeado (se dibuja a 4x y se reduce para que el borde quede suave)
        t = round(48 * f)
        g = Image.new("RGBA", (t * 4, t * 4), (0, 0, 0, 0))
        ImageDraw.Draw(g).rounded_rectangle((0, 0, t * 4 - 1, t * 4 - 1), radius=t * 4 // 5, fill=NEGRO)
        lado = round(t * 4 * 0.70)
        g.alpha_composite(_logo(lado), ((t * 4 - lado) // 2, (t * 4 - lado) // 2))
        g.resize((t, t), Image.LANCZOS).save(carpeta / "ic_launcher.png")
    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(exist_ok=True)
    (anydpi / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@android:color/black" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        '</adaptive-icon>\n', encoding="utf-8")
    print("iconos generados en", RES)


if __name__ == "__main__":
    main()
