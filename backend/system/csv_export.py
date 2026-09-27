"""CSV export for the admin lists.

Kept apart from the Excel report (system/excel.py): that one is a formatted three-sheet
summary for reading, this is the raw rows for a spreadsheet or a mail merge.
"""

import csv
from datetime import date
from typing import Any, Iterable, Sequence

from django.http import StreamingHttpResponse
from django.utils import timezone

CSV_CONTENT_TYPE = "text/csv; charset=utf-8"


class _Echo:
    """A file-like object that returns the line instead of writing it anywhere."""

    def write(self, value: str) -> str:
        return value


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def stream_csv(
    *, filename: str, headers: Sequence[str], rows: Iterable[Sequence[Any]]
) -> StreamingHttpResponse:
    """Stream the rows out instead of building the whole file in memory first.

    A spreadsheet of a few thousand stalls is not large, but streaming costs nothing and keeps
    the response from growing with the table.
    """
    writer = csv.writer(_Echo())

    def lines():
        # Excel opens a UTF-8 CSV as the system codepage unless it sees a byte-order mark,
        # which turns Vietnamese names into mojibake.
        yield "﻿"
        yield writer.writerow(headers)
        for row in rows:
            yield writer.writerow([_cell(value) for value in row])

    stamp = timezone.localdate().isoformat()
    response = StreamingHttpResponse(lines(), content_type=CSV_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}-{stamp}.csv"'
    return response
