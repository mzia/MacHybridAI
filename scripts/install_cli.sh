#!/usr/bin/env bash
set -euo pipefail

# Installs the `machybrid` and `mh` Hybrid Agentic CLI commands into ~/.local/bin
# without requiring root or external pip downloads.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
INSTALL_BIN="${HOME}/.local/bin"

if [ ! -f "${BACKEND_DIR}/machybrid/cli.py" ]; then
    if [ -f "/Applications/MacHybridAI.app/Contents/Resources/backend/machybrid/cli.py" ]; then
        BACKEND_DIR="/Applications/MacHybridAI.app/Contents/Resources/backend"
    else
        echo "Error: Could not find machybrid backend directory." >&2
        exit 1
    fi
fi

PYTHON_BIN="/opt/homebrew/bin/python3"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="$(command -v python3 || echo /usr/bin/python3)"
fi

mkdir -p "${INSTALL_BIN}"

cat > "${INSTALL_BIN}/machybrid" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${BACKEND_DIR}\${PYTHONPATH:+:\$PYTHONPATH}"
exec "${PYTHON_BIN}" -m machybrid.cli "\$@"
EOF

chmod +x "${INSTALL_BIN}/machybrid"
ln -sf "${INSTALL_BIN}/machybrid" "${INSTALL_BIN}/mh"

echo "Installed MacHybridAI Hybrid Agentic CLI:"
echo "  - ${INSTALL_BIN}/machybrid"
echo "  - ${INSTALL_BIN}/mh"
echo ""
if [[ ":${PATH}:" != *":${INSTALL_BIN}:"* ]]; then
    echo "Add ~/.local/bin to your PATH if not already present:"
    echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
fi
echo "Try running: machybrid --help"
