"""AnalysisUseCase — parses an uploaded log and runs the domain analysis
(session stats + cycle detection). No Dash/plotly here — that's presentation,
built by adapters/inbound/dash_ui/* from this use-case's output.
"""

from typing import Optional

import pandas as pd

from batterylogger.application.dto import AnalysisResult
from batterylogger.domain.cycle_analysis import detect_cycles
from batterylogger.domain.ports import ReadingParserPort
from batterylogger.domain.stats import compute_session_stats


class AnalysisUseCase:
    def __init__(self, parser: ReadingParserPort):
        self.parser = parser

    def parse(self, contents_b64: str, filename: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        return self.parser.parse(contents_b64, filename)

    def analyze(self, df: pd.DataFrame) -> AnalysisResult:
        stats = compute_session_stats(df)
        cycles = detect_cycles(df)
        return AnalysisResult(stats=stats, cycles=cycles)
