#!/bin/bash
set -e
cd -- "$(dirname -- "$0")"
PYTHON_BIN=""
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import sys; assert sys.version_info >= (3,9)' >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "Instala Python 3.9 o posterior para macOS desde https://www.python.org/downloads/macos/"
  echo "Después vuelve a abrir este archivo. No necesitas instalar paquetes adicionales."
  read -r -p "Pulsa Enter para cerrar… "
  exit 1
fi
"$PYTHON_BIN" app.py
