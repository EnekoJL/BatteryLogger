#!/usr/bin/env bash
# Launches the logger (polls the BMS in cfg.ini, writes timestamped CSV rows).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -x env/bin/python ]; then
    echo "error: ./env not found. Run ./run.sh first to provision it." >&2
    exit 1
fi

exec env/bin/python -m batterylogger.entrypoints.logger_main "$@"
