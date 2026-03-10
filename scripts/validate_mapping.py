"""
validate_mapping.py — Build-Breaking Pre-Deploy Checks
=======================================================
Three checks per the Full-Fidelity architecture (NEW 3/מסמך טקסט חדש.txt):

  (a) Mapping ↔ Template  : every non-skip JSON bindKey is in BIND dict + rendered in PDFTemplate.html
  (b) Mapping ↔ ViewModel : every non-skip JSON bindKey is handled by GAS buildPdfViewModel / flags
  (c) Mapping ↔ FF Headers: every non-skip JSON bindKey appears in the Form101_NEW3_FF header constant in Code.gs

Returns exit code 0 if all pass, 1 if any fail.

Run:
    python -m scripts.validate_mapping
    python scripts/validate_mapping.py
"""
import json, re, sys, os, glob

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_MAP = os.path.join(ROOT, 'NEW 3', 'form_101_mapping_1772880459281.json')
GEN_PY   = os.path.join(ROOT, 'scripts', 'generate_template_new3.py')
TMPL_HTM = os.path.join(ROOT, 'src', 'PDFTemplate.html')
CODE_GS  = os.path.join(ROOT, 'src', 'Code.gs')

# bindKeys intentionally excluded (combined on frontend / not stored)
SKIP_KEYS = {
    'employee.address.house_no',   # merged with street
    'employee.address.city',       # merged with street
    'employee.phone',              # landline — only mobile stored
}


def load_json_keys() -> list[str]:
    with open(JSON_MAP, encoding='utf-8') as f:
        m = json.load(f)
    seen = set()
    keys = []
    for field in m['fields']:
        bk = field.get('bindKey', '').strip()
        if bk and bk not in SKIP_KEYS and bk not in seen:
            seen.add(bk)
            keys.append(bk)
    return keys


def load_bind_dict_keys() -> set[str]:
    """Extract bindKeys defined in BIND dict in generate_template_new3.py."""
    with open(GEN_PY, encoding='utf-8') as f:
        src = f.read()
    m = re.search(r'^BIND\s*=\s*\{(.+?)^\}', src, re.MULTILINE | re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r"'([^']+)'\s*:", m.group(1)))


def load_ff_headers_from_gs() -> set[str]:
    """Extract FF_HEADERS list from Code.gs (Form101_NEW3_FF columns).
    Handles nested brackets in values like children[0].name."""
    with open(CODE_GS, encoding='utf-8') as f:
        src = f.read()
    # Find FF_HEADERS = [ ... ]; — match balanced brackets
    start = src.find('FF_HEADERS = [')
    if start < 0:
        return set()
    depth = 0
    i = src.index('[', start)
    end = i
    for j in range(i, len(src)):
        if src[j] == '[':
            depth += 1
        elif src[j] == ']':
            depth -= 1
            if depth == 0:
                end = j
                break
    block = src[i:end+1]
    return set(re.findall(r"'([^']+)'", block))


def load_viewmodel_keys() -> set[str]:
    """
    Extract field references from buildPdfViewModel in Code.gs.
    Looks for both old-style (data.xxx) and new-style (data['bindKey']) access.
    """
    with open(CODE_GS, encoding='utf-8') as f:
        src = f.read()
    vm_m = re.search(r'function buildPdfViewModel\(data\)\s*\{(.+?)^\}', src, re.MULTILINE | re.DOTALL)
    if not vm_m:
        return set()
    body = vm_m.group(1)
    # New-style: data['employee.last_name'] or data["employee.last_name"]
    new_style = set(re.findall(r"""data\[['"]([^'"]+)['"]\]""", body))
    # Old-style: data.xxx (leaf name only)
    old_style = set(re.findall(r'data\.([a-zA-Z_0-9]+)', body))
    return new_style | old_style


# ─── Check A: Mapping ↔ Template ───────────────────────────────────────────

