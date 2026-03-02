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

# Make.com webhook URL (leave empty to skip Make verification in pipeline)
MAKE_WEBHOOK_URL = ""

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORM_LOCAL_PATH = "file:///" + PROJECT_DIR.replace("\\", "/") + "/index_v6.html"

# ── Test data (Hebrew) ───────────────────────────────────────────────────────
TEST_DATA = {
    "last_name":       "טסט",
    "first_name":      "אוטומציה",
    "id_number":       "123456789",
    "mobile_phone":    "0500000001",
    "email":           "automation@test.com",
    "employer_name":   "חברת בדיקות",
    "employer_tax_id": "500000001",
    "employer_phone":  "0500000002",
    "street":          "רחוב הבדיקה",
    "house_number":    "1",
    "city":            "תל אביב",
    "start_date":      "2026-01-01",
    "gender":          "זכר",
    "marital_status":  "רווק/ה",
    "israeli_resident":"כן",
    "kibbutz_member":  "לא",
    "health_fund":     "מכבי",
    # checkboxes
    "income_type_monthly":  True,
    "relief_1_resident":    True,
    "confirm_declaration":  True,
}

# ── Sheet column validation ──────────────────────────────────────────────────
# Maps Hebrew column header → expected value (substring match is enough)
# Schema v7: 41 columns in official Form 101 section order
EXPECTED_SHEET_COLS = {
    "שנת מס":                    "2026",          # col 2
    "שם המעסיק":                 "חברת בדיקות",  # col 3
    "שם משפחה":                  "טסט",           # col 8
    "שם פרטי":                   "אוטומציה",      # col 9
    "מספר זהות":                 "123456789",      # col 10
    "טלפון נייד":                "0500000001",     # col 16
    "תאריך תחילת עבודה":        "2026-01-01",     # col 7
    "סוג הכנסה ממעסיק":         "משכורת",         # col 25 (substring)
    "זכאויות - סיכום":           "תושב",           # col 33 (substring)
    "סטטוס":                     "✅ הושלם",       # col 39
    "קישור PDF":                 "https",          # col 37 — just check not empty
}

# ── Expected PDF text fields: (name, page, left_mm, top_mm, expected_text) ──
# Based on PDFTemplate_v6.html field positions.
# Verification searches a ±TOLERANCE_MM box around the anchor point.
EXPECTED_TEXT_FIELDS = [
    ("taxYear",        1, 106.0,  25.3, "2026"),
    # employer_name: right-aligned RTL — search from left edge of field
    ("employer_name",  1, 130.0,  57.8, "חברת"),      # widen search to left
    ("last_name",      1, 120.0,  78.8, "טסט"),        # widen search to left
    ("first_name",     1, 100.0,  78.8, "אוטומציה"),  # widen search to left
    ("id_number_p1",   1,  30.0,  78.8, "123456789"),  # widen to left
    ("id_number_p2",   2,  80.0,   7.2, "123456789"),
]

# ── Expected PDF marks: (name, page, left_mm, top_mm) ───────────────────────
# These are ✓ checkmarks that must appear near the given CSS coordinates.
# Only marks that should be checked given TEST_DATA above.
# Positions verified from actual pdfplumber extraction (rowNum=20, @16 deploy).
EXPECTED_MARKS = [
    # Page 1 — Section B radios (RTL positions from real PDF calibration)
    ("gender_male",         1, 187.1, 100.0),
    ("marital_single",      1, 173.3,  99.5),
    ("resident_yes",        1, 108.8, 100.3),
    ("kibbutz_no",          1,  96.2, 104.2),
    # Page 1 — Section D income type
    ("income_type_monthly", 1,  84.7, 127.5),
    # Page 1 — Section E no other income
    ("no_other_income",     1,  84.2, 161.7),
    # Page 1 — Section F no spouse
    ("no_spouse",           1, 145.3, 254.3),
    # Page 2 — Section H relief 1
    ("relief_1_resident",   2, 181.0,  15.6),
]

TOLERANCE_MM = 8.0   # ±mm around expected position
MM_TO_PT     = 2.8346  # 1 mm = 2.8346 pt at 72 DPI
