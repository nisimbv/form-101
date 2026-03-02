"""
Edge-case scenario tests for Form 101 PDF generation.

Tests 7 scenarios not covered by the basic/comprehensive pipeline:
  1. Spouse with work income → correct marks at 100.4mm + 57.2mm, NOT 145.3mm
  2. Employer address field → text appears in PDF
  3. Tax coordination (has_tax_coordination=True) → Section T mark
  4. has_other_income=True → YES mark present; no_other_income mark ABSENT
  5. relief_wants + relief_has_other → both marks rendered
  6. Changes section + aliya_date → aliya text in PDF
  7. Non-resident → resident_no mark; resident_yes mark ABSENT

Usage:
    python -m scripts.test_edge_cases
"""
import io, json, base64, sys
from pathlib import Path
import requests
import pdfplumber

from scripts.config import APPS_SCRIPT_URL, MM_TO_PT

MARK_CHARS = {"✓", "v", "V", "\u2713", "\u2714", "\u221a"}


# ── Infrastructure ─────────────────────────────────────────────────────────────

def _post_and_get_pdf(data: dict) -> tuple[dict, bytes | None]:
    """POST form data to GAS, download resulting PDF."""
    try:
        r = requests.post(
            APPS_SCRIPT_URL,
            data=json.dumps(data, ensure_ascii=False),
            headers={"Content-Type": "text/plain"},
            timeout=60,
        )
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        print(f"  ❌ POST failed: {e}")
        return {"success": False, "error": str(e)}, None

    if not result.get("success"):
        print(f"  ❌ GAS error: {result.get('error')}")
        return result, None

    file_id = result.get("fileId")
    if not file_id:
        return result, None

    try:
        r2 = requests.get(
            APPS_SCRIPT_URL,
            params={"action": "getPdf", "id": file_id},
            timeout=60,
        )
        pdf_result = r2.json()
        if pdf_result.get("success"):
            pdf_bytes = base64.b64decode(pdf_result["data"])
            print(f"  ✅ GAS accepted — rowNum={result.get('rowNum')}, {len(pdf_bytes):,} bytes")
            return result, pdf_bytes
        print(f"  ❌ PDF download error: {pdf_result.get('error')}")
    except Exception as e:
        print(f"  ❌ PDF download failed: {e}")
    return result, None


def _collect_marks_page(pdf_bytes: bytes, page_num: int = 1) -> list[tuple[float, float]]:
    """Return list of (x_mm, y_mm) for all mark characters on the given page."""
    marks = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if page_num > len(pdf.pages):
            return marks
        page = pdf.pages[page_num - 1]
        for ch in (page.chars or []):
            if ch.get("text", "") in MARK_CHARS:
                marks.append((ch.get("x0", 0) / MM_TO_PT, ch.get("top", 0) / MM_TO_PT))
    return marks


def _found(marks: list, left_mm: float, top_mm: float, tol: float = 5.0) -> bool:
    """True if any mark is within ±tol mm of (left_mm, top_mm)."""
    return any(abs(x - left_mm) < tol and abs(y - top_mm) < tol for x, y in marks)


def _absent(marks: list, left_mm: float, top_mm: float, tol: float = 4.0) -> bool:
    """True if NO mark is within ±tol mm of (left_mm, top_mm).
    Uses tighter tolerance than _found to avoid false positives from nearby marks."""
    return not any(abs(x - left_mm) < tol and abs(y - top_mm) < tol for x, y in marks)