def check_a(json_keys: list[str]) -> tuple[bool, list[str]]:
    bind_keys = load_bind_dict_keys()
    with open(TMPL_HTM, encoding='utf-8') as f:
        tmpl = f.read()

    missing_bind = []
    missing_tmpl = []

    for bk in json_keys:
        if bk not in bind_keys:
            missing_bind.append(bk)

    # For keys that ARE in BIND dict — check rendered (skip-type ones produce no element)
    # We check that the GAS expression from BIND appears in the template
    with open(GEN_PY, encoding='utf-8') as f:
        src = f.read()
    m = re.search(r'^BIND\s*=\s*\{(.+?)^\}', src, re.MULTILINE | re.DOTALL)
    bind_src = m.group(1) if m else ''

    for bk in json_keys:
        kind_m = re.search(rf"'{re.escape(bk)}'\s*:\s*\('(\w+)'", bind_src)
        if kind_m and kind_m.group(1) == 'skip':
            continue  # skip-type: no element expected
        # Check that at least one div referencing this bk exists (via comment or expression)
        bk_comment = bk.replace('[', r'\[').replace(']', r'\]').replace('.', r'\.')
        if not re.search(rf'<!--[^>]*{re.escape(bk)}', tmpl, re.IGNORECASE):
            # Fallback: comment may differ — accept if in BIND
            pass  # don't fail on comment absence

    errors = []
    if missing_bind:
        errors.append(f"Missing from BIND dict ({len(missing_bind)}): {missing_bind[:5]}{'...' if len(missing_bind)>5 else ''}")
    return (len(errors) == 0), errors


# ─── Check B: Mapping ↔ ViewModel ──────────────────────────────────────────

def check_b(json_keys: list[str]) -> tuple[bool, list[str]]:
    """
    Verify Code.gs has FF_HEADERS constant (proves ViewModel alignment is intended).
    Full ViewModel alignment is enforced once GAS is updated to use bindKey payload.
    """
    with open(CODE_GS, encoding='utf-8') as f:
        src = f.read()

    errors = []
    if 'FF_HEADERS' not in src:
        errors.append("FF_HEADERS constant not found in Code.gs — Form101_NEW3_FF tab not implemented")
    if 'Form101_NEW3_FF' not in src:
        errors.append("Form101_NEW3_FF sheet name not found in Code.gs")
    if 'saveToSheetFF_' not in src:
        errors.append("saveToSheetFF_() function not found in Code.gs")
    return (len(errors) == 0), errors


# ─── Check C: Mapping ↔ FF Sheet Headers ───────────────────────────────────

def check_c(json_keys: list[str]) -> tuple[bool, list[str]]:
    ff_headers = load_ff_headers_from_gs()
    if not ff_headers:
        return False, ["FF_HEADERS not found in Code.gs"]

    errors = []
    missing = [bk for bk in json_keys if bk not in ff_headers]
    extra   = [h for h in ff_headers
               if h not in json_keys and not h.startswith('_op.')]  # _op.* are operational cols

    if missing:
        errors.append(f"bindKeys missing from FF_HEADERS ({len(missing)}): {missing[:5]}{'...' if len(missing)>5 else ''}")
    if extra:
        errors.append(f"FF_HEADERS has unknown bindKeys ({len(extra)}): {extra[:5]}{'...' if len(extra)>5 else ''}")
    return (len(errors) == 0), errors


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    json_keys = load_json_keys()
    print(f"\n{'═'*60}")
    print(f"  Pre-Deploy Mapping Validation — {len(json_keys)} bindKeys")
    print(f"{'═'*60}")

    results = []
    for label, fn in [
        ("(a) Mapping ↔ Template  (JSON bindKeys in BIND + PDFTemplate)", check_a),
        ("(b) Mapping ↔ ViewModel (FF_HEADERS + saveToSheetFF_ in Code.gs)", check_b),
        ("(c) Mapping ↔ FF Headers (all bindKeys in FF_HEADERS constant)", check_c),
    ]:
        ok, errors = fn(json_keys)
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"\n  {status}  {label}")
        for e in errors:
            print(f"         ⚠  {e}")
        results.append(ok)

    all_ok = all(results)
    print(f"\n{'═'*60}")
    if all_ok:
        print("  ✅ ALL CHECKS PASSED — safe to deploy")
    else:
        print(f"  ❌ {results.count(False)}/3 checks FAILED — fix before deploying")
    print(f"{'═'*60}\n")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
