"""
English: Zero-dependency CSV Data Exporter for Lila Framework.
         Converts Pydantic models, SQLAlchemy objects, or dict lists to downloadable CSV responses.
Español: Exportador de datos CSV sin dependencias para Lila Framework.
         Convierte modelos Pydantic, objetos SQLAlchemy o listas de dicts en respuestas CSV descargables.
"""

import csv
import io
from typing import Any, List, Optional, Union, Dict
from pydantic import BaseModel
from lila.core.responses import Response, LilaResponseMixin


class CSVResponse(LilaResponseMixin, Response):
    """
    HTTP Response class specifically for downloading CSV files.
    """
    media_type = "text/csv; charset=utf-8"

    def __init__(self, content: str, filename: str = "export.csv", status_code: int = 200, headers: dict = None):
        headers = headers or {}
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        super().__init__(content=content, status_code=status_code, headers=headers, media_type=self.media_type)


class Exporter:
    """
    English: Utilities to serialize Python data structures to CSV format.
    Español: Utilidades para serializar estructuras de datos Python a formato CSV.
    """

    @staticmethod
    def to_csv_string(data: List[Union[Dict[str, Any], BaseModel, Any]], headers: Optional[List[str]] = None, delimiter: str = ",") -> str:
        """
        Converts a list of dicts, Pydantic models, ORM models, or tuples into a CSV string.
        Zero external dependencies — uses Python's native csv module.
        """
        if not data:
            return ""

        output = io.StringIO()
        
        # Normalize items
        first_item = data[0]
        
        # 1. List of Pydantic models
        if isinstance(first_item, BaseModel):
            dict_data = [item.model_dump() for item in data]
            fieldnames = headers or list(dict_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict_data)

        # 2. List of Dictionaries
        elif isinstance(first_item, dict):
            fieldnames = headers or list(first_item.keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

        # 3. SQLAlchemy / ORM models with __dict__
        elif hasattr(first_item, "__table__") or hasattr(first_item, "__dict__"):
            dict_data = []
            for item in data:
                d = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
                dict_data.append(d)
            fieldnames = headers or (list(dict_data[0].keys()) if dict_data else [])
            writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dict_data)

        # 4. List of Lists/Tuples
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
    def to_csv_response(cls, data: List[Any], filename: str = "export.csv", headers: Optional[List[str]] = None, delimiter: str = ",") -> CSVResponse:
        """
        Converts data to a downloadable CSV HTTP Response.
        Usage:
            return Exporter.to_csv_response(users, filename="users.csv")
        """
        csv_content = cls.to_csv_string(data, headers=headers, delimiter=delimiter)
        return CSVResponse(content=csv_content, filename=filename)
