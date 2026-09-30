"""Render og-image.html -> ../og-image.png (1200x627). Run: python tools/make_og.py"""
import pathlib
from playwright.sync_api import sync_playwright
here = pathlib.Path(__file__).resolve().parent
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 627})
    pg.goto((here / "og-image.html").as_uri())
    pg.wait_for_timeout(300)
    pg.screenshot(path=str(here.parent / "og-image.png"))
    b.close()
