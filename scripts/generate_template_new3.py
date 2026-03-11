"""
generate_template_new3.py
=========================
Generates PDFTemplate_v6.html from:
  - NEW 3/form_101_mapping_1772880459281.json  (authoritative field mapping)
  - NEW 3/101LAST.pdf                          (background image source)

Coordinate system:
  JSON x,y,w,h are in PDF POINTS (72 DPI), same coordinate system used by
  reportlab/PyPDF2. Convert to CSS mm: 1 pt = 25.4/72 mm = 0.352778 mm
  SX = SY = 25.4/72 = 0.352778 mm/pt

Run:
  python scripts/generate_template_new3.py
"""

import json, base64, os, sys

SX = 25.4 / 72    # mm per PDF point (x) — JSON coords are PDF points
SY = 25.4 / 72    # mm per PDF point (y)

MARK_PT = 10        # font-size (pt) for checkmark ✓ — fits 3.94mm checkbox

# ---------------------------------------------------------------------------
# Per-field font-size overrides (pt) for fields whose JSON fontSize causes
# text overflow into adjacent areas on the official form.
# ---------------------------------------------------------------------------
FIELD_FONT_OVERRIDES = {
    # Official form box is only 13.8mm wide; 10pt overflows for all 4 main HMOs.
    # 7pt fits 'כללית כבנות' (longest common name, ~10 chars) within the box.
    'employee.health_fund.name':   7,
}

