"""
Reposition all PDF template fields based on NEW2 template JSON files.
Extracts background images from NEW2 PDF and computes CSS mm coordinates.

Usage: python -m scripts.reposition_from_new2
"""
import json, base64, re, sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("ERROR: pip install PyMuPDF")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
NEW2 = ROOT / "NEW2"
PDF_PATH = NEW2 / "searchable_20260225_092314.pdf"
TEMPLATE_P1 = NEW2 / "template (2).json"   # page=0 → page 1 of PDF
TEMPLATE_P2 = NEW2 / "template.json"        # page=1 → page 2 of PDF
OUT_HTML = ROOT / "PDFTemplate_v6.html"

# ── Scale factors ─────────────────────────────────────────────────────────────
# PDF page size (pts) → scanned at large scale
doc = fitz.open(str(PDF_PATH))
PAGE_W_PTS = doc[0].rect.width   # 2551.89
PAGE_H_PTS = doc[0].rect.height  # 3608.23
doc.close()

SCAN_W_MM = PAGE_W_PTS * 25.4 / 72   # ~900.2 mm
SCAN_H_MM = PAGE_H_PTS * 25.4 / 72   # ~1272.9 mm

# Render at 150 DPI → pixel dimensions of full scan
PX_W = PAGE_W_PTS * 150 / 72   # ~5316
PX_H = PAGE_H_PTS * 150 / 72   # ~7517

# Scale: JSON pixel → A4 mm
SX = 210.0 / PX_W   # mm per JSON-px (horizontal)
SY = 297.0 / PX_H   # mm per JSON-px (vertical)

def px2mm(x, y, w=0, h=0, center=False):
    """Convert JSON (x,y,w,h) → CSS (left_mm, top_mm, width_mm, height_mm).
    If center=True, use center of box for positioning (good for checkmarks).
    """
    if center:
        left = (x + w / 2) * SX
        top  = (y + h / 2) * SY
    else:
        left = x * SX
        top  = y * SY
    return round(left, 1), round(top, 1), round(w * SX, 1), round(h * SY, 1)

def mm(v):
    return f"{v}mm"

# ── Load JSON ─────────────────────────────────────────────────────────────────
p1_fields = {f["bindKey"]: f for f in json.loads(TEMPLATE_P1.read_text(encoding="utf-8"))["fields"]}
p2_fields = {f["bindKey"]: f for f in json.loads(TEMPLATE_P2.read_text(encoding="utf-8"))["fields"] if f["page"] == 1}

def get1(key):
    """Get field from page-1 JSON."""
    return p1_fields.get(key, {})

def get2(key):
    """Get field from page-2 JSON."""
    return p2_fields.get(key, {})

def field_pos(f, center=False):
    """Return (left_mm, top_mm, width_mm) for a field dict."""
    return px2mm(f["x"], f["y"], f.get("w", 0), f.get("h", 0), center=center)

# ── Extract background images ─────────────────────────────────────────────────
def extract_backgrounds():
    """Extract PDF pages as 1240×1753 px JPEG images (A4 @ 150 DPI)."""
    doc = fitz.open(str(PDF_PATH))
    images = []
    for i, page in enumerate(doc):
        # Render at A4 150 DPI (1240×1753 px)
        mat = fitz.Matrix(1240 / PAGE_W_PTS, 1753 / PAGE_H_PTS)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        jpeg_bytes = pix.tobytes("jpeg", jpg_quality=90)
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        images.append(b64)
        print(f"  Page {i+1}: {pix.width}×{pix.height} px, {len(jpeg_bytes):,} bytes")
    doc.close()
    return images

