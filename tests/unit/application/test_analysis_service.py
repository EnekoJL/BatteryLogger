import pandas as pd

from batterylogger.application.analysis_service import AnalysisUseCase


class FakeParser:
    def __init__(self, df=None, error=None):
        self._df = df
        self._error = error
        self.calls: list[tuple] = []

    def parse(self, contents_b64, filename):
        self.calls.append((contents_b64, filename))
        return self._df, self._error


def test_parse_delegates_to_parser_port():
    df = pd.DataFrame({'soc': [1, 2]})
    parser = FakeParser(df=df)
    use_case = AnalysisUseCase(parser=parser)

    result_df, error = use_case.parse('data:...', 'log.csv')

    assert result_df is df
    assert error is None
    assert parser.calls == [('data:...', 'log.csv')]


def test_parse_propagates_error():
    parser = FakeParser(df=None, error="bad file")
    use_case = AnalysisUseCase(parser=parser)

    result_df, error = use_case.parse('data:...', 'log.csv')

    assert result_df is None
    assert error == "bad file"


def test_analyze_runs_domain_stats_and_cycle_detection():
    df = pd.DataFrame({
        'Timestamp': pd.date_range('2026-01-01', periods=3, freq='h'),
        'soc': [80.0, 60.0, 40.0],
        'current': [-5.0, -5.0, -5.0],
    })
    use_case = AnalysisUseCase(parser=FakeParser())

    result = use_case.analyze(df)

    assert result.stats.record_count == 3
    assert isinstance(result.cycles, list)