# ---------------------------------------------------------------------------
# bindKey  →  ('text'|'checkbox'|'sig'|'skip', GAS_expression)
# ---------------------------------------------------------------------------
BIND = {
    # ── Meta ────────────────────────────────────────────────────────────────
    'meta.tax_year':                    ('text', "s(pdf.taxYear)"),

    # ── Section A – Employer ─────────────────────────────────────────────────
    'employer.name':                    ('text', "s(pdf.employer_name)"),
    'employer.deductions_file':         ('text', "s(pdf.employer_tax_id)"),
    'employer.address':                 ('text', "s(pdf.employer_address)"),
    'employer.phone':                   ('text', "s(pdf.employer_phone)"),

    # ── Section B – Employee ─────────────────────────────────────────────────
    'employee.id':                      ('text', "s(pdf.id_number)"),
    'employee.last_name':               ('text', "s(pdf.last_name)"),
    'employee.first_name':              ('text', "s(pdf.first_name)"),
    'employee.birth_date':              ('text', "dmy(pdf.birth_date)"),
    'employee.immigration_date':        ('text', "dmy(pdf.aliyah_date)"),
    'employee.passport':                ('text', "s(pdf.passport_number)"),

    # address: frontend combines street+house+city into a single string
    'employee.address.house_no':        ('skip', ''),
    'employee.address.street':          ('text', "s(pdf.address)"),
    'employee.address.city':            ('skip', ''),
    'employee.address.zip':             ('text', "s(pdf.postal_code)"),

    'employee.phone':                   ('text', "s(data.phone || '')"),
    'employee.mobile':                  ('text', "s(pdf.mobile_phone)"),
    'employee.email':                   ('text', "s(pdf.email)"),

    # Gender
    'employee.gender.male':             ('checkbox', "eq(pdf.gender,'זכר')"),
    'employee.gender.female':           ('checkbox', "eq(pdf.gender,'נקבה')"),

    # Marital status
    'employee.marital_status.married':  ('checkbox', "eq(pdf.marital_status,'נשוי') || eq(pdf.marital_status,'נשואה')"),
    'employee.marital_status.single':   ('checkbox', "eq(pdf.marital_status,'רווק') || eq(pdf.marital_status,'רווקה')"),
    'employee.marital_status.divorced': ('checkbox', "eq(pdf.marital_status,'גרוש') || eq(pdf.marital_status,'גרושה')"),
    'employee.marital_status.widowed':  ('checkbox', "eq(pdf.marital_status,'אלמן') || eq(pdf.marital_status,'אלמנה')"),
    'employee.marital_status.separated':('checkbox', "eq(pdf.marital_status,'פרוד') || eq(pdf.marital_status,'פרודה')"),

    # Has Israeli ID (non-empty id_number → yes; empty → no)
    'employee.has_id.yes':              ('checkbox', "s(pdf.id_number) !== ''"),
    'employee.has_id.no':               ('checkbox', "s(pdf.id_number) === ''"),

    # Kibbutz
    'employee.kibbutz_member.no':                       ('checkbox', "!yes(pdf.kibbutz_member)"),
    'employee.kibbutz_member.income_transferred':       ('checkbox', "yes(pdf.kibbutz_member) && !eq(pdf.kibbutz_member,'8')"),
    'employee.kibbutz_member.income_not_transferred':   ('checkbox', "eq(pdf.kibbutz_member,'8') || eq(pdf.kibbutz_member,'אינן מועברות')"),

    # Health fund
    'employee.health_fund.member.yes': ('checkbox', "yes(pdf.health_fund)"),
    'employee.health_fund.member.no':  ('checkbox', "!yes(pdf.health_fund)"),
    'employee.health_fund.name':       ('text',     "s(pdf.health_fund)"),

    # ── Section C – Children ─────────────────────────────────────────────────
    'children[0].name':               ('text',     "s(childAt(0).name)"),
    'children[0].id':                 ('text',     "s(childAt(0).id)"),
    'children[0].birth_date':         ('text',     "dmy(childAt(0).birth_date)"),
    'children[0].in_custody':         ('checkbox', "yes(childAt(0).in_custody)"),
    'children[0].receives_allowance': ('checkbox', "yes(childAt(0).receives_allowance)"),

    'children[1].name':               ('text',     "s(childAt(1).name)"),
    'children[1].id':                 ('text',     "s(childAt(1).id)"),
    'children[1].birth_date':         ('text',     "dmy(childAt(1).birth_date)"),
    'children[1].in_custody':         ('checkbox', "yes(childAt(1).in_custody)"),
    'children[1].receives_allowance': ('checkbox', "yes(childAt(1).receives_allowance)"),

    'children[2].name':               ('text',     "s(childAt(2).name)"),
    'children[2].id':                 ('text',     "s(childAt(2).id)"),
    'children[2].birth_date':         ('text',     "dmy(childAt(2).birth_date)"),
    'children[2].in_custody':         ('checkbox', "yes(childAt(2).in_custody)"),
    'children[2].receives_allowance': ('checkbox', "yes(childAt(2).receives_allowance)"),

    'children[3].name':               ('text',     "s(childAt(3).name)"),
    'children[3].id':                 ('text',     "s(childAt(3).id)"),
    'children[3].birth_date':         ('text',     "dmy(childAt(3).birth_date)"),
    'children[3].in_custody':         ('checkbox', "yes(childAt(3).in_custody)"),
    'children[3].receives_allowance': ('checkbox', "yes(childAt(3).receives_allowance)"),

    # ── Section D – Income type (main employer) ───────────────────────────────
    'income.main.monthly_salary':   ('checkbox', "yes(flags.income_type_monthly)"),
    'income.main.additional_job':   ('checkbox', "yes(flags.income_type_additional)"),
    'income.main.partial_salary':   ('checkbox', "yes(flags.income_type_partial)"),
    'income.main.daily_worker':     ('checkbox', "yes(flags.income_type_daily)"),
    'income.main.pension':          ('checkbox', "yes(flags.income_type_pension)"),
    'income.main.scholarship':      ('checkbox', "yes(flags.income_type_scholarship)"),

    'employment.start_date': ('text', "dmy(pdf.start_date)"),

    # ── Section E – Other income ─────────────────────────────────────────────
    'income.other.none':              ('checkbox', "!pdf.has_other_income"),
    'income.other.monthly_salary':    ('checkbox', "yes(flags.other_income_monthly)"),
    'income.other.additional_job':    ('checkbox', "yes(flags.other_income_additional)"),
    'income.other.partial_salary':    ('checkbox', "yes(flags.other_income_partial)"),
    'income.other.daily_worker':      ('checkbox', "yes(flags.other_income_daily)"),
    'income.other.pension':           ('checkbox', "yes(flags.other_income_pension)"),
    'income.other.scholarship':       ('checkbox', "yes(flags.other_income_scholarship)"),
    'income.other.no_training_fund':  ('checkbox', "yes(flags.no_study_fund_other)"),
    'income.other.no_pension':        ('checkbox', "yes(flags.no_pension_other)"),

    # Credit-point requests
    'income.credit_request.get_credits_here':      ('checkbox', "yes(flags.relief_wants)"),
    'income.credit_request.get_credits_elsewhere': ('checkbox', "yes(flags.relief_has_other)"),

    # ── Section F – Spouse ───────────────────────────────────────────────────
    'spouse.id':               ('text', "s(pdf.spouse_id)"),
    'spouse.passport':         ('text', "s(pdf.spouse_passport)"),
    'spouse.last_name':        ('text', "s(pdf.spouse_last_name)"),
    'spouse.first_name':       ('text', "s(pdf.spouse_first_name)"),
    'spouse.birth_date':       ('text', "dmy(pdf.spouse_birth_date)"),
    'spouse.immigration_date': ('text', "dmy(pdf.spouse_aliya_date)"),

    'spouse.has_income.none': ('checkbox', "!pdf.has_spouse || eq(pdf.spouse_has_income,'לא')"),
    'spouse.has_income.yes':  ('checkbox', "pdf.has_spouse && !eq(pdf.spouse_has_income,'לא')"),
    'spouse.income_type.work':  ('checkbox', "eq(pdf.spouse_has_income,'עבודה')"),
    'spouse.income_type.other': ('checkbox', "eq(pdf.spouse_has_income,'אחר')"),

    # ── Section H – Credits (page 2) ─────────────────────────────────────────
    'credits.1_israeli_resident':                    ('checkbox', "yes(flags.relief_1_resident)"),
    'credits.2a_disability_100_or_blind':            ('checkbox', "yes(flags.relief_2_disabled)"),
    'credits.2b_monthly_benefit':                    ('checkbox', "yes(flags.relief_2_1_allowance)"),
    'credits.3_eligible_locality':                   ('checkbox', "yes(flags.relief_3_settlement)"),
    'credits.3_from_date':                           ('text',     "yes(flags.relief_3_settlement) ? dmy(pdf.relief_dates.relief_3_date) : ''"),
    'credits.3_locality_name':                       ('text',     "yes(flags.relief_3_settlement) ? s(data.relief_3_settlement_name || data.relief_3_locality || '') : ''"),
    'credits.4_new_immigrant':                       ('checkbox', "yes(flags.relief_4_new_immigrant)"),
    'credits.4_from_date':                           ('text',     "yes(flags.relief_4_new_immigrant) ? dmy(pdf.aliyah_date) : ''"),
    'credits.4_no_income_until':                     ('text',     "yes(flags.relief_4_new_immigrant) ? dmy(pdf.relief_dates.relief_4_no_income_until) : ''"),
    'credits.5_spouse_no_income':                    ('checkbox', "yes(flags.relief_5_spouse)"),
    'credits.6_single_parent_family':                ('checkbox', "yes(flags.relief_6_single_parent)"),
    'credits.7_children_in_custody':                 ('checkbox', "yes(flags.relief_7_children_custody)"),
    'credits.7_children_born_in_year':               ('text',     "s(data.relief_7_born || '')"),
    'credits.7_children_count_6_17':                 ('text',     "s(data.relief_7_count_6_17 || '')"),
    'credits.7_children_count_18':                   ('text',     "s(data.relief_7_count_18 || '')"),
    'credits.7_children_count_1_5':                  ('text',     "s(data.relief_7_count_1_5 || '')"),
    'credits.8_children_not_in_custody':             ('checkbox', "yes(flags.relief_8_children_general)"),
    'credits.8_children_count_1_5':                  ('text',     "s(data.relief_8_count_1_5 || '')"),
    'credits.8_children_count_6_17':                 ('text',     "s(data.relief_8_count_6_17 || '')"),
    'credits.9_single_parent':                       ('checkbox', "yes(flags.relief_9_sole_parent)"),
    'credits.10_children_not_in_custody_maintenance':('checkbox', "yes(flags.relief_10_children_not_custody)"),
    'credits.11_disabled_child':                     ('checkbox', "yes(flags.relief_11_disabled_children)"),
    'credits.12_spousal_support':                    ('checkbox', "yes(flags.relief_12_alimony)"),
    'credits.13_age_16_18':                          ('checkbox', "yes(flags.relief_13_age_16_18)"),
    'credits.14_released_soldier_or_service':        ('checkbox', "yes(flags.relief_14_discharged_soldier)"),
    'credits.14_service_start':                      ('text',     "yes(flags.relief_14_discharged_soldier) ? dmy(pdf.relief_dates.relief_14_start) : ''"),
    'credits.14_service_end':                        ('text',     "yes(flags.relief_14_discharged_soldier) ? dmy(pdf.relief_dates.relief_14_end) : ''"),
    'credits.15_graduation':                         ('checkbox', "yes(flags.relief_15_academic)"),
    'credits.16_reserve_combat':                     ('checkbox', "yes(flags.relief_16_reserve)"),
    'credits.16_reserve_days_prev_year':             ('text',     "yes(flags.relief_16_reserve) ? s(pdf.relief_dates.relief_16_days) : ''"),

    # ── Section T – Tax coordination (page 2) ────────────────────────────────
    'tax_coordination.no_income_until_start':  ('checkbox', "yes(data.t1_no_prior_income)"),
    'tax_coordination.has_additional_income':  ('checkbox', "yes(pdf.has_tax_coordination)"),
    'tax_coordination.approval_attached':      ('checkbox', "yes(pdf.tax_coordination_approved)"),

    # Additional incomes table (page 2)
    'other_income[0].type':           ('text', "s(incAt(0).type)"),
    'other_income[0].payer_name':     ('text', "s(incAt(0).employer)"),
    'other_income[0].address':        ('text', "s(incAt(0).address)"),
    'other_income[0].deductions_file':('text', "s(incAt(0).tax_id)"),
    'other_income[0].monthly_amount': ('text', "s(incAt(0).amount)"),
    'other_income[0].tax_withheld':   ('text', "s(incAt(0).tax)"),

    'other_income[1].type':           ('text', "s(incAt(1).type)"),
    'other_income[1].payer_name':     ('text', "s(incAt(1).employer)"),
    'other_income[1].address':        ('text', "s(incAt(1).address)"),
    'other_income[1].deductions_file':('text', "s(incAt(1).tax_id)"),
    'other_income[1].monthly_amount': ('text', "s(incAt(1).amount)"),
    'other_income[1].tax_withheld':   ('text', "s(incAt(1).tax)"),

    # ── Signature & Declaration ──────────────────────────────────────────────
    'signature.date':                 ('text',     "dmy(pdf.declaration_date)"),
    'signature.declaration':          ('checkbox', "yes(pdf.confirm_declaration)"),
    'signature.applicant_signature':  ('sig',      "pdf.signature"),
}

