"""Verify that an analyst can log in and open the two primary COSMOS tools."""

import json
import os
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


def check(result, output, base):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="en-US")
            page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
            page.on("response", lambda response: result["http_errors"].append(
                {"url": response.url, "status": response.status}
            ) if response.status >= 400 else None)
            page.goto(base, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(output / "before-login.png"), full_page=True)
            password = page.locator('input[type="password"]')
            if password.count() and password.first.is_visible():
                password.first.fill(os.environ["LAB_API_PASSWORD"])
                page.get_by_role("button", name=re.compile(r"log.?in|sign.?in", re.I)).click()
                password.first.wait_for(state="hidden", timeout=15000)
            result["pre_login_page_errors"] = list(result["page_errors"])
            result["pre_login_http_errors"] = list(result["http_errors"])
            result["page_errors"].clear()
            result["http_errors"].clear()
            if password.count() and password.first.is_visible():
                raise RuntimeError("COSMOS login did not complete")
            result["url"] = page.url
            result["body"] = page.locator("body").inner_text()[:5000]
            page.screenshot(path=str(output / "after-login.png"), full_page=True)
            for tool in ("cmdsender", "tlmviewer"):
                page.goto(f"{base}/tools/{tool}/", wait_until="networkidle", timeout=30000)
                result["tools"][tool] = page.locator("body").inner_text()[:5000]
                page.screenshot(path=str(output / f"{tool}.png"), full_page=True)
        finally:
            browser.close()

    tool_bodies = result["tools"].values()
    if (len(result["tools"]) != 2 or result["page_errors"] or result["http_errors"]
            or any(not body.strip() or "NoSuchKey" in body for body in tool_bodies)):
        raise RuntimeError("COSMOS UI failed to render")


def main():
    output = Path("/evidence")
    output.mkdir(parents=True, exist_ok=True)
    result = {"page_errors": [], "http_errors": [], "tools": {},
              "scope": "COSMOS login and primary tool rendering"}
    try:
        check(result, output, os.environ.get("LAB_URL", "http://localhost:2900"))
        result["status"] = "passed"
    except Exception as exc:
        result.update(status="failed", error=str(exc))
    (output / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