def _text_on_page(pdf_bytes: bytes, text: str, page_num: int = 1) -> bool:
    """True if text (or its Hebrew visual reversal) appears anywhere on the page."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if page_num > len(pdf.pages):
            return False
        full = pdf.pages[page_num - 1].extract_text() or ""
        return text in full or text[::-1] in full


def _check(name: str, condition: bool) -> bool:
    if condition:
        print(f"    ✅ {name}")
    else:
        print(f"    ❌ {name}")
    return condition


# ── Base test payload ──────────────────────────────────────────────────────────

BASE = {
    "last_name":        "טסט",
    "first_name":       "אוטומציה",
    "id_number":        "123456789",
    "birth_date":       "1985-06-15",
    "mobile_phone":     "0500000001",
    "email":            "automation@test.com",
    "employer_name":    "חברת בדיקות",
    "employer_tax_id":  "500000001",
    "employer_phone":   "0500000002",
    "street":           "רחוב הבדיקה",
    "house_number":     "1",
    "city":             "תל אביב",
    "postal_code":      "61000",
    "start_date":       "2026-01-01",
    "gender":           "זכר",
    "marital_status":   "רווק/ה",
    "israeli_resident": "כן",
    "kibbutz_member":   "לא",
    "income_type_monthly": True,
    "confirm_declaration": True,
}


# ── Test scenarios ─────────────────────────────────────────────────────────────

def test_spouse_with_work_income() -> tuple[bool, int | None]:
    """Spouse with work income → marks at 100.4mm (has-income) + 57.2mm (work), NOT 145.3mm (no-income)."""
    data = {**BASE,
        "marital_status": "נשוי/אה",
        "has_spouse": True,
        "spouse_last_name": "לוי",
        "spouse_first_name": "שרה",
        "spouse_id_number": "444444444",
        "spouse_birth_date": "1987-04-20",
        "spouse_has_income": "עבודה",
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("spouse_has_income mark at 100.4mm",       _found(m, 100.4, 255.2)),
        _check("spouse_work mark at 57.2mm",              _found(m, 57.2,  255.2)),
        _check("no_income mark at 145.3mm is ABSENT",     _absent(m, 145.3, 255.1)),
    ])
    return ok, result.get("rowNum")


def test_employer_address() -> tuple[bool, int | None]:
    """Employer address field text appears in PDF."""
    data = {**BASE, "employer_address": "רחוב הבדיקה 5 תל אביב"}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    ok = _check("employer_address text on page 1", _text_on_page(pdf_bytes, "הבדיקה", 1))
    return ok, result.get("rowNum")


def test_tax_coordination() -> tuple[bool, int | None]:
    """has_tax_coordination=True → Section T t2 mark appears."""
    data = {**BASE, "has_tax_coordination": True}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 2)
    ok = _check("tax_coordination mark on page 2 @(181.5mm, 182.1mm)",
                _found(m, 181.5, 182.1))
    return ok, result.get("rowNum")


def test_has_other_income() -> tuple[bool, int | None]:
    """has_other_income=True → YES mark present; no_other_income mark ABSENT.
    Uses tight tolerance (4mm) for absence check to avoid false positive from nearby mark."""
    data = {**BASE,
        "has_other_income": True,
        "other_income_monthly": True,
        "other_income_pension": True,
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("has_other_income YES mark @(84.2mm, 171.0mm)",  _found(m, 84.2, 171.0)),
        _check("other_income_monthly mark @(84.2mm, 175.4mm)",  _found(m, 84.2, 175.4)),
        _check("other_income_pension mark @(42.6mm, 179.2mm)",  _found(m, 42.6, 179.2)),
        _check("no_other_income mark @162.4mm is ABSENT (tol=4mm)",
               _absent(m, 84.2, 162.4, tol=4.0)),
    ])
    return ok, result.get("rowNum")


def test_relief_wants_and_has_other() -> tuple[bool, int | None]:
    """relief_wants + relief_has_other marks are rendered."""
    data = {**BASE, "relief_wants": True, "relief_has_other": True}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("relief_wants mark @(83.87mm, 191.33mm)",    _found(m, 83.87, 191.33)),
        _check("relief_has_other mark @(83.87mm, 199.55mm)", _found(m, 83.87, 199.55)),
    ])
    return ok, result.get("rowNum")


def test_changes_and_aliya() -> tuple[bool, int | None]:
    """Changes section + aliya_date → aliya text appears in PDF."""
    data = {**BASE,
        "aliya_date": "2010-05-01",
        "changes": [
            {"date": "2026-02-01", "details": "שינוי כתובת",
             "notification_date": "2026-02-05", "signature": ""},
        ],
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    ok = all([
        _check("aliya_date text on page 1",    _text_on_page(pdf_bytes, "2010", 1)),
        _check("change_details text on page 1", _text_on_page(pdf_bytes, "כתובת", 1)),
    ])
    return ok, result.get("rowNum")


def test_non_resident() -> tuple[bool, int | None]:
    """Non-resident → resident_no mark present; resident_yes mark ABSENT."""
    data = {**BASE, "israeli_resident": "לא"}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("resident_no mark @(96.2mm, 100.5mm)",           _found(m, 96.2, 100.5)),
        _check("resident_yes mark @(108.8mm, 101.2mm) is ABSENT", _absent(m, 108.8, 101.2)),
    ])
    return ok, result.get("rowNum")


# ── Runner ─────────────────────────────────────────────────────────────────────

TESTS = [
    test_spouse_with_work_income,
    test_employer_address,
    test_tax_coordination,
    test_has_other_income,
    test_relief_wants_and_has_other,
    test_changes_and_aliya,
    test_non_resident,
]


def main() -> None:
    row_nums: list[int] = []
    results: list[tuple[int, str, bool]] = []

    for i, t in enumerate(TESTS, 1):
        print(f"\n{'─' * 55}")
        print(f"  Test {i}: {t.__name__}")
        print(f"{'─' * 55}")
        ok, row_num = t()
        if row_num:
            row_nums.append(int(row_num))
        results.append((i, t.__name__, ok))

    # ── Cleanup ────────────────────────────────────────────────────────────────
    if row_nums:
        print(f"\n[CLEANUP] Deleting {len(row_nums)} test rows: {row_nums}")
        try:
            r = requests.get(
                APPS_SCRIPT_URL,
                params={"action": "deleteTestRows"},
                timeout=30,
            )
            data = r.json()
            if data.get("success"):
                print(f"  ✅ Deleted {data.get('deleted', '?')} rows")
            else:
                print(f"  ⚠  Cleanup: {data}")
        except Exception as e:
            print(f"  ⚠  Cleanup failed: {e}")

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'═' * 55}")
    print("  EDGE-CASE TEST SUMMARY")
    print(f"{'═' * 55}")
    passed = sum(1 for _, _, ok in results if ok)
    for i, name, ok in results:
        status = "✅" if ok else "❌"
        print(f"  {status}  Test {i}: {name}")
    print(f"\n  {passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
