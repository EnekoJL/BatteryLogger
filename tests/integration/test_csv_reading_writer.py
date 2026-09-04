import csv
from datetime import datetime, timedelta

from freezegun import freeze_time

from batterylogger.adapters.outbound.csv_reading_writer import CsvReadingWriter
from batterylogger.domain.entities import BatteryReading
from batterylogger.domain.value_objects import BatteryConfig, FirmwareInfo


def make_writer(tmp_path, rotate_daily=True):
    config_path = str(tmp_path / 'cfg.ini')
    (tmp_path / 'cfg.ini').write_text('')  # writer only needs the path, not contents
    return CsvReadingWriter(rotate_daily=rotate_daily, config_path=config_path)


def test_first_write_creates_file_with_header_and_row(tmp_path):
    writer = make_writer(tmp_path)
    writer.configure(FirmwareInfo(mcs_core='v1'), BatteryConfig(battery_model='E_BICK_LV_280'))

    writer.write(BatteryReading(voltage=51.0, soc=80.0), datetime(2026, 1, 1, 12, 0, 0))

    assert writer.filename
    with open(writer.filename, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]['Timestamp'] == '2026-01-01 12:00:00'
    assert rows[0]['meta_battery_model'] == 'E_BICK_LV_280'
    assert rows[0]['voltage'] == '51.0'


def test_zero_voltage_row_is_skipped(tmp_path):
    writer = make_writer(tmp_path)
    writer.configure(FirmwareInfo(), BatteryConfig())

    writer.write(BatteryReading(voltage=0.0), datetime(2026, 1, 1, 12, 0, 0))

    with open(writer.filename, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0  # header only, no data row


def test_daily_rotation_creates_new_file(tmp_path):
    # _create_file names the file from the real wall clock (matches original
    # behavior) — freeze it so two rotations don't collide on the same second.
    writer = make_writer(tmp_path, rotate_daily=True)
    writer.configure(FirmwareInfo(), BatteryConfig())

    with freeze_time("2026-01-01 23:59:00"):
        writer.write(BatteryReading(voltage=51.0), datetime(2026, 1, 1, 23, 59, 0))
        first_file = writer.filename

    with freeze_time("2026-01-02 00:01:00"):
        writer.write(BatteryReading(voltage=51.0), datetime(2026, 1, 2, 0, 1, 0))
        second_file = writer.filename

    assert first_file != second_file


def test_no_rotation_when_disabled(tmp_path):
    writer = make_writer(tmp_path, rotate_daily=False)
    writer.configure(FirmwareInfo(), BatteryConfig())

    writer.write(BatteryReading(voltage=51.0), datetime(2026, 1, 1, 23, 59, 0))
    first_file = writer.filename

    writer.write(BatteryReading(voltage=51.0), datetime(2026, 1, 2, 0, 1, 0))

    assert writer.filename == first_file


def test_close_reports_records_written_and_duration(tmp_path):
    writer = make_writer(tmp_path)
    writer.configure(FirmwareInfo(), BatteryConfig())

    start = datetime(2026, 1, 1, 12, 0, 0)
    writer.write(BatteryReading(voltage=51.0), start)
    writer.write(BatteryReading(voltage=52.0), start + timedelta(seconds=10))

    summary = writer.close(start + timedelta(seconds=30))

    assert summary.records_written == 2
    assert summary.duration_s == 30
    assert summary.filename == writer.filename
