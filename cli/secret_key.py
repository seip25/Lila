import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import typer 
import os 
from pathlib import Path
from app.helpers.security import generate_token_value


PATH_ENV= Path(".env")


app = typer.Typer()

@app.command()
def create():
    key_replace= "SECRET_KEY='SECRET_KEY'"
    new_key=generate_token_value()
    content=None
    try:
        with open(PATH_ENV, "r", encoding="utf-8") as f:
            content = f.read() 
        content = content.replace(key_replace, f"SECRET_KEY='{new_key}'")
        print()
        with open(PATH_ENV, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"key generated is SECRET_KEY='{new_key}'")
    except Exception as e:
        print(e)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
 