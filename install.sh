#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
echo ""
echo "  Checking for Python..."
for py in python3 python; do
    if command -v "$py" >/dev/null 2>&1; then
        if "$py" -c 'import sys; print("  Found Python", sys.version.split()[0]); sys.exit(sys.version_info < (3, 8))'; then
            chmod +x play.sh 2>/dev/null
            echo ""
            echo "  All set! Terminal-RPG has no extra packages to install."
            echo "  Start your adventure with:  ./play.sh"
            exit 0
        fi
    fi
done
echo "  Python 3.8+ was not found. Install it (e.g. 'sudo apt install python3' or"
echo "  'brew install python') and run this script again."
exit 1
