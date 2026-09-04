"""Smoke tests: call the Dash callback functions directly (no server needed —
they're plain functions since the refactor in callbacks.py) against a real
log fixture, checking they don't blow up and return sane component shapes."""

import base64

from dash import html
import dash_bootstrap_components as dbc

from batterylogger.adapters.inbound.dash_ui import callbacks
from batterylogger.bootstrap.container import build_analysis_use_case


def _as_data_uri(path: str) -> str:
    with open(path, 'rb') as f:
        raw = f.read()
    return 'data:text/csv;base64,' + base64.b64encode(raw).decode()


def test_update_store_with_no_upload_returns_hidden_state():
    use_case = build_analysis_use_case()
    data, filename_hint, btn_style, badge, selector_style = callbacks.update_store(use_case, None, None)
    assert data is None
    assert btn_style == {'display': 'none'}


def test_update_store_parses_real_log(sample_log_csv_path):
    use_case = build_analysis_use_case()
    contents = _as_data_uri(sample_log_csv_path)

    data, filename_hint, btn_style, badge, selector_style = callbacks.update_store(
        use_case, contents, 'sample_log.csv',
    )

    assert data is not None
    assert len(data) > 0
    assert isinstance(badge, dbc.Badge)
    assert btn_style == {'display': 'inline-block'}


def test_update_store_reports_parse_errors():
    use_case = build_analysis_use_case()
    bad_csv = 'data:text/csv;base64,' + base64.b64encode(b'no_timestamp_here\n1\n').decode()

    data, filename_hint, btn_style, badge, selector_style = callbacks.update_store(
        use_case, bad_csv, 'bad.csv',
    )

    assert data is None
    assert isinstance(filename_hint, dbc.Alert)


def test_update_graphs_with_no_data_shows_placeholder():
    use_case = build_analysis_use_case()
    result = callbacks.update_graphs(use_case, None, 1)
    assert isinstance(result, html.Div)


def test_update_graphs_renders_full_dashboard(sample_log_csv_path):
    # sample_log.csv predates per-string logging (no string1_* columns) —
    # this is the backward-compat path: no string tabs rendered.
    use_case = build_analysis_use_case()
    contents = _as_data_uri(sample_log_csv_path)
    data, *_ = callbacks.update_store(use_case, contents, 'sample_log.csv')

    result = callbacks.update_graphs(use_case, data, 1)

    assert isinstance(result, html.Div)
    # device panel + stats + cycle table + hr + 3 chart rows + string-tabs slot = 8 children
    assert len(result.children) == 8
    assert isinstance(result.children[-1], html.Div)
    assert not result.children[-1].children  # empty placeholder — no strings discovered


def _multi_string_records():
    import pandas as pd
    df = pd.DataFrame({
        'Timestamp': pd.date_range('2026-01-01', periods=5, freq='5min'),
        'voltage': [51.0] * 5,
        'current': [10.0, 8.0, -5.0, -8.0, 2.0],
        'soc': [50.0, 55.0, 52.0, 48.0, 49.0],
        'string1_voltage': [51.0] * 5,
        'string1_current': [5.0, 4.0, -2.0, -4.0, 1.0],
        'string1_soc': [50.0, 55.0, 52.0, 48.0, 49.0],
        'string1_dispersion_dispersionMax': [1, 1, 2, 1, 1],
        'string2_voltage': [51.0] * 5,
        'string2_current': [5.0, 4.0, -3.0, -4.0, 1.0],
        'string2_soc': [50.0, 56.0, 53.0, 47.0, 48.0],
        'string2_dispersion_dispersionMax': [1, 2, 2, 1, 1],
    })
    return df.to_dict('records')


def test_update_graphs_renders_string_tabs_for_multi_string_data():
    use_case = build_analysis_use_case()
    data = _multi_string_records()

    result = callbacks.update_graphs(use_case, data, 1)

    string_tabs = result.children[-1]
    assert isinstance(string_tabs, dbc.Tabs)
    assert len(string_tabs.children) == 2
    assert string_tabs.children[0].label == 'String 1'
    assert string_tabs.children[1].label == 'String 2'


def test_download_html_report_with_no_data_is_noop():
    import dash
    result = callbacks.download_html_report(None)
    assert result is dash.no_update


def test_download_html_report_builds_html(sample_log_csv_path):
    use_case = build_analysis_use_case()
    contents = _as_data_uri(sample_log_csv_path)
    data, *_ = callbacks.update_store(use_case, contents, 'sample_log.csv')

    result = callbacks.download_html_report(data)

    assert result['filename'].startswith('battery_report_')
    assert '<html' in result['content']


def test_sync_zoom_no_trigger_returns_no_update():
    import dash
    result = callbacks.sync_zoom([], [])
    assert result == []
