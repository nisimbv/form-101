# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated Israeli Tax Form 101 (טופס 101) digitization system. An employee fills a web form; the system saves the data to Google Sheets, generates an official-looking 2-page PDF overlay, stores it in Google Drive, and optionally notifies via Make → WhatsApp Business.

## Architecture

```
GitHub Pages (index_v6.html)
        │  POST JSON (Content-Type: text/plain to avoid CORS preflight)
        ▼
Google Apps Script Web App (/exec URL)
        │  Code.gs:  normalizePayload → saveToSheet → createPDF → updateSheetAfterPdf → sendToMake
        ├─▶ Google Sheets  (tab: "מעקב טופס 101", 32 Hebrew columns)
        ├─▶ Google Drive   (HR_101/{taxYear}/{employer_name}/טופס_101_*.pdf)
        └─▶ Make Webhook   (optional) → WhatsApp Business
```

## Files

| Local file | Purpose | Deployed as |
|---|---|---|
| `index_v6.html` | Frontend form (RTL Hebrew, vanilla JS) | GitHub Pages |
| `Code_v6_fixed2.gs` | GAS backend | `Code.gs` in Apps Script project |
| `PDFTemplate_v6.html` | HTML PDF template with base64 background JPEGs | `PDFTemplate.html` in Apps Script project |

There is no build step. Edit files locally → paste into the relevant target.

## Deployment Checklist

**Backend (any change to Code.gs or PDFTemplate.html):**
1. Paste updated file content into Apps Script editor (Extensions → Apps Script)
2. **Deploy → Manage deployments → edit pencil → New version → Deploy**
3. The Web App URL (`/exec`) does **not** change between versions

**Frontend:**
- Update `APPS_SCRIPT_URL` constant at `index_v6.html:1205` if the Web App URL ever changes
- Upload `index_v6.html` to GitHub Pages (no build needed)

## Required Configuration (Code_v6_fixed2.gs)

```javascript
const CONFIG = {
  SHEET_NAME: 'מעקב טופס 101',
  SPREADSHEET_ID: '',      // MUST fill — paste Spreadsheet ID here
  MAIN_FOLDER: 'HR_101',
  MAKE_WEBHOOK_URL: '',    // optional
  HR_PHONE: '',            // optional
  HR_EMAIL: '',            // optional
  TIMEZONE: 'Asia/Jerusalem',
};
```

`SPREADSHEET_ID` must be set; otherwise the script tries `SpreadsheetApp.getActiveSpreadsheet()` which fails for standalone Web Apps.

## PDF Generation System

`createPDF(data)` passes two objects to `PDFTemplate.html`:
- `template.data` — raw normalized payload
- `template.pdf` — view model from `buildPdfViewModel(data)` (flat, typed fields + `flags` object for all booleans)

**Template scriptlet helpers** (defined at top of PDFTemplate.html):
- `s(v)` — safe string
- `yes(v)` — truthy for `true/'true'/'כן'/'on'/'1'`
- `eq(a,b)` — string equality
- `dmy(v)` — converts `YYYY-MM-DD` → `DD/MM/YYYY`
- `childAt(i)`, `incAt(i)`, `chgAt(i)` — safe array access

**CSS classes in PDFTemplate.html:**
- `.page` — A4 container (210mm × 297mm), two of them for 2 pages
- `.bg` — background JPEG (base64 embedded, 1240×1753 px at 150 DPI)
- `.field` — text overlay (`position:absolute`, units in mm)
- `.mark` — blue checkmark overlay (`position:absolute`, color `#1f5fe0`, font Segoe Script/Comic Sans). **Must NOT have CSS `transform`** — GAS PDF renderer ignores `position:absolute` on transformed elements, causing all marks to collapse to (0,0)
- `.sig` — signature `<img>` element

**Coordinate system:** CSS `left`/`top` in mm from the top-left of `.page`. GAS converts 1px → 0.75pt (96→72 DPI). The CTM applied is approximately `[0.75, 0, 0, -0.75, x_offset, 841.92]`.

## Data Flow and Field Names

Frontend `buildPayload()` (`index_v6.html:1465`) collects `FormData` then:
- Combines `street` + `house_number` + `city` → `data.address` (backend expects single `address` field)
- Collects dynamic children as `data.children[]` objects: `{name, id, birth_date, in_custody, receives_allowance}`
- Collects additional incomes as `data.additional_incomes[]`: `{employer, address, tax_id, type, amount, tax}`
- Collects changes as `data.changes[]`: `{date, details, notification_date, signature}`

**Critical field name mapping** (frontend input `name` → backend/PDF key):

| Frontend `name` attr | Backend key |
|---|---|
| `aliya_date` | `aliya_date` |
| `spouse_id_number` | `spouse_id_number` |
| `spouse_passport_number` | `spouse_passport_number` |
| `spouse_aliya_date` | `spouse_aliya_date` |

All checkbox boolean fields are normalized by `normalizePayload()` via the `boolKeys` list. Unchecked checkboxes do not appear in FormData — they arrive as `undefined` and are coerced to `false`.

## Google Sheets Structure

32 columns, Hebrew headers, auto-created on first submission. Column 25 (קישור PDF), 26 (מזהה קובץ), and 27 (סטטוס) are written in a second pass by `updateSheetAfterPdf()` after the PDF is created.

**Header refresh logic:** On each submission, headers are compared via `JSON.stringify`. If they don't match the V6 layout exactly, they are overwritten. This ensures old V4/V5 header rows are replaced automatically.

## GAS PDF Renderer Constraints

The built-in `blob.getAs(MimeType.PDF)` HTML-to-PDF renderer has significant CSS limitations:
- **No CSS `transform`** (breaks `position:absolute` — all elements collapse to origin)
- **No external fonts** (use only system-safe fonts: Arial, Helvetica, Segoe UI, Comic Sans MS)
- **No flexbox/grid** (use only `position:absolute` for overlay layout)
- **No CSS variables** or modern CSS features
- `@page { size: A4; margin: 0; }` is supported and required

## Working Cycle (COWORK Framework)

This project uses an iterative fix cycle defined in `Code_הסברים v6_fixed2.gs`. Each session should:
1. Analyze current state (what works, what's broken, evidence)
2. Plan the round (priority order: form submit → PDF creation → Sheet save → Drive save → PDF positioning → Make → WhatsApp → UX)
3. Execute fixes with full file output
4. Provide deployment instructions
5. Return a round report (passed/failed/severity/root-cause)
6. Continue until all end-to-end goals are met

## Testing

There is no automated test suite. Test by submitting the live form and verifying:
1. Row appears in Google Sheet with correct column values
2. PDF file appears in Drive under `HR_101/{year}/{employer}/`
3. PDF visually matches the official Form 101 (2 pages, marks inside boxes, text in correct fields)
4. Make webhook receives payload (if configured)

To test Apps Script in isolation: Apps Script editor → Run `doPost` with a mock event, or use the **Execution log** to inspect `Logger.log` output.
