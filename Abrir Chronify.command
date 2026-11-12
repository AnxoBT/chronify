#!/bin/sh
# Mac / Linux: doble clic (en Mac) o ./"Abrir Chronify.command" para abrir Chronify. Necesita Python 3.10+.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 app.py "$@"; fi
echo "Chronify necesita Python 3.10 o posterior: https://www.python.org/downloads/"
read -r _
