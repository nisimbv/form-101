# Make.com — Setup Guide for Form 101 Automation

Complete guide for importing and configuring the two Make.com scenarios that connect
the Form 101 system to WhatsApp Business.

---

## Prerequisites

| Item | Where to find it |
|------|-----------------|
| WhatsApp Business account connected in Make | Make → Connections → Add → WhatsApp Business |
| GAS Deployment ID | Apps Script → Deploy → Manage Deployments → copy ID from URL |
| GAS Web App URL (`/exec`) | Same dialog — ends with `/exec` |
| HR phone number | Your HR department's WhatsApp number (`0XXXXXXXXX` format) |
| HR email address | For error notifications |
| Anthropic API key (optional) | console.anthropic.com → API Keys |

---

## Architecture

```
Form submission
      │ POST
      ▼
GAS doPost → saveToSheet → createPDF → updateSheetAfterPdf → sendToMake()
                                                                    │ POST webhook
                                                                    ▼
                                                         Make Scenario B
                                                         ┌─────────────────────────┐
                                                         │ 1. Webhook               │
                                                         │ 2. validatePdf (GAS)     │
                                                         │ 3. Router:               │
                                                         │    pass/skip → cont.     │
                                                         │    fail → Email HR       │
                                                         │ 4. Format employee phone │
                                                         │ 5. WA → employee         │
                                                         │ 6. Format HR phone       │
                                                         │ 7. WA → HR               │
                                                         │ 8. confirmSubmission     │
                                                         │ [Error] → Email HR       │
                                                         └─────────────────────────┘

HR invites new employee:
GET /exec?action=notifyEmployee → GAS → Make Scenario A
                                        ┌──────────────────┐
                                        │ 1. Webhook        │
                                        │ 2. Format phone   │
                                        │ 3. WA → employee  │
                                        └──────────────────┘
```

---

## Scenario A — Employee Invite

**Purpose:** HR calls a GAS endpoint to invite a new employee to fill Form 101.
GAS calls Make Scenario A, which sends a WhatsApp message to the employee.

### Import Blueprint

1. In Make: **Scenarios → Import Blueprint**
2. Select `make/scenario_a_invite.json`
3. Make creates the scenario with 3 modules

### Configure Webhook

1. Click the **Webhooks (module 1)** → **Add**
2. Name it `form101_invite`
3. Click **Save** — Make shows the webhook URL
4. Copy the URL
5. Paste it into:
   - `Code_v6_fixed2.gs` → `CONFIG.MAKE_INVITE_WEBHOOK_URL`
   - `src/Code.gs` → same location

### Assign Connections

- **Module 3** (WhatsApp): click the connection field → select your WhatsApp Business connection
  (replaces `REPLACE_ME_WA_CONNECTION_ID`)

### How to trigger

```
GET https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec
  ?action=notifyEmployee
  &phone=0521234567
  &name=ישראל ישראלי
  &employer=חברת דוגמה
  &taxYear=2026
```

Or from the pipeline:
```bash
python -m scripts.pipeline --no-deploy --no-make
```

---

## Scenario B — Form Submitted

**Purpose:** Triggered automatically by GAS after a Form 101 is submitted and the PDF
is saved to Drive. Runs Claude PDF validation, then sends WhatsApp confirmations to
both the employee and HR, and finally calls back to GAS to update the sheet status.

### Import Blueprint

1. In Make: **Scenarios → Import Blueprint**
2. Select `make/scenario_b_submitted.json`
3. Make creates the scenario with 9 modules (including a Router)

### Configure Webhook

1. Click **Webhooks (module 1)** → **Add**
2. Name it `form101_submitted`
3. Copy the URL
4. Paste it into:
   - `Code_v6_fixed2.gs` → `CONFIG.MAKE_WEBHOOK_URL`
   - `src/Code.gs` → same location
   - `scripts/config.py` → `MAKE_WEBHOOK_URL`

### Replace Placeholders

Open the scenario and update every `REPLACE_ME_` value:

| Placeholder | Where | Value |
|-------------|-------|-------|
| `REPLACE_ME_GAS_DEPLOYMENT_ID` | Modules 2 and 8, URL field | Your GAS deployment ID |
| `REPLACE_ME_WA_CONNECTION_ID` | Modules 5 and 7 | Your WhatsApp Business connection |
| `REPLACE_ME_HR_PHONE` | Module 6, SetVariable value | HR phone in `0XXXXXXXXX` format |
| `REPLACE_ME_HR_EMAIL` | Module 9 (error email), To field | HR email address |
| `REPLACE_ME_EMAIL_CONNECTION_ID` | Module 9 | Your Gmail or SMTP connection |

### Module details

| # | Type | Purpose |
|---|------|---------|
| 1 | Custom Webhook | Receives payload from GAS `sendToMake()` |
| 2 | HTTP GET | Calls `validatePdf` on GAS → Claude QA |
| 3 | Router | Splits: QA pass/skip → flow A; QA fail → flow B |
| 4 | Set Variables | Formats employee phone for WhatsApp (`972XXXXXXXXX`) |
| 5 | WhatsApp | Sends `form_101_confirmation` template to employee |
| 6 | Set Variables | Formats HR phone for WhatsApp |
| 7 | WhatsApp | Sends `form_101_hr_notify` template to HR |
| 8 | HTTP GET | Calls `confirmSubmission` on GAS → updates sheet status |
| 9 | Send Email | Error handler — emails HR if QA fails |

---

## WhatsApp Message Templates

WhatsApp Business requires **pre-approved templates** for first-contact messages.
Submit the following templates in your Meta Business account:

### Template 1: `form_101_invite`

