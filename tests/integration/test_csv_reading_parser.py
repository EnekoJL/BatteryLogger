import base64

from batterylogger.adapters.outbound.csv_reading_parser import CsvReadingParser


def _as_data_uri(path: str) -> str:
    with open(path, 'rb') as f:
        raw = f.read()
    return 'data:text/csv;base64,' + base64.b64encode(raw).decode()


def test_parses_real_log_fixture(sample_log_csv_path):
    parser = CsvReadingParser()
    df, error = parser.parse(_as_data_uri(sample_log_csv_path), 'sample_log.csv')

    assert error is None
    assert df is not None
    assert 'Timestamp' in df.columns
    assert 'soc' in df.columns
    assert len(df) > 0


def test_missing_timestamp_column_returns_error(tmp_path):
    csv_path = tmp_path / 'no_timestamp.csv'
    csv_path.write_text('soc,voltage\n50,51.0\n60,52.0\n')
    parser = CsvReadingParser()

    df, error = parser.parse(_as_data_uri(str(csv_path)), 'no_timestamp.csv')

    assert df is None
    assert "'Timestamp' column not found." == error


def test_rows_sorted_by_timestamp(tmp_path):
    csv_path = tmp_path / 'unsorted.csv'
    csv_path.write_text('Timestamp,soc\n2026-01-02 00:00:00,20\n2026-01-01 00:00:00,10\n')
    parser = CsvReadingParser()

    df, error = parser.parse(_as_data_uri(str(csv_path)), 'unsorted.csv')

    assert error is None
    assert list(df['soc']) == [10, 20]
