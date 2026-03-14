"""
test_non_resident.py
====================
Playwright test: submit Form 101 for a non-resident (foreign) employee.
Tests fixes:
  1. עיר/ישוב sent in payload
  2. תאריך עליה becomes required when israeli_resident = לא
  3. מספר דרכון appears in page-2 ID field instead of ת.ז
"""
import json, time, threading, os, sys
import http.server, socketserver
from playwright.sync_api import sync_playwright

# ── Test data — non-resident employee ─────────────────────────────────────────
NON_RESIDENT_DATA = {
    # Employer
    "employer_name":   "חברת ייבוא יוצאת",
    "employer_tax_id": "500000099",
    "employer_phone":  "0500000099",
    # Employee
    "last_name":       "סמית",
    "first_name":      "ג'ון",
    "birth_date":      "1990-03-20",
    "passport_number": "AB1234567",       # דרכון במקום ת.ז
    "aliya_date":      "2024-07-01",      # תאריך עליה — חובה כשלא תושב
    "street":          "שדרות רוטשילד",
    "house_number":    "45",
    "city":            "תל אביב",         # עיר/ישוב — תיקון #1
    "postal_code":     "6578401",
    "mobile_phone":    "0524669515",
    "email":           "john.smith@test.com",
    "gender":          "זכר",
    "marital_status":  "רווק/ה",
    "israeli_resident": "לא",            # <-- לא תושב ישראל
    "kibbutz_member":  "לא",
    "health_fund":     "כללית",
    "start_date":      "2026-01-15",
}

_LOCAL_PORT = 8766
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORM_HTTP_URL = f"http://localhost:{_LOCAL_PORT}/index_v6.html"


def _start_server():
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=_PROJECT_DIR, **kw)
        def log_message(self, *a): pass
    with socketserver.TCPServer(("127.0.0.1", _LOCAL_PORT), Handler) as s:
        s.allow_reuse_address = True
        s.serve_forever()


def _fill(page, sel, val):
    el = page.locator(sel)
    if el.count() == 0:
        print(f"    ⚠  not found: {sel}")
        return False
    el.first.scroll_into_view_if_needed()
    el.first.fill(val)
    return True


def _check(page, sel):
    el = page.locator(sel)
    if el.count() == 0:
        print(f"    ⚠  not found: {sel}")
        return False
    try:
        el.first.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    try:
        el.first.check(timeout=3000)
        return True
    except Exception:
        pass
    ok = page.evaluate("""
        sel => {
            const el = document.querySelector(sel);
            if (!el) return false;
            if (!el.checked) {
                el.checked = true;
                el.dispatchEvent(new Event('change', {bubbles:true}));
                el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            }
            return el.checked;
        }
    """, sel)
    print(f"    {'✓ (JS)' if ok else '⚠  FAIL'} {sel}")
    return bool(ok)


def _draw_signature(page):
    page.evaluate("""
        () => {
            const c = document.getElementById('signatureCanvas');
            if (!c) return;
            const ctx = c.getContext('2d');
            ctx.strokeStyle='#111'; ctx.lineWidth=2; ctx.lineCap='round';
            ctx.beginPath();
            ctx.moveTo(30,28); ctx.bezierCurveTo(55,8,95,42,120,28);
            ctx.bezierCurveTo(140,15,155,38,170,30); ctx.stroke();
        }
    """)
    print("    ✓ Signature drawn")


