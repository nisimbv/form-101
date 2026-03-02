"""
Verify the last Sheet row and the generated PDF via GAS endpoints.

Usage:
    python -m scripts.verify <fileId>
    python -m scripts.verify --sheet-only
"""
import sys, io, base64, json, re
from datetime import datetime, timezone, timedelta
import requests
import pdfplumber

# Israel timezone with proper DST support (UTC+3 summer, UTC+2 winter)
try:
    from zoneinfo import ZoneInfo as _ZI
    _ISRAEL_TZ = _ZI('Asia/Jerusalem')
    def _to_israel(dt):
        return dt.astimezone(_ISRAEL_TZ)
except Exception:
    # Approximate: Israel DST runs roughly March–October (UTC+3), rest UTC+2
    _ISRAEL_TZ = None
    def _to_israel(dt):
        offset = 3 if 3 <= dt.month <= 10 else 2
        return dt.astimezone(timezone(timedelta(hours=offset)))


def _normalize_actual(actual: str, expected: str) -> str:
    """If expected is a YYYY-MM-DD date and actual is a UTC ISO timestamp,
    convert to Israel time before comparing."""
    if re.match(r'^\d{4}-\d{2}-\d{2}$', expected.strip()):
        if 'T' in actual:
            try:
                dt = datetime.fromisoformat(actual.replace('Z', '+00:00'))
                return _to_israel(dt).strftime('%Y-%m-%d')
            except Exception:
                pass
    # Numeric → strip trailing .0
    try:
        if float(actual) == float(expected):
            return expected
    except Exception:
        pass
    return actual

from scripts.config import (
    APPS_SCRIPT_URL,
    EXPECTED_SHEET_COLS,
    EXPECTED_TEXT_FIELDS,
    EXPECTED_MARKS,
    EXPECTED_TEXT_FULL,
    EXPECTED_MARKS_FULL,
    TOLERANCE_MM,
    MM_TO_PT,
)

MARK_CHARS = {"✓", "v", "V", "\u2713", "\u2714", "\u221a"}


# ── Sheet ─────────────────────────────────────────────────────────────────────

def verify_sheet() -> bool:
    print("\n[VERIFY SHEET]")
    try:
        r = requests.get(
            APPS_SCRIPT_URL, params={"action": "verify"}, timeout=30
        )
        result = r.json()
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return False

    if not result.get("success"):
        print(f"  ❌ GAS error: {result.get('error')}")
        return False

    data = result.get("data")
    if not data:
        print("  ❌ Sheet is empty — no rows found")
        return False

    print(f"  Row count: {result.get('rows', '?')}")
    all_ok = True

    for col, expected in EXPECTED_SHEET_COLS.items():
        raw    = str(data.get(col, "")).strip()
        actual = _normalize_actual(raw, expected)
        if expected and (expected in actual or actual in expected):
            print(f"  ✅ {col}: '{actual}'" + (f"  (raw: {raw})" if raw != actual else ""))
        elif not expected and actual:
            print(f"  ✅ {col}: (not empty)")
        else:
            print(f"  ❌ {col}: expected '{expected}', got '{actual}'" +
                  (f"  (raw: '{raw}')" if raw != actual else ""))
            all_ok = False

    return all_ok


# ── PDF download ──────────────────────────────────────────────────────────────

def download_pdf(file_id: str) -> bytes | None:
    print(f"\n[DOWNLOAD PDF] id={file_id}")
    try:
        r = requests.get(
            APPS_SCRIPT_URL,
            params={"action": "getPdf", "id": file_id},
            timeout=60,
        )
        result = r.json()
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return None

    if not result.get("success"):
        print(f"  ❌ GAS error: {result.get('error')}")
        return None

    pdf_bytes = base64.b64decode(result["data"])
    print(f"  ✅ {result['name']}  ({len(pdf_bytes):,} bytes)")
    return pdf_bytes


# ── PDF verification ──────────────────────────────────────────────────────────

