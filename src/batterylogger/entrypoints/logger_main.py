"""Battery Logger entry point — thin shim into adapters.inbound.cli.

Usage:
  python -m batterylogger.entrypoints.logger_main [--config PATH] [--log-level LEVEL] [--no-csv]
                 [--status-interval SECS] [--poll-interval SECS]
                 [--log-freq SECS] [--dry-run]
"""

import asyncio

from batterylogger.adapters.inbound.cli import run


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