# ---------------------------------------------------------------------------

def px(v, axis):
    """Convert PDF points to mm."""
    return v * (SX if axis == 'x' else SY)

def render_field(f):
    bk = f.get('bindKey', '')
    kind, expr = BIND.get(bk, (None, None))

    if kind is None:
        return f"  <!-- UNMAPPED: {f['name']} bindKey={bk} -->"
    if kind == 'skip':
        return f"  <!-- SKIP: {f['name']} bindKey={bk} -->"

    x  = px(f['x'], 'x')
    y  = px(f['y'], 'y')
    w  = px(f['w'], 'x')
    h  = px(f['h'], 'y')
    fs = FIELD_FONT_OVERRIDES.get(bk, f.get('fontSize', 9))
    align = f.get('align', 'right')
    name = f['name']

    if kind == 'text':
        style = (f"left:{x:.2f}mm;top:{y:.2f}mm;"
                 f"width:{w:.2f}mm;height:{h:.2f}mm;"
                 f"font-size:{fs}pt;text-align:{align};"
                 f"direction:rtl;")
        return (f"  <!-- {name} -->\n"
                f"  <div class=\"field\" style=\"{style}\"><?= {expr} ?></div>")

    if kind == 'checkbox':
        # Center the ✓ vertically in the checkbox box
        # MARK_PT in mm: MARK_PT * 0.352778
        mark_h_mm = MARK_PT * 0.352778
        top = y + (h / 2) - (mark_h_mm / 2)
        style = f"left:{x:.2f}mm;top:{top:.2f}mm;"
        return (f"  <!-- {name} -->\n"
                f"  <? if ({expr}) {{ ?>"
                f"<div class=\"mark\" style=\"{style}\">&#x2713;</div>"
                f"<? }} ?>")

    if kind == 'sig':
        style = (f"left:{x:.2f}mm;top:{y:.2f}mm;"
                 f"width:{w:.2f}mm;height:{h:.2f}mm;")
        return (f"  <!-- {name} -->\n"
                f"  <? if ({expr}) {{ ?>"
                f"<img class=\"sig\" style=\"{style}\" src=\"<?= {expr} ?>\"/>"
                f"<? }} ?>")

    return f"  <!-- UNHANDLED kind={kind} {name} -->"


