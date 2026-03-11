"""
Full automation pipeline:
  1. Deploy (clasp push + clasp deploy)
  2. Fill & submit form (Playwright)
  3. Verify Sheet + PDF (via GAS endpoints)
  4. Verify Make Scenario B webhook (skipped if MAKE_WEBHOOK_URL not configured)
  5. Verify Make Scenario A invite webhook (skipped if MAKE_INVITE_WEBHOOK_URL not configured)

Usage:
    python -m scripts.pipeline                   # full pipeline
    python -m scripts.pipeline --no-deploy       # skip step 1
    python -m scripts.pipeline --verify-only     # step 3 only (reads state file)
    python -m scripts.pipeline --visible         # show browser window
    python -m scripts.pipeline --no-make         # skip both Make webhook steps
    python -m scripts.pipeline --comprehensive   # add full-section PDF verification step
    python -m scripts.pipeline --visual-qa       # add Claude visual QA step (needs ANTHROPIC_API_KEY + poppler)
    python -m scripts.pipeline --validate-pdf-endpoint  # test GAS validatePdf endpoint (skipped if no API key)

State between steps is stored in .pipeline_state.json
"""
import sys, json, os, time
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / ".pipeline_state.json"


# ── steps ─────────────────────────────────────────────────────────────────────

def step_deploy() -> bool:
    from scripts.deploy import run as deploy_run
    try:
        deploy_run()
        time.sleep(5)   # give GAS a moment to propagate the new version
        return True
    except Exception as e:
        print(f"  ❌ Deploy error: {e}")
        return False


def step_test(headless: bool = True) -> bool:
    from scripts.test_form import run_form_test
    result = run_form_test(headless=headless)
    if result and result.get("success"):
        STATE_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  State saved → {STATE_FILE}")
        return True
    return False


def step_verify() -> bool:
    if not STATE_FILE.exists():
        print("  ❌ No state file — run the test step first")
        return False

    state = json.loads(STATE_FILE.read_text())
    file_id = state.get("fileId")
    if not file_id:
        print("  ❌ fileId missing from state")
        return False

    from scripts.verify import verify_sheet, download_pdf, verify_pdf
    sheet_ok = verify_sheet()
    pdf_bytes = download_pdf(file_id)
    pdf_ok = verify_pdf(pdf_bytes) if pdf_bytes else False
    return sheet_ok and pdf_ok


def step_verify_confirm() -> bool:
    """
    Tests the doGet?action=confirmSubmission endpoint.
    Simulates the callback that Make sends back to GAS after delivering the WhatsApp message.
    In production Make calls this URL automatically; here we call it ourselves to verify
    the endpoint works and the sheet status is updated correctly.
    """
    if not STATE_FILE.exists():
        print("  ❌ No state file — run the test step first")
        return False

    state = json.loads(STATE_FILE.read_text())
    row_num = state.get("rowNum")
    if not row_num:
        print("  ❌ rowNum missing from state")
        return False

    from scripts.verify import verify_confirm_submission
    return verify_confirm_submission(int(row_num))


def step_verify_comprehensive() -> bool:
    """
    Posts TEST_DATA_FULL directly to GAS (no Playwright) and runs comprehensive
    PDF + sheet verification covering all form sections.
    """
    from scripts.test_pdf_direct import run_direct_test
    from scripts.verify import verify_sheet_comprehensive, verify_pdf_comprehensive

    result, pdf_bytes = run_direct_test(save_state=False)
    if not result.get("success"):
        print("  ❌ Direct API test failed — cannot run comprehensive verification")
        return False

    sheet_ok = verify_sheet_comprehensive(result.get("rowNum"))
    pdf_ok = verify_pdf_comprehensive(pdf_bytes) if pdf_bytes else False

    if sheet_ok and pdf_ok:
        print("\n  ✅ Comprehensive verification PASSED")
    else:
        print("\n  ❌ Comprehensive verification FAILED — see above")
    return sheet_ok and pdf_ok