# ── Compute field positions ───────────────────────────────────────────────────
def compute_positions():
    """Returns dict of all field positions (left_mm, top_mm, width_mm)."""
    pos = {}

    # ── Page 1 ────────────────────────────────────────────────────────────────
    # Tax year (use from template p2 page=0 entry as it has more fields)
    ty = get1("meta.tax_year")
    if ty:
        l, t, w, _ = field_pos(ty)
        pos["tax_year"] = (l, t, w)

    # Section A: Employer
    for key, name in [
        ("employer.name",            "employer_name"),
        ("employer.address",         "employer_address"),
        ("employer.phone",           "employer_phone"),
        ("employer.deductions_file", "employer_tax_id"),
    ]:
        f = get1(key)
        if f:
            l, t, w, _ = field_pos(f)
            pos[name] = (l, t, w)

    # Section B: Employee text fields
    for key, name in [
        ("employee.last_name",       "last_name"),
        ("employee.first_name",      "first_name"),
        ("employee.id",              "id_number"),
        ("employee.birth_date",      "birth_date"),
        ("employee.immigration_date","aliya_date"),
        ("employee.address.street",  "address"),
        ("employee.address.zip",     "postal_code"),
        ("employee.email",           "email"),
        ("employee.mobile",          "mobile_phone"),
        ("employee.hmo.name",        "health_fund_name"),
    ]:
        f = get1(key)
        if f:
            l, t, w, _ = field_pos(f)
            pos[name] = (l, t, w)

    # Section B: Checkboxes (center of checkbox box)
    for key, name in [
        ("employee.gender.male",              "mark_gender_male"),
        ("employee.gender.female",            "mark_gender_female"),
        ("employee.marital.single",           "mark_marital_single"),
        ("employee.marital.married",          "mark_marital_married"),
        ("employee.marital.divorced",         "mark_marital_divorced"),
        ("employee.marital.widowed",          "mark_marital_widowed"),
        ("employee.marital.separated",        "mark_marital_separated"),
        ("employee.israeli_resident_yes",     "mark_resident_yes"),
        ("employee.israeli_resident_no",      "mark_resident_no"),
        ("employee.kibbutz.no",               "mark_kibbutz_no"),
        ("employee.kibbutz.yes_transfer",     "mark_kibbutz_yes"),
        ("employee.hmo.is_member_yes",        "mark_hmo_yes"),
        ("employee.hmo.is_member_no",         "mark_hmo_no"),
    ]:
        f = get1(key)
        if f:
            l, t, _, _ = field_pos(f, center=True)
            pos[name] = (l, t, 0)

    # Employment start date
    f = get1("employment.start_date")
    if f:
        l, t, w, _ = field_pos(f)
        pos["start_date"] = (l, t, w)

    # Section D: Income type checkboxes (center)
    for key, name in [
        ("income.main.monthly_salary",  "mark_income_monthly"),
        ("income.main.additional_job",  "mark_income_additional"),
        ("income.main.partial_salary",  "mark_income_partial"),
        ("income.main.daily_worker",    "mark_income_daily"),
        ("income.main.pension",         "mark_income_pension"),
        ("income.main.scholarship",     "mark_income_scholarship"),
    ]:
        f = get1(key)
        if f:
            l, t, _, _ = field_pos(f, center=True)
            pos[name] = (l, t, 0)

    # Section C: Children (rows 0 and 1 from JSON, extrapolate rest)
    child_rows = []
    c0_name = get1("children[0].name")
    c1_name = get1("children[1].name")
    if c0_name and c1_name:
        y0 = c0_name["y"] * SY
        y1 = c1_name["y"] * SY
        spacing = y1 - y0
        for i in range(6):
            child_rows.append(round(y0 + i * spacing, 1))
        pos["child_y_rows"] = child_rows

        # X positions from child[0]
        c0_id = get1("children[0].id")
        c0_bd = get1("children[0].birth_date")
        pos["child_name_left"]  = round(c0_name["x"] * SX, 1)
        pos["child_name_width"] = round(c0_name.get("w", 300) * SX, 1)
        pos["child_id_left"]    = round(c0_id["x"] * SX, 1) if c0_id else 105.0
        pos["child_id_width"]   = round(c0_id.get("w", 600) * SX, 1) if c0_id else 25.0
        pos["child_bd_left"]    = round(c0_bd["x"] * SX, 1) if c0_bd else 71.0
        pos["child_bd_width"]   = round(c0_bd.get("w", 700) * SX, 1) if c0_bd else 30.0
        # in_custody and receives_allowance (not in JSON - estimate from name field x)
        # These checkboxes are to the LEFT of the name field in Hebrew RTL
        pos["child_custody_left"]   = round((c0_name["x"] + c0_name.get("w", 300) + 80) * SX, 1)
        pos["child_allowance_left"] = round((c0_name["x"] + c0_name.get("w", 300) + 40) * SX, 1)

    # Section E: Other income checkboxes (center)
    for key, name in [
        ("income.other.none",                        "mark_no_other_income"),
        ("income.other.monthly_salary",              "mark_other_income_monthly"),
        ("income.other.daily_worker",                "mark_other_income_daily"),
        ("income.other.additional_job",              "mark_other_income_additional"),
        ("income.other.pension",                     "mark_other_income_pension"),
        ("income.credit_request.get_credits_here",   "mark_relief_wants"),
        ("income.credit_request.get_credits_elsewhere","mark_relief_has_other"),
        ("income.other.no_training_fund",            "mark_no_study_fund"),
        ("income.other.no_pension",                  "mark_no_pension"),
    ]:
        f = get1(key)
        if f:
            l, t, _, _ = field_pos(f, center=True)
            pos[name] = (l, t, 0)

    # has_other_income (positive checkbox) — near "no_other_income" but lower
    # Not in JSON; estimate: ~8.6mm below no_other_income
    if "mark_no_other_income" in pos:
        l, t, _ = pos["mark_no_other_income"]
        pos["mark_has_other_income"] = (l, round(t + 8.6, 1), 0)

    # Other income table row 1 → extrapolate for rows 0-2
    # JSON has row 1 positions; use those as base, extrapolate row spacing
    oi_type = get1("other_income[0].type")
    oi_name = get1("other_income[0].payer_name")
    oi_addr = get1("other_income[0].address")
    oi_file = get1("other_income[0].deductions_file")
    oi_amt  = get1("other_income[0].monthly_amount")
    oi_tax  = get1("other_income[0].tax_withheld")

    if oi_type:
        base_y = oi_type["y"] * SY
        # Row spacing: 5mm (same as current template)
        ROW_SPACING = 5.0
        pos["other_income_base_y"]     = round(base_y, 1)
        pos["other_income_row_spacing"] = ROW_SPACING
        pos["other_income_type_left"]   = round(oi_type["x"] * SX, 1) if oi_type else 61.0
        pos["other_income_type_width"]  = round(oi_type.get("w", 400) * SX, 1) if oi_type else 20.0
        pos["other_income_name_left"]   = round(oi_name["x"] * SX, 1) if oi_name else 109.0
        pos["other_income_name_width"]  = round(oi_name.get("w", 700) * SX, 1) if oi_name else 48.0
        pos["other_income_addr_left"]   = round(oi_addr["x"] * SX, 1) if oi_addr else 109.0
        pos["other_income_addr_width"]  = round(oi_addr.get("w", 1000) * SX, 1) if oi_addr else 48.0
        pos["other_income_file_left"]   = round(oi_file["x"] * SX, 1) if oi_file else 81.0
        pos["other_income_file_width"]  = round(oi_file.get("w", 400) * SX, 1) if oi_file else 27.0
        pos["other_income_amt_left"]    = round(oi_amt["x"] * SX, 1) if oi_amt else 35.0
        pos["other_income_amt_width"]   = round(oi_amt.get("w", 500) * SX, 1) if oi_amt else 26.0
        pos["other_income_tax_left"]    = round(oi_tax["x"] * SX, 1) if oi_tax else 9.0
        pos["other_income_tax_width"]   = round(oi_tax.get("w", 450) * SX, 1) if oi_tax else 26.0

    # Section F: Spouse text fields
    for key, name in [
        ("spouse.last_name",  "spouse_last_name"),
        ("spouse.first_name", "spouse_first_name"),
    ]:
        f = get1(key)
        if f:
            l, t, w, _ = field_pos(f)
            pos[name] = (l, t, w)

    # Spouse ID — use the LARGER id field (right side)
    sp_id_a = get1("spouse.id")
    # template(2).json has 2 entries for spouse.id; take the one at x=3949 (right side)
    # Since dict stores by bindKey, we get the last one. Let's get by scanning.
    p2j = json.loads(TEMPLATE_P1.read_text(encoding="utf-8"))["fields"]
    sp_ids = [f for f in p2j if f["bindKey"] == "spouse.id"]
    sp_id_right = max(sp_ids, key=lambda f: f["x"]) if sp_ids else None
    if sp_id_right:
        l, t, w, _ = field_pos(sp_id_right)
        pos["spouse_id"] = (l, t, w)

    # Spouse birth_date and aliya_date — not in JSON, keep old positions
    # (will be set manually in template)

    # Signature / declaration
    sig_date = get1("signature.date")
    sig_box  = get1("signature.reserved_box")
    if sig_date:
        l, t, w, _ = field_pos(sig_date)
        pos["declaration_date"] = (l, t, w)
    if sig_box:
        l, t, w, h = field_pos(sig_box)
        pos["signature_img"] = (l, t, w)

    # ── Page 2 ────────────────────────────────────────────────────────────────
    # Relief checkboxes (center of checkbox)
    relief_map = {
        "credits.1_israeli_resident":               "mark_relief_1",
        "credits.2a_disability_100_or_blind":       "mark_relief_2",
        "credits.2b_monthly_benefit":               "mark_relief_2_1",
        "credits.3_eligible_locality":              "mark_relief_3",
        "credits.4_new_immigrant":                  "mark_relief_4",
        "credits.5_spouse_no_income":               "mark_relief_5",
        "credits.6_single_parent_family":           "mark_relief_6",
        "credits.7_children_in_custody":            "mark_relief_7",
        "credits.8_children_not_in_custody_allowance": "mark_relief_8",
        "credits.9_single_parent":                  "mark_relief_9",
        "credits.11_disabled_child":                "mark_relief_11",
        "credits.12_spousal_support":               "mark_relief_12",
        "credits.13_age_16_18":                     "mark_relief_13",
        "credits.14_released_soldier_or_service":   "mark_relief_14",
        "credits.15_graduation":                    "mark_relief_15",
        "credits.16_reserve_combat":                "mark_relief_16",
        "tax_coordination.no_income_until_start":   "mark_t1_no_income",
        "tax_coordination.approval_attached":       "mark_t3_approved",
    }
    for key, name in relief_map.items():
        f = get2(key)
        if f:
            l, t, _, _ = field_pos(f, center=True)
            pos[name] = (l, t, 0)

    # Relief date fields
    for key, name in [
        ("credits.3_from_date",         "relief_3_date"),
        ("credits.3_locality_name",     "relief_3_locality"),
        ("credits.4_from_date",         "relief_4_date"),
        ("credits.4_no_income_until",   "relief_4_no_income"),
        ("credits.14_service_start",    "relief_14_start"),
        ("credits.14_service_end",      "relief_14_end"),
        ("credits.16_reserve_days_prev_year", "relief_16_days"),
    ]:
        f = get2(key)
        if f:
            l, t, w, _ = field_pos(f)
            pos[name] = (l, t, w)

    # Tax coordination (no_income_until_start → t1, approval_attached → t3)
    # already handled above in relief_map

    return pos

