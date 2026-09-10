#!/usr/bin/env bash
# Provisions ./env (the project virtual environment) and installs the
# package with its dev extras. Safe to re-run; repairs a broken/unisolated
# venv automatically. Called by run.sh — not meant to be run standalone
# from an arbitrary directory.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

readonly VENV_DIR="env"
readonly VENV_PYTHON="${VENV_DIR}/bin/python"

# A venv is only trustworthy if its own interpreter reports isolation
# (sys.prefix != sys.base_prefix). Checking that env/bin/pip merely exists
# is not enough: a half-built venv (missing python3.X-venv on the host) can
# leave a pip file in place that still resolves back to the system
# interpreter, which then refuses with externally-managed-environment.
venv_is_isolated() {
    "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1 || return 1
    "${VENV_PYTHON}" -m platform >/dev/null 2>&1 || return 1
    "${VENV_PYTHON}" -c "import sys; raise SystemExit(sys.prefix == sys.base_prefix)"
}

create_venv() {
    echo "Creating virtual environment in ./${VENV_DIR} ..."
    python3 -m venv "${VENV_DIR}"
}

# When the venv module can't produce an isolated interpreter, the host is
# missing the matching python3.X-venv package (a separate apt package on
# Debian/Ubuntu). Install it and rebuild.
install_missing_venv_package() {
    local python_version package_name
    python_version="$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
    package_name="python${python_version}-venv"

    echo "System is missing ${package_name} (required for an isolated venv)."
    echo "Installing it via sudo apt-get ..."
    sudo apt-get install -y "${package_name}"
}

if [ -d "${VENV_DIR}" ] && ! venv_is_isolated; then
    echo "Existing ./${VENV_DIR} is broken (not isolated) — recreating it."
    rm -rf "${VENV_DIR}"
fi

if [ ! -d "${VENV_DIR}" ]; then
    create_venv
fi

if ! venv_is_isolated; then
    install_missing_venv_package
    rm -rf "${VENV_DIR}"
    create_venv
fi

if ! venv_is_isolated; then
    echo "error: could not provision an isolated virtual environment in ./${VENV_DIR}." >&2
    echo "Try manually: rm -rf ${VENV_DIR} && sudo apt-get install python3-venv && ./run.sh" >&2
    exit 1
fi

"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -e ".[dev]"