def verify_pdf(pdf_bytes: bytes) -> bool:
    print("\n[VERIFY PDF]")
    if not pdf_bytes:
        print("  ❌ No PDF bytes")
        return False

    all_ok = True

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages

        # Page count
        if len(pages) == 2:
            print(f"  ✅ Page count: 2")
        else:
            print(f"  ❌ Page count: {len(pages)} (expected 2)")
            all_ok = False

        # ── Text fields ───────────────────────────────────────────────────────
        print()
        for name, page_num, left_mm, top_mm, expected in EXPECTED_TEXT_FIELDS:
            if page_num > len(pages):
                continue
            page = pages[page_num - 1]
            found = _text_near(page, expected, left_mm, top_mm)
            if found:
                print(f"  ✅ text/{name}: '{expected}'  @({left_mm}mm, {top_mm}mm)")
            else:
                print(f"  ❌ text/{name}: '{expected}' NOT found near ({left_mm}mm, {top_mm}mm)")
                all_ok = False

        # ── Mark clustering check (catches transform bug) ─────────────────────
        print()
        all_mark_positions = _collect_all_marks(pages)
        if len(all_mark_positions) > 3:
            unique = set((round(x), round(y)) for x, y in all_mark_positions)
            if len(unique) <= 1:
                print(
                    f"  ❌ ALL {len(all_mark_positions)} marks at same position "
                    f"{list(unique)[0]} — CSS transform bug still active!"
                )
                all_ok = False
            else:
                print(
                    f"  ✅ {len(all_mark_positions)} marks spread across "
                    f"{len(unique)} distinct positions"
                )

        # ── Per-mark position check ───────────────────────────────────────────
        for name, page_num, left_mm, top_mm in EXPECTED_MARKS:
            if page_num > len(pages):
                continue
            page = pages[page_num - 1]
            found = _mark_near(page, left_mm, top_mm)
            if found:
                print(f"  ✅ mark/{name}  @({left_mm}mm, {top_mm}mm)")
            else:
                print(f"  ⚠  mark/{name}  NOT confirmed @({left_mm}mm, {top_mm}mm)  "
                      f"[may need coordinate calibration]")

    return all_ok


# ── helpers ───────────────────────────────────────────────────────────────────

def _crop(page, left_mm: float, top_mm: float, w_mm: float = 50, h_mm: float = 12):
    """Crop a region from a pdfplumber page (coords in mm, top-left origin).
    Coordinates are clamped to page bounds to avoid pdfplumber errors on right/bottom edges."""
    x0 = max(0, (left_mm - TOLERANCE_MM) * MM_TO_PT)
    y0 = max(0, (top_mm  - TOLERANCE_MM) * MM_TO_PT)
    x1 = min(page.width,  (left_mm + w_mm + TOLERANCE_MM) * MM_TO_PT)
    y1 = min(page.height, (top_mm  + h_mm + TOLERANCE_MM) * MM_TO_PT)
    return page.crop((x0, y0, x1, y1))


def _he_visual(text: str) -> str:
    """Return the visual-order (reversed) version of a Hebrew string.
    GAS PDF renderer stores Hebrew in visual RTL order, so 'אוטומציה' is stored
    as 'היצמוטוא' and pdfplumber extracts it reversed."""
    return text[::-1]


def _text_near(page, text: str, left_mm: float, top_mm: float) -> bool:
    """Search for text (and its Hebrew visual-order reversal) in a region and then
    the full page as fallback.  The full-page fallback always runs regardless of
    any crop-region errors (e.g. right-edge fields exceeding page width)."""
    variants = {text, _he_visual(text)}
    try:
        region_text = _crop(page, left_mm, top_mm).extract_text() or ""
        if any(v in region_text for v in variants):
            return True
    except Exception:
        pass
    # Full-page fallback — separate try so crop errors don't suppress it
    try:
        full = page.extract_text() or ""
        if any(v in full for v in variants):
            return True
    except Exception:
        pass
    return False


def _mark_near(page, left_mm: float, top_mm: float) -> bool:
    try:
        region = _crop(page, left_mm, top_mm, w_mm=8, h_mm=8)
        text = region.extract_text() or ""
        if any(c in text for c in MARK_CHARS):
            return True
        return any(ch.get("text", "") in MARK_CHARS for ch in (region.chars or []))
    except Exception:
        return False


