"""
test_template_new3.py
=====================
Renders PDFTemplate_v6.html with sample data using Playwright → PDF.
Saves result as: בדיקה_new3_template.pdf

Run:
  python scripts/test_template_new3.py
"""

import os, sys, re, json, base64, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Sample data (mirrors what GAS would receive after normalizePayload)
# ---------------------------------------------------------------------------
SAMPLE_DATA = {
    "taxYear": "2026",
    # Employer
    "employer_name":    "חברת דוגמה בע\"מ",
    "employer_tax_id":  "512345678",
    "employer_address": "רחוב הרצל 10, תל אביב",
    "employer_phone":   "03-1234567",
    "start_date":       "2026-01-01",
    # Employee
    "last_name":        "ישראלי",
    "first_name":       "ישראל",
    "id_number":        "123456789",
    "passport_number":  "",
    "birth_date":       "1985-05-15",
    "aliya_date":       "",
    "address":          "רחוב בן גוריון 5 חיפה",
    "postal_code":      "3308001",
    "mobile_phone":     "050-1234567",
    "email":            "israel@example.com",
    "gender":           "זכר",
    "marital_status":   "נשוי",
    "israeli_resident": "כן",
    "kibbutz_member":   "",
    "health_fund":      "מכבי",
    # Income types
    "income_type_monthly":     True,
    "income_type_additional":  False,
    "income_type_partial":     False,
    "income_type_daily":       False,
    "income_type_pension":     False,
    "income_type_scholarship": False,
    # Other income
    "has_other_income":        False,
    "other_income_monthly":    False,
    "other_income_additional": False,
    "other_income_partial":    False,
    "other_income_daily":      False,
    "other_income_pension":    False,
    "other_income_scholarship":False,
    "no_study_fund_other":     False,
    "no_pension_other":        False,
    "relief_wants":            True,
    "relief_has_other":        False,
    # Children
    "children": [
        {"name": "דנה ישראלי", "id": "234567890", "birth_date": "2015-03-10",
         "in_custody": True, "receives_allowance": True},
        {"name": "אדם ישראלי", "id": "345678901", "birth_date": "2018-07-22",
         "in_custody": True, "receives_allowance": True},
    ],
    # Spouse
    "has_spouse":              True,
    "spouse_last_name":        "ישראלי",
    "spouse_first_name":       "שרה",
    "spouse_id_number":        "987654321",
    "spouse_passport_number":  "",
    "spouse_birth_date":       "1987-08-20",
    "spouse_aliya_date":       "",
    "spouse_has_income":       "עבודה",
    # Tax coordination
    "has_tax_coordination":    False,
    "tax_coordination_approved": False,
    "t1_no_prior_income":      False,
    # Additional incomes (for tax coord table)
    "additional_incomes": [],
    # Reliefs
    "relief_1_resident":        True,
    "relief_2_disabled":        False,
    "relief_2_1_allowance":     False,
    "relief_3_settlement":      False,
    "relief_3_date":            "",
    "relief_3_settlement_name": "",
    "relief_4_new_immigrant":   False,
    "relief_4_no_income_until": "",
    "relief_5_spouse":          True,
    "relief_6_single_parent":   False,
    "relief_7_children_custody":True,
    "relief_7_born":            "1",
    "relief_7_count_1_5":       "1",
    "relief_7_count_6_17":      "1",
    "relief_7_count_18":        "0",
    "relief_8_children_general":False,
    "relief_8_count_1_5":       "",
    "relief_8_count_6_17":      "",
    "relief_9_sole_parent":     False,
    "relief_10_children_not_custody": False,
    "relief_11_disabled_children": False,
    "relief_12_alimony":        False,
    "relief_13_age_16_18":      False,
    "relief_14_discharged_soldier": False,
    "relief_14_start":          "",
    "relief_14_end":            "",
    "relief_15_academic":       False,
    "relief_16_reserve":        False,
    "relief_16_days":           "",
    "relief_17_no_income":      False,
    # Declaration
    "confirm_declaration":      True,
    "declaration_date":         "2026-03-08",
    "signature":                "",
    # Changes
    "changes": [],
}