def main():
    # Start local HTTP server
    t = threading.Thread(target=_start_server, daemon=True)
    t.start()
    time.sleep(0.8)
    print(f"  → HTTP server on :{_LOCAL_PORT}")

    print("\n[TEST] עובד לא תושב ישראל — דרכון + תאריך עליה + עיר")
    print(f"  → Opening: {FORM_HTTP_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=80)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Capture response from GAS
        gas_response = {}
        def _on_response(resp):
            if "script.google" in resp.url or "googleusercontent" in resp.url:
                try:
                    body = resp.json()
                    gas_response.update(body)
                except Exception:
                    pass
        page.on("response", _on_response)
        page.on("console", lambda m: print(f"  [JS {m.type}] {m.text}")
                if m.type in ("error", "warning") else None)

        page.goto(FORM_HTTP_URL, wait_until="networkidle", timeout=30_000)
        # Disable HTML5 validation so JS handler runs
        page.evaluate("document.getElementById('form101').setAttribute('novalidate','')")

        # ── A. Employer ────────────────────────────────────────────────────────
        print("  → סעיף א׳: פרטי מעסיק")
        _fill(page, 'input[name="employer_name"]',   NON_RESIDENT_DATA["employer_name"])
        _fill(page, 'input[name="employer_tax_id"]', NON_RESIDENT_DATA["employer_tax_id"])
        _fill(page, 'input[name="employer_phone"]',  NON_RESIDENT_DATA["employer_phone"])

        # ── B. Employee ────────────────────────────────────────────────────────
        print("  → סעיף ב׳: פרטי עובד (לא תושב)")
        _fill(page, 'input[name="last_name"]',    NON_RESIDENT_DATA["last_name"])
        _fill(page, 'input[name="first_name"]',   NON_RESIDENT_DATA["first_name"])
        _fill(page, 'input[name="birth_date"]',   NON_RESIDENT_DATA["birth_date"])

        # בחר "לא תושב" — זה מפעיל updateIdPassportRequired
        print("  → israeli_resident = לא")
        _check(page, 'input[name="israeli_resident"][value="לא"]')
        page.wait_for_timeout(400)

        # בדוק שתאריך עליה הפך ל-required
        aliya_required = page.evaluate("""
            () => document.getElementById('aliya_date')?.required
        """)
        print(f"    aliya_date.required = {aliya_required}  {'✓' if aliya_required else '⚠  FAIL'}")

        # בדוק שדרכון הפך ל-required
        passport_required = page.evaluate("""
            () => document.getElementById('passport_number')?.required
        """)
        print(f"    passport_number.required = {passport_required}  {'✓' if passport_required else '⚠  FAIL'}")

        # מלא תאריך עליה ודרכון
        _fill(page, 'input[name="aliya_date"]',       NON_RESIDENT_DATA["aliya_date"])
        _fill(page, 'input[name="passport_number"]',  NON_RESIDENT_DATA["passport_number"])

        # כתובת (כולל עיר — תיקון #1)
        _fill(page, 'input[name="street"]',       NON_RESIDENT_DATA["street"])
        _fill(page, 'input[name="house_number"]', NON_RESIDENT_DATA["house_number"])
        _fill(page, 'input[name="city"]',         NON_RESIDENT_DATA["city"])
        _fill(page, 'input[name="postal_code"]',  NON_RESIDENT_DATA["postal_code"])
        _fill(page, 'input[name="mobile_phone"]', NON_RESIDENT_DATA["mobile_phone"])
        _fill(page, 'input[name="email"]',        NON_RESIDENT_DATA["email"])

        _check(page, f'input[name="gender"][value="{NON_RESIDENT_DATA["gender"]}"]')
        _check(page, f'input[name="marital_status"][value="{NON_RESIDENT_DATA["marital_status"]}"]')
        _check(page, f'input[name="kibbutz_member"][value="{NON_RESIDENT_DATA["kibbutz_member"]}"]')
        page.select_option('select[name="health_fund"]', NON_RESIDENT_DATA["health_fund"])

        # ── D. Income ─────────────────────────────────────────────────────────
        print("  → סעיף ד׳: סוג הכנסה")
        _fill(page, 'input[name="start_date"]', NON_RESIDENT_DATA["start_date"])
        _check(page, 'input[name="income_type_monthly"]')

        # ── E. Other income ───────────────────────────────────────────────────
        print("  → סעיף ה׳: הכנסות אחרות")
        _check(page, 'input[name="has_other_income"][value="לא"]')

        # ── Signature ─────────────────────────────────────────────────────────
        print("  → חתימה")
        page.locator('#signatureCanvas').scroll_into_view_if_needed()
        _draw_signature(page)

        # ── Declaration ───────────────────────────────────────────────────────
        print("  → הצהרה")
        _check(page, 'input[name="confirm_declaration"]')

        # ── בדוק payload לפני שליחה ───────────────────────────────────────────
        print("\n  → בודק payload לפני שליחה:")
        payload_check = page.evaluate("""
            () => {
                const form = document.getElementById('form101');
                try {
                    const p = buildPayload(form);
                    return {
                        city:          p['employee.address.city'],
                        house_no:      p['employee.address.house_no'],
                        street:        p['employee.address.street'],
                        passport:      p['employee.passport'],
                        aliya:         p['employee.immigration_date'],
                        resident:      p['employee.israeli_resident'] || '(no key)',
                    };
                } catch(e) { return {error: e.message}; }
            }
        """)
        for k, v in payload_check.items():
            status = '✓' if v and v != '(no key)' and v != '' else '⚠ '
            print(f"    {status} {k}: {repr(v)}")

        # ── Submit ─────────────────────────────────────────────────────────────
        print("\n  → שולח טופס...")
        page.locator('button[type="submit"]').scroll_into_view_if_needed()
        page.locator('button[type="submit"]').click()

        # Wait for success or error
        try:
            page.wait_for_selector('#successMessage.active, #errorMessage.active',
                                   timeout=90_000)
        except Exception:
            print("  ⚠  Timeout waiting for response")

        success_visible = page.locator('#successMessage.active').count() > 0
        error_visible   = page.locator('#errorMessage.active').count()  > 0

        print("\n" + "="*60)
        if success_visible:
            print("  ✅ הגשה הצליחה!")
            if gas_response:
                print(f"  rowNum:  {gas_response.get('rowNum','?')}")
                print(f"  fileId:  {gas_response.get('fileId','?')[:30]}...")
                print(f"  pdfUrl:  {gas_response.get('pdfUrl','?')[:60]}")
        elif error_visible:
            err = page.locator('#errorText').inner_text()
            print(f"  ❌ שגיאה: {err}")
        else:
            print("  ⚠  לא ברור — בדוק את הדפדפן")

        print("="*60)
        print("\n  [עצור] הדפדפן פתוח לבדיקה. לחץ Enter לסגור.")
        input()
        browser.close()


if __name__ == "__main__":
    main()
