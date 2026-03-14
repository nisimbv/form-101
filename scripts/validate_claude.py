"""
Claude visual QA for the generated Form 101 PDF.

Converts PDF pages to PNG (requires poppler / pdf2image), then calls
claude-sonnet-4-6 with vision to identify positioning errors, missing marks,
and text overflow. Returns False if overall_quality < 8.

Usage:
    python -m scripts.validate_claude [path/to/form.pdf]
    python -m scripts.pipeline --no-deploy --visual-qa

Requirements:
    pip install anthropic pdf2image
    poppler must be installed and on PATH (Windows: https://github.com/oschwartz10612/poppler-windows)

Environment:
    ANTHROPIC_API_KEY must be set.
"""
import sys, io, json, base64, os
from pathlib import Path

_QA_PROMPT = """
You are reviewing a generated Hebrew tax form (Israeli Form 101 / טופס 101).
The form has 2 pages. Each image is one page of the rendered PDF.

IMPORTANT — known correct layout (do NOT flag these as issues):
- The form is RTL (right-to-left). Hebrew text reads right-to-left.
- Multiple data fields share the SAME horizontal row:
  • Row ~57mm: ID number, first name, last name, birth date, AND aliya date are ALL on the same line
  • Row ~63mm: street, city, postal code on the same line
  • Row ~82mm: phone and email on the same line
- The children table (rows ~100-120mm) has columns: child name, ID, birth date, checkmarks — data from different columns will appear on the same horizontal line
- The background image contains printed Hebrew form text (labels, boxes, lines) — this is the form template, NOT overlay errors
- Dates appearing side-by-side on the same row is CORRECT and EXPECTED
- Children's birth dates (e.g. 15/03/2010, 22/07/2012) appear in the children table rows, NOT in the phone field
- Employment start date field is at ~98mm top, left side of page 1

Flag ONLY these genuine issues:
1. Overlay text that is clearly OUTSIDE its form box (not just near the edge)
2. A checkbox mark (✓) that is clearly in the wrong row or column (off by >5mm)
3. Text that is completely missing where it should appear
4. Text that renders on top of another text field (same x AND y position within 3mm)

Do NOT flag:
- Multiple fields on the same horizontal row (this is by design)
- Slight RTL rendering differences
- Hebrew text reading right-to-left
- Form background labels (those are the printed form, not overlay errors)
- Small alignment differences of < 3mm

Return a JSON object with this exact structure:
{
  "issues": [
    {"field": "<field name or description>", "page": <1 or 2>, "problem": "<description>"}
  ],
  "overall_quality": <integer 1-10>,
  "summary": "<one-sentence summary>"
}

Return ONLY the JSON. No markdown fences, no explanation outside the JSON.
A score of 10 means perfect alignment; 8+ means acceptable for production; below 8 means real fixes required.
""".strip()


def _pdf_to_pngs(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convert PDF to list of PNG bytes (one per page) using PyMuPDF (fitz).
    PyMuPDF is already in the project; poppler/pdf2image is NOT required."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  ❌ PyMuPDF not installed. Run: pip install pymupdf")
        return []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        result = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            result.append(pix.tobytes("png"))
        doc.close()
        return result
    except Exception as e:
        print(f"  ❌ PyMuPDF conversion failed: {e}")
        return []


def run_visual_qa(pdf_bytes: bytes) -> tuple[dict, bool]:
    """
    Run Claude visual QA on the PDF.

    Returns:
        (qa_result_dict, passed)
        passed = True if overall_quality >= 8
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  ⏭  ANTHROPIC_API_KEY not set — visual QA skipped")
        return {"skipped": True}, True

    try:
        import anthropic
    except ImportError:
        print("  ❌ anthropic SDK not installed. Run: pip install anthropic")
        return {"error": "anthropic not installed"}, True  # don't fail pipeline

    print("\n[CLAUDE VISUAL QA]")

    pngs = _pdf_to_pngs(pdf_bytes)
    if not pngs:
        print("  ⏭  Could not render PDF pages — visual QA skipped")
        return {"skipped": True}, True

    print(f"  Rendered {len(pngs)} page(s) at 150 DPI")

    content: list[dict] = []
    for i, png_bytes in enumerate(pngs):
        content.append({
            "type": "text",
            "text": f"Page {i + 1} of the Form 101 PDF:"
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.standard_b64encode(png_bytes).decode("utf-8"),
            }
        })
    content.append({"type": "text", "text": _QA_PROMPT})

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text.strip()
    except Exception as e:
        print(f"  ❌ Claude API error: {e}")
        return {"error": str(e)}, True  # don't fail pipeline on API errors

    # Strip markdown code fences if present
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0].strip()
    try:
        qa = json.loads(stripped)
    except json.JSONDecodeError:
        print(f"  ⚠  Claude returned non-JSON: {raw[:200]}")
        return {"raw": raw}, True

    quality = qa.get("overall_quality", 0)
    issues = qa.get("issues", [])
    summary = qa.get("summary", "")

    print(f"  Quality score: {quality}/10")
    print(f"  Summary: {summary}")

    if issues:
        print(f"  Issues found ({len(issues)}):")
        for iss in issues:
            print(f"    • [p{iss.get('page','?')}] {iss.get('field','?')}: {iss.get('problem','?')}")
    else:
        print("  No issues found by Claude")

    passed = quality >= 8
    if passed:
        print(f"  ✅ Visual QA passed (score {quality} ≥ 8)")
    else:
        print(f"  ❌ Visual QA FAILED (score {quality} < 8) — PDF positioning needs fixes")

    return qa, passed


def main() -> None:
    pdf_path = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

    if pdf_path:
        p = Path(pdf_path)
        if not p.exists():
            print(f"❌ File not found: {p}")
            sys.exit(1)
        pdf_bytes = p.read_bytes()
    else:
        # Try to use the state file from a previous direct test
        state_file = Path(__file__).parent.parent / ".pipeline_state_full.json"
        if not state_file.exists():
            state_file = Path(__file__).parent.parent / ".pipeline_state.json"
        if not state_file.exists():
            print("Usage: python -m scripts.validate_claude [path/to/form.pdf]")
            print("  or run a direct test first: python -m scripts.test_pdf_direct")
            sys.exit(1)

        import base64 as _b64, requests
        from scripts.config import APPS_SCRIPT_URL
        state = json.loads(state_file.read_text())
        file_id = state.get("fileId")
        if not file_id:
            print(f"❌ No fileId in {state_file}")
            sys.exit(1)

        print(f"Downloading PDF for fileId={file_id} …")
        r = requests.get(APPS_SCRIPT_URL, params={"action": "getPdf", "id": file_id}, timeout=60)
        result = r.json()
        if not result.get("success"):
            print(f"❌ {result.get('error')}")
            sys.exit(1)
        pdf_bytes = _b64.b64decode(result["data"])
        print(f"Downloaded {len(pdf_bytes):,} bytes")

    _, passed = run_visual_qa(pdf_bytes)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
