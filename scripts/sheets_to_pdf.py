"""
sheets_to_pdf.py
================
קורא שורה מ-Sheets (JSON), ממיר לערכי PDF, וממלא טופס 101.

מצבים:
  Mode A (מועדף): השורה מכילה 'full_json' (עמודה 41) — כל השדות נקראים ישירות.
  Mode B (fallback): רק עמודות Sheets → sheets_mapping.json + פיענוח summaries.

שימוש:
  python scripts/sheets_to_pdf.py --data test_data/sample_row.json
  python scripts/sheets_to_pdf.py --data test_data/sample_row.json --out my_output.pdf
"""

import argparse, json, io, os, re, sys
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PyPDF2 import PdfReader, PdfWriter

ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_GLOB    = os.path.join(ROOT, 'NEW 3', 'form_101_mapping_1772880459281.json')
SHEETS_MAP   = os.path.join(ROOT, 'config', 'sheets_mapping.json')
BG_PDF       = os.path.join(ROOT, 'NEW 3', '101LAST.pdf')
DEFAULT_OUT  = os.path.join(ROOT, 'NEW 3', 'sheets_output.pdf')

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT_NAME = 'ArialHeb'
FONT_PATH = r'C:\Windows\Fonts\arial.ttf'
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
else:
    FONT_NAME = 'Helvetica'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def dmy(v):
    if not v: return ''
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', str(v))
    if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return str(v)

def yes(v):
    return v in (True, 'true', 'כן', 'on', '1', 1)

def s(v):
    return '' if v is None else str(v)

# ---------------------------------------------------------------------------
# Summary parsers (Mode B fallback)
# ---------------------------------------------------------------------------

# Maps text fragment from buildReliefsSummary → data key
RELIEF_MARKER_TO_KEY = {
    '1. תושב':          'relief_1_resident',
    '2. נכות':          'relief_2_disabled',
    '2.1':              'relief_2_1_allowance',
    '3. יישוב':         'relief_3_settlement',
    '4. עולה':          'relief_4_new_immigrant',
    '5. בן/בת זוג':     'relief_5_spouse',
    '6. הורה יחיד':     'relief_6_single_parent',
    '7. ילדים בחזקתי':  'relief_7_children_custody',
    '8. ילדים':         'relief_8_children_general',
    '9. הורה עצמאי':    'relief_9_sole_parent',
    '10. ילדים לא':     'relief_10_children_not_custody',
    '11. ילד נכה':      'relief_11_disabled_children',
    '12. מזונות':       'relief_12_alimony',
    '13. ילדים בגיל':   'relief_13_age_16_18',
    '14. חייל':         'relief_14_discharged_soldier',
    '15. השכלה':        'relief_15_academic',
    '16. שירות מילואים':'relief_16_reserve',
    '17. אין הכנסה':    'relief_17_no_income',
}

INCOME_TYPE_MARKER = {
    'משכורת חודשית':   'income_type_monthly',
    'משרה נוספת':      'income_type_additional',
    'חלקית':           'income_type_partial',
    'יומי':            'income_type_daily',
    'קצבה':            'income_type_pension',
    'מלגה':            'income_type_scholarship',
}

def parse_summary_reliefs(text: str) -> dict:
    """'בקשות להקלות מס: 1. תושב/ת ישראל · 5. ...' → {relief_1_resident: True, ...}"""
    result = {}
    if not text:
        return result
    for marker, key in RELIEF_MARKER_TO_KEY.items():
        result[key] = marker in text
    return result

def parse_summary_income_types(text: str) -> dict:
    """'משכורת חודשית' → {income_type_monthly: True, ...}"""
    result = {k: False for k in INCOME_TYPE_MARKER.values()}
    if not text:
        return result
    for marker, key in INCOME_TYPE_MARKER.items():
        if marker in text:
            result[key] = True
    return result

