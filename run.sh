#!/usr/bin/env bash
# Create the virtual env (if missing/broken) and install the package + dependencies
# (runtime + dev/test tools) in editable mode.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# A venv without pip (happens when the matching python3.X-venv apt package is
# missing — ensurepip silently no-ops) is useless: activation then falls
# through to system pip, which on Debian/Ubuntu refuses with
# "externally-managed-environment". Detect and rebuild rather than fail there.
if [ -d env ] && [ ! -x env/bin/pip ]; then
    echo "Existing ./env has no pip (broken venv) — recreating it..."
    rm -rf env
fi

if [ ! -d env ]; then
    echo "Creating virtual environment in ./env ..."
    python3 -m venv env

    if [ ! -x env/bin/pip ]; then
        echo "venv created without pip — bootstrapping via ensurepip..."
        env/bin/python -m ensurepip --upgrade || true
    fi

    if [ ! -x env/bin/pip ]; then
        py_minor="$(env/bin/python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
        pkg="python${py_minor}-venv"
        echo "Still no pip in ./env — system is missing ${pkg}."
        echo "Installing it (requires sudo)..."
        rm -rf env
        sudo apt-get install -y "$pkg"
        python3 -m venv env
    fi

    if [ ! -x env/bin/pip ]; then
        echo "error: could not provision pip into ./env — install python3-venv manually and rerun." >&2
        exit 1
    fi
fi

source env/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

echo ""
echo "Done. Activate with:  source env/bin/activate"
echo "Then run:"
echo "  python -m batterylogger.entrypoints.logger_main"
echo "  python -m batterylogger.entrypoints.analyzer_main"
echo "  pytest --cov=batterylogger"
