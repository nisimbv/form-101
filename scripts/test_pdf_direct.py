"""
Direct API test: POST TEST_DATA_FULL directly to GAS doPost (no Playwright).
Returns (result_dict, pdf_bytes) for use by comprehensive verification.

Usage:
    python -m scripts.test_pdf_direct
"""
import json, base64, sys
from pathlib import Path
import requests

STATE_FILE = Path(__file__).parent.parent / ".pipeline_state_full.json"


def run_direct_test(data: dict | None = None, save_state: bool = True) -> tuple[dict, bytes | None]:
    """
    POST data to GAS doPost and download the generated PDF.

    Returns:
        (result_dict, pdf_bytes)
        result_dict has at least: success, rowNum, fileId
        pdf_bytes is None if the PDF could not be retrieved.
    """
    from scripts.config import APPS_SCRIPT_URL, TEST_DATA_FULL

    payload = data or TEST_DATA_FULL

    print("\n[DIRECT API TEST]")
    print(f"  Posting to: {APPS_SCRIPT_URL}")
    print(f"  Fields: {len(payload)}")

    # GAS doPost expects Content-Type: text/plain to avoid CORS preflight
    try:
        r = requests.post(
            APPS_SCRIPT_URL,
            data=json.dumps(payload, ensure_ascii=False),
            headers={"Content-Type": "text/plain"},
            timeout=60,
        )
        r.raise_for_status()
        result = r.json()
    except Exception as e:
        print(f"  ❌ POST failed: {e}")
        return {"success": False, "error": str(e)}, None

    if not result.get("success"):
        print(f"  ❌ GAS error: {result.get('error')}")
        return result, None

    row_num = result.get("rowNum")
    file_id = result.get("fileId")
    print(f"  ✅ GAS accepted — rowNum={row_num}, fileId={file_id}")

    if save_state:
        STATE_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  State saved → {STATE_FILE}")

    # Download PDF
    pdf_bytes = None
    if file_id:
        try:
            r2 = requests.get(
                APPS_SCRIPT_URL,
                params={"action": "getPdf", "id": file_id},
                timeout=60,
            )
            r2.raise_for_status()
            pdf_result = r2.json()
            if pdf_result.get("success"):
                pdf_bytes = base64.b64decode(pdf_result["data"])
                print(f"  ✅ PDF downloaded — {len(pdf_bytes):,} bytes  ({pdf_result.get('name', '')})")
            else:
                print(f"  ❌ PDF download error: {pdf_result.get('error')}")
        except Exception as e:
            print(f"  ❌ PDF download failed: {e}")

    return result, pdf_bytes


def main() -> None:
    result, pdf_bytes = run_direct_test()
    if not result.get("success"):
        print("\n❌ DIRECT TEST FAILED")
        sys.exit(1)
    if pdf_bytes is None:
        print("\n⚠  Submission succeeded but PDF could not be downloaded")
        sys.exit(1)
    print(f"\n✅ DIRECT TEST PASSED — rowNum={result.get('rowNum')}")
    # Optionally save PDF to disk for inspection
    out = Path(__file__).parent.parent / "test_output_full.pdf"
    out.write_bytes(pdf_bytes)
    print(f"  PDF saved → {out}")


if __name__ == "__main__":
    main()
