import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer 
import os 
from pathlib import Path
from lila.core.auth import generate_token_value


PATH_ENV= Path(".env")


app = typer.Typer()

@app.command()
def create():
    import re
    new_key=generate_token_value()
    content=None
    try:
        with open(PATH_ENV, "r", encoding="utf-8") as f:
            content = f.read() 
        # Match SECRET_KEY='...' or SECRET_KEY="..." or SECRET_KEY=...
        content, count = re.subn(r"(SECRET_KEY\s*=\s*['\"])(.*?)(['\"])", rf"\g<1>{new_key}\g<3>", content)
        if count == 0:
            # Fallback if no quotes used
            content, count = re.subn(r"(SECRET_KEY\s*=\s*)([^\s'\"#]+)", rf"\g<1>'{new_key}'", content)
            
        with open(PATH_ENV, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"key generated is SECRET_KEY='{new_key}'")
    except Exception as e:
        print(e)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
 