# טופס 101 — מערכת דיגיטלית אוטומטית v6

מערכת מלאה לאיסוף, עיבוד ושליחת **טופס 101 (תיאום מס)** הישראלי הרשמי — מהגשת הטופס על-ידי העובד ועד ל-WhatsApp לצוות ה-HR, בצורה אוטומטית לחלוטין.

---

## מטרת הפרויקט

בישראל, כל עובד חדש (ועובד קיים בתחילת כל שנת מס) מחויב להגיש **טופס 101** — טופס תיאום מס רשמי של רשות המיסים.
הטופס המסורתי הוא PDF ממולא ידנית, נדפס, נחתם ומוגש. התהליך הזה מסורבל, גוזל זמן ונוטה לטעויות.

**הפרויקט הזה מדיגיטל את התהליך כולו:**

1. עובד ממלא טופס אינטרנטי נוח בעברית (RTL מלא)
2. המערכת שומרת את הנתונים ב-Google Sheets
3. מייצרת PDF זהה לטופס הרשמי — 2 עמודים עם רקע סרוק ושכבת מילוי מדויקת
4. שומרת את ה-PDF ב-Google Drive מאורגן לפי שנה ומעסיק
5. שולחת התראת WhatsApp לעובד ול-HR דרך Make.com
6. מעדכנת את הגיליון לסטטוס "אושר על ידי HR"

---

## ארכיטקטורה

```
GitHub Pages (index_v6.html)
        │  POST JSON (Content-Type: text/plain — עוקף CORS preflight)
        ▼
Google Apps Script Web App (/exec)
        │  normalizePayload → saveToSheet → createPDF → updateSheetAfterPdf → sendToMake
        ├─▶ Google Sheets  (מעקב טופס 101 — 41 עמודות)
        ├─▶ Google Drive   (HR_101/{שנת מס}/{מעסיק}/טופס_101_*.pdf)
        └─▶ Make.com Webhook
                │
                ▼
        Scenario B — טופס הוגש
        ┌──────────────────────────────────┐
        │ 1. Webhook (קבלת הנתונים)         │
        │ 2. validatePdf → GAS Claude QA   │
        │ 3. Router:                        │
        │    עבר/דולג → Route A            │
        │    נכשל QA  → Route B (התראה HR) │
        │ 4. WhatsApp → עובד               │
        │ 5. WhatsApp → HR                 │
        │ 6. confirmSubmission → GAS       │
        │    [שגיאה] → Email HR            │
        └──────────────────────────────────┘

        Scenario A — הזמנת עובד חדש
        ┌──────────────────────────────────┐
        │ 1. Webhook (notifyEmployee)       │
        │ 2. WhatsApp → עובד (לינק טופס)   │
        │    [שגיאה] → Email HR            │
        └──────────────────────────────────┘
```

---

## קבצי הפרויקט

### קבצים ראשיים (נפרסים)

| קובץ מקומי | נפרס כ- | תפקיד |
|---|---|---|
| `index_v6.html` | GitHub Pages | טופס הקצה — RTL, Vanilla JS, ולידציה |
| `Code_v6_fixed2.gs` | `Code.gs` ב-Apps Script | Backend מלא: קבלת הטופס, שמירה, PDF, Make |
| `PDFTemplate_v6.html` | `PDFTemplate.html` ב-Apps Script | תבנית HTML לייצור PDF — רקע base64 + שכבת מילוי |
| `src/Code.gs` | sync עם clasp | גרסת clasp של הקוד (זהה ל-Code_v6_fixed2.gs) |

### Make.com Blueprints

| קובץ | תרחיש | פעולה |
|---|---|---|
| `make/scenario_a_invite.json` | Scenario A | Import Blueprint → הזמנת עובד חדש |
| `make/scenario_b_submitted.json` | Scenario B | Import Blueprint → עיבוד טופס שהוגש |

### Pipeline ובדיקות אוטומטיות

| קובץ | תפקיד |
|---|---|
| `scripts/pipeline.py` | מנהל ה-pipeline: clasp deploy → Playwright → verify |
| `scripts/config.py` | נתוני בדיקה, URLs, מיקומי שדות מצופים |
| `scripts/test_form.py` | Playwright E2E — ממלא ושולח טופס |
| `scripts/verify.py` | מאמת Sheets + PDF + confirmSubmission |
| `scripts/test_pdf_direct.py` | POST ישיר ל-GAS עם TEST_DATA_FULL (כל הסעיפים) |
| `scripts/validate_claude.py` | QA חזותי של PDF עם Claude Vision (PyMuPDF) |
| `scripts/test_edge_cases.py` | 7 תרחישי קצה (בן/זוג עם הכנסה, כתובת מעסיק, תיאום מס...) |
| `scripts/deploy.py` | `clasp push` + `clasp deploy` |
| `scripts/patch_make_scenario_b.py` | תיקון Router של Scenario B דרך Make API |
| `run_pipeline.bat` | קיצור דרך ל-Windows |

