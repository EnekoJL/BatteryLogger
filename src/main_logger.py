"""
Battery Logger - entry point.

Usage:
  python main.py [--config PATH] [--log-level LEVEL] [--no-csv]
                 [--status-interval SECS] [--poll-interval SECS]
                 [--log-freq SECS] [--dry-run]
"""

import argparse
import asyncio
import configparser
import logging
import os
import signal
import sys
from datetime import datetime

from datastruct import BatteryData
from api_controller import APIController
from csv_writer import CSVWriter

APP_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='battery_logger',
        description=f'Battery Logger v{APP_VERSION} — Real-time BCS data logger',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                            default cfg.ini, all features on
  python main.py --config /data/cfg.ini     custom config path
  python main.py --log-level DEBUG          verbose output
  python main.py --no-csv                   monitor only, skip CSV
  python main.py --dry-run                  test API connectivity, no logging
  python main.py --poll-interval 5          override API poll rate to 5s
  python main.py --log-freq 30              log a CSV row every 30s
  python main.py --status-interval 10       print status every 10s
        """,
    )
    parser.add_argument(
        '--config', default='cfg.ini', metavar='PATH',
        help='Path to config file (default: cfg.ini)',
    )
    parser.add_argument(
        '--log-level', default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging verbosity (default: INFO)',
    )
    parser.add_argument(
        '--no-csv', action='store_true',
        help='Disable CSV logging (monitor-only mode)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Fetch device info and print one snapshot, then exit',
    )
    parser.add_argument(
        '--status-interval', type=int, default=10, metavar='SECS',
        help='Console status print interval in seconds (default: 10)',
    )
    parser.add_argument(
        '--poll-interval', type=int, metavar='SECS',
        help='API polling interval in seconds (overrides cfg.ini)',
    )
    parser.add_argument(
        '--log-freq', type=int, metavar='SECS',
        help='CSV row frequency in seconds (overrides cfg.ini)',
    )
    parser.add_argument(
        '--version', action='version', version=f'%(prog)s {APP_VERSION}',
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_battery_config(config_path: str) -> tuple[int, int]:
    config = configparser.ConfigParser()
    config.read(config_path)
    section = config['Battery_Config'] if 'Battery_Config' in config else {}
    num_cells = int(section.get('NumCells', 15))
    num_modules = int(section.get('NumModules', 1))
    return num_cells, num_modules


def load_alert_thresholds(config_path: str) -> dict:
    config = configparser.ConfigParser()
    config.read(config_path)
    defaults = {'SocLowThreshold': 20, 'TempHighThreshold': 40}
    if 'Alerts' not in config:
        return defaults
    section = config['Alerts']
    return {
        'SocLowThreshold': float(section.get('SocLowThreshold', defaults['SocLowThreshold'])),
        'TempHighThreshold': float(section.get('TempHighThreshold', defaults['TempHighThreshold'])),
    }


# ---------------------------------------------------------------------------
# Runtime tasks
# ---------------------------------------------------------------------------

async def status_loop(
    battery_data: BatteryData,
    controller: APIController,
    interval: int,
    thresholds: dict,
):
    alert_logger = logging.getLogger('alerts')
    while True:
        await asyncio.sleep(interval)
        snapshot = await battery_data.get_snapshot()
        status_tag = "ONLINE " if controller.is_connected else "OFFLINE"
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [{status_tag}] {snapshot}\n")

        if snapshot.voltage > 0:
            if snapshot.soc < thresholds['SocLowThreshold']:
                alert_logger.warning(
                    f"LOW SOC ALERT: {snapshot.soc:.1f}% "
                    f"(threshold {thresholds['SocLowThreshold']}%)"
                )
            if snapshot.temperature.tempMax > thresholds['TempHighThreshold']:
                alert_logger.warning(
                    f"HIGH TEMP ALERT: {snapshot.temperature.tempMax:.1f}°C "
                    f"(threshold {thresholds['TempHighThreshold']}°C)"
                )


async def dry_run(controller: APIController, battery_data: BatteryData):
    logger = logging.getLogger('dry-run')
    logger.info("Dry-run mode: fetching device info and one data snapshot...")

    import aiohttp
    async with aiohttp.ClientSession() as session:
        ok = await controller.fetch_static_info(session)
        if not ok:
            logger.error("Could not reach the Battery API.")
            return

        logger.info("Fetching live data snapshot...")
        await controller.fetch_live_data(session)
        snapshot = await battery_data.get_snapshot()

    print("\n" + "=" * 60)
    print("  DRY-RUN RESULT")
    print("=" * 60)
    print(f"  Firmware : {controller.firmware_info}")
    print(f"  Battery  : {controller.battery_config}")
    print(f"\n{snapshot}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Shutdown banner
# ---------------------------------------------------------------------------

async def print_session_summary(
    start: datetime,
    controller: APIController,
    csv_writer: CSVWriter | None,
    battery_data: BatteryData,
):
    energy = await battery_data.get_energy_stats()
    duration = datetime.now() - start
    h, rem = divmod(int(duration.total_seconds()), 3600)
    m, s = divmod(rem, 60)

    print("\n" + "=" * 60)
    print("  SESSION SUMMARY")
    print("=" * 60)
    print(f"  Duration      : {h:02d}:{m:02d}:{s:02d}")
    print(f"  API polls     : {controller._total_polls} ({controller.error_rate:.1%} error rate)")
    print(f"  Energy in     : {energy['energy_ch_wh']:.1f} Wh")
    print(f"  Energy out    : {energy['energy_dch_wh']:.1f} Wh")
    if csv_writer:
        print(f"  CSV records   : {csv_writer.records_written}")
        print(f"  CSV file      : {csv_writer.filename}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger('main')

    if not os.path.exists(args.config):
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    num_cells, num_modules = load_battery_config(args.config)
    thresholds = load_alert_thresholds(args.config)
    logger.info(f"Battery config: {num_cells} cells × {num_modules} modules")

    battery_data = BatteryData(num_cells=num_cells, num_modules=num_modules)
    controller = APIController(battery_data, config_path=args.config)

    if args.poll_interval:
        controller.poll_interval = args.poll_interval

    # --- Dry-run mode ---
    if args.dry_run:
        await dry_run(controller, battery_data)
        return

    # --- Normal mode ---
    session_start = datetime.now()
    shutdown_event = asyncio.Event()

    def _handle_shutdown(*_):
        if not shutdown_event.is_set():
            logger.info("Shutdown signal received.")
            shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_shutdown)
        except (NotImplementedError, OSError):
            signal.signal(sig, _handle_shutdown)

    print(f"\n{'=' * 60}")
    print(f"  Battery Logger v{APP_VERSION}")
    print(f"  Config  : {os.path.abspath(args.config)}")
    print(f"  CSV     : {'disabled' if args.no_csv else 'enabled'}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'=' * 60}\n")

    tasks: list[asyncio.Task] = []

    api_task = asyncio.create_task(controller.run_loop(), name='api-poller')
    tasks.append(api_task)

    # Wait until static device info is available (or timeout)
    try:
        await asyncio.wait_for(
            asyncio.shield(controller.static_info_ready.wait()),
            timeout=60,
        )
        print(f"  Firmware : {controller.firmware_info}")
        print(f"  Battery  : {controller.battery_config}\n")
    except asyncio.TimeoutError:
        logger.warning("Device info not available yet — continuing with empty metadata.")

    csv_writer: CSVWriter | None = None
    if not args.no_csv:
        csv_writer = CSVWriter(
            battery_data,
            firmware_info=controller.firmware_info,
            battery_config=controller.battery_config,
            config_path=args.config,
        )
        if args.log_freq:
            csv_writer.frequency = args.log_freq
        csv_task = asyncio.create_task(csv_writer.run_loop(), name='csv-writer')
        tasks.append(csv_task)
    else:
        logger.info("CSV logging disabled.")

    status_task = asyncio.create_task(
        status_loop(battery_data, controller, args.status_interval, thresholds),
        name='status-printer',
    )
    tasks.append(status_task)

    await shutdown_event.wait()

    print("\nShutting down...")
    controller.stop()
    if csv_writer:
        csv_writer.stop()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await print_session_summary(session_start, controller, csv_writer, battery_data)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