def build_pdf_view_model(data):
    def ss(v):
        return '' if v is None else str(v)
    return {
        'taxYear':    ss(data.get('taxYear')),
        'employer_name':    ss(data.get('employer_name')),
        'employer_tax_id':  ss(data.get('employer_tax_id')),
        'employer_address': ss(data.get('employer_address')),
        'employer_phone':   ss(data.get('employer_phone')),
        'last_name':        ss(data.get('last_name')),
        'first_name':       ss(data.get('first_name')),
        'id_number':        ss(data.get('id_number')),
        'passport_number':  ss(data.get('passport_number')),
        'birth_date':       ss(data.get('birth_date')),
        'aliyah_date':      ss(data.get('aliya_date')),
        'address':          ss(data.get('address')),
        'postal_code':      ss(data.get('postal_code')),
        'mobile_phone':     ss(data.get('mobile_phone')),
        'email':            ss(data.get('email')),
        'gender':           ss(data.get('gender')),
        'marital_status':   ss(data.get('marital_status')),
        'israeli_resident': ss(data.get('israeli_resident')),
        'kibbutz_member':   ss(data.get('kibbutz_member')),
        'health_fund':      ss(data.get('health_fund')),
        'start_date':       ss(data.get('start_date')),
        'has_other_income': bool(data.get('has_other_income')),
        'has_spouse':       bool(data.get('has_spouse')),
        'spouse_has_income':ss(data.get('spouse_has_income')),
        # Spouse detail fields (required by template)
        'spouse_last_name':   ss(data.get('spouse_last_name')),
        'spouse_first_name':  ss(data.get('spouse_first_name')),
        'spouse_id':          ss(data.get('spouse_id_number')),
        'spouse_passport':    ss(data.get('spouse_passport_number')),
        'spouse_birth_date':  ss(data.get('spouse_birth_date')),
        'spouse_aliya_date':  ss(data.get('spouse_aliya_date')),
        'has_tax_coordination':    bool(data.get('has_tax_coordination')),
        'tax_coordination_approved': bool(data.get('tax_coordination_approved')),
        'confirm_declaration': bool(data.get('confirm_declaration')),
        'declaration_date': ss(data.get('declaration_date')),
        'signature':        ss(data.get('signature')),
        'relief_dates': {
            'relief_3_date':         ss(data.get('relief_3_date')),
            'relief_4_date':         ss(data.get('relief_4_date')),
            'relief_4_no_income_until': ss(data.get('relief_4_no_income_until')),
            'relief_14_start':       ss(data.get('relief_14_start')),
            'relief_14_end':         ss(data.get('relief_14_end')),
            'relief_16_days':        ss(data.get('relief_16_days')),
        },
        'flags': {
            'income_type_monthly':    bool(data.get('income_type_monthly')),
            'income_type_additional': bool(data.get('income_type_additional')),
            'income_type_partial':    bool(data.get('income_type_partial')),
            'income_type_daily':      bool(data.get('income_type_daily')),
            'income_type_pension':    bool(data.get('income_type_pension')),
            'income_type_scholarship':bool(data.get('income_type_scholarship')),
            'other_income_monthly':   bool(data.get('other_income_monthly')),
            'other_income_additional':bool(data.get('other_income_additional')),
            'other_income_partial':   bool(data.get('other_income_partial')),
            'other_income_daily':     bool(data.get('other_income_daily')),
            'other_income_pension':   bool(data.get('other_income_pension')),
            'other_income_scholarship':bool(data.get('other_income_scholarship')),
            'no_study_fund_other':    bool(data.get('no_study_fund_other')),
            'no_pension_other':       bool(data.get('no_pension_other')),
            'relief_wants':           bool(data.get('relief_wants')),
            'relief_has_other':       bool(data.get('relief_has_other')),
            'relief_1_resident':      bool(data.get('relief_1_resident')),
            'relief_2_disabled':      bool(data.get('relief_2_disabled')),
            'relief_2_1_allowance':   bool(data.get('relief_2_1_allowance')),
            'relief_3_settlement':    bool(data.get('relief_3_settlement')),
            'relief_4_new_immigrant': bool(data.get('relief_4_new_immigrant')),
            'relief_5_spouse':        bool(data.get('relief_5_spouse')),
            'relief_6_single_parent': bool(data.get('relief_6_single_parent')),
            'relief_7_children_custody': bool(data.get('relief_7_children_custody')),
            'relief_8_children_general': bool(data.get('relief_8_children_general')),
            'relief_9_sole_parent':   bool(data.get('relief_9_sole_parent')),
            'relief_10_children_not_custody': bool(data.get('relief_10_children_not_custody')),
            'relief_11_disabled_children': bool(data.get('relief_11_disabled_children')),
            'relief_12_alimony':      bool(data.get('relief_12_alimony')),
            'relief_13_age_16_18':    bool(data.get('relief_13_age_16_18')),
            'relief_14_discharged_soldier': bool(data.get('relief_14_discharged_soldier')),
            'relief_15_academic':     bool(data.get('relief_15_academic')),
            'relief_16_reserve':      bool(data.get('relief_16_reserve')),
            'relief_17_no_income':    bool(data.get('relief_17_no_income')),
        }
    }


class AttrDict:
    """Dict with attribute access, for simulating JavaScript objects in Python."""
    def __init__(self, d):
        for k, v in (d.items() if isinstance(d, dict) else []):
            setattr(self, k, AttrDict(v) if isinstance(v, dict) else v)
    def __getattr__(self, name):
        return ''   # undefined → empty string (like JS)
    def __bool__(self):
        return True


