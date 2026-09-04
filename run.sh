#!/usr/bin/env bash
# Create the virtual env (if missing) and install/update dependencies.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d env ]; then
    echo "Creating virtual environment in ./env ..."
    python3 -m venv env
fi

source env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Done. Activate with:  source env/bin/activate"
echo "Then run:"
echo "  python src/main_logger.py"
echo "  python src/visual_log.py"
