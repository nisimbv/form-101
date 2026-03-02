# Make.com — הגדרת תרחישים לאוטומציית טופס 101

מסמך זה מתאר שני תרחישים (Scenarios) ב-Make.com המחברים את מערכת טופס 101 ל-WhatsApp Business.

---

## תרחיש A — שליחת הזמנה לעובד חדש

**מטרה:** כאשר HR רוצה להזמין עובד חדש למלא טופס 101, הוא קורא לנקודת הקצה של GAS.
GAS שולח Webhook ל-Make, ו-Make שולח הודעת WhatsApp לעובד עם לינק לטופס.

### זרימת נתונים

```
HR → GET /exec?action=notifyEmployee&phone=0500000001&name=...&employer=...&taxYear=2026
        ↓
GAS notifyNewEmployee_()
        ↓
POST → Make Scenario A Webhook
        ↓
WhatsApp Business → הודעה לעובד עם לינק לטופס
```

### בנייה ב-Make.com

**שלב 1: צור תרחיש חדש**
- לחץ "Create a new scenario"
- שם: `form101_invite`

**שלב 2: Trigger — Custom Webhook**
1. בחר Module: **Webhooks → Custom webhook**
2. לחץ "Add" → תן שם "form101_invite"
3. העתק את כתובת ה-Webhook שנוצרת
4. הדבק אותה ב-`Code_v6_fixed2.gs` → `CONFIG.MAKE_INVITE_WEBHOOK_URL`

**מבנה ה-JSON שמגיע מ-GAS:**
```json
{
  "action": "invite",
  "sentAt": "2026-03-01T10:00:00.000Z",
  "rowNum": 24,
  "employee": {
    "name": "ישראל ישראלי",
    "phone": "0500000001"
  },
  "employer": "חברת דוגמה בע\"מ",
  "taxYear": "2026",
  "formUrl": "https://nisimbv.github.io/form-101/index_v6.html"
}
```

**שלב 3: Module 2 — WhatsApp Business → Send a Message**
- **To:** `{{1.employee.phone}}`
  (בפורמט ישראלי: 972XXXXXXXXX — אם WhatsApp דורש +972, הוסף Set Variable שממיר)
- **Message:**
```
שלום {{1.employee.name}} 👋

המעסיק שלך *{{1.employer}}* מבקש ממך למלא טופס 101 לשנת המס {{1.taxYear}}.

📋 לחץ על הקישור למילוי הטופס:
{{1.formUrl}}

לשאלות פנה/י למחלקת משאבי אנוש.
```

> **הערה:** WhatsApp Business דורש Template Message מאושר לשיחה ראשונה עם לקוח.
> שם ה-Template המומלץ: `form_101_invite` (שפה: עברית / Hebrew).

---

## תרחיש B — אישור קבלת טופס 101

**מטרה:** לאחר שעובד מגיש טופס 101 → GAS מייצר PDF ושולח Webhook ל-Make.
Make שולח הודעת WhatsApp לעובד עם אישור קבלה ולינק ל-PDF, ואז קורא ל-GAS Callback לעדכון סטטוס בגיליון.

### זרימת נתונים

```
עובד → Submit טופס → GAS (doPost)
        ↓
saveToSheet → createPDF → updateSheetAfterPdf → sendToMake()
        ↓
POST → Make Scenario B Webhook
        ↓
WhatsApp Business → הודעת אישור + לינק PDF לעובד
        ↓
HTTP GET → GAS confirmSubmission (עדכון סטטוס בגיליון)
```

### בנייה ב-Make.com

**שלב 1: צור תרחיש חדש**
- שם: `form101_submitted`

**שלב 2: Trigger — Custom Webhook**
1. בחר Module: **Webhooks → Custom webhook**
2. לחץ "Add" → תן שם "form101_submitted"
3. העתק את כתובת ה-Webhook שנוצרת
4. הדבק אותה ב-`Code_v6_fixed2.gs` → `CONFIG.MAKE_WEBHOOK_URL`
   וגם ב-`scripts/config.py` → `MAKE_WEBHOOK_URL`