def parse_summary_spouse(text: str, has_spouse: bool) -> dict:
    """'בן/בת זוג: ישראלי שרה · ת"ז/דרכון: 987654321 · ...' → individual fields"""
    if not has_spouse or not text:
        return {}
    result = {'has_spouse': True}
    # שם
    m = re.search(r'בן/בת זוג:\s*([^ ·][^·]+?)(?:\s*·|$)', text)
    if m:
        parts = m.group(1).strip().split()
        if len(parts) >= 2:
            result['spouse_last_name']  = parts[0]
            result['spouse_first_name'] = ' '.join(parts[1:])
        elif len(parts) == 1:
            result['spouse_last_name'] = parts[0]
    # ת"ז/דרכון
    m = re.search(r'ת[""״]ז/דרכון:\s*(\S+)', text)
    if m:
        val = m.group(1).rstrip('·').strip()
        if val.isdigit() and len(val) == 9:
            result['spouse_id_number'] = val
        else:
            result['spouse_passport_number'] = val
    # ת. לידה
    m = re.search(r'ת\. לידה:\s*(\S+)', text)
    if m:
        result['spouse_birth_date'] = m.group(1).rstrip('·').strip()
    # הכנסה
    result['spouse_has_income'] = 'עבודה' if 'יש לבן/בת הזוג הכנסה: כן' in text else 'לא'
    return result

