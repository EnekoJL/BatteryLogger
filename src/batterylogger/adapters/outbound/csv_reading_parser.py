"""Turns a Dash-uploaded CSV (base64 data URI) into a DataFrame."""

import base64
import io
from typing import Callable, Optional

import pandas as pd


class CsvReadingParser:
    """Implements domain.ports.ReadingParserPort."""

    def parse(
        self,
        contents_b64: str,
        filename: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[Optional[pd.DataFrame], Optional[str]]:
        _, content_string = contents_b64.split(',', 1)
        decoded = base64.b64decode(content_string)
        text = decoded.decode('utf-8-sig')
        try:
            # Exact row count up front (a single cheap newline scan) rather
            # than an estimate, so progress reporting is real, not synthetic
            # — and it sizes the chunk count to ~50 updates regardless of
            # file size, enough to animate smoothly without flooding the
            # caller with updates on a very large log.
            total_rows = max(text.count('\n') - 1, 0)
            chunk_size = max(total_rows // 50, 200) if total_rows else 5000

            chunks = []
            rows_so_far = 0
            for chunk in pd.read_csv(io.StringIO(text), chunksize=chunk_size):
                chunks.append(chunk)
                rows_so_far += len(chunk)
                if on_progress:
                    on_progress(rows_so_far, total_rows or rows_so_far)

            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            if 'Timestamp' not in df.columns:
                return None, "'Timestamp' column not found."
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            df.sort_values('Timestamp', inplace=True)
            df['Timestamp'] = df['Timestamp'].astype(str)
            if on_progress:
                on_progress(len(df), len(df))
            return df, None
        except Exception as e:
            return None, str(e)
