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


# ── helpers ───────────────────────────────────────────────────────────────────

def _fill(page: Page, selector: str, value: str) -> bool:
    """Fill a text input — scroll into view first."""
    el = page.locator(selector)
    if el.count() == 0:
        print(f"    ⚠  field not found: {selector}")
        return False
    el.first.scroll_into_view_if_needed()
    el.first.fill(value)
    return True


def _check(page: Page, selector: str) -> bool:
    """
    Check a checkbox or radio.
    1. Scroll into view so Playwright can interact.
    2. Try native .check() — works for visible elements.
    3. Fall back to JS if element is not actionable (hidden section, etc.).
    """
    el = page.locator(selector)
    if el.count() == 0:
        print(f"    ⚠  not found: {selector}")
        return False

    # Scroll the element into the viewport
    try:
        el.first.scroll_into_view_if_needed(timeout=3_000)
    except Exception:
        pass  # scroll failure is non-fatal; try check anyway

    # Try native check (fast path for visible elements)
    try:
        el.first.check(timeout=3_000)
        return True
    except Exception:
        pass

    # JS fallback — works even if element is hidden or in a collapsed section
    ok = page.evaluate("""
        (sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            if (!el.checked) {
                el.checked = true;
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            }
            return el.checked;
        }
    """, selector)

    if ok:
        print(f"    ✓ (via JS) {selector}")
    else:
        print(f"    ⚠  could not check: {selector}")
    return bool(ok)


def _select(page: Page, selector: str, value: str) -> bool:
    """Select a <select> option — scroll into view first."""
    el = page.locator(selector)
    if el.count() == 0:
        print(f"    ⚠  select not found: {selector}")
        return False
    el.first.scroll_into_view_if_needed()
    page.select_option(selector, value)
    return True


def _scroll_to_section(page: Page, selector: str) -> None:
    """Scroll a section heading or landmark into view."""
    el = page.locator(selector)
    if el.count() > 0:
        try:
            el.first.scroll_into_view_if_needed(timeout=2_000)
            page.wait_for_timeout(150)
        except Exception:
            pass


def _verify_checked(page: Page, selectors: list[str]) -> None:
    """Log which checkboxes are actually checked in the DOM before submit."""
    for sel in selectors:
        checked = page.evaluate(
            "(sel) => { const e = document.querySelector(sel); return e ? e.checked : null; }",
            sel,
        )
        icon = "✓" if checked else ("✗" if checked is False else "?")
        print(f"    [{icon}] {sel}")


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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=60)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Capture alerts
        alert_messages: list[str] = []
        def _on_dialog(dialog):
            alert_messages.append(dialog.message)
            print(f"  ⚠  Alert: {dialog.message}")
            dialog.accept()

        page.on("dialog", _on_dialog)

        # Log JS errors and GAS network activity
        page.on("console", lambda m: print(f"  [JS {m.type}] {m.text}")
                 if m.type in ("error", "warning") else None)
        page.on("request", lambda req: print(f"  [→] {req.method} {req.url[:90]}")
                 if "script.google" in req.url or "googleusercontent" in req.url else None)
        page.on("requestfailed", lambda req: print(
                 f"  [✗] {req.url[:90]} — {req.failure}")
                 if "script.google" in req.url or "googleusercontent" in req.url else None)

        print(f"  → Opening: {FORM_HTTP_URL}")
        page.goto(FORM_HTTP_URL, wait_until="networkidle", timeout=30_000)
        # Bypass HTML5 required-field validation so our JS handler always fires
        page.evaluate("document.getElementById('form101').setAttribute('novalidate', '')")

        # ── A. Employer ───────────────────────────────────────────────────────
        print("  → Section A: employer")
        _fill(page, 'input[name="employer_name"]',   TEST_DATA["employer_name"])
        _fill(page, 'input[name="employer_tax_id"]', TEST_DATA["employer_tax_id"])
        _fill(page, 'input[name="employer_phone"]',  TEST_DATA["employer_phone"])

        # ── B. Employee personal details ──────────────────────────────────────
        print("  → Section B: employee details")
        _fill(page, 'input[name="last_name"]',    TEST_DATA["last_name"])
        _fill(page, 'input[name="first_name"]',   TEST_DATA["first_name"])
        _fill(page, 'input[name="id_number"]',    TEST_DATA["id_number"])
        _fill(page, 'input[name="mobile_phone"]', TEST_DATA["mobile_phone"])
        _fill(page, 'input[name="email"]',        TEST_DATA["email"])
        _fill(page, 'input[name="street"]',       TEST_DATA["street"])
        _fill(page, 'input[name="house_number"]', TEST_DATA["house_number"])
        _fill(page, 'input[name="city"]',         TEST_DATA["city"])

        # Radios — scroll to each group first
        _check(page, f'input[name="gender"][value="{TEST_DATA["gender"]}"]')
        _check(page, f'input[name="marital_status"][value="{TEST_DATA["marital_status"]}"]')
        _check(page, f'input[name="israeli_resident"][value="{TEST_DATA["israeli_resident"]}"]')
        _check(page, f'input[name="kibbutz_member"][value="{TEST_DATA["kibbutz_member"]}"]')
        _select(page, 'select[name="health_fund"]', TEST_DATA["health_fund"])

        # ── D. Income type ────────────────────────────────────────────────────
        print("  → Section D: income type + start date")
        _fill(page, 'input[name="start_date"]', TEST_DATA["start_date"])
        _scroll_to_section(page, 'input[name="income_type_monthly"]')
        for key in [k for k in TEST_DATA if k.startswith("income_type_") and TEST_DATA[k] is True]:
            _check(page, f'input[name="{key}"]')

        # ── E. Other income ───────────────────────────────────────────────────
        print("  → Section E: other income")
        _scroll_to_section(page, 'input[name="has_other_income"]')
        _check(page, 'input[name="has_other_income"][value="לא"]')

        # ── H. Relief checkboxes (page 2 of the HTML form) ───────────────────
        print("  → Section H: relief checkboxes")
        _scroll_to_section(page, 'input[name="relief_1_resident"]')
        for key in [k for k in TEST_DATA if k.startswith("relief_") and TEST_DATA[k] is True]:
            _check(page, f'input[name="{key}"]')

        # ── Signature ─────────────────────────────────────────────────────────
        print("  → Signature")
        _scroll_to_section(page, '#signatureCanvas')
        _draw_signature(page)

        # ── Declaration ───────────────────────────────────────────────────────
        print("  → Declaration")
        _scroll_to_section(page, 'input[name="confirm_declaration"]')
        _check(page, 'input[name="confirm_declaration"]')

        # ── Pre-submit verification ───────────────────────────────────────────
        print("  → Verifying checkbox state before submit:")
        _verify_checked(page, [
            'input[name="income_type_monthly"]',
            'input[name="relief_1_resident"]',
            'input[name="confirm_declaration"]',
            'input[name="has_other_income"][value="לא"]',
            f'input[name="gender"][value="{TEST_DATA["gender"]}"]',
        ])


        # ── Submit ────────────────────────────────────────────────────────────
        submit_btn = page.locator("#submitBtn")
        submit_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        # Verify signature not empty
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