# ---------------------------------------------------------------------------
# Mode A: build VALUES directly from full GAS payload
# ---------------------------------------------------------------------------
def payload_to_values(d: dict) -> dict:
    """Maps the full GAS normalized payload → {bindKey: value} for reportlab."""

    def child(i):
        arr = d.get('children') or []
        return arr[i] if i < len(arr) else {}

    def inc(i):
        arr = d.get('additional_incomes') or []
        return arr[i] if i < len(arr) else {}

    relief_dates = d.get('relief_dates') or {}

    v = {
        # Meta
        'meta.tax_year':                    s(d.get('taxYear')),

        # Section A
        'employer.name':                    s(d.get('employer_name')),
        'employer.deductions_file':         s(d.get('employer_tax_id')),
        'employer.address':                 s(d.get('employer_address')),
        'employer.phone':                   s(d.get('employer_phone')),

        # Section B
        'employee.id':                      s(d.get('id_number')),
        'employee.last_name':               s(d.get('last_name')),
        'employee.first_name':              s(d.get('first_name')),
        'employee.birth_date':              dmy(d.get('birth_date')),
        'employee.immigration_date':        dmy(d.get('aliya_date')),
        'employee.passport':                s(d.get('passport_number')),
        'employee.address.street':          s(d.get('address')),
        'employee.address.zip':             s(d.get('postal_code')),
        'employee.mobile':                  s(d.get('mobile_phone')),
        'employee.email':                   s(d.get('email')),

        'employee.gender.male':             d.get('gender') == 'זכר',
        'employee.gender.female':           d.get('gender') == 'נקבה',

        'employee.marital_status.married':  d.get('marital_status') in ('נשוי', 'נשואה'),
        'employee.marital_status.single':   d.get('marital_status') in ('רווק', 'רווקה'),
        'employee.marital_status.divorced': d.get('marital_status') in ('גרוש', 'גרושה'),
        'employee.marital_status.widowed':  d.get('marital_status') in ('אלמן', 'אלמנה'),
        'employee.marital_status.separated':d.get('marital_status') in ('פרוד', 'פרודה'),

        'employee.has_id.yes':              yes(d.get('israeli_resident')),
        'employee.has_id.no':               not yes(d.get('israeli_resident')),

        'employee.kibbutz_member.no':                       not yes(d.get('kibbutz_member')),
        'employee.kibbutz_member.income_transferred':       yes(d.get('kibbutz_member')) and d.get('kibbutz_member') not in ('8', 'אינן מועברות'),
        'employee.kibbutz_member.income_not_transferred':   d.get('kibbutz_member') in ('8', 'אינן מועברות'),

        'employee.health_fund.member.yes':  bool(d.get('health_fund')),
        'employee.health_fund.member.no':   not bool(d.get('health_fund')),
        'employee.health_fund.name':        s(d.get('health_fund')),

        # Section C
        'children[0].name':               s(child(0).get('name')),
        'children[0].id':                 s(child(0).get('id')),
        'children[0].birth_date':         dmy(child(0).get('birth_date')),
        'children[0].in_custody':         yes(child(0).get('in_custody')),
        'children[0].receives_allowance': yes(child(0).get('receives_allowance')),

        'children[1].name':               s(child(1).get('name')),
        'children[1].id':                 s(child(1).get('id')),
        'children[1].birth_date':         dmy(child(1).get('birth_date')),
        'children[1].in_custody':         yes(child(1).get('in_custody')),
        'children[1].receives_allowance': yes(child(1).get('receives_allowance')),

        'children[2].name':               s(child(2).get('name')),
        'children[2].id':                 s(child(2).get('id')),
        'children[2].birth_date':         dmy(child(2).get('birth_date')),
        'children[2].in_custody':         yes(child(2).get('in_custody')),
        'children[2].receives_allowance': yes(child(2).get('receives_allowance')),

        'children[3].name':               s(child(3).get('name')),
        'children[3].id':                 s(child(3).get('id')),
        'children[3].birth_date':         dmy(child(3).get('birth_date')),
        'children[3].in_custody':         yes(child(3).get('in_custody')),
        'children[3].receives_allowance': yes(child(3).get('receives_allowance')),

        # Section D
        'income.main.monthly_salary':   yes(d.get('income_type_monthly')),
        'income.main.additional_job':   yes(d.get('income_type_additional')),
        'income.main.partial_salary':   yes(d.get('income_type_partial')),
        'income.main.daily_worker':     yes(d.get('income_type_daily')),
        'income.main.pension':          yes(d.get('income_type_pension')),
        'income.main.scholarship':      yes(d.get('income_type_scholarship')),
        'employment.start_date':        dmy(d.get('start_date')),

        # Section E
        'income.other.none':              not d.get('has_other_income'),
        'income.other.monthly_salary':    yes(d.get('other_income_monthly')),
        'income.other.additional_job':    yes(d.get('other_income_additional')),
        'income.other.partial_salary':    yes(d.get('other_income_partial')),
        'income.other.daily_worker':      yes(d.get('other_income_daily')),
        'income.other.pension':           yes(d.get('other_income_pension')),
        'income.other.scholarship':       yes(d.get('other_income_scholarship')),
        'income.other.no_training_fund':  yes(d.get('no_study_fund_other')),
        'income.other.no_pension':        yes(d.get('no_pension_other')),
        'income.credit_request.get_credits_here':      yes(d.get('relief_wants')),
        'income.credit_request.get_credits_elsewhere': yes(d.get('relief_has_other')),

        # Section F
        'spouse.last_name':        s(d.get('spouse_last_name')),
        'spouse.first_name':       s(d.get('spouse_first_name')),
        'spouse.id':               s(d.get('spouse_id_number')),
        'spouse.passport':         s(d.get('spouse_passport_number')),
        'spouse.birth_date':       dmy(d.get('spouse_birth_date')),
        'spouse.immigration_date': dmy(d.get('spouse_aliya_date')),
        'spouse.has_income.none':  not d.get('has_spouse') or d.get('spouse_has_income') == 'לא',
        'spouse.has_income.yes':   bool(d.get('has_spouse')) and d.get('spouse_has_income') != 'לא',
        'spouse.income_type.work': d.get('spouse_has_income') == 'עבודה',
        'spouse.income_type.other':d.get('spouse_has_income') == 'אחר',

        # Section H
        'credits.1_israeli_resident':                    yes(d.get('relief_1_resident')),
        'credits.2a_disability_100_or_blind':            yes(d.get('relief_2_disabled')),
        'credits.2b_monthly_benefit':                    yes(d.get('relief_2_1_allowance')),
        'credits.3_eligible_locality':                   yes(d.get('relief_3_settlement')),
        'credits.3_from_date':                           dmy(d.get('relief_3_date') or relief_dates.get('relief_3_date')),
        'credits.3_locality_name':                       s(d.get('relief_3_settlement_name') or d.get('relief_3_locality') or ''),
        'credits.4_new_immigrant':                       yes(d.get('relief_4_new_immigrant')),
        'credits.4_from_date':                           dmy(d.get('aliya_date')),
        'credits.4_no_income_until':                     dmy(d.get('relief_4_no_income_until') or relief_dates.get('relief_4_no_income_until')),
        'credits.5_spouse_no_income':                    yes(d.get('relief_5_spouse')),
        'credits.6_single_parent_family':                yes(d.get('relief_6_single_parent')),
        'credits.7_children_in_custody':                 yes(d.get('relief_7_children_custody')),
        'credits.7_children_born_in_year':               s(d.get('relief_7_born') or ''),
        'credits.7_children_count_6_17':                 s(d.get('relief_7_count_6_17') or ''),
        'credits.7_children_count_18':                   s(d.get('relief_7_count_18') or ''),
        'credits.7_children_count_1_5':                  s(d.get('relief_7_count_1_5') or ''),
        'credits.8_children_not_in_custody':             yes(d.get('relief_8_children_general')),
        'credits.8_children_count_1_5':                  s(d.get('relief_8_count_1_5') or ''),
        'credits.8_children_count_6_17':                 s(d.get('relief_8_count_6_17') or ''),
        'credits.9_single_parent':                       yes(d.get('relief_9_sole_parent')),
        'credits.10_children_not_in_custody_maintenance':yes(d.get('relief_10_children_not_custody')),
        'credits.11_disabled_child':                     yes(d.get('relief_11_disabled_children')),
        'credits.12_spousal_support':                    yes(d.get('relief_12_alimony')),
        'credits.13_age_16_18':                          yes(d.get('relief_13_age_16_18')),
        'credits.14_released_soldier_or_service':        yes(d.get('relief_14_discharged_soldier')),
        'credits.14_service_start':                      dmy(d.get('relief_14_start') or relief_dates.get('relief_14_start')),
        'credits.14_service_end':                        dmy(d.get('relief_14_end')   or relief_dates.get('relief_14_end')),
        'credits.15_graduation':                         yes(d.get('relief_15_academic')),
        'credits.16_reserve_combat':                     yes(d.get('relief_16_reserve')),
        'credits.16_reserve_days_prev_year':             s(d.get('relief_16_days') or relief_dates.get('relief_16_days') or ''),

        # Section T
        'tax_coordination.no_income_until_start':  yes(d.get('t1_no_prior_income')),
        'tax_coordination.has_additional_income':  bool(d.get('has_tax_coordination')),
        'tax_coordination.approval_attached':      yes(d.get('tax_coordination_approved')),

        # Additional incomes table
        'other_income[0].type':            s(inc(0).get('type')),
        'other_income[0].payer_name':      s(inc(0).get('employer')),
        'other_income[0].address':         s(inc(0).get('address')),
        'other_income[0].deductions_file': s(inc(0).get('tax_id')),
        'other_income[0].monthly_amount':  s(inc(0).get('amount')),
        'other_income[0].tax_withheld':    s(inc(0).get('tax')),

        'other_income[1].type':            s(inc(1).get('type')),
        'other_income[1].payer_name':      s(inc(1).get('employer')),
        'other_income[1].address':         s(inc(1).get('address')),
        'other_income[1].deductions_file': s(inc(1).get('tax_id')),
        'other_income[1].monthly_amount':  s(inc(1).get('amount')),
        'other_income[1].tax_withheld':    s(inc(1).get('tax')),

        # Declaration
        'signature.date':        dmy(d.get('declaration_date')),
        'signature.declaration': yes(d.get('confirm_declaration')),
        'signature.applicant_signature': False,
    }
    return v

