# טופס 101 — מערכת דיגיטלית אוטומטית

מערכת מלאה לאיסוף, שמירה וייצור PDF של טופס 101 (תיאום מס) לפי עיצוב רשמי.

---

## מה המערכת עושה?

עובד ממלא טופס אינטרנטי בעברית (RTL).
לאחר שליחה, המערכת:

1. **שומרת את הנתונים** בגיליון Google Sheets (38 עמודות בעברית)
2. **מייצרת PDF** בפורמט הרשמי של טופס 101 — 2 עמודים עם רקע סרוק ושכבת מילוי
3. **שומרת את ה-PDF** ב-Google Drive תחת `HR_101/{שנת מס}/{שם מעסיק}/`
4. **מעדכנת את השורה** בשיטס עם קישור ל-PDF וסטטוס ✅ הושלם
5. **(אופציונלי)** שולחת התראה ל-WhatsApp Business דרך Make

---

## ארכיטקטורה

```
GitHub Pages (index_v6.html)
        │  POST JSON
        ▼
Google Apps Script (/exec)
        │  Code.gs: normalizePayload → saveToSheet → createPDF → updateSheet → sendToMake
        ├─▶ Google Sheets  (מעקב טופס 101 — 38 עמודות)
        ├─▶ Google Drive   (HR_101/{שנת מס}/{מעסיק}/טופס_101_*.pdf)
        └─▶ Make Webhook   (→ WhatsApp Business)
```

---

## קבצים

| קובץ | תפקיד | נפרס כ- |
|---|---|---|
| `index_v6.html` | טופס הקצה (RTL, JS ונילה) | GitHub Pages |
| `Code_v6_fixed2.gs` | Backend — GAS | `Code.gs` בפרויקט Apps Script |
| `PDFTemplate_v6.html` | תבנית PDF עם רקע base64 | `PDFTemplate.html` בפרויקט Apps Script |
| `scripts/pipeline.py` | Pipeline אוטומטי: clasp push + E2E test + verify | הרצה מקומית |
| `scripts/test_form.py` | Playwright E2E — ממלא ושולח את הטופס | הרצה מקומית |
| `scripts/verify_sheet.py` | מאמת שורה ב-Sheets | הרצה מקומית |
| `scripts/verify_pdf.py` | מאמת מיקומי טקסט וסימונים ב-PDF | הרצה מקומית |
| `scripts/config.py` | נתוני בדיקה, URLs, ומיקומי שדות מצופים | shared config |

---

## דרישות טכניות

- **Google Workspace** — Sheets + Drive + Apps Script
- **clasp** — `npm install -g @google/clasp` (לפריסה מקומית)
- **Python 3.11+** עם: `playwright`, `pdfplumber`, `requests`, `google-auth`
- **Node.js** (לclasp)

---

## פריסה ראשונית

### Backend (Apps Script)

1. פתח [script.google.com](https://script.google.com) → צור פרויקט חדש
2. הדבק את תוכן `Code_v6_fixed2.gs` לתוך `Code.gs`
3. צור קובץ HTML חדש בשם `PDFTemplate` והדבק את `PDFTemplate_v6.html`
4. ב-`Code.gs` הגדר `SPREADSHEET_ID` ב-`CONFIG`:
   ```javascript
   const CONFIG = {
     SPREADSHEET_ID: 'ID_של_הגיליון_שלך',
     SHEET_NAME: 'מעקב טופס 101',
     MAIN_FOLDER: 'HR_101',
     MAKE_WEBHOOK_URL: '',  // אופציונלי
     HR_PHONE: '',          // אופציונלי
     HR_EMAIL: '',          // אופציונלי
     TIMEZONE: 'Asia/Jerusalem',
   };
   ```
5. **פרוס:** Deploy → New deployment → Web app → Execute as Me → Who has access: Anyone
6. העתק את URL ה-`/exec`

### Frontend (GitHub Pages)

1. ב-`index_v6.html` עדכן את `APPS_SCRIPT_URL` (שורה ~1205) ל-URL שקיבלת
2. דחוף ל-GitHub → הפעל Pages מ-master branch
3. הטופס זמין ב: `https://{username}.github.io/{repo}/index_v6.html`

---

## Pipeline אוטומטי (בדיקות E2E)

```bash
# הרצה מ-root של הפרויקט:
python -m scripts.pipeline

# או דרך הסקריפט:
run_pipeline.bat
```

הpipeline:
1. `clasp push` + `clasp deploy` (מגדרסה חדשה)
2. Playwright ממלא ושולח את הטופס עם נתוני בדיקה
3. מאמת שורה ב-Sheets (ערכים מצופים)
4. מוריד את ה-PDF ומאמת מיקומי טקסט וסימנים (±8mm tolerance)

---

## מבנה ה-PDF

- **2 עמודים** A4 (210×297mm)
- **רקע:** JPEG סרוק של הטופס הרשמי (base64 מוטמע ב-HTML)
- **שכבת מילוי:** `.field` (טקסט), `.mark` (✓ כחול), `.sig` (חתימה)
- **מנוע PDF:** `HtmlService.createTemplateFromFile → blob.getAs(PDF)` של GAS

---

## טכנולוגיות

| שכבה | טכנולוגיה |
|---|---|
| Frontend | HTML5, Vanilla JS, CSS (RTL) |
| Backend | Google Apps Script (V8) |
| Storage | Google Sheets + Google Drive |
| PDF | GAS HtmlService → PDF blob |
| Automation | Playwright, Python, clasp |
| Hosting | GitHub Pages |
| Notifications | Make.com → WhatsApp Business API |

---

## מגבלות ידועות של מנוע ה-PDF של GAS

- **אין CSS transform** — כל `.mark` חייב להיות `position:absolute` בלי transform
- **אין פונטים חיצוניים** — משתמשים ב-Arial, Segoe UI, Comic Sans MS
- **אין flexbox/grid** — פריסה ע"י `position:absolute` בלבד
- **אין CSS variables**
- הסט מערכתי של ~0.9mm כלפי מעלה על כל הסימונים — עקבי ומקובל

---

## מבנה גיליון Google Sheets

38 עמודות בעברית:
- **1–24:** שדות עיקריים (שם, ת"ז, מעסיק, תאריכים, בחירות...)
- **25–30:** עמודות סיכום (כתובת, ילדים, זכאויות, בן/בת זוג...)
- **31:** קישור PDF
- **32:** מזהה קובץ Drive
- **33:** סטטוס (✅ הושלם / ❌ שגיאה)
- **34–38:** JSON גולמי של שדות מורכבים

---

*נבנה עבור ניהול HR פנים-ארגוני. כל הנתונים נשמרים ב-Google Workspace של הארגון.*
