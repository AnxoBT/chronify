"""Publica una versión: comprueba, compila el APK, crea el tag y la release de GitHub con el zip (PC) y el APK (móvil).

Antes: subir VERSION en core/version.py, poner la entrada en CHANGELOG.md y hacer commit.
Uso: python -m tools.publicar            (--sin-subir: lo prepara todo en salida/ pero no publica)

El APK se firma con la clave propia (~/.android/chronify-release.jks, datos en android/keystore.properties):
sin ella el móvil no podría instalar la actualización encima de la versión que tiene.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.version import VERSION  # noqa: E402


def run(*cmd, cwd=ROOT, salida=False):
    print("$", " ".join(map(str, cmd)))
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=salida, text=True, shell=str(cmd[0]).endswith(".bat"))
    if r.returncode:
        sys.exit(f"Falló: {' '.join(map(str, cmd))}\n{(r.stderr or r.stdout or '')[-2000:] if salida else ''}")
    return r.stdout if salida else ""


def notas():
    s = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    i = s.index(f"## v{VERSION}")
    j = s.find("\n## v", i + 1)
    return s[i:j if j > 0 else None].split("\n", 1)[1].strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-subir", action="store_true")
    args = ap.parse_args()
    tag = f"v{VERSION}"
    if run("git", "status", "--porcelain", salida=True).strip():
        sys.exit("Hay cambios sin commit: haz commit antes de publicar")
    # países/oyentes/fechas de MusicBrainz buscados en este PC → conocimiento/ (viaja con la versión)
    from core import conocimiento  # noqa: E402
    if conocimiento.exportar() and run("git", "status", "--porcelain", "conocimiento", salida=True).strip():
        run("git", "add", "conocimiento")
        run("git", "commit", "-q", "-m", "chore: conocimiento compartido actualizado")
    if run("git", "status", "--porcelain", salida=True).strip():
        sys.exit("Hay cambios sin commit: haz commit antes de publicar")
    if tag in run("git", "tag", salida=True).split():
        sys.exit(f"El tag {tag} ya existe: sube VERSION en core/version.py")
    if f"## v{VERSION}" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        sys.exit(f"Falta la entrada ## v{VERSION} en CHANGELOG.md")
    if not (ROOT / "android/keystore.properties").exists():
        sys.exit("Falta android/keystore.properties (clave propia del APK)")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")

    out = ROOT / "salida" / "release"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    gradle = ROOT / "android" / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    run(gradle, "assembleRelease", "--console=plain", "-q", cwd=ROOT / "android")
    apk = out / f"Chronify-{tag}.apk"
    shutil.copyfile(ROOT / "android/app/build/outputs/apk/release/app-release.apk", apk)
    (out / "notas.md").write_text(notas() + "\n", encoding="utf-8")

    run("git", "tag", tag)
    zipf = out / f"Chronify-{tag}.zip"
    run("git", "archive", "--format=zip", "--prefix=Chronify/", "-o", zipf, tag)
    print(f"Preparado en {out}: {zipf.name} ({zipf.stat().st_size // 1024} KB), {apk.name} ({apk.stat().st_size // 1024 // 1024} MB)")
    if args.sin_subir:
        run("git", "tag", "-d", tag)
        return
    run("git", "push", "origin", "HEAD")
    run("git", "push", "origin", tag)
    run("gh", "release", "create", tag, zipf, apk, "--title", tag, "--notes-file", out / "notas.md")
    print(f"Publicada {tag}")


if __name__ == "__main__":
    main()