def js_expr_to_py(expr: str) -> str:
    """Translate JS boolean operators to Python."""
    import re as _re
    # && → and,  || → or,  ! → not  (careful with != and !yes(...))
    expr = _re.sub(r'\s*&&\s*', ' and ', expr)
    expr = _re.sub(r'\s*\|\|\s*', ' or ', expr)
    # !x  →  not x  (but NOT !=)
    expr = _re.sub(r'(?<!=)!(?!=)', 'not ', expr)
    return expr


def eval_gas_template(html: str, data: dict, pdf: dict, flags: dict) -> str:
    """Minimal GAS scriptlet evaluator for testing (Python port)."""
    import re as _re

    def s(v):
        return '' if v is None else str(v)
    def yes(v):
        if isinstance(v, bool): return v
        if v is None: return False
        sv = str(v)
        return sv in ('true', 'כן', 'on', '1') or (sv.strip() != '' and sv not in ('false','0','לא',''))
    def eq(a, b):
        return str(a if a is not None else '') == str(b if b is not None else '')
    def dmy(v):
        if not v: return ''
        m = _re.match(r'^(\d{4})-(\d{2})-(\d{2})$', str(v))
        if m: return f"{m[3]}/{m[2]}/{m[1]}"
        return str(v)

    # Wrap dicts as AttrDict for JS-style dot access
    ad = AttrDict(data)
    apdf = AttrDict(pdf)
    aflags = AttrDict(flags)

    def childAt(i):
        children = data.get('children', [])
        c = children[i] if i < len(children) else {}
        return AttrDict(c) if isinstance(c, dict) else c
    def incAt(i):
        incs = data.get('additional_incomes', [])
        c = incs[i] if i < len(incs) else {}
        return AttrDict(c) if isinstance(c, dict) else c

    ctx = {
        'data': ad, 'pdf': apdf, 'flags': aflags,
        's': s, 'yes': yes, 'eq': eq, 'dmy': dmy,
        'childAt': childAt, 'incAt': incAt,
        'True': True, 'False': False, 'None': None,
        'null': None, 'undefined': None,
    }

    if_stack = []

    def active():
        return all(if_stack) if if_stack else True

    tokens = _re.split(r'(<\?.*?\?>)', html, flags=_re.DOTALL)
    parts = []
    for tok in tokens:
        if tok.startswith('<?='):
            if active():
                expr_str = js_expr_to_py(tok[3:-2].strip())
                try:
                    val = eval(expr_str, {"__builtins__": {}}, ctx)
                    parts.append(str(val) if val is not None else '')
                except Exception as e:
                    parts.append('')   # silent fail in test
        elif tok.startswith('<?'):
            code_str = tok[2:-2].strip()
            m_if = _re.match(r'if\s*\((.+)\)\s*\{', code_str, _re.DOTALL)
            m_else = _re.match(r'\}\s*else\s*\{', code_str.strip())
            m_close = _re.match(r'\}', code_str.strip())
            if m_if:
                cond_js = m_if.group(1)
                cond_py = js_expr_to_py(cond_js)
                parent_active = all(if_stack) if if_stack else True
                try:
                    cond = bool(eval(cond_py, {"__builtins__": {}}, ctx))
                except Exception:
                    cond = False
                if_stack.append(cond and parent_active)
            elif m_else:
                if if_stack:
                    last = if_stack.pop()
                    parent_active = all(if_stack) if if_stack else True
                    if_stack.append(parent_active and not last)
            elif m_close:
                if if_stack:
                    if_stack.pop()
            # skip function definitions
        else:
            if active():
                parts.append(tok)
    return ''.join(parts)


def main():
    tmpl_path = os.path.join(ROOT, 'PDFTemplate_v6.html')
    with open(tmpl_path, 'r', encoding='utf-8') as f:
        tmpl_html = f.read()

    data = SAMPLE_DATA
    pdf  = build_pdf_view_model(data)
    flags = pdf['flags']

    print("Evaluating template...")
    rendered = eval_gas_template(tmpl_html, data, pdf, flags)

    # Save rendered HTML for inspection
    html_out = os.path.join(ROOT, 'בדיקה_new3_template.html')
    with open(html_out, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"Rendered HTML: {html_out}")

    # Generate PDF with Playwright
    try:
        from playwright.sync_api import sync_playwright
        pdf_out = os.path.join(ROOT, 'בדיקה_new3_template.pdf')
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(rendered, wait_until='networkidle')
            page.pdf(
                path=pdf_out,
                format='A4',
                margin={'top':'0','bottom':'0','left':'0','right':'0'},
                print_background=True,
            )
            browser.close()
        size_kb = os.path.getsize(pdf_out) // 1024
        print(f"PDF generated: {pdf_out}  ({size_kb} KB)")
    except ImportError:
        print("playwright not installed — only HTML output available.")
    except Exception as e:
        print(f"PDF generation error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
