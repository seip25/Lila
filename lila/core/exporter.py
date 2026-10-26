"""Lila Framework v2.0.0 CSV Data Exporter.
Zero-dependency CSV exporter for Dicts, Pydantic models, and SQLAlchemy objects.
"""

import csv
import io
from typing import Any, List, Optional, Union, Dict
from pydantic import BaseModel
from lila.core.responses import Response, LilaResponseMixin


class CSVResponse(LilaResponseMixin, Response):
    media_type = "text/csv; charset=utf-8"

    def __init__(
        self,
        content: str,
        filename: str = "export.csv",
        status_code: int = 200,
        headers: Optional[dict] = None,
    ):
        hdrs = dict(headers or {})
        hdrs["Content-Disposition"] = f'attachment; filename="{filename}"'
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

        # 1. Pydantic models
        if isinstance(first_item, BaseModel):
            dict_data = [item.model_dump() for item in data]
            fieldnames = headers or list(dict_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict_data)

        # 2. Dictionaries
        elif isinstance(first_item, dict):
            fieldnames = headers or list(first_item.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

        # 3. Objects with to_dict or __table__
        elif hasattr(first_item, "to_dict"):
            dict_data = [item.to_dict() for item in data]
            fieldnames = headers or list(dict_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict_data)

        # 4. Tuples / Lists
        elif isinstance(first_item, (list, tuple)):
            writer = csv.writer(output, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            writer.writerows(data)

        else:
            # Fallback
            writer = csv.writer(output, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            for item in data:
                writer.writerow([str(item)])

        return output.getvalue()

    @classmethod
    def to_csv_response(
        cls,
        data: List[Any],
        filename: str = "export.csv",
        headers: Optional[List[str]] = None,
        delimiter: str = ",",
    ) -> CSVResponse:
        content = cls.to_csv_string(data, headers=headers, delimiter=delimiter)
        return CSVResponse(content=content, filename=filename)
