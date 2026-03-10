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

# Anthropic API key — used by step_validate_pdf_endpoint() to test the GAS validatePdf action
# Set via environment variable to avoid committing secrets:  export ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Make.com Scenario B — called by GAS sendToMake() after PDF is created
# Paste the Custom Webhook URL from Make here to enable end-to-end verification
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/e3efecqlm7mnpm2gns0gfan7m7e7vdut"

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
    "סטטוס":                     "✅",              # col 39 — matches any success state (הושלם / אושר על ידי HR)
    "קישור PDF":                 "https",           # col 37 — just check not empty
}

# ── Expected PDF text fields: (name, page, left_mm, top_mm, expected_text) ──
# Positions based on NEW3 JSON mapping (2026-03-08). Canvas 800×1131px → A4 210×297mm.
# SX=0.2625 mm/px, SY=0.26259 mm/px. Verification searches a ±TOLERANCE_MM box.
EXPECTED_TEXT_FIELDS = [
    # ── Page 1 header ──────────────────────────────────────────────────────
    ("taxYear",         1,  57.0,  22.3, "2026"),          # meta.tax_year x=217,y=85
    # ── Section A — Employer ───────────────────────────────────────────────
    ("employer_name",   1, 109.7,  43.3, "חברת"),          # employer.name x=418,y=165
    # ── Section B — Employee row 1 ─────────────────────────────────────────
    ("last_name",       1,  83.0,  56.7, "טסט"),           # employee.last_name x=316,y=216
    ("first_name",      1,  56.2,  56.7, "אוטומציה"),      # employee.first_name x=214,y=216
    ("id_number_p1",    1, 115.8,  56.7, "123456789"),      # employee.id x=441,y=216
    ("birth_date",      1,  31.2,  56.7, "15/06/1985"),     # employee.birth_date x=119,y=216; dmy()→DD/MM/YYYY
    # ── Section B — Address row ────────────────────────────────────────────
    ("postal_code",     1,   9.7,  62.5, "61000"),          # employee.address.zip x=37,y=238
    # ── Section B — Contact row ────────────────────────────────────────────
    ("mobile_phone",    1,   8.1,  81.7, "0500000001"),     # employee.mobile x=31,y=311
    # email skipped — LTR ASCII in RTL PDF is not reliably extractable by pdfplumber
    # ── Page 2 header ──────────────────────────────────────────────────────
    ("id_number_p2",    2,  26.5,   3.9, "123456789"),      # employee.id (p2) x=101,y=15
]

# ── Expected PDF marks: (name, page, left_mm, top_mm) ───────────────────────
# Only marks present given TEST_DATA (gender=זכר, marital=רווק, has_id=yes,
# kibbutz=לא, hmo=מכבי, income monthly+pension, no other income, no spouse,
# relief_1+3, declaration confirmed).
# All positions from NEW3 JSON mapping.
EXPECTED_MARKS = [
    # Page 1 — Section B checkboxes
    ("gender_male",          1, 138.1,  73.2),  # employee.gender.male x=526,y=278
    ("marital_single",       1, 127.3,  72.7),  # employee.marital_status.single x=485,y=276
    ("has_id_yes",           1,  80.9,  72.9),  # employee.has_id.yes x=308,y=277
    ("kibbutz_no",           1,  70.1,  72.7),  # employee.kibbutz_member.no x=267,y=276
    ("hmo_yes",              1,  31.5,  75.8),  # employee.health_fund.member.yes x=120,y=288
    # Page 1 — Section D income types
    ("income_type_monthly",  1,  61.4,  93.4),  # income.main.monthly_salary x=234,y=355
    ("income_type_pension",  1,  61.7, 106.0),  # income.main.pension x=235,y=403
    # Page 1 — Section E no other income
    ("no_other_income",      1,  60.9, 118.9),  # income.other.none x=232,y=452
    # Page 1 — Section F no spouse (no has_spouse → none checkbox)
    ("no_spouse",            1, 106.6, 187.4),  # spouse.has_income.none x=406,y=713
    # Page 2 — Section H reliefs
    ("relief_1_resident",    2, 133.6,  10.2),  # credits.1_israeli_resident x=509,y=39
    ("relief_3_settlement",  2, 133.1,  24.6),  # credits.3_eligible_locality x=507,y=94
]

