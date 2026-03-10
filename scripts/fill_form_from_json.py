"""
fill_form_from_json.py
======================
ממלא את PDF טופס 101 ישירות לפי JSON מיפוי מ-NEW 3.

שיטת קואורדינטות:
  - x, y, w, h ב-JSON הם ב-PDF points (595×841)
  - y_for_reportlab = pdf_height - json_y - json_h  (PDF origin = תחתית שמאל)
  - אין צורך ב-scaling

פלט: NEW 3/filled_form_test.pdf

Run:
  python scripts/fill_form_from_json.py
"""

import json, io, os, sys
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'NEW 3', 'form_101_mapping_1772880459281.json')
BG_PDF    = os.path.join(ROOT, 'NEW 3', '101LAST.pdf')
OUT_PDF   = os.path.join(ROOT, 'NEW 3', 'filled_form_test.pdf')

# ---------------------------------------------------------------------------
# Register Hebrew font (Arial from Windows)
# ---------------------------------------------------------------------------
FONT_NAME = 'ArialHeb'
FONT_PATH = r'C:\Windows\Fonts\arial.ttf'
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
else:
    FONT_NAME = 'Helvetica'  # fallback — no RTL support but positions are correct

# ---------------------------------------------------------------------------
# Test data — values per bindKey
# ---------------------------------------------------------------------------
# dmy helper
def dmy(v):
    if not v:
        return ''
    import re
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', v)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return v

VALUES = {
    # Meta
    'meta.tax_year':                    '2026',

    # Section A — Employer
    'employer.name':                    'חברת דוגמה בע"מ',
    'employer.deductions_file':         '512345678',
    'employer.address':                 'רחוב הרצל 10, תל אביב',
    'employer.phone':                   '03-1234567',

    # Section B — Employee
    'employee.id':                      '123456789',
    'employee.last_name':               'ישראלי',
    'employee.first_name':              'ישראל',
    'employee.birth_date':              dmy('1985-05-15'),
    'employee.immigration_date':        '',
    'employee.passport':                '',
    'employee.address.house_no':         '',   # combined into street
    'employee.address.street':          'רחוב בן גוריון 5 חיפה',
    'employee.address.city':            '',   # combined into street
    'employee.address.zip':             '3308001',
    'employee.phone':                   '',
    'employee.mobile':                  '050-1234567',
    'employee.email':                   'israel@example.com',

    # Gender checkboxes
    'employee.gender.male':             True,
    'employee.gender.female':           False,

    # Marital status
    'employee.marital_status.married':  True,
    'employee.marital_status.single':   False,
    'employee.marital_status.divorced': False,
    'employee.marital_status.widowed':  False,
    'employee.marital_status.separated':False,

    # Resident / Kibbutz / Health
    'employee.has_id.yes':              True,
    'employee.has_id.no':               False,
    'employee.kibbutz_member.no':               True,
    'employee.kibbutz_member.income_transferred':   False,
    'employee.kibbutz_member.income_not_transferred': False,
    'employee.health_fund.member.yes':  True,
    'employee.health_fund.member.no':   False,
    'employee.health_fund.name':        'מכבי',

    # Section C — Children
    'children[0].name':               'דנה ישראלי',
    'children[0].id':                 '234567890',
    'children[0].birth_date':         dmy('2015-03-10'),
    'children[0].in_custody':         True,
    'children[0].receives_allowance': True,

    'children[1].name':               'אדם ישראלי',
    'children[1].id':                 '345678901',
    'children[1].birth_date':         dmy('2018-07-22'),
    'children[1].in_custody':         True,
    'children[1].receives_allowance': True,

    'children[2].name':               '',
    'children[2].id':                 '',
    'children[2].birth_date':         '',
    'children[2].in_custody':         False,
    'children[2].receives_allowance': False,

    'children[3].name':               '',
    'children[3].id':                 '',
    'children[3].birth_date':         '',
    'children[3].in_custody':         False,
    'children[3].receives_allowance': False,

    # Section D — Income type
    'income.main.monthly_salary':   True,
    'income.main.additional_job':   False,
    'income.main.partial_salary':   False,
    'income.main.daily_worker':     False,
    'income.main.pension':          False,
    'income.main.scholarship':      False,
    'employment.start_date':        dmy('2026-01-01'),

    # Section E — Other income
    'income.other.none':              True,
    'income.other.monthly_salary':    False,
    'income.other.additional_job':    False,
    'income.other.partial_salary':    False,
    'income.other.daily_worker':      False,
    'income.other.pension':           False,
    'income.other.scholarship':       False,
    'income.other.no_training_fund':  False,
    'income.other.no_pension':        False,
    'income.credit_request.get_credits_here':      True,
    'income.credit_request.get_credits_elsewhere': False,

    # Section F — Spouse
    'spouse.last_name':        'ישראלי',
    'spouse.first_name':       'שרה',
    'spouse.id':               '987654321',
    'spouse.passport':         '',
    'spouse.birth_date':       dmy('1987-08-20'),
    'spouse.immigration_date': '',
    'spouse.has_income.none':  False,
    'spouse.has_income.yes':   True,
    'spouse.income_type.work': True,
    'spouse.income_type.other':False,

    # Section H — Credits (page 2)
    'credits.1_israeli_resident':                    True,
    'credits.2a_disability_100_or_blind':            False,
    'credits.2b_monthly_benefit':                    False,
    'credits.3_eligible_locality':                   False,
    'credits.3_from_date':                           '',
    'credits.3_locality_name':                       '',
    'credits.4_new_immigrant':                       False,
    'credits.4_from_date':                           '',
    'credits.4_no_income_until':                     '',
    'credits.5_spouse_no_income':                    True,
    'credits.6_single_parent_family':                False,
    'credits.7_children_in_custody':                 True,
    'credits.7_children_born_in_year':               '1',
    'credits.7_children_count_6_17':                 '1',
    'credits.7_children_count_18':                   '0',
    'credits.7_children_count_1_5':                  '1',
    'credits.8_children_not_in_custody':             False,
    'credits.8_children_count_1_5':                  '',
    'credits.8_children_count_6_17':                 '',
    'credits.9_single_parent':                       False,
    'credits.10_children_not_in_custody_maintenance':False,
    'credits.11_disabled_child':                     False,
    'credits.12_spousal_support':                    False,
    'credits.13_age_16_18':                          False,
    'credits.14_released_soldier_or_service':        False,
    'credits.14_service_start':                      '',
    'credits.14_service_end':                        '',
    'credits.15_graduation':                         False,
    'credits.16_reserve_combat':                     False,
    'credits.16_reserve_days_prev_year':             '',

    # Section T — Tax coordination
    'tax_coordination.no_income_until_start':  False,
    'tax_coordination.has_additional_income':  False,
    'tax_coordination.approval_attached':      False,

    # Additional income table
    'other_income[0].type':           '',
    'other_income[0].payer_name':     '',
    'other_income[0].address':        '',
    'other_income[0].deductions_file':'',
    'other_income[0].monthly_amount': '',
    'other_income[0].tax_withheld':   '',

    'other_income[1].type':           '',
    'other_income[1].payer_name':     '',
    'other_income[1].address':        '',
    'other_income[1].deductions_file':'',
    'other_income[1].monthly_amount': '',
    'other_income[1].tax_withheld':   '',

    # Declaration
    'signature.date':        dmy('2026-03-08'),
    'signature.declaration': True,
    'signature.applicant_signature': False,  # no sig image in this test
}

