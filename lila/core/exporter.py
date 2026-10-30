"""Lila Framework v2.0.x CSV Data Exporter.

Zero-dependency CSV exporter with:
- formula-injection protection (cells starting with = + - @),
- optional UTF-8 BOM so Excel opens Chinese/Spanish text correctly,
- safe Content-Disposition filenames.
"""

import csv
import io
import re
from typing import Any, List, Optional, Union, Dict
from pydantic import BaseModel
from lila.core.responses import Response, LilaResponseMixin


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _safe_filename(filename: str, default: str = "export.csv") -> str:
    name = str(filename or default).strip().replace("\r", "").replace("\n", "")
    name = name.replace('"', "")
    return name or default


class CSVResponse(LilaResponseMixin, Response):
    media_type = "text/csv; charset=utf-8"

    def __init__(
        self,
        content: str,
        filename: str = "export.csv",
        status_code: int = 200,
        headers: Optional[dict] = None,
        bom: bool = True,
    ):
        hdrs = dict(headers or {})
        hdrs["Content-Disposition"] = f'attachment; filename="{_safe_filename(filename)}"'
        if bom:
            hdrs["Content-Type"] = "text/csv; charset=utf-8"
            content = "\ufeff" + content
        super().__init__(
            content=content, status_code=status_code, headers=hdrs, media_type=self.media_type
        )


class Exporter:
    """Serializes Python data structures to CSV format."""

    @staticmethod
    def to_csv_string(
        data: List[Union[Dict[str, Any], BaseModel, Any]],
        headers: Optional[List[str]] = None,
        delimiter: str = ",",
    ) -> str:
        if not data:
            return ""

        output = io.StringIO()
        first_item = data[0]

        def _write_rows(rows: List[dict], fieldnames: List[str]) -> None:
            writer = csv.DictWriter(
                output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({key: _safe_cell(row.get(key)) for key in fieldnames})

        if isinstance(first_item, BaseModel):
            dict_data = [item.model_dump() for item in data]
            _write_rows(dict_data, headers or list(dict_data[0].keys()))

        elif isinstance(first_item, dict):
            _write_rows(data, headers or list(first_item.keys()))

        elif hasattr(first_item, "to_dict"):
            dict_data = [item.to_dict() for item in data]
            _write_rows(dict_data, headers or list(dict_data[0].keys()))

        elif isinstance(first_item, (list, tuple)):
            writer = csv.writer(output, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            writer.writerows([[_safe_cell(cell) for cell in row] for row in data])

        else:
            writer = csv.writer(output, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            for item in data:
                writer.writerow([_safe_cell(str(item))])

        return output.getvalue()

    @classmethod
    def to_csv_response(
        cls,
        data: List[Any],
        filename: str = "export.csv",
        headers: Optional[List[str]] = None,
        delimiter: str = ",",
        bom: bool = True,
    ) -> CSVResponse:
        content = cls.to_csv_string(data, headers=headers, delimiter=delimiter)
        return CSVResponse(content=content, filename=filename, bom=bom)
