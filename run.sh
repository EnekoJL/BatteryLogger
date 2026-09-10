#!/usr/bin/env bash
# Entry point: provisions ./env via scripts/setup_env.sh, then prints how
# to activate it and run the project.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

./scripts/setup_env.sh

cat <<'MSG'

Done. Activate with:  source env/bin/activate
Then run:
  python -m batterylogger.entrypoints.logger_main
  python -m batterylogger.entrypoints.analyzer_main
  pytest --cov=batterylogger
MSG