# ---------------------------------------------------------------------------
# Mode B: build VALUES from Sheets columns via sheets_mapping.json
# ---------------------------------------------------------------------------
def sheets_row_to_values(row: dict, mapping: dict) -> dict:
    """Converts a Sheets row dict to VALUES using sheets_mapping.json."""
    values = {}

    # Parse JSON sub-fields first
    children_raw = row.get('children_json', '[]')
    children = children_raw if isinstance(children_raw, list) else json.loads(children_raw or '[]')

    incomes_raw = row.get('additional_incomes_json', '[]')
    incomes = incomes_raw if isinstance(incomes_raw, list) else json.loads(incomes_raw or '[]')

    # Parse summaries for fields not in sheets_mapping
    relief_fields   = parse_summary_reliefs(row.get('summary_reliefs', ''))
    income_flags    = parse_summary_income_types(row.get('summary_income_types', ''))
    has_spouse_bool = row.get('has_spouse') == 'כן'
    spouse_fields   = parse_summary_spouse(row.get('summary_spouse', ''), has_spouse_bool)

    # Merge parsed data into row for consistent handling
    merged = dict(row)
    merged.update(relief_fields)
    merged.update(income_flags)
    merged.update(spouse_fields)
    merged['children']           = children
    merged['additional_incomes'] = incomes

    # Now apply sheets_mapping
    for col_key, map_entry in mapping.items():
        if col_key.startswith('_') or col_key not in merged:
            continue
        col_val = merged[col_key]

        if isinstance(map_entry, str):
            values[map_entry] = col_val

        elif isinstance(map_entry, dict):
            t = map_entry.get('type')

            if t == 'enum':
                matched = map_entry['values'].get(str(col_val))
                # Set matched=True, all others=False
                for enum_bk in map_entry['values'].values():
                    if enum_bk:
                        values[enum_bk] = (enum_bk == matched)

            elif t == 'boolean_yesno':
                values[map_entry['bindKey']] = (col_val == 'כן')

            elif t == 'derived':
                # health_fund special case
                if col_key == 'health_fund':
                    values[map_entry['bindKeys']['name']]       = s(col_val)
                    values[map_entry['bindKeys']['member_yes']] = bool(col_val)
                    values[map_entry['bindKeys']['member_no']]  = not bool(col_val)

            elif t == 'json_array':
                prefix    = map_entry['prefix']
                fields_map = map_entry['fields']   # sheets_field → bk_suffix
                items = col_val if isinstance(col_val, list) else []
                for i, item in enumerate(items):
                    for sheets_field, bk_suffix in fields_map.items():
                        values[f"{prefix}[{i}].{bk_suffix}"] = item.get(sheets_field, '')

    # Inject parsed relief + income flags into values via payload_to_values
    values.update(payload_to_values(merged))

    return values