def build_page_html(fields, bg_b64):
    lines = [f'<div class="page">']
    lines.append(f'  <img class="bg" src="data:image/jpeg;base64,{bg_b64}" />')
    for f in fields:
        lines.append(render_field(f))
    lines.append('</div>')
    return '\n'.join(lines)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root, 'NEW 3', 'form_101_mapping_1772880459281.json')
    bg1_path  = os.path.join(root, 'NEW 3', 'page1_bg.b64')
    bg2_path  = os.path.join(root, 'NEW 3', 'page2_bg.b64')

    with open(json_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    with open(bg1_path, 'r') as f:
        bg1 = f.read().strip()
    with open(bg2_path, 'r') as f:
        bg2 = f.read().strip()

    fields_p0 = [f for f in mapping['fields'] if f['page'] == 0]
    fields_p1 = [f for f in mapping['fields'] if f['page'] == 1]

    print(f"Fields page 0: {len(fields_p0)}, page 1: {len(fields_p1)}")

    unmapped = [f['bindKey'] for f in mapping['fields']
                if f.get('bindKey','') not in BIND]
    if unmapped:
        print(f"WARN – unmapped bindKeys: {unmapped}")

    header = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <style>
    @page { size: A4; margin: 0; }
    html, body { margin:0; padding:0; direction: rtl; font-family: Arial, Helvetica, sans-serif; }
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .page { position: relative; width: 210mm; height: 297mm; page-break-after: always; overflow: hidden; }
    .page:last-child { page-break-after: auto; }
    .bg { position:absolute; top:0; left:0; width:210mm; height:297mm; }
    .field { position:absolute; color:#111; line-height:1.1; white-space:nowrap; overflow:hidden; }
    .mark {
      position:absolute; color:#1f5fe0; font-size:10pt; line-height:1; font-weight:700;
      font-family:"Segoe Script","Comic Sans MS",cursive;
    }
    .sig { position:absolute; max-width:30mm; max-height:12mm; object-fit:contain; }
  </style>
</head>
<body>
<?
  function s(v) { return v == null ? '' : String(v); }
  function yes(v) { return v === true || v === 'true' || v === 'כן' || v === 'on' || v === '1'; }
  function eq(a,b) { return String(a||'') === String(b||''); }
  function dmy(v) {
    if (!v) return '';
    var m = String(v).match(/^(\\d{4})-(\\d{2})-(\\d{2})$/);
    if (m) return m[3] + '/' + m[2] + '/' + m[1];
    return String(v);
  }
  function childAt(i) { return (data.children && data.children[i]) ? data.children[i] : {}; }
  function incAt(i) { return (data.additional_incomes && data.additional_incomes[i]) ? data.additional_incomes[i] : {}; }
  function chgAt(i) { return (pdf.changes && pdf.changes[i]) ? pdf.changes[i] : {}; }
?>"""

    footer = """\
</body>
</html>"""

    page1_html = build_page_html(fields_p0, bg1)
    page2_html = build_page_html(fields_p1, bg2)

    # Section Z — שינויים במהלך השנה (3 rows × 4 cols, NOT in JSON mapping)
    # Table bounds from PyMuPDF: x=10.1..190.3mm, y=266.4..290.4mm
    # Column left edges (RTL): date=170.5mm, details=67.0mm, notif=41.0mm, sig=10.1mm
    # Row tops: 270.9 / 276.9 / 282.9 mm  (6mm per row)
    section_z_lines = ['  <!-- Section Z — שינויים במהלך השנה -->']
    ROW_TOPS   = [271.15, 277.15, 283.15]   # top of text box in each row
    ROW_HEIGHT = 5.25                         # mm — fits within 6mm row cell
    COLS = [
        # (name_in_chgAt, left_mm, width_mm, align, is_date)
        ('date',              170.5, 19.8, 'center', True),
        ('details',            67.0, 103.5, 'right',  False),
        ('notification_date',  41.0, 26.0,  'center', True),
        ('signature',          10.1, 30.9,  'center', False),
    ]
    for i, row_top in enumerate(ROW_TOPS):
        section_z_lines.append(f'  <!-- Z row {i+1} (top={row_top:.2f}mm) -->')
        for col_name, left, width, align, is_date in COLS:
            expr = f'dmy(chgAt({i}).{col_name})' if is_date else f's(chgAt({i}).{col_name})'
            rtl = ';direction:rtl' if align == 'right' else ''
            section_z_lines.append(
                f'  <div class="field" style="left:{left:.2f}mm;top:{row_top:.2f}mm;'
                f'width:{width:.2f}mm;height:{ROW_HEIGHT:.2f}mm;'
                f'font-size:8pt;text-align:{align}{rtl};">'
                f'<?= {expr} ?></div>'
            )
    section_z_html = '\n'.join(section_z_lines)

    # Insert Section Z before closing </div> of page 1
    page1_html = page1_html.rstrip()
    assert page1_html.endswith('</div>'), "page1_html should end with </div>"
    page1_html = page1_html[:-len('</div>')] + '\n' + section_z_html + '\n</div>'

    full_html = header + '\n\n' + page1_html + '\n\n' + page2_html + '\n\n' + footer

    out1 = os.path.join(root, 'PDFTemplate_v6.html')
    out2 = os.path.join(root, 'src', 'PDFTemplate.html')

    for out in [out1, out2]:
        with open(out, 'w', encoding='utf-8') as f:
            f.write(full_html)
        size_kb = os.path.getsize(out) // 1024
        print(f"Written: {out}  ({size_kb} KB)")

    print("Done.")

if __name__ == '__main__':
    main()
