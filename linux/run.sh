#!/usr/bin/env bash
# Entry point: provisions ./env via linux/setup_env.sh, then prints how
# to activate it and run the project.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

./setup_env.sh

cat <<'MSG'

Done. Activate with:  source env/bin/activate
Then run:
  ./linux/run_logger.sh
  ./linux/run_analyzer.sh
  pytest --cov=batterylogger
MSG