TOLERANCE_MM = 8.0   # ±mm around expected position
MM_TO_PT     = 2.8346  # 1 mm = 2.8346 pt at 72 DPI

# ── Comprehensive test data (all sections) — bindKey names (FF architecture) ─
TEST_DATA_FULL = {
    # Meta
    "meta.tax_year":              "2026",
    # Section A — Employer
    "employer.name":              "חברת בדיקות",
    "employer.deductions_file":   "500000001",
    "employer.phone":             "0500000002",
    "employment.start_date":      "2026-01-01",
    # Section B — Employee
    "employee.last_name":         "טסט",
    "employee.first_name":        "אוטומציה",
    "employee.id":                "123456789",
    "employee.birth_date":        "1985-06-15",
    "employee.mobile":            "0500000001",
    "employee.email":             "auto@test.com",
    "employee.address.street":    "רחוב הבדיקה 1",
    "employee.address.zip":       "61000",
    "employee.gender.male":       True,
    "employee.gender.female":     False,
    "employee.marital_status.married":   True,
    "employee.marital_status.single":    False,
    "employee.marital_status.divorced":  False,
    "employee.marital_status.widowed":   False,
    "employee.marital_status.separated": False,
    "employee.has_id.yes":        True,
    "employee.has_id.no":         False,
    "employee.kibbutz_member.no": True,
    "employee.health_fund.member.yes": True,
    "employee.health_fund.member.no":  False,
    "employee.health_fund.name":  "מכבי",
    # Section C — 2 children (array items keep their own sub-field names)
    "children": [
        {"name": "ילד א", "id": "222222222", "birth_date": "2018-03-10",
         "in_custody": True, "receives_allowance": True},
        {"name": "ילד ב", "id": "333333333", "birth_date": "2021-07-22",
         "in_custody": True, "receives_allowance": False},
    ],
    # Section D — Income types
    "income.main.monthly_salary": True,
    "income.main.pension":        True,
    "income.main.additional_job": False,
    "income.main.partial_salary": False,
    "income.main.daily_worker":   False,
    "income.main.scholarship":    False,
    # Section E — Other income
    "income.other.none":              True,
    "income.other.monthly_salary":    False,
    "income.other.pension":           False,
    "income.other.no_training_fund":  True,
    "income.other.no_pension":        True,
    "income.credit_request.get_credits_here":      False,
    "income.credit_request.get_credits_elsewhere": False,
    # Section F — Spouse
    "spouse.last_name":           "לוי",
    "spouse.first_name":          "שרה",
    "spouse.id":                  "444444444",
    "spouse.birth_date":          "1987-04-20",
    "spouse.has_income.none":     True,
    "spouse.has_income.yes":      False,
    "spouse.income_type.work":    False,
    "spouse.income_type.other":   False,
    # Section H — Credits / Reliefs
    "credits.1_israeli_resident":          True,
    "credits.3_eligible_locality":         True,
    "credits.5_spouse_no_income":          True,
    "credits.7_children_in_custody":       True,
    "credits.2a_disability_100_or_blind":  False,
    "credits.4_new_immigrant":             False,
    "credits.6_single_parent_family":      False,
    "credits.8_children_not_in_custody":   False,
    # Tax coordination
    "tax_coordination.no_income_until_start": False,
    "tax_coordination.has_additional_income": False,
    "tax_coordination.approval_attached":     False,
    # Declaration
    "signature.declaration": True,
    # Arrays
    "other_income": [],
    "changes":      [],
}