# ── Print position report ─────────────────────────────────────────────────────
def print_report(pos):
    print("\n=== NEW FIELD POSITIONS (mm) ===")
    print(f"{'Field':<40} {'Left':>8} {'Top':>8} {'Width':>8}")
    print("-" * 70)
    for k, v in sorted(pos.items()):
        if isinstance(v, list) or not isinstance(v, tuple):
            print(f"  {k:<38} {str(v)}")
        else:
            l, t, w = v
            print(f"  {k:<38} {l:>7.1f}  {t:>7.1f}  {w:>7.1f}")

# ── Generate HTML template ────────────────────────────────────────────────────
def build_html(pos, bg1_b64, bg2_b64):
    """Build complete PDFTemplate_v6.html with new positions."""

    def F(key, fallback_l, fallback_t, fallback_w=None):
        """Get position or use fallback."""
        if key in pos:
            return pos[key]
        return (fallback_l, fallback_t, fallback_w)

    def L(key, fb_l, fb_t, fb_w):
        l, t, w = F(key, fb_l, fb_t, fb_w)
        return l, t, w

    def M(key, fb_l, fb_t):
        """Get mark position."""
        l, t, _ = F(key, fb_l, fb_t, 0)
        return l, t

    # Helper to format field div
    def fld(left, top, width, content, cls="field", align="right", extra=""):
        style = f"left:{left}mm; top:{top}mm;"
        if width:
            style += f" width:{width}mm;"
        style += f" text-align:{align};"
        if extra:
            style += f" {extra}"
        return f'  <div class="{cls}" style="{style}">{content}</div>'

    def mark(left, top):
        return f'  <div class="mark" style="left:{left}mm; top:{top}mm;">✓</div>'

    # ── Page 1 ────────────────────────────────────────────────────────────────
    ty_l, ty_t, ty_w = L("tax_year", 106, 25.3, 26)
    en_l, en_t, en_w = L("employer_name",    145, 59.4, 50)
    ea_l, ea_t, ea_w = L("employer_address", 90,  59.4, 53)
    ep_l, ep_t, ep_w = L("employer_phone",   58.4,59.4, 30)
    et_l, et_t, et_w = L("employer_tax_id",  10.9,59.4, 31)

    ln_l, ln_t, ln_w = L("last_name",  139, 80.8, 44)
    fn_l, fn_t, fn_w = L("first_name", 98,  80.8, 41)
    id_l, id_t, id_w = L("id_number",  183, 80.8, 24)
    bd_l, bd_t, bd_w = L("birth_date", 58.6,80.8, 36)
    al_l, al_t, al_w = L("aliya_date", 26.4,80.8, 32)

    ad_l, ad_t, ad_w = L("address",    80,  89,   80)
    pc_l, pc_t, pc_w = L("postal_code",10,  89,   32)
    em_l, em_t, em_w = L("email",      163, 108.3,35)
    mb_l, mb_t, mb_w = L("mobile_phone",52.6,108.3,35)

    # Checkbox marks
    gm_l, gm_t = M("mark_gender_male",   187.1,100.9)
    gf_l, gf_t = M("mark_gender_female", 187.1,105.4)
    ms_l, ms_t = M("mark_marital_single",  173.3,100.3)
    mm_l, mm_t = M("mark_marital_married", 152.5,100.3)
    md_l, md_t = M("mark_marital_divorced",128.8,100.3)
    mw_l, mw_t = M("mark_marital_widowed", 173.4,105.0)
    mp_l, mp_t = M("mark_marital_separated",156.8,105.0)
    ry_l, ry_t = M("mark_resident_yes",   108.8,101.2)
    rn_l, rn_t = M("mark_resident_no",    96.2, 100.5)
    ky_l, ky_t = M("mark_kibbutz_yes",    88.4, 100.5)
    kn_l, kn_t = M("mark_kibbutz_no",     96.2, 105.1)
    hy_l, hy_t = M("mark_hmo_yes",        44.22,104.73)

    hf_l, hf_t, hf_w = L("health_fund_name", 145, 122.5, 32)
    sd_l, sd_t, sd_w = L("start_date", 10, 123, 30)

    # Section D income marks
    im_l, im_t = M("mark_income_monthly",    84.7,128.4)
    ia_l, ia_t = M("mark_income_additional", 84.7,132.6)
    ip_l, ip_t = M("mark_income_partial",    84.7,136.8)
    id2_l,id2_t= M("mark_income_daily",      84.7,141.2)
    ipe_l,ipe_t= M("mark_income_pension",    84.7,145.3)
    isc_l,isc_t= M("mark_income_scholarship",84.7,149.5)

    # Section C children
    cy = pos.get("child_y_rows", [131.4, 137.9, 145.7, 153.5, 161.2, 168.9])
    cnl = pos.get("child_name_left", 170.7)
    cnw = pos.get("child_name_width", 13.0)
    cil = pos.get("child_id_left", 133.7)
    ciw = pos.get("child_id_width", 25.0)
    cbl = pos.get("child_bd_left", 99.8)
    cbw = pos.get("child_bd_width", 34.0)
    # Custody / allowance checkboxes: right of name column
    ccu_l = pos.get("child_custody_left",   round(cnl + cnw + 4, 1))
    cal_l = pos.get("child_allowance_left", round(cnl + cnw + 0.5, 1))

    # Section E other income marks
    noi_l,noi_t = M("mark_no_other_income",  84.2,162.4)
    hoi_l,hoi_t = M("mark_has_other_income", 84.2,171.0)
    om_l, om_t  = M("mark_other_income_monthly",    84.2,175.4)
    od_l, od_t  = M("mark_other_income_daily",      42.6,175.4)
    oa_l, oa_t  = M("mark_other_income_additional", 84.2,179.2)
    ope_l,ope_t = M("mark_other_income_pension",    42.6,179.2)
    # partial / scholarship not in JSON → keep old fallback positions
    opl_l,opl_t = (84.2,183.1)
    osc_l,osc_t = (42.6,183.1)

    rw_l, rw_t  = M("mark_relief_wants",   83.87,191.33)
    rho_l,rho_t = M("mark_relief_has_other",83.87,199.55)
    nsf_l,nsf_t = M("mark_no_study_fund",  83.9, 208.1)
    np_l, np_t  = M("mark_no_pension",     83.7, 220.3)

    # Other income table
    oib_y  = pos.get("other_income_base_y",     222.0)
    oi_rs  = pos.get("other_income_row_spacing", 5.0)
    oity_l = pos.get("other_income_type_left",   61.0)
    oity_w = pos.get("other_income_type_width",  20.0)
    oinm_l = pos.get("other_income_name_left",  109.0)
    oinm_w = pos.get("other_income_name_width",  48.0)
    oiad_l = pos.get("other_income_addr_left",  109.0)
    oiad_w = pos.get("other_income_addr_width",  48.0)
    oifl_l = pos.get("other_income_file_left",   81.0)
    oifl_w = pos.get("other_income_file_width",  27.0)
    oiam_l = pos.get("other_income_amt_left",    35.0)
    oiam_w = pos.get("other_income_amt_width",   26.0)
    oitx_l = pos.get("other_income_tax_left",     9.0)
    oitx_w = pos.get("other_income_tax_width",   26.0)

    # Section F spouse
    sl_l, sl_t, sl_w = L("spouse_last_name",  140, 248, 42)
    sf_l, sf_t, sf_w = L("spouse_first_name", 103, 248, 37)
    si_l, si_t, si_w = L("spouse_id",         184, 248, 23)

    # Spouse checkboxes (not in JSON → keep old)
    sp_marks_old = {
        "no_spouse": (145.3, 255.1),
        "has_income":(100.4, 255.2),
        "work":      (57.2,  255.2),
        "other":     (29.2,  255.2),
    }

    # Declaration / signature
    dd_l, dd_t, dd_w = L("declaration_date", 55, 231.2, 40)
    si_img_l, si_img_t, _ = L("signature_img", 9, 235, 34)

    # ── Page 2 ────────────────────────────────────────────────────────────────
    r1_l,  r1_t  = M("mark_relief_1",  181, 16.5)
    r2_l,  r2_t  = M("mark_relief_2",  181, 21.7)
    r21_l, r21_t = M("mark_relief_2_1",181, 29.4)
    r3_l,  r3_t  = M("mark_relief_3",  181, 35.3)
    r4_l,  r4_t  = M("mark_relief_4",  181, 45.1)
    r5_l,  r5_t  = M("mark_relief_5",  181, 59.3)
    r6_l,  r6_t  = M("mark_relief_6",  181, 67.2)
    r7_l,  r7_t  = M("mark_relief_7",  181, 75.3)
    r8_l,  r8_t  = M("mark_relief_8",  181, 95.9)
    r9_l,  r9_t  = M("mark_relief_9",  181, 113.4)
    r11_l, r11_t = M("mark_relief_11", 181, 127.0)
    r12_l, r12_t = M("mark_relief_12", 181, 137.2)
    r13_l, r13_t = M("mark_relief_13", 181, 142.3)
    r14_l, r14_t = M("mark_relief_14", 181, 147.6)
    r15_l, r15_t = M("mark_relief_15", 181, 156.1)
    r16_l, r16_t = M("mark_relief_16", 181, 160.9)
    r17_l, r17_t = (181, 165.5)   # not in JSON → keep old

    r3d_l,  r3d_t,  r3d_w  = L("relief_3_date",    98,  42.2, 28)
    r3loc_l,r3loc_t,r3loc_w = L("relief_3_locality",80,  50.0, 36)
    r4d_l,  r4d_t,  r4d_w  = L("relief_4_date",   140,  49.7, 24)
    r4ni_l, r4ni_t, r4ni_w = L("relief_4_no_income",98, 57.4, 24)
    r14s_l, r14s_t, r14s_w = L("relief_14_start", 104, 181.2, 24)
    r14e_l, r14e_t, r14e_w = L("relief_14_end",    72, 181.2, 24)
    r16d_l, r16d_t, r16d_w = L("relief_16_days",  120, 199.6, 10)

    t1_l,  t1_t  = M("mark_t1_no_income",  181.5,171.9)
    t3_l,  t3_t  = M("mark_t3_approved",   181.5,210.1)

    # ── Build HTML ─────────────────────────────────────────────────────────────
    lines = []
    w = lines.append

    w('<!DOCTYPE html>')
    w('<html lang="he" dir="rtl">')
    w('<head>')
    w('  <meta charset="UTF-8" />')
    w('  <style>')
    w('    @page { size: A4; margin: 0; }')
    w('    html, body { margin:0; padding:0; direction: rtl; font-family: Arial, Helvetica, sans-serif; }')
    w('    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }')
    w('    .page { position: relative; width: 210mm; height: 297mm; page-break-after: always; overflow: hidden; }')
    w('    .page:last-child { page-break-after: auto; }')
    w('    .bg { position:absolute; inset:0; background-repeat:no-repeat; background-size:210mm 297mm; }')
    w('    .field { position:absolute; color:#111; font-size:9.5pt; line-height:1.05; white-space:nowrap; }')
    w('    .small { font-size:8.3pt; }')
    w('    .tiny { font-size:7.4pt; }')
    w('    .mark {')
    w('      position:absolute; color:#1f5fe0; font-size:18pt; line-height:1; font-weight:700;')
    w('      font-family:"Segoe Script","Comic Sans MS",cursive;')
    w('    }')
    w('    .sig { position:absolute; max-width:34mm; max-height:12mm; object-fit:contain; }')
    w('  </style>')
    w('</head>')
    w('<body>')
    w('<? ')
    w("  function s(v) { return v == null ? '' : String(v); }")
    w("  function nz(v) { return v ? String(v) : ''; }")
    w("  function yes(v) { return v === true || v === 'true' || v === 'כן' || v === 'on' || v === '1'; }")
    w("  function eq(a,b) { return String(a||'') === String(b||''); }")
    w('  function dmy(v) {')
    w("    if (!v) return '';")
    w("    var m = String(v).match(/^(\\d{4})-(\\d{2})-(\\d{2})$/);")
    w("    if (m) return m[3] + '/' + m[2] + '/' + m[1];")
    w('    return String(v);')
    w('  }')
    w('  function childAt(i) { return (data.children && data.children[i]) ? data.children[i] : {}; }')
    w('  function incAt(i) { return (data.additional_incomes && data.additional_incomes[i]) ? data.additional_incomes[i] : {}; }')
    w('  function chgAt(i) { return (data.changes && data.changes[i]) ? data.changes[i] : {}; }')
    w('  // pdf   → available from template.pdf   (set via createPDF → template.pdf   = pdfViewModel)')
    w('  // flags → available from template.flags (set via createPDF → template.flags = pdfViewModel.flags)')
    w("  // Do NOT redeclare them with 'var' — JS var-hoisting would shadow the template globals with undefined.")
    w('?>')
    w('')

    # ── Page 1 ────────────────────────────────────────────────────────────────
    w('<div class="page">')
    w(f'<div class="bg" style="background-image:url(\'data:image/jpeg;base64,{bg1_b64}\');"></div>')
    w('')
    w('  <!-- שנת מס -->')
    w(f'  <div class="field" style="left:{ty_l}mm; top:{ty_t}mm; width:{ty_w}mm; text-align:center; font-size:13pt; font-weight:bold;"><?= s(pdf.taxYear || data.taxYear) ?></div>')
    w('')
    w('  <!-- א. פרטי המעסיק -->')
    w(f'  <div class="field" style="left:{en_l}mm; top:{en_t}mm; width:{en_w}mm; text-align:right;"><?= s(pdf.employer_name || data.employer_name) ?></div>')
    w(f'  <div class="field small" style="left:{ea_l}mm; top:{ea_t}mm; width:{ea_w}mm; text-align:right;"><?= s(pdf.employer_address || data.employer_address) ?></div>')
    w(f'  <div class="field" style="left:{ep_l}mm; top:{ep_t}mm; width:{ep_w}mm; text-align:center;"><?= s(pdf.employer_phone || data.employer_phone) ?></div>')
    w(f'  <div class="field" style="left:{et_l}mm; top:{et_t}mm; width:{et_w}mm; text-align:center;"><?= s(pdf.employer_tax_id || data.employer_tax_id) ?></div>')
    w('')
    w('  <!-- ב. פרטי העובד -->')
    w(f'  <div class="field" style="left:{ln_l}mm; top:{ln_t}mm; width:{ln_w}mm; text-align:right;"><?= s(data.last_name) ?></div>')
    w(f'  <div class="field" style="left:{fn_l}mm; top:{fn_t}mm; width:{fn_w}mm; text-align:right;"><?= s(data.first_name) ?></div>')
    w(f'  <div class="field" style="left:{id_l}mm; top:{id_t}mm; width:{id_w}mm; text-align:center;"><?= s(data.id_number || data.passport_number) ?></div>')
    w(f'  <div class="field small" style="left:{bd_l}mm; top:{bd_t}mm; width:{bd_w}mm; text-align:center;"><?= dmy(data.birth_date) ?></div>')
    w(f'  <div class="field small" style="left:{al_l}mm; top:{al_t}mm; width:{al_w}mm; text-align:center;"><?= dmy(data.aliya_date) ?></div>')
    w('')
    w(f'  <div class="field small" style="left:{ad_l}mm; top:{ad_t}mm; width:{ad_w}mm; text-align:right;"><?= s(data.address) ?></div>')
    w(f'  <div class="field small" style="left:{pc_l}mm; top:{pc_t}mm; width:{pc_w}mm; text-align:center;"><?= s(data.postal_code) ?></div>')
    w(f'  <div class="field small" style="left:{em_l}mm; top:{em_t}mm; width:{em_w}mm; text-align:left;"><?= s(data.email) ?></div>')
    w(f'  <div class="field small" style="left:{mb_l}mm; top:{mb_t}mm; width:{mb_w}mm; text-align:center;"><?= s(data.mobile_phone) ?></div>')
    w('')
    w('  <!-- מין -->')
    w(f"  <? if (eq(data.gender,'זכר')) {{ ?> {mark(gm_l, gm_t)} <? }} ?>")
    w(f"  <? if (eq(data.gender,'נקבה')) {{ ?> {mark(gf_l, gf_t)} <? }} ?>")
    w('')
    w('  <!-- מצב משפחתי -->')
    w(f"  <? if (eq(data.marital_status,'רווק/ה')) {{ ?> {mark(ms_l, ms_t)} <? }} ?>")
    w(f"  <? if (eq(data.marital_status,'נשוי/אה')) {{ ?> {mark(mm_l, mm_t)} <? }} ?>")
    w(f"  <? if (eq(data.marital_status,'גרוש/ה')) {{ ?> {mark(md_l, md_t)} <? }} ?>")
    w(f"  <? if (eq(data.marital_status,'אלמן/ה')) {{ ?> {mark(mw_l, mw_t)} <? }} ?>")
    w(f"  <? if (eq(data.marital_status,'פרוד/ה')) {{ ?> {mark(mp_l, mp_t)} <? }} ?>")
    w('')
    w('  <!-- תושב ישראל -->')
    w(f"  <? if (eq(data.israeli_resident,'כן')) {{ ?> {mark(ry_l, ry_t)} <? }} ?>")
    w(f"  <? if (eq(data.israeli_resident,'לא')) {{ ?> {mark(rn_l, rn_t)} <? }} ?>")
    w('')
    w('  <!-- חבר קיבוץ -->')
    w(f"  <? if (eq(data.kibbutz_member,'כן')) {{ ?> {mark(ky_l, ky_t)} <? }} ?>")
    w(f"  <? if (eq(data.kibbutz_member,'לא')) {{ ?> {mark(kn_l, kn_t)} <? }} ?>")
    w('')
    w('  <!-- קופת חולים -->')
    w(f'  <div class="field small" style="left:{hf_l}mm; top:{hf_t}mm; width:{hf_w}mm; text-align:center;"><?= s(data.health_fund) ?></div>')
    w(f'  <? if (data.health_fund) {{ ?>{mark(hy_l, hy_t)}<? }} ?>')
    w('')
    w('  <!-- ד. תאריך תחילת עבודה -->')
    w(f'  <div class="field small" style="left:{sd_l}mm; top:{sd_t}mm; width:{sd_w}mm; text-align:center;"><?= dmy(data.start_date) ?></div>')
    w('')
    w('  <!-- ד. סוגי הכנסה מהמעסיק -->')
    w(f'  <? if (flags.income_type_monthly) {{ ?> {mark(im_l, im_t)} <? }} ?>')
    w(f'  <? if (flags.income_type_additional) {{ ?> {mark(ia_l, ia_t)} <? }} ?>')
    w(f'  <? if (flags.income_type_partial) {{ ?> {mark(ip_l, ip_t)} <? }} ?>')
    w(f'  <? if (flags.income_type_daily) {{ ?> {mark(id2_l, id2_t)} <? }} ?>')
    w(f'  <? if (flags.income_type_pension) {{ ?> {mark(ipe_l, ipe_t)} <? }} ?>')
    w(f'  <? if (flags.income_type_scholarship) {{ ?> {mark(isc_l, isc_t)} <? }} ?>')
    w('')
    w('  <!-- ג. ילדים - עד 6 שורות -->')
    cy_str = "[" + ", ".join(str(y) for y in cy) + "]"
    w(f'  <? var childY = {cy_str}; for (var i=0; i<6; i++) {{ var c = childAt(i); var y = childY[i]; ?>')
    w(f'    <div class="field tiny" style="left:{cnl}mm; top:<?= y ?>mm; width:{cnw}mm; text-align:right;"><?= s(c.name) ?></div>')
    w(f'    <div class="field tiny" style="left:{cil}mm; top:<?= y ?>mm; width:{ciw}mm; text-align:center;"><?= s(c.id) ?></div>')
    w(f'    <div class="field tiny" style="left:{cbl}mm; top:<?= y ?>mm; width:{cbw}mm; text-align:center;"><?= dmy(c.birth_date) ?></div>')
    w(f'    <? if (yes(c.in_custody)) {{?><div class="mark" style="left:{ccu_l}mm; top:<?= y-1.6 ?>mm;">✓</div><? }} ?>')
    w(f'    <? if (yes(c.receives_allowance)) {{?><div class="mark" style="left:{cal_l}mm; top:<?= y-1.6 ?>mm;">✓</div><? }} ?>')
    w('  <? } ?>')
    w('')
    w('  <!-- ה. הכנסות אחרות -->')
    w(f'  <? if (!data.has_other_income) {{ ?>{mark(noi_l, noi_t)}<? }} ?>')
    w(f'  <? if (data.has_other_income) {{ ?>{mark(hoi_l, hoi_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_monthly) {{ ?>{mark(om_l, om_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_daily) {{ ?>{mark(od_l, od_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_additional) {{ ?>{mark(oa_l, oa_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_pension) {{ ?>{mark(ope_l, ope_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_partial) {{ ?>{mark(opl_l, opl_t)}<? }} ?>')
    w(f'  <? if (flags.other_income_scholarship) {{ ?>{mark(osc_l, osc_t)}<? }} ?>')
    w(f'  <? if (flags.no_study_fund_other) {{ ?>{mark(nsf_l, nsf_t)}<? }} ?>')
    w(f'  <? if (flags.no_pension_other) {{ ?>{mark(np_l, np_t)}<? }} ?>')
    w(f'  <? if (flags.relief_wants) {{ ?>{mark(rw_l, rw_t)}<? }} ?>')
    w(f'  <? if (flags.relief_has_other) {{ ?>{mark(rho_l, rho_t)}<? }} ?>')
    w('')
    w('  <!-- טבלת הכנסות נוספות -->')
    w(f'  <? for (var i=0; i<3; i++) {{ var inc = incAt(i); var y2 = {oib_y} + (i*{oi_rs}); ?>')
    w(f'    <div class="field tiny" style="left:{oitx_l}mm;  top:<?= y2 ?>mm; width:{oitx_w}mm; text-align:center;"><?= s(inc.tax) ?></div>')
    w(f'    <div class="field tiny" style="left:{oiam_l}mm;  top:<?= y2 ?>mm; width:{oiam_w}mm; text-align:center;"><?= s(inc.amount) ?></div>')
    w(f'    <div class="field tiny" style="left:{oity_l}mm;  top:<?= y2 ?>mm; width:{oity_w}mm; text-align:center;"><?= s(inc.type) ?></div>')
    w(f'    <div class="field tiny" style="left:{oifl_l}mm;  top:<?= y2 ?>mm; width:{oifl_w}mm; text-align:center;"><?= s(inc.tax_id || \'\') ?></div>')
    w(f'    <div class="field tiny" style="left:{oinm_l}mm; top:<?= y2 ?>mm; width:{oinm_w}mm; text-align:right;"><?= s(inc.employer) ?> <?= s(inc.address) ?></div>')
    w('  <? } ?>')
    w('')
    w('  <!-- ו. בן/בת זוג -->')
    w(f"  <? if (!data.has_spouse) {{ ?>{mark(sp_marks_old['no_spouse'][0], sp_marks_old['no_spouse'][1])}<? }} ?>")
    w(f"  <? if (data.has_spouse && !eq(data.spouse_has_income,'לא')) {{ ?>{mark(sp_marks_old['has_income'][0], sp_marks_old['has_income'][1])}<? }} ?>")
    w(f'  <div class="field tiny" style="left:{sl_l}mm; top:{sl_t}mm; width:{sl_w}mm; text-align:right;"><?= s(data.spouse_last_name) ?></div>')
    w(f'  <div class="field tiny" style="left:{sf_l}mm; top:{sf_t}mm; width:{sf_w}mm; text-align:right;"><?= s(data.spouse_first_name) ?></div>')
    w(f'  <div class="field tiny" style="left:{si_l}mm; top:{si_t}mm; width:{si_w}mm; text-align:center;"><?= s(data.spouse_id_number || data.spouse_passport_number) ?></div>')
    w('  <div class="field tiny" style="left:66mm;  top:248mm; width:34mm; text-align:center;"><?= dmy(data.spouse_birth_date) ?></div>')
    w('  <div class="field tiny" style="left:33mm;  top:248mm; width:32mm; text-align:center;"><?= dmy(data.spouse_aliya_date) ?></div>')
    w(f"  <? if (eq(data.spouse_has_income,'לא')) {{ ?>{mark(sp_marks_old['no_spouse'][0], sp_marks_old['no_spouse'][1])}<? }} ?>")
    w(f"  <? if (eq(data.spouse_has_income,'עבודה')) {{ ?>{mark(sp_marks_old['work'][0], sp_marks_old['work'][1])}<? }} ?>")
    w(f"  <? if (eq(data.spouse_has_income,'אחר')) {{ ?>{mark(sp_marks_old['other'][0], sp_marks_old['other'][1])}<? }} ?>")
    w('')
    w('  <!-- ז. שינויים במהלך השנה -->')
    w('  <? for (var i=0; i<3; i++) { var ch = chgAt(i); var y3 = 274.4 + (i*9.0); ?>')
    w('    <div class="field tiny" style="left:10mm;  top:<?= y3 ?>mm; width:30mm;  text-align:right;"><?= s(ch.signature) ?></div>')
    w('    <div class="field tiny" style="left:41mm;  top:<?= y3 ?>mm; width:25mm;  text-align:center;"><?= dmy(ch.notification_date) ?></div>')
    w('    <div class="field tiny" style="left:67mm;  top:<?= y3 ?>mm; width:103mm; text-align:right; white-space:normal;"><?= s(ch.details) ?></div>')
    w('    <div class="field tiny" style="left:170mm; top:<?= y3 ?>mm; width:21mm;  text-align:center;"><?= dmy(ch.date) ?></div>')
    w('  <? } ?>')
    w('</div>')
    w('')

    # ── Page 2 ────────────────────────────────────────────────────────────────
    w('<div class="page">')
    w(f'<div class="bg" style="background-image:url(\'data:image/jpeg;base64,{bg2_b64}\');"></div>')
    w('')
    w('  <!-- מספר זהות / שנת מס -->')
    w('  <div class="field" style="left:103mm; top:7.2mm; width:36mm; text-align:center;"><?= s(data.id_number || data.passport_number) ?></div>')
    w('')
    w('  <!-- ח. הקלות מס - סימוני V -->')
    w(f'  <? if (flags.relief_1_resident) {{ ?>{mark(r1_l, r1_t)}<? }} ?>')
    w(f'  <? if (flags.relief_2_disabled) {{ ?>{mark(r2_l, r2_t)}<? }} ?>')
    w(f'  <? if (flags.relief_2_1_allowance) {{ ?>{mark(r21_l, r21_t)}<? }} ?>')
    w(f'  <? if (flags.relief_3_settlement) {{ ?>{mark(r3_l, r3_t)}<? }} ?>')
    w(f'  <div class="field tiny" style="left:{r3d_l}mm; top:{r3d_t}mm; width:{r3d_w}mm; text-align:center;"><?= dmy(pdf.relief_dates && pdf.relief_dates.relief_3_date) ?></div>')
    w('')
    w(f'  <? if (flags.relief_4_new_immigrant) {{ ?>{mark(r4_l, r4_t)}<? }} ?>')
    w(f'  <div class="field tiny" style="left:{r4d_l}mm; top:{r4d_t}mm; width:{r4d_w}mm; text-align:center;"><?= dmy(pdf.relief_dates && pdf.relief_dates.relief_4_date) ?></div>')
    w(f'  <div class="field tiny" style="left:{r4ni_l}mm; top:{r4ni_t}mm; width:{r4ni_w}mm; text-align:center;"><?= dmy(pdf.relief_dates && pdf.relief_dates.relief_4_no_income_until) ?></div>')
    w('')
    w(f'  <? if (flags.relief_5_spouse) {{ ?>{mark(r5_l, r5_t)}<? }} ?>')
    w(f'  <? if (flags.relief_6_single_parent) {{ ?>{mark(r6_l, r6_t)}<? }} ?>')
    w(f'  <? if (flags.relief_7_children_custody) {{ ?>{mark(r7_l, r7_t)}<? }} ?>')
    w(f'  <? if (flags.relief_8_children_general) {{ ?>{mark(r8_l, r8_t)}<? }} ?>')
    w(f'  <? if (flags.relief_9_sole_parent) {{ ?>{mark(r9_l, r9_t)}<? }} ?>')
    w('  <? if (flags.relief_10_children_not_custody) { ?><div class="mark" style="left:181mm; top:119.6mm;">✓</div><? } ?>')
    w(f'  <? if (flags.relief_11_disabled_children) {{ ?>{mark(r11_l, r11_t)}<? }} ?>')
    w(f'  <? if (flags.relief_12_alimony) {{ ?>{mark(r12_l, r12_t)}<? }} ?>')
    w(f'  <? if (flags.relief_13_age_16_18) {{ ?>{mark(r13_l, r13_t)}<? }} ?>')
    w(f'  <? if (flags.relief_14_discharged_soldier) {{ ?>{mark(r14_l, r14_t)}<? }} ?>')
    w(f'  <div class="field tiny" style="left:{r14s_l}mm; top:{r14s_t}mm; width:{r14s_w}mm; text-align:center;"><?= dmy(pdf.relief_dates && pdf.relief_dates.relief_14_start) ?></div>')
    w(f'  <div class="field tiny" style="left:{r14e_l}mm; top:{r14e_t}mm; width:{r14e_w}mm; text-align:center;"><?= dmy(pdf.relief_dates && pdf.relief_dates.relief_14_end) ?></div>')
    w('')
    w(f'  <? if (flags.relief_15_academic) {{ ?>{mark(r15_l, r15_t)}<? }} ?>')
    w(f'  <? if (flags.relief_16_reserve) {{ ?>{mark(r16_l, r16_t)}<? }} ?>')
    w(f'  <div class="field tiny" style="left:{r16d_l}mm; top:{r16d_t}mm; width:{r16d_w}mm; text-align:center;"><?= s(pdf.relief_dates && pdf.relief_dates.relief_16_days) ?></div>')
    w(f'  <? if (flags.relief_17_no_income) {{ ?>{mark(r17_l, r17_t)}<? }} ?>')
    w('')
    w('  <!-- ט. תיאום מס -->')
    w(f'  <? if (!data.has_tax_coordination) {{ ?>{mark(t1_l, t1_t)}<? }} ?>')
    w('  <? if (data.has_tax_coordination) { ?><div class="mark" style="left:181.5mm; top:182.1mm;">✓</div><? } ?>')
    w('  <? for (var i=0; i<3; i++) { var inc2 = incAt(i); var yy = 195.1 + (i*5.05); ?>')
    w('    <div class="field tiny" style="left:109mm; top:<?= yy ?>mm; width:48mm; text-align:right;"><?= s(inc2.employer) ?> <?= s(inc2.address) ?></div>')
    w('    <div class="field tiny" style="left:81mm;  top:<?= yy ?>mm; width:27mm; text-align:center;"><?= s(inc2.tax) ?></div>')
    w('    <div class="field tiny" style="left:61mm;  top:<?= yy ?>mm; width:20mm; text-align:center;"><?= s(inc2.type) ?></div>')
    w('    <div class="field tiny" style="left:35mm;  top:<?= yy ?>mm; width:26mm; text-align:center;"><?= s(inc2.amount) ?></div>')
    w('    <div class="field tiny" style="left:9mm;   top:<?= yy ?>mm; width:26mm; text-align:center;"><?= s(inc2.tax_amount || \'\') ?></div>')
    w('  <? } ?>')
    w(f'  <? if (data.tax_coordination_approved) {{ ?>{mark(t3_l, t3_t)}<? }} ?>')
    w('')
    w('  <!-- י. הצהרה -->')
    w('  <? if (data.confirm_declaration) { ?><div class="mark" style="left:181mm; top:220mm;">✓</div><? } ?>')
    w(f'  <div class="field small" style="left:{dd_l}mm; top:{dd_t}mm; width:{dd_w}mm; text-align:center;"><?= dmy(data.declaration_date) ?></div>')
    w('  <div class="field small" style="left:100mm; top:231.2mm; width:60mm; text-align:center;"><?= s(data.last_name) ?> <?= s(data.first_name) ?></div>')
    w(f'  <? if (data.signature) {{ ?><img class="sig" style="left:{si_img_l}mm; top:{si_img_t}mm;" src="<?= data.signature ?>" /><? }} ?>')
    w('</div>')
    w('</body>')
    w('</html>')

    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"PDF: {PDF_PATH}")
    print(f"Scale: SX={SX:.5f} mm/px, SY={SY:.5f} mm/px")
    print(f"Page: {PAGE_W_PTS:.1f} × {PAGE_H_PTS:.1f} pts = {SCAN_W_MM:.1f} × {SCAN_H_MM:.1f} mm")
    print()

    print("Computing field positions...")
    pos = compute_positions()
    print_report(pos)

    print("\nExtracting background images...")
    bgs = extract_backgrounds()
    print()

    print("Generating new PDFTemplate_v6.html...")
    html = build_html(pos, bgs[0], bgs[1])
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = len(html.encode("utf-8")) / 1024
    print(f"Written: {OUT_HTML}  ({size_kb:.0f} KB)")
    print("\nDone! Review PDFTemplate_v6.html and run the pipeline to verify.")