**מבנה ה-JSON שמגיע מ-GAS (עיקרי):**
```json
{
  "meta": {
    "form_version": "101-v6",
    "submitted_at": "2026-03-01T10:05:00.000Z",
    "tax_year": "2026",
    "sheet_row": 24,
    "spreadsheet_id": "1VFSgcm..."
  },
  "pdf": {
    "url": "https://drive.google.com/file/d/.../view",
    "id": "1abc...",
    "name": "טופס_101_2026_ישראלי_ישראל.pdf",
    "drive_path": "HR_101/2026/חברת דוגמה"
  },
  "employer": {
    "name": "חברת דוגמה בע\"מ",
    "tax_id": "500000001",
    "phone": "0500000002",
    "start_date": "2026-01-01"
  },
  "employee": {
    "full_name": "ישראלי ישראל",
    "first_name": "ישראל",
    "last_name": "ישראלי",
    "id_number": "123456789",
    "mobile_phone": "0500000001",
    "email": "israel@example.com",
    "gender": "זכר",
    "marital_status": "רווק/ה"
  },
  "income": { "monthly": true, "pension": false, "summary": "..." },
  "reliefs": { "relief_1_resident": true, "summary": "..." },
  "declaration": { "confirmed": true, "date": "2026-03-01" }
}
```

**שלב 3: Module 2 — WhatsApp Business → Send a Message**
- **To:** `{{1.employee.mobile_phone}}`
- **Message:**
```
שלום {{1.employee.full_name}} ✅

טופס 101 שלך לשנת {{1.meta.tax_year}} *התקבל בהצלחה*!

📄 הטופס הדיגיטלי שלך שמור ב-Google Drive:
{{1.pdf.url}}

תודה שמילאת את הטופס.
*{{1.employer.name}}* — מחלקת משאבי אנוש
```

**שלב 4: Module 3 — HTTP → Make a Request (Callback ל-GAS)**

> שלב זה מעדכן את סטטוס השורה בגיליון מ-"✅ הושלם" → "✅ אושר על ידי HR".

- **URL:**
  ```
  https://script.google.com/macros/s/{DEPLOYMENT_ID}/exec
  ```
  החלף `{DEPLOYMENT_ID}` ב-ID הפריסה של GAS.
- **Method:** GET
- **Query String Parameters:**

  | Key | Value |
  |-----|-------|
  | `action` | `confirmSubmission` |
  | `rowNum` | `{{1.meta.sheet_row}}` |
  | `status` | `✅ אושר על ידי HR` |
  | `source` | `make` |

- **Parse response:** Yes
- **Expected response:**
  ```json
  { "success": true, "rowNum": 24, "status": "✅ אושר על ידי HR" }
  ```

**שלב 5: Error Handler (אופציונלי)**
- הוסף Route עם Filter: `{{3.success}} = false`
- Action: Send email / Slack לצוות HR עם פרטי השגיאה

---

## הגדרת phone format ל-WhatsApp

WhatsApp מצפה למספר בפורמט בינלאומי ללא `+`: `972XXXXXXXXX`
GAS שומר מספרים בפורמט ישראלי: `0XXXXXXXXX`

**המרה ב-Make (Tools → Set Variable):**
```
972{{substring(1.employee.mobile_phone; 1)}}
```
(מסיר את ה-`0` הראשון ומוסיף `972`)

---

## סטטוסים בגיליון

| סטטוס | משמעות |
|-------|---------|
| `ממתין ל-PDF` | הטופס נשמר, PDF בייצור |
| `✅ הושלם` | PDF נוצר, שמור ב-Drive |
| `✅ הושלם · נשלח ל-Make` | Webhook נשלח בהצלחה ל-Make |
| `📨 הזמנה נשלחה` | WhatsApp הזמנה נשלחה לעובד (Scenario A) |
| `✅ אושר על ידי HR` | Make קיבל + שלח WhatsApp + Callback התקבל |
| `⚠ שגיאה: ...` | כישלון בשליחה ל-Make (פרטים בלשונית "שגיאות") |

---

## בדיקת Pipeline

לאחר הגדרת שתי כתובות ה-Webhook ב-`scripts/config.py` ו-`Code_v6_fixed2.gs`, הרץ:

```bash
run_pipeline.bat
```

ה-pipeline בודק:
1. ✅ שליחת טופס E2E (Playwright)
2. ✅ גיליון: 13 עמודות
3. ✅ PDF: 9 שדות טקסט + 10 סימונים
4. ✅ `confirmSubmission` callback
5. ✅ Make webhook (אם `MAKE_WEBHOOK_URL` מוגדר)
