"""
Edge-case scenario tests for Form 101 PDF generation.
All positions from NEW3 JSON mapping (2026-03-08). Canvas 800x1131px -> A4 210x297mm.

Tests 7 scenarios not covered by the basic/comprehensive pipeline:
  1. Spouse with work income -> marks at 73.5mm (has-income) + 41.0mm (work), NOT 106.6mm (no-income)
  2. Employer address field -> text appears in PDF
  3. Tax coordination (has_tax_coordination=True) -> Section T mark at P2 (134.1, 133.3)
  4. has_other_income=True -> income-type marks present; income.other.none mark ABSENT
  5. relief_wants + relief_has_other -> both marks rendered (61.2mm + 60.9mm, top ~140-147mm)
  6. Aliya date -> aliya text appears in PDF (Section Z not in NEW3 template)
  7. Passport-only employee (no ID) -> has_id.no mark; has_id.yes mark ABSENT

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


# ── Base test payload (Full-Fidelity: all keys are bindKeys 1:1) ───────────────

BASE = {
    "meta.tax_year": "2026",
    # Employer
    "employer.name":            "חברת בדיקות",
    "employer.deductions_file": "500000001",
    "employer.phone":           "0500000002",
    "employer.address":         "",
    # Employee
    "employee.last_name":         "טסט",
    "employee.first_name":        "אוטומציה",
    "employee.id":                "123456789",
    "employee.passport":          "",
    "employee.birth_date":        "1985-06-15",
    "employee.immigration_date":  "",
    "employee.address.street":    "רחוב הבדיקה 1",
    "employee.address.zip":       "61000",
    "employee.mobile":            "0500000001",
    "employee.email":             "automation@test.com",
    # Gender (male)
    "employee.gender.male":   True,
    "employee.gender.female": False,
    # Marital (single)
    "employee.marital_status.married":   False,
    "employee.marital_status.single":    True,
    "employee.marital_status.divorced":  False,
    "employee.marital_status.widowed":   False,
    "employee.marital_status.separated": False,
    # has_id (has ID)
    "employee.has_id.yes": True,
    "employee.has_id.no":  False,
    # Kibbutz
    "employee.kibbutz_member.no":                     True,
    "employee.kibbutz_member.income_transferred":     False,
    "employee.kibbutz_member.income_not_transferred": False,
    # Health fund
    "employee.health_fund.member.yes": False,
    "employee.health_fund.member.no":  True,
    "employee.health_fund.name":       "",
    # Children
    "children": [],
    # Employment + income main
    "employment.start_date":      "2026-01-01",
    "income.main.monthly_salary": True,
    "income.main.additional_job": False,
    "income.main.partial_salary": False,
    "income.main.daily_worker":   False,
    "income.main.pension":        False,
    "income.main.scholarship":    False,
    # Other income (none)
    "income.other.none":            True,
    "income.other.monthly_salary":  False,
    "income.other.additional_job":  False,
    "income.other.partial_salary":  False,
    "income.other.daily_worker":    False,
    "income.other.pension":         False,
    "income.other.scholarship":     False,
    "income.credit_request.get_credits_here":      False,
    "income.credit_request.get_credits_elsewhere": False,
    "income.other.no_training_fund": False,
    "income.other.no_pension":       False,
    # Spouse (none)
    "spouse.id":               "",
    "spouse.passport":         "",
    "spouse.last_name":        "",
    "spouse.first_name":       "",
    "spouse.birth_date":       "",
    "spouse.immigration_date": "",
    "spouse.has_income.none":   True,
    "spouse.has_income.yes":    False,
    "spouse.income_type.work":  False,
    "spouse.income_type.other": False,
    # Credits (all False)
    "credits.1_israeli_resident":                     False,
    "credits.2a_disability_100_or_blind":             False,
    "credits.2b_monthly_benefit":                     False,
    "credits.3_eligible_locality":                    False,
    "credits.3_from_date":                            "",
    "credits.3_locality_name":                        "",
    "credits.4_new_immigrant":                        False,
    "credits.4_from_date":                            "",
    "credits.4_no_income_until":                      "",
    "credits.5_spouse_no_income":                     False,
    "credits.6_single_parent_family":                 False,
    "credits.7_children_in_custody":                  False,
    "credits.7_children_born_in_year":                "0",
    "credits.7_children_count_6_17":                  "0",
    "credits.7_children_count_18":                    "0",
    "credits.7_children_count_1_5":                   "0",
    "credits.8_children_not_in_custody":              False,
    "credits.8_children_count_1_5":                   "0",
    "credits.8_children_count_6_17":                  "0",
    "credits.9_single_parent":                        False,
    "credits.10_children_not_in_custody_maintenance": False,
    "credits.11_disabled_child":                      False,
    "credits.12_spousal_support":                     False,
    "credits.13_age_16_18":                           False,
    "credits.14_released_soldier_or_service":         False,
    "credits.14_service_start":                       "",
    "credits.14_service_end":                         "",
    "credits.15_graduation":                          False,
    "credits.16_reserve_combat":                      False,
    "credits.16_reserve_days_prev_year":              "",
    # Tax coordination
    "tax_coordination.no_income_until_start":  False,
    "tax_coordination.has_additional_income":  False,
    "tax_coordination.approval_attached":      False,
    # Other income table
    "other_income": [],
    # Signature
    "signature.date":                "2026-03-10",
    "signature.declaration":         True,
    "signature.applicant_signature": "",
    # Section Z (not in FF, kept for legacy sheet)
    "changes": [],
}


# ── Test scenarios ─────────────────────────────────────────────────────────────

def test_spouse_with_work_income() -> tuple[bool, int | None]:
    """Spouse with work income -> spouse.has_income.yes at (73.5,188.5) + income_type.work at (41.0,188.0),
    spouse.has_income.none at (106.6,187.4) must be ABSENT. [NEW3 positions]"""
    data = {**BASE,
        "employee.marital_status.married": True,
        "employee.marital_status.single":  False,
        "spouse.last_name":        "לוי",
        "spouse.first_name":       "שרה",
        "spouse.id":               "444444444",
        "spouse.birth_date":       "1987-04-20",
        "spouse.has_income.none":  False,
        "spouse.has_income.yes":   True,
        "spouse.income_type.work": True,
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("spouse.has_income.yes mark @(73.5mm, 188.5mm)",  _found(m, 73.5, 188.5)),
        _check("spouse.income_type.work mark @(41.0mm, 188.0mm)", _found(m, 41.0, 188.0)),
        _check("spouse.has_income.none @(106.6mm, 187.4mm) ABSENT", _absent(m, 106.6, 187.4)),
    ])
    return ok, result.get("rowNum")


def test_employer_address() -> tuple[bool, int | None]:
    """Employer address field text appears in PDF at correct position.
    NEW3: field at left=55.65mm, top=43.33mm, width=53.55mm (right-aligned RTL).
    pdfplumber shows text right-aligned within box, so keyword appears at ~75-109mm x, top~43.3mm."""
    data = {**BASE, "employer.address": "רחוב הבדיקה 5 תל אביב"}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    ok = _check("employer_address text on page 1", _text_on_page(pdf_bytes, "הבדיקה", 1))

    # Position check: keyword must appear within the employer row (35-55mm top, 47-117mm left)
    pos_ok = False
    keyword = "הבדיקה"
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        p = pdf.pages[0]
        x0 = 47 * MM_TO_PT; y0 = 35 * MM_TO_PT
        x1 = 117 * MM_TO_PT; y1 = 55 * MM_TO_PT
        crop = p.crop((x0, y0, x1, y1))
        txt = crop.extract_text() or ""
        pos_ok = keyword in txt or keyword[::-1] in txt
    ok &= _check(f"employer_address position in field box (55.65-109.2mm, ~43mm top)", pos_ok)
    return ok, result.get("rowNum")


def test_tax_coordination() -> tuple[bool, int | None]:
    """has_tax_coordination=True -> tax_coordination.has_additional_income mark at P2 (134.1, 133.3). [NEW3]"""
    data = {**BASE, "tax_coordination.has_additional_income": True}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 2)
    ok = _check("tax_coordination.has_additional_income mark on page 2 @(134.1mm, 133.3mm)",
                _found(m, 134.1, 133.3))
    return ok, result.get("rowNum")


def test_has_other_income() -> tuple[bool, int | None]:
    """has_other_income=True -> income type marks present; income.other.none ABSENT. [NEW3]
    Tight tolerance (4mm) for absence: income.other.none at 118.9mm, monthly at 128.1mm (9.2mm apart)."""
    data = {**BASE,
        "income.other.none":           False,
        "income.other.monthly_salary": True,
        "income.other.pension":        True,
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("income.other.monthly_salary mark @(60.9mm, 128.1mm)",  _found(m, 60.9, 128.1)),
        _check("income.other.pension mark @(30.2mm, 131.2mm)",          _found(m, 30.2, 131.2)),
        _check("income.other.none @(60.9mm, 118.9mm) ABSENT (tol=4mm)",
               _absent(m, 60.9, 118.9, tol=4.0)),
    ])
    return ok, result.get("rowNum")


def test_relief_wants_and_has_other() -> tuple[bool, int | None]:
    """relief_wants + relief_has_other -> credit_request marks rendered. [NEW3]
    get_credits_here @(61.2, 140.2), get_credits_elsewhere @(60.9, 146.7)."""
    data = {**BASE,
        "income.credit_request.get_credits_here":      True,
        "income.credit_request.get_credits_elsewhere": True,
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    ok = all([
        _check("income.credit_request.get_credits_here @(61.2mm, 140.2mm)",
               _found(m, 61.2, 140.2)),
        _check("income.credit_request.get_credits_elsewhere @(60.9mm, 146.7mm)",
               _found(m, 60.9, 146.7)),
    ])
    return ok, result.get("rowNum")


def test_aliya_date() -> tuple[bool, int | None]:
    """aliya_date -> immigration date text appears on page 1. [NEW3]
    Note: Section Z (changes) is NOT in the NEW3 template mapping."""
    data = {**BASE, "employee.immigration_date": "2010-05-01"}
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    ok = _check("aliya_date (dmy: 01/05/2010) text on page 1",
                _text_on_page(pdf_bytes, "2010", 1))
    return ok, result.get("rowNum")


def test_passport_only_employee() -> tuple[bool, int | None]:
    """Passport-only employee (no id_number) -> employee.has_id.no at (80.9,76.1);
    employee.has_id.yes at (80.9,72.9) ABSENT. [NEW3 replaces non-resident test]"""
    data = {**BASE,
        "employee.id":        "",
        "employee.passport":  "A12345678",
        "employee.has_id.yes": False,
        "employee.has_id.no":  True,
    }
    result, pdf_bytes = _post_and_get_pdf(data)
    if pdf_bytes is None:
        return False, result.get("rowNum")

    m = _collect_marks_page(pdf_bytes, 1)
    # has_id.no actual PDF y ≈ 75.8mm (GAS renders ~0.3mm above CSS calc of 76.1mm).
    # Absent check uses tol=2.0mm so 75.8mm (2.9mm away) stays outside the window.
    ok = all([
        _check("employee.has_id.no mark @(80.9mm, 76.1mm)",              _found(m, 80.9, 76.1)),
        _check("employee.has_id.yes @(80.9mm, 72.9mm) ABSENT (tol=2mm)", _absent(m, 80.9, 72.9, tol=2.0)),
    ])
    return ok, result.get("rowNum")


# ── Runner ─────────────────────────────────────────────────────────────────────

TESTS = [
    test_spouse_with_work_income,
    test_employer_address,
    test_tax_coordination,
    test_has_other_income,
    test_relief_wants_and_has_other,
    test_aliya_date,
    test_passport_only_employee,
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
