from batterylogger.adapters.outbound.ini_config_repository import IniConfigRepository


def _write_ini(tmp_path, content: str) -> str:
    path = tmp_path / 'cfg.ini'
    path.write_text(content)
    return str(path)


def test_missing_file_yields_all_defaults(tmp_path):
    repo = IniConfigRepository(str(tmp_path / 'does_not_exist.ini'))
    assert repo.load_api_settings().base_url == ""
    assert repo.load_logger_settings().log_frequency == 60
    assert repo.load_battery_topology().num_cells == 15
    assert repo.load_alert_thresholds().soc_low == 20.0


def test_full_config_parsed_correctly(tmp_path):
    path = _write_ini(tmp_path, """
[Battery_API]
IP=192.168.1.50
PollInterval=7

[Logging]
LogFrequency=15
RotateDaily=false

[Battery_Config]
NumCells=14
NumModules=2

[Alerts]
SocLowThreshold=25
TempHighThreshold=45
""")
    repo = IniConfigRepository(path)

    api = repo.load_api_settings()
    assert api.base_url == "http://192.168.1.50"
    assert api.poll_interval == 7

    logging_settings = repo.load_logger_settings()
    assert logging_settings.log_frequency == 15
    assert logging_settings.rotate_daily is False

    topology = repo.load_battery_topology()
    assert topology.num_cells == 14
    assert topology.num_modules == 2

    thresholds = repo.load_alert_thresholds()
    assert thresholds.soc_low == 25.0
    assert thresholds.temp_high == 45.0


def test_missing_sections_fall_back_to_defaults(tmp_path):
    path = _write_ini(tmp_path, "[Battery_API]\nIP=10.0.0.1\n")
    repo = IniConfigRepository(path)

    assert repo.load_logger_settings().log_frequency == 60
    assert repo.load_battery_topology().num_cells == 15
    assert repo.load_alert_thresholds().temp_high == 40.0


def test_invalid_log_frequency_falls_back_to_default(tmp_path):
    path = _write_ini(tmp_path, "[Logging]\nLogFrequency=not-a-number\n")
    repo = IniConfigRepository(path)
    assert repo.load_logger_settings().log_frequency == 60
