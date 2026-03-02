"""
Full automation pipeline:
  1. Deploy (clasp push + clasp deploy)
  2. Fill & submit form (Playwright)
  3. Verify Sheet + PDF (via GAS endpoints)
  4. Verify Make webhook (skipped if MAKE_WEBHOOK_URL not configured)

Usage:
    python -m scripts.pipeline                   # full pipeline
    python -m scripts.pipeline --no-deploy       # skip step 1
    python -m scripts.pipeline --verify-only     # step 3 only (reads state file)
    python -m scripts.pipeline --visible         # show browser window
    python -m scripts.pipeline --no-make         # skip Make webhook step

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


def step_verify_make() -> bool:
    from scripts.config import MAKE_WEBHOOK_URL
    print("\n[VERIFY MAKE]")

    if not MAKE_WEBHOOK_URL or not MAKE_WEBHOOK_URL.strip():
        print("  ⏭  MAKE_WEBHOOK_URL not configured in scripts/config.py — skipped")
        print("     Set MAKE_WEBHOOK_URL to enable Make.com verification.")
        return True  # not a failure — just unconfigured

    import requests
    try:
        r = requests.post(
            MAKE_WEBHOOK_URL,
            json={"test": True, "source": "form101-pipeline", "message": "webhook reachability check"},
            timeout=15,
        )
        if r.status_code in (200, 204):
            print(f"  ✅ Make webhook reachable — status {r.status_code}")
            return True
        else:
            print(f"  ❌ Make webhook returned status {r.status_code}: {r.text[:120]}")
            return False
    except Exception as e:
        print(f"  ❌ Make webhook error: {e}")
        return False


# ── runner ────────────────────────────────────────────────────────────────────

def _banner(title: str) -> None:
    print(f"\n{'═' * 55}")
    print(f"  {title}")
    print(f"{'═' * 55}")


def main() -> None:
    args = sys.argv[1:]
    no_deploy    = "--no-deploy"    in args
    verify_only  = "--verify-only"  in args
    no_make      = "--no-make"      in args
    headless     = "--visible"      not in args

    steps: list[tuple[str, callable]] = []

    if not (no_deploy or verify_only):
        steps.append(("Deploy to Apps Script", step_deploy))

    if not verify_only:
        steps.append(("Fill & submit form (Playwright)", lambda: step_test(headless)))

    steps.append(("Verify Sheet + PDF", step_verify))
    steps.append(("Test confirmSubmission callback", step_verify_confirm))

    if not no_make:
        steps.append(("Verify Make webhook", step_verify_make))

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
