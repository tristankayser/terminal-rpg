#!/usr/bin/env bash
# Launch Terminal-RPG with whichever Python 3 is available.
cd "$(dirname "$0")" || exit 1
for py in python3 python; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 8))'; then
        exec "$py" main.py
    fi
done
echo ""
echo "  Python 3.8 or newer is needed to play Terminal-RPG."
echo "  Install it with your package manager (e.g. 'sudo apt install python3')"
echo "  or from https://www.python.org/downloads/"
exit 1