### תיעוד

| קובץ | תוכן |
|---|---|
| `MAKE_SETUP.md` | הוראות מלאות לחיבור Make.com: import, WhatsApp, Claude QA |
| `CLAUDE.md` | הנחיות לעבודה עם Claude Code על הפרויקט |
| `scripts/field_positions.json` | מיקומי שדות מדויקים שחולצו מה-PDF הרשמי המקורי |

---

## מבנה הטופס — 2 עמודים

### עמוד 1

| סעיף | תוכן |
|---|---|
| **א׳** | פרטי מעסיק (שם, תיק ניכויים, טלפון, כתובת, תחילת עבודה) |
| **ב׳** | פרטי עובד (שם, ת"ז, תאריך לידה, כתובת, טלפון, מייל, מין, מצב משפחתי, תושבות, קיבוץ, קופ"ח) |
| **ג׳** | ילדים (עד 6 שורות: שם, ת"ז, לידה, חזקה, קצבה) |
| **ד׳** | סוג הכנסה ממעסיק (משכורת/נוספת/חלקית/יומית/קצבה/מלגה) |
| **ה׳** | הכנסות אחרות + ויתור על קרן השתלמות/פנסיה |
| **ו׳** | בן/בת זוג (פרטים + סוג הכנסה) |
| **ז׳** | שינויים במהלך השנה (עד 3 שורות) |

### עמוד 2

| סעיף | תוכן |
|---|---|
| **ח׳** | זכאויות להקלות מס (17 אפשרויות: תושב, נכה, יישוב, עולה חדש, בן/זוג, הורה יחיד, ילדים, פנסיונר, מילואים...) |
| **ת׳** | תיאום מס — הכנסות נוספות (עד 3 שורות) |
| **הצהרה** | תאריך, שם, חתימה |

---

## מבנה גיליון Google Sheets (41 עמודות — Schema v7)

| עמודות | סעיף |
|---|---|
| 1–2 | מטא: תאריך הגשה, שנת מס |
| 3–7 | סעיף א׳ — מעסיק |
| 8–22 | סעיף ב׳ — עובד (15 שדות) |
| 23–24 | סעיף ג׳ — ילדים (מספר + JSON) |
| 25 | סעיף ד׳ — סוג הכנסה |
| 26–30 | סעיף ה׳ — הכנסות אחרות |
| 31–32 | סעיף ו׳ — בן/בת זוג |
| 33 | סעיף ח׳ — זכאויות (סיכום טקסט) |
| 34 | סעיף ת׳ — תיאום מס |
| 35 | סעיף ז׳ — שינויים (JSON) |
| 36 | תאריך הצהרה |
| 37 | קישור PDF ב-Drive |
| 38 | מזהה קובץ Drive |
| 39 | סטטוס (`✅ הושלם` / `✅ אושר על ידי HR` / `❌`) |
| 40–41 | פנימי: סיכום JSON, JSON מלא |

---

## Pipeline אוטומטי

```bash
# Pipeline בסיסי (deploy + E2E + verify)
python -m scripts.pipeline

# ללא deploy (GAS כבר מעודכן)
python -m scripts.pipeline --no-deploy

# עם אימות כל הסעיפים (TEST_DATA_FULL)
python -m scripts.pipeline --no-deploy --comprehensive

# עם QA חזותי של Claude (צריך ANTHROPIC_API_KEY + PyMuPDF)
python -m scripts.pipeline --no-deploy --visual-qa

# בדיקת endpoint validatePdf
python -m scripts.pipeline --no-deploy --validate-pdf-endpoint

# דפדפן גלוי (לדיבוג Playwright)
python -m scripts.pipeline --no-deploy --visible
```

### שלבי ה-Pipeline

| # | שלב | כלי |
|---|---|---|
| 1 | clasp push + deploy | clasp |
| 2 | מילוי הטופס ב-browser | Playwright |
| 3 | אימות 13 שדות ב-Sheets | requests + Google Sheets API |
| 4 | הורדת PDF מ-Drive | requests + GAS doGet |
| 5 | אימות 9 שדות טקסט ב-PDF | pdfplumber |
| 6 | אימות 10 סימונים (✓) ב-PDF | pdfplumber |
| 7 | קריאה ל-confirmSubmission | requests |
| 8 | בדיקת endpoint validatePdf | requests |
| 9 | בדיקת Make webhook | requests |

---

## מערכת ה-PDF

### עקרון הפעולה

`HtmlService.createTemplateFromFile('PDFTemplate')` → `blob.getAs(MimeType.PDF)`

GAS מרנדר HTML לתוך PDF. הרקע הוא JPEG סרוק של הטופס הרשמי (base64 מוטמע). שכבת המילוי היא אלמנטים `position:absolute` בממ"מ.

### מגבלות מנוע ה-PDF של GAS

| מגבלה | פתרון |
|---|---|
| אין CSS `transform` | `.mark` ללא transform — רק `position:absolute` |
| אין פונטים חיצוניים | Arial, Segoe UI, Comic Sans MS (סימוני ✓) |
| אין flexbox / grid | פריסה ע"י `position:absolute` בלבד |
| אין CSS variables | ערכים ישירים בכל שדה |

### מיקומים (מיקור אמת: `scripts/field_positions.json`)

כל המיקומים חולצו מה-PDF הרשמי המקורי (`form101_REAL_ORIGINAL_FILLED.pdf`) עם PyMuPDF וכוילו ל-A4 (210×297mm).
סקייל: `210 / 900.2` (ממרחב הסריקה ל-mm).

---

## אינטגרציה עם Make.com

### Scenario A — הזמנת עובד חדש

**טריגר:** `GET /exec?action=notifyEmployee&...`
**תוצאה:** WhatsApp לעובד עם קישור לטופס

### Scenario B — עיבוד טופס שהוגש

**טריגר:** Webhook מ-GAS `sendToMake()` (לאחר יצירת ה-PDF)
**תוצאה:**
1. QA על ה-PDF (Claude Vision דרך GAS endpoint)
2. WhatsApp לעובד — אישור קבלה
3. WhatsApp ל-HR — התראה על טופס חדש
4. עדכון סטטוס בשיטס → `✅ אושר על ידי HR`

### GAS Endpoints (doGet)

| action | פרמטרים | תפקיד |
|---|---|---|
| `validatePdf` | `fileId` | QA של PDF דרך Claude API |
| `confirmSubmission` | `rowNum`, `status`, `source` | עדכון סטטוס בשיטס |
| `notifyEmployee` | `...employee data` | שליחת Webhook ל-Scenario A |
| `getPdf` | `id` | הורדת PDF כ-base64 |
| `deleteTestRows` | — | מחיקת שורות בדיקה (dev only) |

### QA אוטומטי של PDF (validatePdf)

Make קורא ל-`?action=validatePdf&fileId=<id>`.
GAS מוריד את ה-PDF מ-Drive, מקודד base64, ושולח ל-Claude (`claude-sonnet-4-6`) עם prompt שמבקש בדיקת:
- שדות טקסט במיקום שגוי
- סימונים (✓) חסרים או שגויים
- חריגת טקסט מגבולות השדה

תוצאה: `{quality: 1-10, passed: bool, issues: [], summary: "..."}` — ניתן ממסף 8 ומעלה.

---

## הגדרת CONFIG (Code_v6_fixed2.gs)

```javascript
const CONFIG = {
  SHEET_NAME:       'מעקב טופס 101',
  SPREADSHEET_ID:   'PASTE_SPREADSHEET_ID_HERE',   // חובה
  MAIN_FOLDER:      'HR_101',
  MAKE_WEBHOOK_URL: 'https://hook.eu1.make.com/...', // Scenario B
  MAKE_INVITE_WEBHOOK_URL: 'https://hook.eu1.make.com/...', // Scenario A
  HR_PHONE:         '972501234567',  // אופציונלי — WhatsApp HR
  HR_EMAIL:         'hr@company.com', // אופציונלי — התראות שגיאה
  TIMEZONE:         'Asia/Jerusalem',
  ANTHROPIC_API_KEY: '',  // אופציונלי — מוסר גם מ-Script Properties
};
```

---

## התקנה ראשונית

### דרישות

- Google Workspace (Sheets + Drive + Apps Script)
- Node.js + `npm install -g @google/clasp`
- Python 3.11+ עם: `playwright pdfplumber requests google-auth anthropic pymupdf`
- חשבון Make.com עם WhatsApp Business Cloud connection

### Backend

```bash
# התחברות ל-Google
clasp login

# Clone הפרויקט הקיים (לפי SCRIPT_ID ב-config.py)
clasp clone <SCRIPT_ID>

# פריסה
clasp push
clasp deploy --description "v6"
```

### Frontend

1. ב-`index_v6.html` עדכן `APPS_SCRIPT_URL` (שורה ~1205)
2. דחוף ל-GitHub → הפעל GitHub Pages

### Make.com

1. Import → `make/scenario_b_submitted.json`
2. החלף את כל ה-`REPLACE_ME_*` placeholders (ראה `MAKE_SETUP.md`)
3. הפעל את התרחיש
4. העתק את ה-Webhook URL → הדבק ב-`CONFIG.MAKE_WEBHOOK_URL`
5. Redeploy ב-GAS

---

## בדיקות ותוצאות

### תוצאות אחרונות (2026-03-02)

| בדיקה | תוצאה |
|---|---|
| Pipeline בסיסי (9 שדות טקסט + 10 סימונים) | ✅ 100% |
| Pipeline כולל (14 שדות טקסט + 18 סימונים) | ✅ 100% |
| 7 תרחישי קצה (edge cases) | ✅ 7/7 |
| E2E מלא: GAS → Make → WhatsApp → confirmSubmission | ✅ |
| Make webhook reachable | ✅ 200 OK |

### תרחישי הקצה שנבדקו

| תרחיש | מה נבדק |
|---|---|
| בן/זוג עם הכנסה מעבודה | סימון שדה `spouse_work` בלבד |
| כתובת מעסיק | שדה `employer_address` מוצג נכון |
| תיאום מס | סעיף ת׳ — שורות הכנסה נוספות |
| יש הכנסות אחרות | סעיף ה׳ — `has_other_income=true` |
| בקשת זכאות / יש זכאות אחרת | שדות `relief_wants`, `relief_has_other` |
| שינויים + תאריך עלייה | סעיף ז׳ + שדה עלייה |
| תושב חוץ | `israeli_resident=לא` — שדה תעודת דרכון |

---

## טכנולוגיות

| שכבה | טכנולוגיה |
|---|---|
| Frontend | HTML5, Vanilla JS, CSS RTL |
| Backend | Google Apps Script (V8 runtime) |
| Storage | Google Sheets + Google Drive |
| PDF Engine | GAS HtmlService → PDF blob |
| Automation | Python, Playwright, clasp |
| Hosting | GitHub Pages |
| Notifications | Make.com → WhatsApp Business Cloud API |
| QA | Claude Vision API (`claude-sonnet-4-6`) + pdfplumber |

---

## מבנה תיקיות

```
form101_v6_files/
├── index_v6.html              ← טופס הקצה
├── Code_v6_fixed2.gs          ← GAS backend
├── PDFTemplate_v6.html        ← תבנית PDF
├── src/
│   ├── Code.gs                ← clasp sync
│   └── PDFTemplate.html
├── make/
│   ├── scenario_a_invite.json
│   └── scenario_b_submitted.json
├── scripts/
│   ├── config.py              ← נתוני בדיקה + URLs + מיקומי שדות
│   ├── pipeline.py            ← מנהל ה-pipeline
│   ├── deploy.py
│   ├── test_form.py           ← Playwright E2E
│   ├── verify.py              ← Sheet + PDF verification
│   ├── test_pdf_direct.py     ← POST ישיר ל-GAS
│   ├── validate_claude.py     ← Claude Vision QA
│   ├── test_edge_cases.py     ← 7 edge cases
│   ├── patch_make_scenario_b.py ← תיקון Router דרך API
│   └── field_positions.json   ← מיקורי אמת של שדות
├── MAKE_SETUP.md              ← הוראות Make.com
├── CLAUDE.md                  ← הנחיות לעבודה עם Claude Code
├── run_pipeline.bat           ← קיצור דרך Windows
└── README.md                  ← מסמך זה
```

---

## הפעלת תיקון Scenario B (validatePdf error fallback)

אם Router ה-Make לא מכיל fallback לשגיאות validatePdf:

```powershell
$env:MAKE_API_TOKEN = "<טוקן-Make-שלך>"
python -m scripts.patch_make_scenario_b
```

הסקריפט מוסיף תנאי שלישי לפילטר Route A: `{{2.data.success}} = false` — כך שגם אם validatePdf נכשל לגמרי (timeout/API error), הזרימה ממשיכה לWhatsApp ו-confirmSubmission.

---

*נבנה עבור ניהול HR פנים-ארגוני. כל הנתונים נשמרים ב-Google Workspace של הארגון בלבד.*