- **Language:** Hebrew (`he`)
- **Category:** Utility
- **Body (example):**
  ```
  שלום {{1}},
  המעסיק {{2}} מזמין אותך למלא טופס 101 לשנת המס {{3}}.
  לחץ כאן למילוי הטופס: {{4}}
  לשאלות פנה/י למחלקת משאבי אנוש.
  ```
- **Parameters:** `{{1}}`=employee name, `{{2}}`=employer name, `{{3}}`=tax year, `{{4}}`=form URL

### Template 2: `form_101_confirmation`

- **Language:** Hebrew (`he`)
- **Category:** Utility
- **Body (example):**
  ```
  שלום {{1}} ✅
  טופס 101 שלך לשנת המס {{2}} התקבל בהצלחה!
  הטופס הדיגיטלי שמור ב-Google Drive: {{3}}
  בברכה, {{4}} — מחלקת משאבי אנוש
  ```
- **Parameters:** `{{1}}`=full name, `{{2}}`=tax year, `{{3}}`=PDF URL, `{{4}}`=employer name

### Template 3: `form_101_hr_notify`

- **Language:** Hebrew (`he`)
- **Category:** Utility
- **Body (example):**
  ```
  עובד חדש מילא טופס 101:
  שם: {{1}}
  ת.ז.: {{2}}
  שנת מס: {{3}}
  PDF: {{4}}
  ```
- **Parameters:** `{{1}}`=full name, `{{2}}`=ID number, `{{3}}`=tax year, `{{4}}`=PDF URL

---

## Claude PDF Validation (`validatePdf`)

GAS validates the generated PDF using the Anthropic Claude API before Make sends
WhatsApp messages. This catches rendering errors early.

### Set the API Key

**Option A — Script Properties (recommended, keeps key out of source code):**
1. Apps Script editor → Project Settings (gear icon) → Script Properties
2. Add property: `ANTHROPIC_API_KEY` = `sk-ant-...`

**Option B — CONFIG (less secure):**
In `Code_v6_fixed2.gs` and `src/Code.gs`, set:
```javascript
ANTHROPIC_API_KEY: 'sk-ant-...',
```

### Without an API key

If `ANTHROPIC_API_KEY` is not set, the endpoint returns:
```json
{ "success": true, "skipped": true, "quality": 10, "passed": true }
```
Make's router treats this as a pass and continues normally. No validation errors will
be surfaced — set the key if you want quality gating.

### Response format

```json
{
  "success": true,
  "quality": 9,
  "passed": true,
  "issues": [],
  "summary": "Form renders correctly on both pages. All fields and checkmarks visible."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `quality` | 1–10 | 10=perfect, 8+=production-ready, <8=needs fix |
| `passed` | bool | `true` if `quality >= 8` |
| `issues` | array | `[{"field":"...","page":1,"problem":"..."}]` |
| `summary` | string | Human-readable assessment |

---

## Phone Number Format

WhatsApp expects international format without `+`: `972XXXXXXXXX`

GAS stores Israeli numbers as `0XXXXXXXXX`.

**Conversion in Make (Set Variable):**
```
972{{substring(phone; 1)}}
```
This removes the leading `0` and prepends `972`.

---

## Sheet Status Flow

| Status | Meaning |
|--------|---------|
| `ממתין ל-PDF` | Form saved, PDF being generated |
| `✅ הושלם` | PDF created and saved to Drive |
| `✅ הושלם · נשלח ל-Make` | Webhook sent to Make successfully |
| `📨 הזמנה נשלחה` | WhatsApp invite sent to employee (Scenario A) |
| `✅ אושר על ידי HR` | Make received + sent WhatsApp + callback confirmed |
| `⚠ שגיאה: ...` | Send failure (details in "שגיאות" sheet tab) |

---

## Pipeline Testing

After setting webhook URLs in `scripts/config.py` and `Code_v6_fixed2.gs`:

```bash
# Full E2E pipeline
run_pipeline.bat

# Test validatePdf endpoint only (no form submission)
python -m scripts.pipeline --no-deploy --validate-pdf-endpoint

# Full pipeline with PDF endpoint test
python -m scripts.pipeline --no-deploy --validate-pdf-endpoint
```

The `--validate-pdf-endpoint` flag:
- Without `ANTHROPIC_API_KEY` → prints `⏭  skipped` (pass)
- With `ANTHROPIC_API_KEY` → calls GAS, prints quality score and summary

---

## Troubleshooting

### Make webhook not receiving data

1. Check `CONFIG.MAKE_WEBHOOK_URL` is set in both `Code_v6_fixed2.gs` and `src/Code.gs`
2. Redeploy GAS after changing CONFIG (Deploy → Manage → New version)
3. Verify Make scenario is **ON** (toggle in top-right corner)

### WhatsApp message not sent

1. Check template is approved in Meta Business Manager
2. Verify the connection is still active (Make → Connections)
3. Check phone format — must be `972XXXXXXXXX` (9 digits after 972, no spaces)
4. Make execution log shows the exact error from WhatsApp API

### `confirmSubmission` not updating the sheet

1. Check `REPLACE_ME_GAS_DEPLOYMENT_ID` is replaced with the actual ID in module 8
2. The deployment ID is the long string in the `/exec` URL — copy only the ID part
3. Test manually: `GET /exec?action=confirmSubmission&rowNum=2&status=test&source=debug`

### `validatePdf` returns `success: false`

1. Check the file is accessible by the GAS service account (Drive sharing)
2. Check `ANTHROPIC_API_KEY` is correct and has sufficient credits
3. View Apps Script execution log (Apps Script editor → Executions) for full error

### PDF quality score below 8

- View `issues` array in the Make execution log for specific field problems
- Run `python -m scripts.pipeline --no-deploy --comprehensive` locally to diagnose
- Check `PDFTemplate_v6.html` for the affected section