# ---------------------------------------------------------------------------
# PDF fill (same engine as fill_form_from_json.py)
# ---------------------------------------------------------------------------
def fill_pdf(values: dict, form_mapping: dict, output_path: str):
    PH = {
        0: form_mapping['page_dimensions']['1']['height'],
        1: form_mapping['page_dimensions']['2']['height'],
    }
    PW = {
        0: form_mapping['page_dimensions']['1']['width'],
        1: form_mapping['page_dimensions']['2']['width'],
    }

    packets  = {0: io.BytesIO(), 1: io.BytesIO()}
    canvases = {
        0: canvas.Canvas(packets[0], pagesize=(PW[0], PH[0])),
        1: canvas.Canvas(packets[1], pagesize=(PW[1], PH[1])),
    }

    drawn = 0
    for field in form_mapping['fields']:
        page = field['page']
        can  = canvases[page]
        bk   = field.get('bindKey', '')
        val  = values.get(bk)
        if val is None:
            continue

        x      = field['x']
        y_json = field['y']
        w      = field['w']
        h      = field['h']
        y      = PH[page] - y_json - h          # top-origin → bottom-origin
        ftype  = field.get('type', 'text')

        if ftype == 'checkbox':
            if val:
                can.setFillColorRGB(0.122, 0.373, 0.878)
                font_size = field.get('fontSize', 10)
                can.setFont(FONT_NAME, font_size)
                can.drawString(x + w / 2 - 2, y + h / 2 - 3, '✓')
                drawn += 1
        else:
            text = str(val) if val else ''
            if text:
                text = get_display(text)
            if not text:
                continue
            font_size = field.get('fontSize', 9)
            can.setFont(FONT_NAME, font_size)
            can.setFillColorRGB(0, 0, 0)
            y_text = y + (h - font_size) / 2 + 2
            align  = field.get('align', 'right')
            if align == 'center':
                can.drawCentredString(x + w / 2, y_text, text)
            else:
                can.drawRightString(x + w - 3, y_text, text)
            drawn += 1

    for pg in (0, 1):
        canvases[pg].save()
        packets[pg].seek(0)

    reader = PdfReader(BG_PDF)
    writer = PdfWriter()
    for pg_idx in range(2):
        bg_page = reader.pages[pg_idx]
        bg_page.merge_page(PdfReader(packets[pg_idx]).pages[0])
        writer.add_page(bg_page)

    with open(output_path, 'wb') as f:
        writer.write(f)

    return drawn

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Sheets row JSON → filled PDF')
    parser.add_argument('--data', required=True, help='נתיב ל-JSON של שורת Sheets')
    parser.add_argument('--out',  default=DEFAULT_OUT, help='נתיב פלט PDF')
    args = parser.parse_args()

    # Load input
    with open(args.data, encoding='utf-8') as f:
        row = json.load(f)

    # Load mappings
    with open(JSON_GLOB, encoding='utf-8') as f:
        form_mapping = json.load(f)
    with open(SHEETS_MAP, encoding='utf-8') as f:
        sheets_mapping = json.load(f)

    # Choose mode
    full_json_raw = row.get('full_json')
    if full_json_raw:
        mode   = 'A'
        payload = full_json_raw if isinstance(full_json_raw, dict) else json.loads(full_json_raw)
        values  = payload_to_values(payload)
        print("📋 Mode A — משתמש ב-full_json (עמודה 41)")
    else:
        mode   = 'B'
        values  = sheets_row_to_values(row, sheets_mapping)
        print("📋 Mode B — פיענוח מעמודות Sheets + summaries")

    # Fill
    drawn = fill_pdf(values, form_mapping, args.out)

    print(f"✅ {drawn} שדות מולאו")
    print(f"📄 PDF נשמר: {args.out}")


if __name__ == '__main__':
    main()
