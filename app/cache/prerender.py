from pathlib import Path
from playwright.async_api import async_playwright
import asyncio

CACHE_DIR = Path("templates/html/cache/")

ROUTES = [
    "/",
]


async def prerender_task():
    while True:
        try:

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                for route in ROUTES:
                    url = f"http://localhost:5173/{route}"
                    await page.goto(url, wait_until="networkidle")
                    html = await page.inner_html("#root")
                    filename = (
                        CACHE_DIR
                        / f"{route.strip('/').replace('/', '_') or 'index'}_cache.html"
                    )
                    filename.write_text(html, encoding="utf-8")
                    print(f"✅ Cache generado: {filename}")

                await browser.close()
        except Exception as e:
            print(f"⚠️ Error prerender: {e}")
        await asyncio.sleep(30)
