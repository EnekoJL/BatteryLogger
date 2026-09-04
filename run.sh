#!/usr/bin/env bash
# Create the virtual env (if missing) and install the package + dependencies
# (runtime + dev/test tools) in editable mode.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d env ]; then
    echo "Creating virtual environment in ./env ..."
    python3 -m venv env
fi

source env/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo ""
echo "Done. Activate with:  source env/bin/activate"
echo "Then run:"
echo "  python -m batterylogger.entrypoints.logger_main"
echo "  python -m batterylogger.entrypoints.analyzer_main"
echo "  pytest --cov=batterylogger"
