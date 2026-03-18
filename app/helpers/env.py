from os import getenv
from typing import Union



def getenvironment(
    key: str, default: Union[str, int, bool] = None
) -> Union[str, int, bool]:
    return getenv(key, default) if default is not None else getenv(key)

