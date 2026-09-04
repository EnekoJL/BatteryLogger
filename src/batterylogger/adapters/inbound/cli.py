"""CLI driving adapter for the logger: argv parsing, signal handling, and
console output. All actual behavior is delegated to LoggingUseCase — this
module's only job is translating between the terminal and the use-case.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

from batterylogger.application.dto import DryRunResult, SessionReport
from batterylogger.bootstrap.container import build_logger_container

APP_VERSION = "2.0.0"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='battery_logger',
        description=f'Battery Logger v{APP_VERSION} — Real-time BCS data logger',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python -m batterylogger.entrypoints.logger_main                     default cfg.ini, all features on
  python -m batterylogger.entrypoints.logger_main --config /data/cfg.ini
  python -m batterylogger.entrypoints.logger_main --log-level DEBUG
  python -m batterylogger.entrypoints.logger_main --no-csv
  python -m batterylogger.entrypoints.logger_main --dry-run
  python -m batterylogger.entrypoints.logger_main --poll-interval 5
  python -m batterylogger.entrypoints.logger_main --log-freq 30
  python -m batterylogger.entrypoints.logger_main --status-interval 10
        """,
    )
    parser.add_argument('--config', default='cfg.ini', metavar='PATH', help='Path to config file (default: cfg.ini)')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Logging verbosity (default: INFO)')
    parser.add_argument('--no-csv', action='store_true', help='Disable CSV logging (monitor-only mode)')
    parser.add_argument('--dry-run', action='store_true', help='Fetch device info and print one snapshot, then exit')
    parser.add_argument('--status-interval', type=int, default=10, metavar='SECS', help='Console status print interval in seconds (default: 10)')
    parser.add_argument('--poll-interval', type=int, metavar='SECS', help='API polling interval in seconds (overrides cfg.ini)')
    parser.add_argument('--log-freq', type=int, metavar='SECS', help='CSV row frequency in seconds (overrides cfg.ini)')
    parser.add_argument('--version', action='version', version=f'%(prog)s {APP_VERSION}')
    return parser.parse_args(argv)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _print_dry_run(result: DryRunResult) -> None:
    log = logging.getLogger('dry-run')
    if not result.ok:
        log.error(result.error)
        return
    print("\n" + "=" * 60)
    print("  DRY-RUN RESULT")
    print("=" * 60)
    print(f"  Firmware : {result.firmware}")
    print(f"  Battery  : {result.battery_config}")
    if result.reading is not None:
        print(f"\n{result.reading}")
    print("=" * 60 + "\n")


def _print_session_summary(report: SessionReport) -> None:
    h, rem = divmod(report.duration_s, 3600)
    m, s = divmod(rem, 60)
    print("\n" + "=" * 60)
    print("  SESSION SUMMARY")
    print("=" * 60)
    print(f"  Duration      : {h:02d}:{m:02d}:{s:02d}")
    print(f"  API polls     : {report.total_polls} ({report.error_rate:.1%} error rate)")
    print(f"  Energy in     : {report.energy.energy_ch_wh:.1f} Wh")
    print(f"  Energy out    : {report.energy.energy_dch_wh:.1f} Wh")
    if report.csv_summary:
        print(f"  CSV records   : {report.csv_summary.records_written}")
        print(f"  CSV file      : {report.csv_summary.filename}")
    print("=" * 60 + "\n")


async def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(args.log_level)
    log = logging.getLogger('main')

    if not os.path.exists(args.config):
        log.error(f"Config file not found: {args.config}")
        sys.exit(1)

    container = build_logger_container(
        config_path=args.config,
        no_csv=args.no_csv,
        poll_interval_override=args.poll_interval,
        log_freq_override=args.log_freq,
        status_interval=args.status_interval,
    )
    use_case = container.use_case
    log.info(f"Battery config: {container.topology.num_cells} cells × {container.topology.num_modules} modules")

    try:
        if args.dry_run:
            result = await use_case.dry_run()
            _print_dry_run(result)
            return

        print(f"\n{'=' * 60}")
        print(f"  Battery Logger v{APP_VERSION}")
        print(f"  Config  : {os.path.abspath(args.config)}")
        print(f"  CSV     : {'disabled' if args.no_csv else 'enabled'}")
        print("  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        await use_case.start()

        def _handle_shutdown(*_):
            log.info("Shutdown signal received.")
            use_case.request_shutdown()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_shutdown)
            except (NotImplementedError, OSError):
                signal.signal(sig, _handle_shutdown)

        got_info = await use_case.wait_for_static_info(60)
        if got_info:
            print(f"  Firmware : {use_case.firmware_info}")
            print(f"  Battery  : {use_case.battery_config}\n")
        else:
            log.warning("Device info not available yet — continuing with empty metadata.")

        await use_case.wait_for_shutdown()
        print("\nShutting down...")
        report = await use_case.stop()
        _print_session_summary(report)
    finally:
        await container.api_client.close()
