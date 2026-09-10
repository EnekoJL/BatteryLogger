#!/usr/bin/env bash
# Create the virtual env (if missing/broken) and install the package + dependencies
# (runtime + dev/test tools) in editable mode.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

VENV_PY="env/bin/python"

# Don't trust PATH/activate here — if something on this machine has ever put
# a stray `pip`/`python` ahead of env/bin (or env/bin/python isn't a real
# isolated interpreter), `source env/bin/activate` + bare `pip`/`python`
# silently resolves to the SYSTEM interpreter, which on Debian/Ubuntu refuses
# with "externally-managed-environment". Always invoke pip via the venv's
# python by absolute path instead, and actually run it (not just check the
# file exists) to confirm it's really isolated.
venv_pip_ok() {
    [ -x "$VENV_PY" ] || return 1
    "$VENV_PY" -m pip --version >/dev/null 2>&1 || return 1
    "$VENV_PY" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)'
}

if [ -d env ] && ! venv_pip_ok; then
    echo "Existing ./env is broken (no working isolated pip) — recreating it..."
    rm -rf env
fi

if [ ! -d env ]; then
    echo "Creating virtual environment in ./env ..."
    python3 -m venv env
fi

if ! venv_pip_ok; then
    py_minor="$("$VENV_PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
    pkg="python${py_minor}-venv"
    echo "./env has no working pip — system is likely missing ${pkg}."
    echo "Installing it (requires sudo)..."
    sudo apt-get install -y "$pkg"
    rm -rf env
    python3 -m venv env
fi

if ! venv_pip_ok; then
    echo "error: could not provision an isolated pip into ./env." >&2
    echo "Try manually: rm -rf env && sudo apt-get install python3-venv && ./run.sh" >&2
    exit 1
fi

"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -e ".[dev]"

echo ""
echo "Done. Activate with:  source env/bin/activate"
echo "Then run:"
echo "  python -m batterylogger.entrypoints.logger_main"
echo "  python -m batterylogger.entrypoints.analyzer_main"
echo "  pytest --cov=batterylogger"