def step_visual_qa() -> bool:
    """
    Runs Claude visual QA on the PDF from the last pipeline run.
    Skipped silently if ANTHROPIC_API_KEY is not set or poppler is unavailable.
    """
    import json, base64
    from pathlib import Path
    import requests

    # Try comprehensive state file first, then basic state file
    for sf in [".pipeline_state_full.json", ".pipeline_state.json"]:
        p = Path(__file__).parent.parent / sf
        if p.exists():
            state = json.loads(p.read_text())
            file_id = state.get("fileId")
            if file_id:
                break
    else:
        print("  ❌ No state file with fileId found — run a test step first")
        return False

    from scripts.config import APPS_SCRIPT_URL
    try:
        r = requests.get(
            APPS_SCRIPT_URL,
            params={"action": "getPdf", "id": file_id},
            timeout=60,
        )
        result = r.json()
        if not result.get("success"):
            print(f"  ❌ PDF download error: {result.get('error')}")
            return False
        pdf_bytes = base64.b64decode(result["data"])
    except Exception as e:
        print(f"  ❌ PDF download failed: {e}")
        return False

    from scripts.validate_claude import run_visual_qa
    _, passed = run_visual_qa(pdf_bytes)
    return passed


def step_validate_pdf_endpoint() -> bool:
    """
    Tests the GAS ?action=validatePdf endpoint using the last pipeline PDF fileId.
    Skipped silently if ANTHROPIC_API_KEY is not set (returns True — not a failure).
    Reads fileId from .pipeline_state_full.json or .pipeline_state.json.
    """
    from pathlib import Path
    import requests
    from scripts.config import APPS_SCRIPT_URL, ANTHROPIC_API_KEY

    print("\n[VALIDATE PDF ENDPOINT]")

    # Locate the most recent state file with a fileId
    file_id = None
    for sf in [".pipeline_state_full.json", ".pipeline_state.json"]:
        p = Path(__file__).parent.parent / sf
        if p.exists():
            try:
                state = json.loads(p.read_text())
                file_id = state.get("fileId")
                if file_id:
                    break
            except Exception:
                pass

    if not file_id:
        print("  ❌ No state file with fileId found — run a test step first")
        return False

    print(f"  fileId: {file_id}")

    try:
        r = requests.get(
            APPS_SCRIPT_URL,
            params={"action": "validatePdf", "fileId": file_id},
            timeout=120,
        )
        result = r.json()
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return False

    if not result.get("success"):
        print(f"  ❌ GAS error: {result.get('error')}")
        return False

    if result.get("skipped"):
        print("  ⏭  validatePdf skipped — ANTHROPIC_API_KEY not configured in GAS (pass)")
        if not ANTHROPIC_API_KEY:
            print("     Tip: set ANTHROPIC_API_KEY env var + GAS Script Property to enable QA")
        return True

    quality = result.get("quality", 0)
    passed  = result.get("passed", False)
    summary = result.get("summary", "")
    issues  = result.get("issues", [])

    if passed:
        print(f"  ✅ Quality: {quality}/10 — {summary}")
        if issues:
            print(f"     Minor issues ({len(issues)}):")
            for iss in issues:
                print(f"       • [p{iss.get('page','-')}] {iss.get('field','?')}: {iss.get('problem','')}")
        return True
    else:
        print(f"  ❌ Quality: {quality}/10 (below threshold 8) — {summary}")
        for iss in issues:
            print(f"     • [p{iss.get('page','-')}] {iss.get('field','?')}: {iss.get('problem','')}")
        return False


