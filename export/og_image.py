"""Render site/og.png, the 1200x630 link-preview image, from the built dashboard.

    python -m export.og_image --site site

Run after export_json so the preview shows the same figures as the page.
Needs Playwright with Chromium (pip install playwright && playwright install chromium);
set CHROME_PATH to use an installed Chrome instead.
"""

from __future__ import annotations

import argparse
import functools
import os
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

HIDE = ".lede,.controls,details{display:none!important} .viz-root{padding-top:22px} h1{font-size:2rem} .tiles{margin-bottom:12px}"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def render(site: Path, out: Path) -> None:
    handler = functools.partial(QuietHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
            page = browser.new_page(viewport={"width": 1000, "height": 525}, device_scale_factor=1.2, color_scheme="light")
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.wait_for_selector("#share-chart svg")
            page.add_style_tag(content=HIDE)
            page.wait_for_timeout(300)
            page.screenshot(path=str(out))
            browser.close()
    finally:
        server.shutdown()
    print(f"wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", type=Path, default=Path("site"))
    args = parser.parse_args()
    render(args.site, args.site / "og.png")


if __name__ == "__main__":
    main()
