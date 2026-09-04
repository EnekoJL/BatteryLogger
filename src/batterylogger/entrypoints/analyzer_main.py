"""Battery Log Analyzer entry point — thin shim.

Usage:
  python -m batterylogger.entrypoints.analyzer_main
  Open http://localhost:8050 and drag-drop a CSV log.
"""

from batterylogger.adapters.inbound.dash_ui.app import create_app
from batterylogger.bootstrap.container import build_analysis_use_case


def main() -> None:
    app = create_app(build_analysis_use_case())
    app.run(debug=True, port=8050, host='0.0.0.0')


if __name__ == '__main__':
    main()