def step_verify_make() -> bool:
    from scripts.config import MAKE_WEBHOOK_URL
    print("\n[VERIFY MAKE — Scenario B (form submitted)]")

    if not MAKE_WEBHOOK_URL or not MAKE_WEBHOOK_URL.strip():
        print("  ⏭  MAKE_WEBHOOK_URL not configured in scripts/config.py — skipped")
        print("     Set MAKE_WEBHOOK_URL to enable Make.com Scenario B verification.")
        return True  # not a failure — just unconfigured

    import requests
    try:
        r = requests.post(
            MAKE_WEBHOOK_URL,
            json={"test": True, "source": "form101-pipeline", "message": "webhook reachability check"},
            timeout=15,
        )
        if r.status_code in (200, 204):
            print(f"  ✅ Scenario B webhook reachable — status {r.status_code}")
            return True
        else:
            print(f"  ❌ Scenario B webhook returned status {r.status_code}: {r.text[:120]}")
            return False
    except Exception as e:
        print(f"  ❌ Scenario B webhook error: {e}")
        return False


def step_verify_scenario_a() -> bool:
    """
    Tests Make Scenario A (employee invite) via the GAS notifyEmployee endpoint.
    The endpoint calls notifyNewEmployee_() which POSTs to MAKE_INVITE_WEBHOOK_URL.
    Skipped (not a failure) if MAKE_INVITE_WEBHOOK_URL is not configured.
    """
    from scripts.config import MAKE_INVITE_WEBHOOK_URL, APPS_SCRIPT_URL
    print("\n[VERIFY MAKE — Scenario A (invite employee)]")

    if not MAKE_INVITE_WEBHOOK_URL or not MAKE_INVITE_WEBHOOK_URL.strip():
        print("  ⏭  MAKE_INVITE_WEBHOOK_URL not configured in scripts/config.py — skipped")
        print("     Set MAKE_INVITE_WEBHOOK_URL to enable Make.com Scenario A verification.")
        return True  # not a failure — just unconfigured

    import requests
    try:
        r = requests.get(
            APPS_SCRIPT_URL,
            params={
                "action":   "notifyEmployee",
                "rowNum":   "0",
                "name":     "בדיקה אוטומטית",
                "phone":    "0524669515",
                "employer": "חברת בדיקות",
                "taxYear":  "2026",
            },
            timeout=30,
        )
        result = r.json()
    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return False

    if result.get("success") and result.get("sent"):
        to = result.get("to", "?")
        print(f"  ✅ Scenario A invite sent via GAS — to: {to}")
        return True
    else:
        print(f"  ❌ Scenario A failed: {result}")
        return False


# ── runner ────────────────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")


def main() -> None:
    args = sys.argv[1:]
    no_deploy            = "--no-deploy"            in args
    verify_only          = "--verify-only"          in args
    no_make              = "--no-make"              in args
    headless             = "--visible"              not in args
    comprehensive        = "--comprehensive"        in args
    visual_qa            = "--visual-qa"            in args
    validate_pdf_ep      = "--validate-pdf-endpoint" in args

    steps: list[tuple[str, callable]] = []

    if not (no_deploy or verify_only):
        steps.append(("Deploy to Apps Script", step_deploy))

    if not verify_only:
        steps.append(("Fill & submit form (Playwright)", lambda: step_test(headless)))

    steps.append(("Verify Sheet + PDF", step_verify))
    steps.append(("Test confirmSubmission callback", step_verify_confirm))

    if comprehensive:
        steps.append(("Comprehensive PDF verification (all sections)", step_verify_comprehensive))

    if visual_qa:
        steps.append(("Claude visual QA", step_visual_qa))

    if validate_pdf_ep:
        steps.append(("Test validatePdf GAS endpoint", step_validate_pdf_endpoint))

    if not no_make:
        steps.append(("Verify Make — Scenario B (form submitted)", step_verify_make))
        steps.append(("Verify Make — Scenario A (invite employee)", step_verify_scenario_a))

    overall = True
    for name, func in steps:
        _banner(f"STEP: {name}")
        ok = func()
        if not ok:
            _banner(f"✗ PIPELINE FAILED at: {name}")
            overall = False
            break

    if overall:
        _banner("✅ PIPELINE COMPLETE — ALL STEPS PASSED")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
