"""
Fill and submit Form 101 using Playwright.

Returns the GAS response dict on success (contains fileId, rowNum, pdfUrl).
Returns None on failure.
"""
import json, time, threading, os
import http.server, socketserver
from playwright.sync_api import sync_playwright, Page

from scripts.config import TEST_DATA

# Serve the form over HTTP so fetch() CORS works correctly
_LOCAL_PORT = 8765
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORM_HTTP_URL = f"http://localhost:{_LOCAL_PORT}/index_v6.html"


def _start_local_server(directory: str) -> None:
    """Serve a specific directory on localhost so CORS fetch to GAS works."""
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
        def log_message(self, *args):
            pass  # silence access logs

    with socketserver.TCPServer(("127.0.0.1", _LOCAL_PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        httpd.serve_forever()


_server_started = False

def _ensure_server() -> None:
    global _server_started
    if _server_started:
        return
    t = threading.Thread(
        target=_start_local_server,
        args=(_PROJECT_DIR,),
        daemon=True,
    )
    t.start()
    time.sleep(0.8)
    _server_started = True
    print(f"  → Local HTTP server on port {_LOCAL_PORT}")


# ── helpers ──────────────────────────────────────────────────────────────────

def _fill(page: Page, selector: str, value: str) -> bool:
    el = page.locator(selector)
    if el.count() == 0:
        print(f"    ⚠  field not found: {selector}")
        return False
    el.first.fill(value)
    return True


def _check(page: Page, selector: str) -> bool:
    el = page.locator(selector)
    if el.count() == 0:
        print(f"    ⚠  checkbox/radio not found: {selector}")
        return False
    el.first.check()
    return True


def _draw_signature(page: Page) -> None:
    """Draw directly on the canvas via JS — bypasses getBoundingClientRect issues."""
    drawn = page.evaluate("""
        () => {
            const canvas = document.getElementById('signatureCanvas');
            if (!canvas) return false;
            const ctx = canvas.getContext('2d');
            ctx.strokeStyle = '#222';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(30, 28);
            ctx.bezierCurveTo(55, 8,  95, 42, 120, 28);
            ctx.bezierCurveTo(140, 15, 155, 38, 170, 30);
            ctx.stroke();
            // Verify it's not blank
            const blank = document.createElement('canvas');
            blank.width = canvas.width;
            blank.height = canvas.height;
            return canvas.toDataURL() !== blank.toDataURL();
        }
    """)
    if drawn:
        print("    ✓ Signature drawn on canvas")
    else:
        print("    ⚠  Canvas draw may have failed")


# ── main ─────────────────────────────────────────────────────────────────────

def run_form_test(headless: bool = True) -> dict | None:
    print("\n[TEST FORM]")
    _ensure_server()
    captured: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=80)
        page = browser.new_page()

        # Capture alerts (signature-empty warning, etc.)
        alert_messages: list[str] = []
        def _on_dialog(dialog):
            alert_messages.append(dialog.message)
            print(f"  ⚠  Alert: {dialog.message}")
            dialog.accept()

        page.on("dialog", _on_dialog)

        # Log JS errors and all relevant network activity
        page.on("console", lambda m: print(f"  [JS {m.type}] {m.text}")
                 if m.type in ("error", "warning") else None)
        page.on("request", lambda req: print(f"  [→] {req.method} {req.url[:90]}")
                 if "script.google" in req.url or "googleusercontent" in req.url else None)
        page.on("requestfailed", lambda req: print(
                 f"  [✗] {req.url[:90]} — {req.failure}")
                 if "script.google" in req.url or "googleusercontent" in req.url else None)

        print(f"  → Opening: {FORM_HTTP_URL}")
        page.goto(FORM_HTTP_URL, wait_until="networkidle", timeout=30_000)
        # Bypass HTML5 required validation so JS handler always fires
        page.evaluate("document.getElementById('form101').setAttribute('novalidate', '')")

        # ── Employer section ─────────────────────────────────────────────────
        _fill(page, 'input[name="employer_name"]',   TEST_DATA["employer_name"])
        _fill(page, 'input[name="employer_tax_id"]', TEST_DATA["employer_tax_id"])
        _fill(page, 'input[name="employer_phone"]',  TEST_DATA["employer_phone"])

        # ── Employee personal details ────────────────────────────────────────
        _fill(page, 'input[name="last_name"]',  TEST_DATA["last_name"])
        _fill(page, 'input[name="first_name"]', TEST_DATA["first_name"])
        _fill(page, 'input[name="id_number"]',  TEST_DATA["id_number"])
        _fill(page, 'input[name="mobile_phone"]', TEST_DATA["mobile_phone"])
        _fill(page, 'input[name="email"]',      TEST_DATA["email"])
        _fill(page, 'input[name="street"]',     TEST_DATA["street"])
        _fill(page, 'input[name="house_number"]', TEST_DATA["house_number"])
        _fill(page, 'input[name="city"]',       TEST_DATA["city"])
        _fill(page, 'input[name="start_date"]', TEST_DATA["start_date"])

        # ── Radios / selects ─────────────────────────────────────────────────
        _check(page, f'input[name="gender"][value="{TEST_DATA["gender"]}"]')
        _check(page, f'input[name="marital_status"][value="{TEST_DATA["marital_status"]}"]')
        _check(page, f'input[name="israeli_resident"][value="{TEST_DATA["israeli_resident"]}"]')
        _check(page, f'input[name="kibbutz_member"][value="{TEST_DATA["kibbutz_member"]}"]')
        page.select_option('select[name="health_fund"]', TEST_DATA["health_fund"])

        # ── Checkboxes ───────────────────────────────────────────────────────
        _check(page, 'input[name="income_type_monthly"]')
        _check(page, 'input[name="relief_1_resident"]')

        # "No other income" radio
        _check(page, 'input[name="has_other_income"][value="לא"]')

        # ── Signature ────────────────────────────────────────────────────────
        _draw_signature(page)

        # Declaration date is auto-set by JS; confirm checkbox
        _check(page, 'input[name="confirm_declaration"]')

        # ── Scroll submit button into view and click ─────────────────────────
        submit_btn = page.locator("#submitBtn")
        submit_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        # Verify signature not empty before submitting
        is_empty = page.evaluate("""
            () => {
                const c = document.getElementById('signatureCanvas');
                const b = document.createElement('canvas');
                b.width = c.width; b.height = c.height;
                return c.toDataURL() === b.toDataURL();
            }
        """)
        if is_empty:
            print("  ❌ Signature canvas is still empty — aborting")
            browser.close()
            return None

        print("  → Submitting and waiting for GAS response …")

        # Use expect_response to directly capture the GAS echo response,
        # bypassing any UI rendering issues.
        try:
            with page.expect_response(
                lambda r: "googleusercontent.com/macros/echo" in r.url
                          or ("script.google.com" in r.url and r.status == 200),
                timeout=120_000,
            ) as resp_info:
                submit_btn.click()

            gas_response = resp_info.value
            print(f"  [←] GAS echo status={gas_response.status} url={gas_response.url[:80]}")
            result = gas_response.json()
            print(f"  [←] GAS result: success={result.get('success')} msg={result.get('message','')}")

        except Exception as exc:
            print(f"  ❌ GAS response error: {exc}")
            if alert_messages:
                print(f"      Alert caught: {alert_messages}")
            browser.close()
            return None

        browser.close()

        if result.get("success"):
            fid = result.get("fileId", "?")
            row = result.get("rowNum", "?")
            print(f"  ✅ Success — rowNum={row}, fileId={fid}")
            return result
        else:
            print(f"  ❌ GAS returned success=false: {result.get('message')}")
            return None


if __name__ == "__main__":
    import sys
    headless = "--visible" not in sys.argv
    result = run_form_test(headless=headless)
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    sys.exit(1)
