from datetime import datetime, date 

 
def convert_date_to_str(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat() if value else None
    return value



