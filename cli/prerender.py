import sys
import os
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import sys
import subprocess
from pathlib import Path
import time
import typer

REQUIRED_PACKAGES = [
    "selenium",
    "webdriver-manager",
    "beautifulsoup4"
]

def ensure_packages():
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"📦Installing / Instalando {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


ensure_packages()

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

app = typer.Typer()

CACHE_DIR = Path("templates/html/react/cache/")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

@app.command()
def cache_page_with_selenium(route: str = "/", url: str = 'http://localhost:5173/'):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=chrome_options
        )
    except Exception as e:
        print(f"❌ Error Selenium: {e}")
        return None

    full_url = f"{url}{route}"
    print(f"🌐 {full_url} with Selenium...")

    try:
        driver.get(full_url)
        time.sleep(5)

        body_html = driver.find_element("tag name", "body").get_attribute('innerHTML')

        soup = BeautifulSoup(body_html, "html.parser")

        root_div = soup.find("div", id="root")
        if root_div:
            root_div.unwrap()

        for script_tag in soup.find_all("script", src="/src/main.jsx"):
            script_tag.decompose()

        filename = CACHE_DIR / f"{route.strip('/') or 'index'}.html"
        filename.write_text(str(soup), encoding="utf-8")

        print(f"✅ Cache saved in {filename}")
        return filename

    except Exception as e:
        print(f"❌ Error : {e}")
        return None

    finally:
        driver.quit()

if __name__ == "__main__":
    app()
