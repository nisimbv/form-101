"""
Central configuration for the Form 101 automation pipeline.
"""
import os

# ── Google Apps Script ───────────────────────────────────────────────────────
SCRIPT_ID = "16nxpGKMs0qiE4Aw-DaGajazlMGBVeBDx1sykc6Fjg8gnF0omTxF-4kCf"
PROD_DEPLOYMENT_ID = "AKfycbzw4Pq6XiaaO2U7ZGrIWySljXhpyQIbKAnTppSNRHIQFVsAQZ9ddQJnbMK8y7z0fXfs"
APPS_SCRIPT_URL = f"https://script.google.com/macros/s/{PROD_DEPLOYMENT_ID}/exec"
SPREADSHEET_ID = "1VFSgcmNagnsAjXPsSDOgR9fadkjrbacK3beXCw2VG9Q"
SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"

# Make.com Scenario B — called by GAS sendToMake() after PDF is created
# Paste the Custom Webhook URL from Make here to enable end-to-end verification
MAKE_WEBHOOK_URL = ""

# Make.com Scenario A — called by GAS notifyNewEmployee_() to invite a new employee
MAKE_INVITE_WEBHOOK_URL = ""

# Public URL of the HTML form (GitHub Pages)
FORM_PUBLIC_URL = "https://nisimbv.github.io/form-101/index_v6.html"

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORM_LOCAL_PATH = "file:///" + PROJECT_DIR.replace("\\", "/") + "/index_v6.html"

# ── Test data (Hebrew) ───────────────────────────────────────────────────────
TEST_DATA = {
    "last_name":       "טסט",
    "first_name":      "אוטומציה",
    "id_number":       "123456789",
    "birth_date":      "1985-06-15",
    "mobile_phone":    "0500000001",
    "email":           "automation@test.com",
    "employer_name":   "חברת בדיקות",
    "employer_tax_id": "500000001",
    "employer_phone":  "0500000002",
    "street":          "רחוב הבדיקה",
    "house_number":    "1",
    "city":            "תל אביב",
    "postal_code":     "61000",
    "start_date":      "2026-01-01",
    "gender":          "זכר",
    "marital_status":  "רווק/ה",
    "israeli_resident":"כן",
    "kibbutz_member":  "לא",
    "health_fund":     "מכבי",
    # checkboxes
    "income_type_monthly":  True,
    "income_type_pension":  True,
    "relief_1_resident":    True,
    "relief_3_settlement":  True,
    "confirm_declaration":  True,
}

# ── Sheet column validation ──────────────────────────────────────────────────
# Maps Hebrew column header → expected value (substring match is enough)
# Schema v7: 41 columns in official Form 101 section order
EXPECTED_SHEET_COLS = {
    "שנת מס":                    "2026",           # col 2
    "שם המעסיק":                 "חברת בדיקות",   # col 3
    "תאריך תחילת עבודה":        "2026-01-01",     # col 7
    "שם משפחה":                  "טסט",            # col 8
    "שם פרטי":                   "אוטומציה",       # col 9
    "מספר זהות":                 "123456789",       # col 10
    "תאריך לידה":                "1985-06-15",     # col 12
    "מיקוד":                     "61000",           # col 15
    "טלפון נייד":                "0500000001",      # col 16
    "סוג הכנסה ממעסיק":         "משכורת",          # col 25 (substring)
    "זכאויות - סיכום":           "תושב",            # col 33 (substring)
    "סטטוס":                     "✅ הושלם",        # col 39
    "קישור PDF":                 "https",           # col 37 — just check not empty
}

# ── Expected PDF text fields: (name, page, left_mm, top_mm, expected_text) ──
# Based on PDFTemplate_v6.html field positions.
# Verification searches a ±TOLERANCE_MM box around the anchor point.
EXPECTED_TEXT_FIELDS = [
    # ── Page 1 header ──────────────────────────────────────────────────────
    ("taxYear",         1, 106.0,  25.3, "2026"),
    # ── Section A — Employer ───────────────────────────────────────────────
    ("employer_name",   1, 130.0,  57.8, "חברת"),        # RTL, wide search
    # ── Section B — Employee row 1 ─────────────────────────────────────────
    ("last_name",       1, 120.0,  78.8, "טסט"),
    ("first_name",      1, 100.0,  78.8, "אוטומציה"),
    ("id_number_p1",    1,  30.0,  78.8, "123456789"),
    ("birth_date",      1,  58.6,  80.8, "15/06/1985"),   # dmy() → DD/MM/YYYY
    # ── Section B — Address row ────────────────────────────────────────────
    ("postal_code",     1,  10.0,  89.0, "61000"),
    # ── Section B — Contact row ────────────────────────────────────────────
    ("mobile_phone",    1,  52.6, 108.3, "0500000001"),
    # email skipped — LTR ASCII in RTL PDF is not reliably extractable by pdfplumber
    # ── Page 2 header ──────────────────────────────────────────────────────
    ("id_number_p2",    2,  80.0,   7.2, "123456789"),
]

# ── Expected PDF marks: (name, page, left_mm, top_mm) ───────────────────────
# Only marks that should be present given TEST_DATA above.
# Positions calibrated from real PDF extraction.
EXPECTED_MARKS = [
    # Page 1 — Section B radios
    ("gender_male",          1, 187.1, 100.0),
    ("marital_single",       1, 173.3,  99.5),
    ("resident_yes",         1, 108.8, 100.3),
    ("kibbutz_no",           1,  96.2, 104.2),
    # Page 1 — Section D income types
    ("income_type_monthly",  1,  84.7, 127.5),
    ("income_type_pension",  1,  84.7, 145.3),
    # Page 1 — Section E no other income
    ("no_other_income",      1,  84.2, 161.7),
    # Page 1 — Section F no spouse
    ("no_spouse",            1, 145.3, 254.3),
    # Page 2 — Section H reliefs
    ("relief_1_resident",    2, 181.0,  15.6),
    ("relief_3_settlement",  2, 181.0,  35.3),
]

TOLERANCE_MM = 8.0   # ±mm around expected position
MM_TO_PT     = 2.8346  # 1 mm = 2.8346 pt at 72 DPI
