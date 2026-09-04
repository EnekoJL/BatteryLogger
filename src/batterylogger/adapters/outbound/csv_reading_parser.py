"""Turns a Dash-uploaded CSV (base64 data URI) into a DataFrame."""

import base64
import io
from typing import Optional

import pandas as pd


class CsvReadingParser:
    """Implements domain.ports.ReadingParserPort."""

    def parse(self, contents_b64: str, filename: str) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        _, content_string = contents_b64.split(',', 1)
        decoded = base64.b64decode(content_string)
        try:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8-sig')))
            if 'Timestamp' not in df.columns:
                return None, "'Timestamp' column not found."
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df.sort_values('Timestamp', inplace=True)
            df['Timestamp'] = df['Timestamp'].astype(str)
            return df, None
        except Exception as e:
            return None, str(e)