# ---------------------------------------------------------------------------
# Build overlay canvases
# ---------------------------------------------------------------------------
with open(JSON_PATH, encoding='utf-8') as f:
    mapping = json.load(f)

# page_dimensions keys are '1' (page index 0) and '2' (page index 1)
PH = {
    0: mapping['page_dimensions']['1']['height'],
    1: mapping['page_dimensions']['2']['height'],
}
PW = {
    0: mapping['page_dimensions']['1']['width'],
    1: mapping['page_dimensions']['2']['width'],
}

packets  = {0: io.BytesIO(), 1: io.BytesIO()}
canvases = {
    0: canvas.Canvas(packets[0], pagesize=(PW[0], PH[0])),
    1: canvas.Canvas(packets[1], pagesize=(PW[1], PH[1])),
}

for field in mapping['fields']:
    page = field['page']
    can  = canvases[page]

    bk = field.get('bindKey', '')
    val = VALUES.get(bk)
    if val is None:
        print(f"  SKIP (no value): {bk}")
        continue

    x = field['x']
    y_json = field['y']
    w = field['w']
    h = field['h']
    pdf_height = PH[page]

    # Convert from top-origin (JSON) → bottom-origin (reportlab)
    y = pdf_height - y_json - h

    ftype = field.get('type', 'text')

    if ftype == 'checkbox':
        if val:
            # Center ✓ in the checkbox cell
            can.setFillColorRGB(0.122, 0.373, 0.878)  # #1f5fe0
            font_size = field.get('fontSize', 10)
            can.setFont(FONT_NAME, font_size)
            can.drawString(x + w / 2 - 2, y + h / 2 - 3, '✓')
    else:
        # text or date
        text = str(val) if val else ''
        if text:
            text = get_display(text)  # הפוך לעברית RTL
        if not text:
            continue
        font_size = field.get('fontSize', 9)
        can.setFont(FONT_NAME, font_size)
        can.setFillColorRGB(0, 0, 0)
        y_text = y + (h - font_size) / 2 + 2
        align = field.get('align', 'right')
        if align == 'center':
            can.drawCentredString(x + w / 2, y_text, text)
        else:
            # right-aligned (RTL fields)
            can.drawRightString(x + w - 3, y_text, text)

# Save canvases
for pg in (0, 1):
    canvases[pg].save()
    packets[pg].seek(0)

# ---------------------------------------------------------------------------
# Merge overlays onto background PDF
# ---------------------------------------------------------------------------
reader  = PdfReader(BG_PDF)
writer  = PdfWriter()

for pg_idx in range(2):
    bg_page = reader.pages[pg_idx]
    overlay = PdfReader(packets[pg_idx]).pages[0]
    bg_page.merge_page(overlay)
    writer.add_page(bg_page)

with open(OUT_PDF, 'wb') as f:
    writer.write(f)

print(f"Written: {OUT_PDF}")