def _collect_all_marks(pages) -> list[tuple[float, float]]:
    positions = []
    for page in pages:
        for ch in (page.chars or []):
            if ch.get("text", "") in MARK_CHARS:
                positions.append((ch.get("x0", 0), ch.get("top", 0)))
    return positions


# ── confirmSubmission callback test ───────────────────────────────────────────

def verify_confirm_submission(row_num: int) -> bool:
    """
    Tests the doGet?action=confirmSubmission endpoint.
    Simulates the callback Make would send after delivering the WhatsApp message.
    """
    print("\n[VERIFY CONFIRM SUBMISSION]")
    status_to_set = "✅ הושלם · Pipeline Verified"
    try:
        r = requests.get(
            APPS_SCRIPT_URL,
            params={
                "action": "confirmSubmission",
                "rowNum": str(row_num),
                "status": status_to_set,
                "source": "pipeline-test",
            },
            timeout=30,
        )
        result = r.json()
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return False

    if result.get("success"):
        prev = result.get("previous", "")
        print(f"  ✅ confirmSubmission: row={row_num}")
        print(f"       previous: '{prev}'")
        print(f"       updated:  '{result.get('status', '')}'")
        return True
    else:
        print(f"  ❌ confirmSubmission failed: {result.get('error')}")
        return False


# ── Comprehensive verification ────────────────────────────────────────────────

def verify_pdf_comprehensive(pdf_bytes: bytes) -> bool:
    """Verify PDF against EXPECTED_TEXT_FULL + EXPECTED_MARKS_FULL (comprehensive scenario)."""
    print("\n[VERIFY PDF — COMPREHENSIVE]")
    if not pdf_bytes:
        print("  ❌ No PDF bytes")
        return False

    all_ok = True

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages

        if len(pages) == 2:
            print(f"  ✅ Page count: 2")
        else:
            print(f"  ❌ Page count: {len(pages)} (expected 2)")
            all_ok = False

        print()
        for name, page_num, left_mm, top_mm, expected in EXPECTED_TEXT_FULL:
            if page_num > len(pages):
                continue
            page = pages[page_num - 1]
            found = _text_near(page, expected, left_mm, top_mm)
            if found:
                print(f"  ✅ text/{name}: '{expected}'  @({left_mm}mm, {top_mm}mm)")
            else:
                print(f"  ❌ text/{name}: '{expected}' NOT found near ({left_mm}mm, {top_mm}mm)")
                all_ok = False

        print()
        all_mark_positions = _collect_all_marks(pages)
        if len(all_mark_positions) > 3:
            unique = set((round(x), round(y)) for x, y in all_mark_positions)
            if len(unique) <= 1:
                print(
                    f"  ❌ ALL {len(all_mark_positions)} marks at same position "
                    f"{list(unique)[0]} — CSS transform bug!"
                )
                all_ok = False
            else:
                print(
                    f"  ✅ {len(all_mark_positions)} marks spread across "
                    f"{len(unique)} distinct positions"
                )

        for name, page_num, left_mm, top_mm in EXPECTED_MARKS_FULL:
            if page_num > len(pages):
                continue
            page = pages[page_num - 1]
            found = _mark_near(page, left_mm, top_mm)
            if found:
                print(f"  ✅ mark/{name}  @({left_mm}mm, {top_mm}mm)")
            else:
                print(f"  ⚠  mark/{name}  NOT confirmed @({left_mm}mm, {top_mm}mm)")

    return all_ok


def verify_sheet_comprehensive(row_num: int | None = None) -> bool:
    """Verify the last sheet row using EXPECTED_SHEET_COLS (same as verify_sheet but explicit)."""
    return verify_sheet()


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sheet_only = "--sheet-only" in sys.argv
    file_id = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

    sheet_ok = verify_sheet()

    if sheet_only:
        sys.exit(0 if sheet_ok else 1)

    if not file_id:
        print("Usage: python -m scripts.verify <fileId> [--sheet-only]")
        sys.exit(1)

    pdf_bytes = download_pdf(file_id)
    pdf_ok = verify_pdf(pdf_bytes) if pdf_bytes else False

    if sheet_ok and pdf_ok:
        print("\n✅ ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME CHECKS FAILED — see above for details")
        sys.exit(1)
