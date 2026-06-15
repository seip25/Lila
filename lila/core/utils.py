from datetime import datetime, date
from typing import Any

def convert_date_to_str(value: Any) -> Any:
    """Converts a date or datetime object to an ISO string."""
    if isinstance(value, (date, datetime)):
        return value.isoformat() if value else None
    return value