# ── Expected PDF text fields for comprehensive test ──────────────────────────
# Positions from NEW3 JSON mapping (2026-03-08).
# (name, page, left_mm, top_mm, expected_text)
EXPECTED_TEXT_FULL = [
    # Page 1 header
    ("taxYear",           1,  57.0,  22.3, "2026"),          # meta.tax_year
    # Section A — Employer
    ("employer_name",     1, 109.7,  43.3, "חברת"),          # employer.name
    ("employer_phone",    1,  33.9,  42.8, "0500000002"),    # employer.phone
    ("employer_tax_id",   1,  10.5,  43.1, "500000001"),     # employer.deductions_file
    # Section B — Employee
    ("last_name",         1,  83.0,  56.7, "טסט"),           # employee.last_name
    ("first_name",        1,  56.2,  56.7, "אוטומציה"),      # employee.first_name
    ("id_number_p1",      1, 115.8,  56.7, "123456789"),      # employee.id
    ("birth_date",        1,  31.2,  56.7, "15/06/1985"),     # employee.birth_date
    ("postal_code",       1,   9.7,  62.5, "61000"),          # employee.address.zip
    ("mobile_phone",      1,   8.1,  81.7, "0500000001"),     # employee.mobile
    # Section F — Spouse
    ("spouse_last_name",  1,  83.2, 182.5, "לוי"),           # spouse.last_name
    ("spouse_first_name", 1,  54.6, 182.0, "שרה"),           # spouse.first_name
    ("spouse_id",         1, 115.8, 182.8, "444444444"),      # spouse.id
    # Page 2 header
    ("id_number_p2",      2,  26.5,   3.9, "123456789"),      # employee.id (p2)
]

# ── Expected PDF marks for comprehensive test ────────────────────────────────
# Positions from NEW3 JSON mapping (2026-03-08).
# (name, page, left_mm, top_mm)
EXPECTED_MARKS_FULL = [
    # Page 1 — Section B checkboxes
    ("gender_male",               1, 138.1,  73.2),  # employee.gender.male
    ("marital_married",           1, 112.4,  72.7),  # employee.marital_status.married
    ("has_id_yes",                1,  80.9,  72.9),  # employee.has_id.yes
    ("kibbutz_no",                1,  70.1,  72.7),  # employee.kibbutz_member.no
    ("hmo_yes",                   1,  31.5,  75.8),  # employee.health_fund.member.yes
    # Page 1 — Section C children (row 0 custody + allowance, row 1 custody)
    ("child0_in_custody",         1, 139.1, 101.6),  # children[0].in_custody
    ("child0_receives_allowance", 1, 136.0, 101.3),  # children[0].receives_allowance
    ("child1_in_custody",         1, 138.9, 106.8),  # children[1].in_custody
    # Page 1 — Section D income types
    ("income_type_monthly",       1,  61.4,  93.4),  # income.main.monthly_salary
    ("income_type_pension",       1,  61.7, 106.0),  # income.main.pension
    # Page 1 — Section E other income flags
    ("no_other_income",           1,  60.9, 118.9),  # income.other.none
    ("no_study_fund_other",       1,  60.9, 153.3),  # income.other.no_training_fund
    ("no_pension_other",          1,  60.9, 162.5),  # income.other.no_pension
    # Page 1 — Section F spouse (has_spouse=True, spouse_has_income=לא → none)
    ("spouse_no_income",          1, 106.6, 187.4),  # spouse.has_income.none
    # Page 2 — Section H reliefs
    ("relief_1_resident",         2, 133.6,  10.2),  # credits.1_israeli_resident
    ("relief_3_settlement",       2, 133.1,  24.6),  # credits.3_eligible_locality
    ("relief_5_spouse",           2, 134.1,  41.7),  # credits.5_spouse_no_income
    ("relief_7_children_custody", 2, 133.9,  54.3),  # credits.7_children_in_custody
]
