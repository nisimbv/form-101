/**
 * ========================================
 * טופס 101 - V6
 * Backend ל-Google Apps Script
 * ========================================
 * מה חדש:
 * 1) כותרות גיליון בעברית
 * 2) תמיכת Spreadsheet קבוע לפי ID (מומלץ)
 * 3) יצירת PDF לפי תבנית רקע של טופס 101 הרשמי (PDFTemplate.html)
 *
 * התקנה:
 * 1) צור Google Spreadsheet (או בחר קיים)
 * 2) Extensions -> Apps Script
 * 3) צור 2 קבצים:
 *    - Code.gs        -> הדבק את הקוד הזה
 *    - PDFTemplate.html -> הדבק את PDFTemplate_v6.html
 * 4) (מומלץ) מלא SPREADSHEET_ID בקונפיג
 * 5) Deploy -> New deployment -> Web app
 *    Execute as: Me
 *    Who has access: Anyone
 */

const CONFIG = {
  // שם הלשונית (Sheet tab)
  SHEET_NAME: 'מעקב טופס 101',

  // מומלץ מאוד: הדבק כאן את ה-ID של ה-Spreadsheet
  // אם נשאר ריק, הסקריפט ינסה להשתמש ב"Active Spreadsheet" (בדרך כלל רק בפרויקט Bound)
  SPREADSHEET_ID: '1VFSgcmNagnsAjXPsSDOgR9fadkjrbacK3beXCw2VG9Q',

  // תיקיית אב ב-Drive לשמירת PDFs
  MAIN_FOLDER: 'HR_101',

  // Webhook של Make — Scenario B: אישור קבלת טופס (נקרא לאחר יצירת PDF)
  MAKE_WEBHOOK_URL: 'https://hook.eu1.make.com/e3efecqlm7mnpm2gns0gfan7m7e7vdut',

  // Webhook של Make — Scenario A: שליחת הזמנה לעובד חדש
  MAKE_INVITE_WEBHOOK_URL: 'https://hook.eu1.make.com/lj01s419gqchr0hxmrnkx19j7zdjp4d8',

  // כתובת הטופס הציבורית (GitHub Pages)
  FORM_PUBLIC_URL: 'https://nisimbv.github.io/form-101/index_v6.html',

  // פרטי HR להודעות (אופציונלי)
  HR_PHONE: '0524669515',
  HR_EMAIL: '',

  TIMEZONE: 'Asia/Jerusalem',

  // Anthropic API Key — enables Claude visual QA via validatePdf endpoint (optional)
  // Can also be set in Apps Script → Project Settings → Script Properties
  ANTHROPIC_API_KEY: '',
};

function doGet(e) {
  const action = (e && e.parameter && e.parameter.action) || '';
  const out = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);

  if (action === 'getPdf') {
    try {
      const id = e.parameter.id;
      const file = DriveApp.getFileById(id);
      const bytes = file.getBlob().getBytes();
      const b64 = Utilities.base64Encode(bytes);
      out.setContent(JSON.stringify({ success: true, name: file.getName(), data: b64 }));
    } catch(err) {
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  if (action === 'verify') {
    try {
      const ss = CONFIG.SPREADSHEET_ID
        ? SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID)
        : SpreadsheetApp.getActiveSpreadsheet();
      const sh = ss.getSheetByName(CONFIG.SHEET_NAME);
      const lastRow = sh.getLastRow();
      const headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
      const values  = sh.getRange(lastRow, 1, 1, sh.getLastColumn()).getValues()[0];
      const data = {};
      headers.forEach(function(h, i) { data[h] = values[i]; });
      out.setContent(JSON.stringify({ success: true, rows: lastRow - 1, data: data }));
    } catch(err) {
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  if (action === 'listTestRows') {
    try {
      out.setContent(JSON.stringify({ success: true, rows: findTestRows_() }));
    } catch(err) {
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  if (action === 'deleteTestRows') {
    try {
      const deleted = deleteTestRows();
      out.setContent(JSON.stringify({ success: true, deleted }));
    } catch(err) {
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  // ── Callback מ-Make לאחר שליחת WhatsApp — מעדכן סטטוס בגיליון ────────────
  // קריאה: GET /exec?action=confirmSubmission&rowNum=24&status=✅+אושר&source=make
  if (action === 'confirmSubmission') {
    try {
      const rowNum  = parseInt(safeString(e.parameter.rowNum) || '0', 10);
      const status  = safeString(e.parameter.status) || '✅ אושר על ידי HR';
      const source  = safeString(e.parameter.source) || 'make';
      if (!rowNum) throw new Error('rowNum נדרש');

      const ss    = getSpreadsheet_();
      const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
      if (!sheet) throw new Error('גיליון לא נמצא');

      const prev = String(sheet.getRange(rowNum, 39).getValue());
      sheet.getRange(rowNum, 39).setValue(status);
      Logger.log(`confirmSubmission: row=${rowNum} "${prev}" → "${status}" (source=${source})`);
      out.setContent(JSON.stringify({ success: true, rowNum, status, previous: prev }));
    } catch(err) {
      Logger.log('confirmSubmission ERROR: ' + String(err));
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  // ── Claude visual QA — Make קורא לפני שליחת WhatsApp ─────────────────────
  // קריאה: GET /exec?action=validatePdf&fileId=<DRIVE_FILE_ID>
  if (action === 'validatePdf') {
    try {
      out.setContent(JSON.stringify(validatePdfAction_(e.parameter)));
    } catch(err) {
      Logger.log('validatePdf ERROR: ' + String(err));
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  // ── שליחת הזמנה לעובד חדש — HR קורא לנקודת קצה זו, GAS שולח ל-Make ────────
  // קריאה: GET /exec?action=notifyEmployee&rowNum=24&name=...&phone=...&employer=...&taxYear=2026
  if (action === 'notifyEmployee') {
    try {
      const rowNum   = parseInt(safeString(e.parameter.rowNum) || '0', 10);
      const name     = safeString(e.parameter.name);
      const phone    = normalizePhone_(safeString(e.parameter.phone));
      const employer = safeString(e.parameter.employer);
      const taxYear  = safeString(e.parameter.taxYear) || String(new Date().getFullYear());
      if (!phone) throw new Error('phone נדרש');

      notifyNewEmployee_(rowNum, name, phone, employer, taxYear);
      out.setContent(JSON.stringify({ success: true, sent: true, to: phone }));
    } catch(err) {
      Logger.log('notifyEmployee ERROR: ' + String(err));
      out.setContent(JSON.stringify({ success: false, error: String(err) }));
    }
    return out;
  }

  out.setContent(JSON.stringify({ status: 'ok', service: 'form-101', version: '6.0' }));
  return out;
}

/* ==============================
   Cleanup — Test Rows
============================== */

const TEST_ID_NUMBERS = ['123456789'];  // ת"ז של שורות בדיקה אוטומטיות

/**
 * Returns an array of { rowNum, name, id, date } for every test row.
 * A "test row" is one whose מספר זהות matches TEST_ID_NUMBERS.
 */
function findTestRows_() {
  const ss = getSpreadsheet_();
  const sh = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sh || sh.getLastRow() < 2) return [];

  const headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  const idCol   = headers.indexOf('מספר זהות') + 1;   // 1-based
  const nameCol = headers.indexOf('שם משפחה')  + 1;
  const firstCol= headers.indexOf('שם פרטי')   + 1;
  const dateCol = headers.indexOf('תאריך הגשה') + 1;
  if (idCol === 0) return [];

  const data = sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).getValues();
  const results = [];
  data.forEach((row, i) => {
    const id = String(row[idCol - 1]).trim();
    if (TEST_ID_NUMBERS.includes(id)) {
      results.push({
        rowNum: i + 2,
        id,
        name: `${row[nameCol - 1]} ${row[firstCol - 1]}`.trim(),
        date: safeString(row[dateCol - 1]),
      });
    }
  });
  return results;
}

/**
 * Deletes all test rows from the sheet (bottom-up to keep row numbers stable).
 * Returns the number of rows deleted.
 */
function deleteTestRows() {
  const ss = getSpreadsheet_();
  const sh = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sh) return 0;

  const testRows = findTestRows_();
  // Delete bottom-up so row indices don't shift
  testRows.slice().reverse().forEach(r => sh.deleteRow(r.rowNum));
  Logger.log(`deleteTestRows: removed ${testRows.length} rows`);
  return testRows.length;
}

/**
 * Weekly trigger function — sends a reminder email (if HR_EMAIL is set)
 * listing all test rows still present in the sheet.
 * Install once via installCleanupReminder().
 */
function weeklyCleanupReminder() {
  const testRows = findTestRows_();
  if (testRows.length === 0) return;  // nothing to report

  const body = [
    `שלום,`,
    ``,
    `נמצאו ${testRows.length} שורות בדיקה בגיליון "${CONFIG.SHEET_NAME}":`,
    ``,
    ...testRows.map(r => `  • שורה ${r.rowNum} — ${r.name} (ת"ז: ${r.id}) — ${r.date}`),
    ``,
    `ניתן למחוק אותן ידנית מהגיליון, או להריץ את deleteTestRows() ב-Apps Script.`,
  ].join('\n');

  if (CONFIG.HR_EMAIL && String(CONFIG.HR_EMAIL).trim()) {
    MailApp.sendEmail({
      to: CONFIG.HR_EMAIL,
      subject: `[טופס 101] תזכורת: ${testRows.length} שורות בדיקה בגיליון`,
      body,
    });
    Logger.log('weeklyCleanupReminder: email sent to ' + CONFIG.HR_EMAIL);
  } else {
    Logger.log('weeklyCleanupReminder: ' + body);
  }
}

/**
 * Run ONCE manually from the Apps Script editor to create the weekly trigger.
 * Subsequent runs are automatic (every Monday at 09:00 IL time).
 */
function installCleanupReminder() {
  // Remove any existing trigger with the same function name to avoid duplicates
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'weeklyCleanupReminder')
    .forEach(t => ScriptApp.deleteTrigger(t));

  ScriptApp.newTrigger('weeklyCleanupReminder')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(9)
    .create();

  Logger.log('installCleanupReminder: weekly trigger created (Monday 09:00)');
}

function doPost(e) {
  const output = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);

  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error('בקשה ריקה / חסר גוף POST');
    }

    const data = JSON.parse(e.postData.contents);
    // Payload arrives with bindKey names directly — no normalizePayload() needed
    data['children']     = Array.isArray(data['children'])     ? data['children']     : [];
    data['other_income'] = Array.isArray(data['other_income']) ? data['other_income'] : [];
    data['changes']      = Array.isArray(data['changes'])      ? data['changes']      : [];
    if (!data['_op.submitted_at']) data['_op.submitted_at'] = new Date().toISOString();

    // 1) שמירה ל-Sheet (Hebrew legacy tab)
    const rowNum = saveToSheet(data);

    // 2) יצירת PDF
    const pdfFile = createPDF(data);

    // 3) עדכון שורה עם פרטי PDF (legacy tab)
    updateSheetAfterPdf(rowNum, pdfFile);

    // 3b) שמירה ל-Form101_NEW3_FF (Full-Fidelity, bindKey columns)
    try {
      const ffRow = saveToSheetFF_(data, null);
      updateSheetFFAfterPdf_(ffRow, pdfFile);
      Logger.log('FF tab row=' + ffRow);
    } catch (ffErr) {
      Logger.log('FF tab error (non-fatal): ' + String(ffErr));
    }

    // 4) ארגון תיקיית עובד ב-Drive (PDF + קבצים מצורפים)
    try {
      organizeEmployeeFolder_(data, pdfFile);
    } catch (folderErr) {
      Logger.log('organizeEmployeeFolder_ error (non-fatal): ' + String(folderErr));
    }

    // 5) Webhook ל-Make (אם הוגדר)
    sendToMake(data, pdfFile, rowNum);

    output.setContent(JSON.stringify({
      success: true,
      message: 'טופס 101 נשלח בהצלחה',
      rowNum,
      pdfUrl: pdfFile.getUrl(),
      fileId: pdfFile.getId(),
      fileName: pdfFile.getName(),
    }));
    return output;

  } catch (err) {
    Logger.log('ERROR: ' + (err && err.stack ? err.stack : err));
    output.setContent(JSON.stringify({
      success: false,
      message: 'שגיאה בעיבוד הטופס: ' + (err && err.message ? err.message : String(err)),
    }));
    return output;
  }
}

/* ==============================
   Summary Builders (legacy Hebrew sheet columns)
   Read from bindKey-named payload fields.
============================== */

function buildIncomeTypesSummary(d) {
  const b = k => !!d[k];
  const a = [];
  if (b('income.main.monthly_salary')) a.push('משכורת חודשית');
  if (b('income.main.additional_job')) a.push('משכורת נוספת');
  if (b('income.main.partial_salary')) a.push('משכורת חלקית');
  if (b('income.main.daily_worker'))   a.push('שכר עבודה (יומי/שבועי)');
  if (b('income.main.pension'))        a.push('קצבה');
  if (b('income.main.scholarship'))    a.push('מלגה');
  return a.length ? ('סוגי הכנסה ממעסיק זה: ' + a.join(', ')) : '';
}

function buildOtherIncomeSummary(d) {
  const b  = k => !!d[k];
  const oi = d['other_income'] || [];
  if (b('income.other.none')) return 'אין הכנסות אחרות (לפי הצהרה)';
  const a = [];
  if (b('income.other.monthly_salary')) a.push('משכורת חודשית');
  if (b('income.other.additional_job')) a.push('משכורת נוספת');
  if (b('income.other.partial_salary')) a.push('משכורת חלקית');
  if (b('income.other.daily_worker'))   a.push('שכר עבודה (יומי/שבועי)');
  if (b('income.other.pension'))        a.push('קצבה');
  if (b('income.other.scholarship'))    a.push('מלגה');
  const parts = ['יש הכנסות אחרות: ' + (a.length ? a.join(', ') : 'כן')];
  if (oi.length) {
    const txt = oi
      .map(x => `${safeString(x.payer_name)||''} ₪${safeString(x.monthly_amount)||''} (מס:${safeString(x.tax_withheld)||''})`)
      .filter(Boolean).join(' | ');
    if (txt) parts.push('פירוט מעסיקים נוספים: ' + txt);
  }
  if (b('income.other.no_training_fund')) parts.push('ללא קרן השתלמות במקום אחר');
  if (b('income.other.no_pension'))        parts.push('ללא קופת גמל/פנסיה במקום אחר');
  return parts.join(' · ');
}

function buildSpouseSummary(d) {
  const sd = k => safeString(d[k]);
  const hasSpouse = !!(sd('spouse.last_name') || sd('spouse.id'));
  if (!hasSpouse) return '';
  const parts = [];
  parts.push(('בן/בת זוג: ' + sd('spouse.last_name') + ' ' + sd('spouse.first_name')).trim());
  const idp = sd('spouse.id') || sd('spouse.passport');
  if (idp) parts.push('ת"ז/דרכון: ' + idp);
  if (sd('spouse.birth_date'))        parts.push('ת. לידה: ' + sd('spouse.birth_date'));
  if (sd('spouse.immigration_date'))  parts.push('ת. עליה: ' + sd('spouse.immigration_date'));
  parts.push('יש לבן/בת הזוג הכנסה: ' + (!!d['spouse.has_income.yes'] ? 'כן' : 'לא'));
  return parts.join(' · ');
}

function buildReliefsSummary(d) {
  const b = k => !!d[k];
  const items = [];
  if (b('credits.1_israeli_resident'))                     items.push('1. תושב/ת ישראל');
  if (b('credits.2a_disability_100_or_blind'))             items.push('2. נכות');
  if (b('credits.2b_monthly_benefit'))                     items.push('2.1 מקבל/ת קצבה');
  if (b('credits.3_eligible_locality'))                    items.push('3. יישוב מזכה');
  if (b('credits.4_new_immigrant'))                        items.push('4. עולה חדש/ה');
  if (b('credits.5_spouse_no_income'))                     items.push('5. בן/בת זוג ללא הכנסה');
  if (b('credits.6_single_parent_family'))                 items.push('6. הורה יחיד');
  if (b('credits.7_children_in_custody'))                  items.push('7. ילדים בחזקתי');
  if (b('credits.8_children_not_in_custody'))              items.push('8. ילדים');
  if (b('credits.9_single_parent'))                        items.push('9. הורה עצמאי/ת');
  if (b('credits.10_children_not_in_custody_maintenance')) items.push('10. ילדים לא בחזקתי');
  if (b('credits.11_disabled_child'))                      items.push('11. ילד נכה');
  if (b('credits.12_spousal_support'))                     items.push('12. מזונות');
  if (b('credits.13_age_16_18'))                           items.push('13. ילדים בגיל 16–18');
  if (b('credits.14_released_soldier_or_service'))         items.push('14. חייל משוחרר/ת');
  if (b('credits.15_graduation'))                          items.push('15. השכלה אקדמית');
  if (b('credits.16_reserve_combat'))                      items.push('16. שירות מילואים');
  if (b('tax_coordination.no_income_until_start'))         items.push('17. אין הכנסה');
  return items.length ? ('בקשות להקלות מס: ' + items.join(' · ')) : '';
}

function buildTaxCoordinationSummary(d) {
  if (!d['tax_coordination.has_additional_income']) return '';
  const parts = ['תיאום מס: כן'];
  if (d['tax_coordination.approval_attached']) parts.push('אישור פקיד שומה: כן');
  return parts.join(' · ');
}

/* ==============================
   Sheet
============================== */

function getSpreadsheet_() {
  if (CONFIG.SPREADSHEET_ID && String(CONFIG.SPREADSHEET_ID).trim()) {
    return SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID.trim());
  }
  return SpreadsheetApp.getActiveSpreadsheet();
}

function saveToSheet(data) {
  const ss = getSpreadsheet_();
  if (!ss) throw new Error('לא נמצא Spreadsheet. מלא CONFIG.SPREADSHEET_ID או ודא שהפרויקט Bound לגיליון.');

  let sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(CONFIG.SHEET_NAME);

    const headers = [
    // מטא מערכת
    'תאריך הגשה',                    // 1
    'שנת מס',                        // 2
    // סעיף א׳ — פרטי המעסיק
    'שם המעסיק',                     // 3
    'מספר תיק ניכויים',              // 4
    'טלפון המעסיק',                  // 5
    'כתובת המעסיק',                  // 6
    'תאריך תחילת עבודה',             // 7
    // סעיף ב׳ — פרטי העובד
    'שם משפחה',                      // 8
    'שם פרטי',                       // 9
    'מספר זהות',                     // 10
    'מספר דרכון',                    // 11
    'תאריך לידה',                    // 12
    'תאריך עלייה',                   // 13
    'כתובת עובד',                    // 14
    'מיקוד',                         // 15
    'טלפון נייד',                    // 16
    'אימייל',                        // 17
    'מין',                           // 18
    'מצב משפחתי',                    // 19
    'תושב ישראל',                    // 20
    'חבר קיבוץ/מושב שיתופי',        // 21
    'קופת חולים',                    // 22
    // סעיף ג׳ — ילדים
    'מספר ילדים',                    // 23
    'ילדים (JSON)',                   // 24
    // סעיף ד׳ — סוג ההכנסה
    'סוג הכנסה ממעסיק',              // 25
    // סעיף ה׳ — הכנסות ממעסיקים אחרים
    'יש הכנסות אחרות',              // 26
    'מספר הכנסות נוספות',           // 27
    'הכנסות נוספות (JSON)',          // 28
    'ללא קרן השתלמות אחרת',         // 29
    'ללא פנסיה/גמל אחרת',           // 30
    // סעיף ו׳ — בן/בת זוג
    'יש בן/בת זוג',                 // 31
    'פרטי בן/בת זוג',               // 32
    // סעיף ח׳ — זכאויות
    'זכאויות - סיכום',              // 33
    // סעיף ת׳ — תיאום מס
    'יש תיאום מס',                  // 34
    // סעיף ז׳ — שינויים
    'שינויים במהלך השנה (JSON)',     // 35
    // הצהרה
    'תאריך הצהרה',                   // 36
    // מערכת / PDF
    'קישור PDF',                     // 37
    'מזהה קובץ ב-Drive',             // 38
    'סטטוס',                         // 39
    // פנימי
    'סיכום',                         // 40
    'JSON מלא',                      // 41
  ];

  // Set headers — refresh if empty or content doesn't match V6 layout
  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  const existing = headerRange.getValues()[0];
  const needsUpdate = existing.every(v => !v) || JSON.stringify(existing) !== JSON.stringify(headers);
  if (needsUpdate) {
    headerRange.setValues([headers]);
    headerRange.setBackground('#1f4e79');
    headerRange.setFontColor('white');
    headerRange.setFontWeight('bold');
    headerRange.setHorizontalAlignment('center');
    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, headers.length);
  }

  // Force text format on phone columns so leading zeros are never dropped by Sheets
  // col 5 = טלפון המעסיק, col 16 = טלפון נייד
  const maxRow = sheet.getMaxRows();
  sheet.getRange(2, 5,  maxRow - 1, 1).setNumberFormat('@');
  sheet.getRange(2, 16, maxRow - 1, 1).setNumberFormat('@');

    // Derive display strings from boolean bindKeys
  const d  = k => safeString(data[k]);
  const b  = k => !!data[k];
  const ch = data['children']     || [];
  const oi = data['other_income'] || [];

  const gender = b('employee.gender.male') ? 'זכר' : b('employee.gender.female') ? 'נקבה' : '';
  const ms = b('employee.marital_status.married')   ? 'נשוי/אה' :
             b('employee.marital_status.single')    ? 'רווק/ה'  :
             b('employee.marital_status.divorced')  ? 'גרוש/ה'  :
             b('employee.marital_status.widowed')   ? 'אלמן/ה'  :
             b('employee.marital_status.separated') ? 'פרוד/ה'  : '';
  const kibbutz   = b('employee.kibbutz_member.income_transferred') ? 'כן' :
                    b('employee.kibbutz_member.no') ? 'לא' : '';
  const hasSpouse = !!(d('spouse.last_name') || d('spouse.id'));

  const mobilePhone   = normalizePhone_(d('employee.mobile'));
  const employerPhone = normalizePhone_(d('employer.phone'));

  const row = [
    // מטא מערכת
    formatTimestamp_(data['_op.submitted_at']),       // 1:  תאריך הגשה
    d('meta.tax_year'),                               // 2:  שנת מס
    // סעיף א׳ — פרטי המעסיק
    d('employer.name'),                               // 3:  שם המעסיק
    d('employer.deductions_file'),                    // 4:  מספר תיק ניכויים
    employerPhone,                                    // 5:  טלפון המעסיק
    d('employer.address'),                            // 6:  כתובת המעסיק
    d('employment.start_date'),                       // 7:  תאריך תחילת עבודה
    // סעיף ב׳ — פרטי העובד
    d('employee.last_name'),                          // 8:  שם משפחה
    d('employee.first_name'),                         // 9:  שם פרטי
    d('employee.id'),                                 // 10: מספר זהות
    d('employee.passport'),                           // 11: מספר דרכון
    d('employee.birth_date'),                         // 12: תאריך לידה
    d('employee.immigration_date'),                   // 13: תאריך עלייה
    d('employee.address.street'),                     // 14: כתובת עובד
    d('employee.address.zip'),                        // 15: מיקוד
    mobilePhone,                                      // 16: טלפון נייד
    d('employee.email'),                              // 17: אימייל
    gender,                                           // 18: מין
    ms,                                               // 19: מצב משפחתי
    b('employee.has_id.yes') ? 'כן' : 'לא',          // 20: תושב ישראל (has_id proxy)
    kibbutz,                                          // 21: חבר קיבוץ/מושב שיתופי
    d('employee.health_fund.name'),                   // 22: קופת חולים
    // סעיף ג׳ — ילדים
    ch.length,                                        // 23: מספר ילדים
    JSON.stringify(ch),                               // 24: ילדים (JSON)
    // סעיף ד׳ — סוג ההכנסה
    buildIncomeTypesSummary(data),                    // 25: סוג הכנסה ממעסיק
    // סעיף ה׳ — הכנסות ממעסיקים אחרים
    !b('income.other.none') ? 'כן' : 'לא',          // 26: יש הכנסות אחרות
    oi.length,                                        // 27: מספר הכנסות נוספות
    JSON.stringify(oi),                               // 28: הכנסות נוספות (JSON)
    b('income.other.no_training_fund') ? 'כן' : 'לא', // 29: ללא קרן השתלמות אחרת
    b('income.other.no_pension') ? 'כן' : 'לא',     // 30: ללא פנסיה/גמל אחרת
    // סעיף ו׳ — בן/בת זוג
    hasSpouse ? 'כן' : 'לא',                         // 31: יש בן/בת זוג
    buildSpouseSummary(data),                         // 32: פרטי בן/בת זוג
    // סעיף ח׳ — זכאויות
    buildReliefsSummary(data),                        // 33: זכאויות - סיכום
    // סעיף ת׳ — תיאום מס
    b('tax_coordination.has_additional_income') ? 'כן' : 'לא', // 34: יש תיאום מס
    // סעיף ז׳ — שינויים
    JSON.stringify(data['changes'] || []),            // 35: שינויים במהלך השנה (JSON)
    // הצהרה
    d('signature.date'),                              // 36: תאריך הצהרה
    // מערכת / PDF
    '',                                               // 37: קישור PDF
    '',                                               // 38: מזהה קובץ ב-Drive
    'ממתין ל-PDF',                                   // 39: סטטוס
    // פנימי
    JSON.stringify(buildSummary(data)),               // 40: סיכום
    JSON.stringify(data),                             // 41: JSON מלא
  ];

  sheet.appendRow(row);
  const newRow = sheet.getLastRow();

  // Re-write phone cells as explicit text so Sheets stores '0XXXXXXXXX', not integer
  const phoneEmployer2 = row[4];   // col 5
  const phoneMobile2   = row[15];  // col 16
  if (phoneEmployer2) sheet.getRange(newRow, 5).setNumberFormat('@').setValue(String(phoneEmployer2));
  if (phoneMobile2)   sheet.getRange(newRow, 16).setNumberFormat('@').setValue(String(phoneMobile2));

  return newRow;
}


function buildSummary(data) {
  const d   = k => safeString(data[k]);
  const b   = k => !!data[k];
  const ch  = data['children']     || [];
  const oi  = data['other_income'] || [];
  const fullName = [d('employee.last_name'), d('employee.first_name')].filter(Boolean).join(' ');
  const hasSpouse = !!(d('spouse.last_name') || d('spouse.id'));
  const parts = [];
  if (fullName)              parts.push('עובד: ' + fullName);
  if (d('employee.id'))      parts.push('ת"ז: ' + d('employee.id'));
  if (d('employer.name'))    parts.push('מעסיק: ' + d('employer.name'));
  if (d('employment.start_date')) parts.push('תחילת עבודה: ' + d('employment.start_date'));
  parts.push('ילדים: ' + ch.length);
  parts.push('הכנסות נוספות: ' + oi.length);
  if (hasSpouse)                           parts.push('יש בן/בת זוג');
  if (!b('income.other.none'))             parts.push('יש הכנסות אחרות');
  if (b('tax_coordination.has_additional_income')) parts.push('יש תיאום מס');
  return {
    full_name:                d('employee.last_name') + ' ' + d('employee.first_name'),
    id_number:                d('employee.id'),
    employer_name:            d('employer.name'),
    start_date:               d('employment.start_date'),
    children_count:           ch.length,
    additional_incomes_count: oi.length,
    has_spouse:               hasSpouse,
    has_other_income:         !b('income.other.none'),
    has_tax_coordination:     b('tax_coordination.has_additional_income'),
    text: parts.join(' | ')
  };
}

/* ==============================
   Form101_NEW3_FF — Full-Fidelity Sheet
   Single source of truth: every column = one bindKey from form_101_mapping JSON.
   No Hebrew in headers; Hebrew display dictionary is maintained separately.
   Operational columns prefixed _op.*
============================== */

// 126 data bindKeys (JSON page-order, skipping house_no / city / landline)
// + 4 operational columns. Generated from NEW3 JSON — do NOT edit manually.
const FF_HEADERS = [
  'meta.tax_year',
  'employer.deductions_file',
  'employer.name',
  'employer.address',
  'employer.phone',
  'employee.id',
  'employee.last_name',
  'employee.first_name',
  'employee.birth_date',
  'employee.immigration_date',
  'employee.passport',
  'employee.address.street',
  'employee.address.house_no',
  'employee.address.city',
  'employee.address.zip',
  'employee.mobile',
  'employee.email',
  'employee.gender.male',
  'employee.gender.female',
  'employee.marital_status.married',
  'employee.marital_status.single',
  'employee.marital_status.divorced',
  'employee.marital_status.widowed',
  'employee.marital_status.separated',
  'employee.has_id.yes',
  'employee.has_id.no',
  'employee.kibbutz_member.no',
  'employee.kibbutz_member.income_transferred',
  'employee.kibbutz_member.income_not_transferred',
  'employee.health_fund.member.yes',
  'employee.health_fund.member.no',
  'employee.health_fund.name',
  'children[0].name',
  'children[0].id',
  'children[0].birth_date',
  'children[1].name',
  'children[1].id',
  'children[1].birth_date',
  'children[0].in_custody',
  'children[1].in_custody',
  'children[1].receives_allowance',
  'children[0].receives_allowance',
  'children[2].receives_allowance',
  'children[2].in_custody',
  'children[2].name',
  'children[2].id',
  'children[2].birth_date',
  'children[3].name',
  'children[3].id',
  'children[3].birth_date',
  'children[3].in_custody',
  'children[3].receives_allowance',
  'income.main.monthly_salary',
  'income.main.additional_job',
  'income.main.partial_salary',
  'income.main.daily_worker',
  'income.main.pension',
  'income.main.scholarship',
  'employment.start_date',
  'income.other.none',
  'income.other.monthly_salary',
  'income.other.additional_job',
  'income.other.partial_salary',
  'income.other.daily_worker',
  'income.other.pension',
  'income.other.scholarship',
  'income.credit_request.get_credits_here',
  'income.credit_request.get_credits_elsewhere',
  'income.other.no_training_fund',
  'income.other.no_pension',
  'spouse.id',
  'spouse.passport',
  'spouse.last_name',
  'spouse.first_name',
  'spouse.birth_date',
  'spouse.immigration_date',
  'spouse.has_income.none',
  'spouse.has_income.yes',
  'spouse.income_type.work',
  'spouse.income_type.other',
  'credits.1_israeli_resident',
  'credits.2a_disability_100_or_blind',
  'credits.2b_monthly_benefit',
  'credits.3_eligible_locality',
  'credits.3_from_date',
  'credits.3_locality_name',
  'credits.4_new_immigrant',
  'credits.4_from_date',
  'credits.4_no_income_until',
  'credits.5_spouse_no_income',
  'credits.6_single_parent_family',
  'credits.7_children_in_custody',
  'credits.7_children_born_in_year',
  'credits.7_children_count_6_17',
  'credits.7_children_count_18',
  'credits.7_children_count_1_5',
  'credits.8_children_not_in_custody',
  'credits.8_children_count_1_5',
  'credits.8_children_count_6_17',
  'credits.9_single_parent',
  'credits.10_children_not_in_custody_maintenance',
  'credits.11_disabled_child',
  'credits.12_spousal_support',
  'credits.13_age_16_18',
  'credits.14_released_soldier_or_service',
  'credits.14_service_start',
  'credits.14_service_end',
  'credits.15_graduation',
  'credits.16_reserve_combat',
  'credits.16_reserve_days_prev_year',
  'tax_coordination.no_income_until_start',
  'tax_coordination.has_additional_income',
  'tax_coordination.approval_attached',
  'other_income[0].type',
  'other_income[0].payer_name',
  'other_income[0].address',
  'other_income[0].deductions_file',
  'other_income[0].monthly_amount',
  'other_income[0].tax_withheld',
  'other_income[1].type',
  'other_income[1].payer_name',
  'other_income[1].address',
  'other_income[1].deductions_file',
  'other_income[1].monthly_amount',
  'other_income[1].tax_withheld',
  'signature.date',
  'signature.declaration',
  'signature.applicant_signature',
  // operational — not in JSON
  '_op.submitted_at',
  '_op.pdf_url',
  '_op.file_id',
  '_op.status',
];

// Hebrew display labels for FF_HEADERS (same order, same length)
const FF_HEADER_LABELS = [
  'שנת מס',
  'מספר תיק ניכויים',
  'שם מעסיק',
  'כתובת מעסיק',
  'טלפון מעסיק',
  'מספר זהות',
  'שם משפחה',
  'שם פרטי',
  'תאריך לידה',
  'תאריך עלייה',
  'מספר דרכון',
  'רחוב',
  'מספר בית',
  'עיר/ישוב',
  'מיקוד',
  'טלפון נייד',
  'דוא"ל',
  'מגדר - זכר',
  'מגדר - נקבה',
  'נשוי/ה',
  'רווק/ה',
  'גרוש/ה',
  'אלמן/ה',
  'פרוד/ה',
  'יש תעודת זהות',
  'אין תעודת זהות',
  'לא חבר קיבוץ',
  'הכנסה מועברת לקיבוץ',
  'הכנסה לא מועברת לקיבוץ',
  'חבר קופת חולים',
  'לא חבר קופת חולים',
  'שם קופת חולים',
  'שם ילד 1',
  'ת.ז ילד 1',
  'ת. לידה ילד 1',
  'שם ילד 2',
  'ת.ז ילד 2',
  'ת. לידה ילד 2',
  'משמורת ילד 1',
  'משמורת ילד 2',
  'קצבה ילד 2',
  'קצבה ילד 1',
  'קצבה ילד 3',
  'משמורת ילד 3',
  'שם ילד 3',
  'ת.ז ילד 3',
  'ת. לידה ילד 3',
  'שם ילד 4',
  'ת.ז ילד 4',
  'ת. לידה ילד 4',
  'משמורת ילד 4',
  'קצבה ילד 4',
  'שכר חודשי רגיל',
  'עבודה נוספת',
  'שכר חלקי',
  'עובד יומי',
  'קצבה',
  'מלגה',
  'תאריך תחילת עבודה',
  'אין הכנסות אחרות',
  'הכנסה אחרת - שכר חודשי',
  'הכנסה אחרת - עבודה נוספת',
  'הכנסה אחרת - שכר חלקי',
  'הכנסה אחרת - עובד יומי',
  'הכנסה אחרת - קצבה',
  'הכנסה אחרת - מלגה',
  'בקשת זיכוי - כאן',
  'בקשת זיכוי - במקום אחר',
  'ללא קרן השתלמות',
  'ללא פנסיה',
  'ת.ז בן/בת זוג',
  'דרכון בן/בת זוג',
  'שם משפחה בן/בת זוג',
  'שם פרטי בן/בת זוג',
  'ת. לידה בן/בת זוג',
  'תאריך עלייה בן/בת זוג',
  'אין הכנסה לבן/בת זוג',
  'יש הכנסה לבן/בת זוג',
  'הכנסת בן/בת זוג - עבודה',
  'הכנסת בן/בת זוג - אחר',
  'זכאות 1 - תושב ישראל',
  'זכאות 2א - נכות 100%',
  'זכאות 2ב - גמלה חודשית',
  'זכאות 3 - ישוב מזכה',
  'זכאות 3 - מתאריך',
  'זכאות 3 - שם ישוב',
  'זכאות 4 - עולה חדש',
  'זכאות 4 - מתאריך',
  'זכאות 4 - ללא הכנסה עד',
  'זכאות 5 - בן/בת זוג ללא הכנסה',
  'זכאות 6 - משפחה חד הורית',
  'זכאות 7 - ילדים במשמורת',
  'זכאות 7 - ילד שנולד בשנה',
  'זכאות 7 - ילדים 6-17',
  'זכאות 7 - ילדים 18+',
  'זכאות 7 - ילדים 1-5',
  'זכאות 8 - ילדים לא במשמורת',
  'זכאות 8 - ילדים 1-5',
  'זכאות 8 - ילדים 6-17',
  'זכאות 9 - הורה יחיד',
  'זכאות 10 - מזונות',
  'זכאות 11 - ילד עם מוגבלות',
  'זכאות 12 - מזונות לבן/בת זוג',
  'זכאות 13 - גיל 16-18',
  'זכאות 14 - שחרור שירות',
  'זכאות 14 - תחילת שירות',
  'זכאות 14 - סיום שירות',
  'זכאות 15 - סיום לימודים',
  'זכאות 16 - מילואים לוחמים',
  'זכאות 16 - ימי מילואים שנה קודמת',
  'תיאום מס - ללא הכנסה עד תחילה',
  'תיאום מס - יש הכנסה נוספת',
  'תיאום מס - אישור מצורף',
  'הכנסה אחרת 1 - סוג',
  'הכנסה אחרת 1 - שם משלם',
  'הכנסה אחרת 1 - כתובת',
  'הכנסה אחרת 1 - תיק ניכויים',
  'הכנסה אחרת 1 - סכום חודשי',
  'הכנסה אחרת 1 - מס שנוכה',
  'הכנסה אחרת 2 - סוג',
  'הכנסה אחרת 2 - שם משלם',
  'הכנסה אחרת 2 - כתובת',
  'הכנסה אחרת 2 - תיק ניכויים',
  'הכנסה אחרת 2 - סכום חודשי',
  'הכנסה אחרת 2 - מס שנוכה',
  'תאריך חתימה',
  'הצהרה',
  'חתימה',
  'זמן הגשה',
  'קישור PDF',
  'מזהה קובץ',
  'סטטוס',
];

/**
 * Build a flat FF row directly from bindKey-named payload `data`.
 * No translation needed — frontend sends bindKey names 1:1.
 * Arrays (children, other_income) are expanded to flat bindKey slots.
 */
function buildFFRow_(data) {
  const ch = data['children']     || [];
  const oi = data['other_income'] || [];
  const row = {};

  // Copy all scalar bindKey fields directly
  FF_HEADERS.forEach(function(h) {
    if (h.startsWith('_op.') || h.startsWith('children[') || h.startsWith('other_income[')) return;
    const v = data[h];
    row[h] = v !== undefined ? String(v) : '';
  });

  // Expand children[] array → children[i].field flat slots
  for (let i = 0; i < 4; i++) {
    row[`children[${i}].name`]               = ch[i] ? String(ch[i].name || '') : '';
    row[`children[${i}].id`]                 = ch[i] ? String(ch[i].id || '') : '';
    row[`children[${i}].birth_date`]         = ch[i] ? String(ch[i].birth_date || '') : '';
    row[`children[${i}].in_custody`]         = ch[i] ? String(!!ch[i].in_custody) : 'false';
    row[`children[${i}].receives_allowance`] = ch[i] ? String(!!ch[i].receives_allowance) : 'false';
  }

  // Expand other_income[] array → other_income[i].field flat slots
  for (let i = 0; i < 2; i++) {
    row[`other_income[${i}].type`]            = oi[i] ? String(oi[i].type || '') : '';
    row[`other_income[${i}].payer_name`]      = oi[i] ? String(oi[i].payer_name || '') : '';
    row[`other_income[${i}].address`]         = oi[i] ? String(oi[i].address || '') : '';
    row[`other_income[${i}].deductions_file`] = oi[i] ? String(oi[i].deductions_file || '') : '';
    row[`other_income[${i}].monthly_amount`]  = oi[i] ? String(oi[i].monthly_amount || '') : '';
    row[`other_income[${i}].tax_withheld`]    = oi[i] ? String(oi[i].tax_withheld || '') : '';
  }

  // Operational columns (filled by caller)
  row['_op.submitted_at'] = '';
  row['_op.pdf_url']      = '';
  row['_op.file_id']      = '';
  row['_op.status']       = '';
  return row;
}

/**
 * Save a submission to the Form101_NEW3_FF tab (Full-Fidelity, bindKey columns).
 * Creates the tab and header row if they don't exist.
 * Returns the 1-based row number written.
 */
function saveToSheetFF_(data, pdfViewModel) {
  const ss = getSpreadsheet_();
  if (!ss) return null;

  const FF_TAB = 'Form101_NEW3_FF';
  let sheet = ss.getSheetByName(FF_TAB);
  if (!sheet) sheet = ss.insertSheet(FF_TAB);

  // Ensure header row matches FF_HEADER_LABELS exactly
  const existingHeaders = sheet.getLastRow() > 0
    ? sheet.getRange(1, 1, 1, FF_HEADERS.length).getValues()[0]
    : [];
  if (JSON.stringify(existingHeaders) !== JSON.stringify(FF_HEADER_LABELS)) {
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(FF_HEADER_LABELS);
    } else {
      sheet.getRange(1, 1, 1, FF_HEADERS.length).setValues([FF_HEADER_LABELS]);
    }
  }

  const rowObj = buildFFRow_(data);
  rowObj['_op.submitted_at'] = data['_op.submitted_at'] || new Date().toISOString();

  const rowArr = FF_HEADERS.map(h => rowObj[h] !== undefined ? rowObj[h] : '');
  sheet.appendRow(rowArr);
  return sheet.getLastRow();
}

/**
 * Update operational columns (_op.pdf_url, _op.file_id, _op.status) in FF tab
 * after PDF creation.
 */
function updateSheetFFAfterPdf_(ffRowNum, pdfFile) {
  if (!ffRowNum || !pdfFile) return;
  const ss = getSpreadsheet_();
  if (!ss) return;
  const sheet = ss.getSheetByName('Form101_NEW3_FF');
  if (!sheet) return;
  const pdfUrlCol  = FF_HEADERS.indexOf('_op.pdf_url')  + 1;
  const fileIdCol  = FF_HEADERS.indexOf('_op.file_id')  + 1;
  const statusCol  = FF_HEADERS.indexOf('_op.status')   + 1;
  if (pdfUrlCol > 0)  sheet.getRange(ffRowNum, pdfUrlCol).setValue(pdfFile.getUrl());
  if (fileIdCol > 0)  sheet.getRange(ffRowNum, fileIdCol).setValue(pdfFile.getId());
  if (statusCol > 0)  sheet.getRange(ffRowNum, statusCol).setValue('✅ הושלם');
}

function updateSheetAfterPdf(rowNum, pdfFile) {
  if (!rowNum || !pdfFile) return;

  const ss = getSpreadsheet_();
  if (!ss) return;

  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) return;

  // עמודות 37-39 לפי headers (קישור PDF, מזהה קובץ, סטטוס)
  sheet.getRange(rowNum, 37).setValue(pdfFile.getUrl());
  sheet.getRange(rowNum, 38).setValue(pdfFile.getId());
  sheet.getRange(rowNum, 39).setValue('✅ הושלם');
}

/* ==============================
   PDF
============================== */

function createPDF(data) {
  // חובה: קובץ HTML בשם PDFTemplate בפרויקט
  const template = HtmlService.createTemplateFromFile('PDFTemplate');
  const pdfViewModel = buildPdfViewModel(data);
  template.data = data;
  template.pdf = pdfViewModel;
  template.flags = pdfViewModel.flags;  // expose flags directly so template can access without nesting

  const html = template.evaluate().getContent();

  const blob = Utilities.newBlob(html, MimeType.HTML, 'temp_101.html');
  const pdfBlob = blob.getAs(MimeType.PDF);

  pdfBlob.setName(buildFileName_(data));

  const folder = getDestinationFolder_(data);
  return folder.createFile(pdfBlob);
}

function buildFileName_(data) {
  const year  = safeString(data['meta.tax_year']) || String(new Date().getFullYear());
  const last  = sanitizeFilePart_(safeString(data['employee.last_name'])  || 'ללא');
  const first = sanitizeFilePart_(safeString(data['employee.first_name']) || 'שם');
  const id    = sanitizeFilePart_(safeString(data['employee.id'])         || '');
  return `טופס_101_${year}_${last}_${first}${id ? '_' + id : ''}.pdf`;
}

function getDestinationFolder_(data) {
  const main       = getOrCreateFolder_(CONFIG.MAIN_FOLDER);
  const yearFolder = getOrCreateFolder_(String(data['meta.tax_year'] || new Date().getFullYear()), main);
  const employerFolderName = sanitizeFilePart_(safeString(data['employer.name']) || '').trim();
  if (employerFolderName) return getOrCreateFolder_(employerFolderName, yearFolder);
  return yearFolder;
}

function getOrCreateFolder_(name, parent) {
  const p = parent || DriveApp.getRootFolder();
  const it = p.getFoldersByName(name);
  if (it.hasNext()) return it.next();
  return p.createFolder(name);
}


function buildPdfViewModel(data) {
  const d  = k => safeString(data[k]);
  const b  = k => !!data[k];
  const ch = data['children']     || [];
  const oi = data['other_income'] || [];

  return {
    taxYear: d('meta.tax_year'),

    full_name:        [d('employee.last_name'), d('employee.first_name')].filter(Boolean).join(' '),
    employer_name:    d('employer.name'),
    employer_tax_id:  d('employer.deductions_file'),
    employer_address: d('employer.address'),
    employer_phone:   d('employer.phone'),

    last_name:       d('employee.last_name'),
    first_name:      d('employee.first_name'),
    id_number:       d('employee.id'),
    passport_number: d('employee.passport'),
    birth_date:      d('employee.birth_date'),
    aliyah_date:     d('employee.immigration_date'),
    address:         d('employee.address.street'),
    house_no:        d('employee.address.house_no'),
    city:            d('employee.address.city'),
    postal_code:     d('employee.address.zip'),
    mobile_phone:    d('employee.mobile'),
    email:           d('employee.email'),

    gender: b('employee.gender.male') ? 'זכר' : b('employee.gender.female') ? 'נקבה' : '',
    marital_status:
      b('employee.marital_status.married')   ? 'נשוי/אה' :
      b('employee.marital_status.single')    ? 'רווק/ה'  :
      b('employee.marital_status.divorced')  ? 'גרוש/ה'  :
      b('employee.marital_status.widowed')   ? 'אלמן/ה'  :
      b('employee.marital_status.separated') ? 'פרוד/ה'  : '',
    israeli_resident: b('employee.has_id.yes') ? 'כן' : 'לא',
    kibbutz_member:
      b('employee.kibbutz_member.income_transferred') ? 'כן' :
      b('employee.kibbutz_member.no') ? 'לא' : '',
    health_fund: d('employee.health_fund.name'),

    start_date:               d('employment.start_date'),
    has_other_income:         !b('income.other.none'),
    has_spouse:               !!(d('spouse.last_name') || d('spouse.id')),
    spouse_has_income:
      b('spouse.income_type.work')  ? 'עבודה' :
      b('spouse.income_type.other') ? 'אחר'   : 'לא',
    has_tax_coordination:     b('tax_coordination.has_additional_income'),
    tax_coordination_approved: b('tax_coordination.approval_attached'),
    confirm_declaration:      b('signature.declaration'),
    declaration_date:         d('signature.date'),
    signature:                d('signature.applicant_signature'),

    children:           ch,
    additional_incomes: oi,
    changes:            data['changes'] || [],

    // Spouse fields for template
    spouse_last_name:    d('spouse.last_name'),
    spouse_first_name:   d('spouse.first_name'),
    spouse_id:           d('spouse.id'),
    spouse_passport:     d('spouse.passport'),
    spouse_birth_date:   d('spouse.birth_date'),
    spouse_aliya_date:   d('spouse.immigration_date'),

    relief_dates: {
      relief_3_date:            d('credits.3_from_date'),
      relief_4_date:            d('credits.4_from_date'),
      relief_4_no_income_until: d('credits.4_no_income_until'),
      relief_14_start:          d('credits.14_service_start'),
      relief_14_end:            d('credits.14_service_end'),
      relief_16_days:           d('credits.16_reserve_days_prev_year'),
    },

    flags: {
      income_type_monthly:    b('income.main.monthly_salary'),
      income_type_additional: b('income.main.additional_job'),
      income_type_partial:    b('income.main.partial_salary'),
      income_type_daily:      b('income.main.daily_worker'),
      income_type_pension:    b('income.main.pension'),
      income_type_scholarship:b('income.main.scholarship'),

      other_income_monthly:    b('income.other.monthly_salary'),
      other_income_additional: b('income.other.additional_job'),
      other_income_partial:    b('income.other.partial_salary'),
      other_income_daily:      b('income.other.daily_worker'),
      other_income_pension:    b('income.other.pension'),
      other_income_scholarship:b('income.other.scholarship'),
      no_study_fund_other:     b('income.other.no_training_fund'),
      no_pension_other:        b('income.other.no_pension'),

      relief_1_resident:              b('credits.1_israeli_resident'),
      relief_2_disabled:              b('credits.2a_disability_100_or_blind'),
      relief_2_1_allowance:           b('credits.2b_monthly_benefit'),
      relief_3_settlement:            b('credits.3_eligible_locality'),
      relief_4_new_immigrant:         b('credits.4_new_immigrant'),
      relief_5_spouse:                b('credits.5_spouse_no_income'),
      relief_6_single_parent:         b('credits.6_single_parent_family'),
      relief_7_children_custody:      b('credits.7_children_in_custody'),
      relief_8_children_general:      b('credits.8_children_not_in_custody'),
      relief_9_sole_parent:           b('credits.9_single_parent'),
      relief_10_children_not_custody: b('credits.10_children_not_in_custody_maintenance'),
      relief_11_disabled_children:    b('credits.11_disabled_child'),
      relief_12_alimony:              b('credits.12_spousal_support'),
      relief_13_age_16_18:            b('credits.13_age_16_18'),
      relief_14_discharged_soldier:   b('credits.14_released_soldier_or_service'),
      relief_15_academic:             b('credits.15_graduation'),
      relief_16_reserve:              b('credits.16_reserve_combat'),
      relief_17_no_income:            b('tax_coordination.no_income_until_start'),
      relief_wants:                   b('income.credit_request.get_credits_here'),
      relief_has_other:               b('income.credit_request.get_credits_elsewhere'),
    }
  };
}


/* ==============================
   Make Webhook
============================== */

/* ==============================
   Employee Drive Folder
============================== */

/**
 * Creates (or reuses) a per-employee subfolder inside the HR root folder,
 * copies the generated PDF there, and saves any uploaded files (ID scan,
 * discharge certificate).
 *
 * Root folder: HR_EMPLOYEES_ROOT_ID (1AiVyavfbhc3S6D2ZPJ1JHfg4TUovfCLt)
 * Subfolder:   {last_name}_{first_name}_{id_or_passport}/
 */
var HR_EMPLOYEES_ROOT_ID = '1AiVyavfbhc3S6D2ZPJ1JHfg4TUovfCLt';

function organizeEmployeeFolder_(data, pdfFile) {
  var rootFolder = DriveApp.getFolderById(HR_EMPLOYEES_ROOT_ID);

  var lastName  = safeString(data['employee.last_name']);
  var firstName = safeString(data['employee.first_name']);
  var idOrPass  = safeString(data['employee.id']) || safeString(data['employee.passport']);
  var folderName = (lastName + '_' + firstName + '_' + idOrPass).replace(/[\/\\?%*:|"<>]/g, '_');

  // Get or create the employee subfolder
  var iter = rootFolder.getFoldersByName(folderName);
  var folder = iter.hasNext() ? iter.next() : rootFolder.createFolder(folderName);

  // Copy the Form 101 PDF into the employee folder
  if (pdfFile) {
    pdfFile.makeCopy(pdfFile.getName(), folder);
  }

  // Save base64-encoded uploaded files
  var FILE_MIME = {
    'image/jpeg': '.jpg', 'image/png': '.png',
    'image/gif': '.gif', 'image/webp': '.webp',
    'application/pdf': '.pdf'
  };

  function saveBase64_(key, baseName) {
    var raw = data[key];
    if (!raw) return;
    var m = String(raw).match(/^data:([^;]+);base64,(.+)$/);
    if (!m) return;
    var mimeType = m[1];
    var b64      = m[2];
    var ext      = FILE_MIME[mimeType] || '.bin';
    var blob = Utilities.newBlob(Utilities.base64Decode(b64), mimeType, baseName + ext);
    folder.createFile(blob);
    Logger.log('Saved ' + baseName + ext + ' to folder ' + folderName);
  }

  saveBase64_('employee.id_scan',        'תעודת_זהות_וספח');
  saveBase64_('employee.discharge_cert', 'תעודת_שחרור');

  return folder.getUrl();
}

function sendToMake(data, pdfFile, rowNum) {
  if (!CONFIG.MAKE_WEBHOOK_URL || !String(CONFIG.MAKE_WEBHOOK_URL).trim()) return;

  const payload = {

    // ── Meta ──────────────────────────────────────────────────────────────
    meta: {
      form_version:   '101-v6',
      submitted_at:   safeString(data['_op.submitted_at']),
      tax_year:       safeString(data['meta.tax_year']),
      sheet_row:      rowNum || null,
      spreadsheet_id: CONFIG.SPREADSHEET_ID || null,
    },

    // ── PDF / Drive ────────────────────────────────────────────────────────
    pdf: {
      url:        pdfFile ? pdfFile.getUrl()  : '',
      id:         pdfFile ? pdfFile.getId()   : '',
      name:       pdfFile ? pdfFile.getName() : '',
      drive_path: pdfFile
        ? ('HR_101/' + safeString(data['meta.tax_year']) + '/' + safeString(data['employer.name']))
        : '',
    },

    // ── Section A — Employer ──────────────────────────────────────────────
    employer: {
      name:       safeString(data['employer.name']),
      tax_id:     safeString(data['employer.deductions_file']),
      phone:      safeString(data['employer.phone']),
      address:    safeString(data['employer.address']),
      start_date: safeString(data['employment.start_date']),
    },

    // ── Section B — Employee ──────────────────────────────────────────────
    employee: {
      last_name:    safeString(data['employee.last_name']),
      first_name:   safeString(data['employee.first_name']),
      full_name:    [safeString(data['employee.last_name']), safeString(data['employee.first_name'])].filter(Boolean).join(' '),
      id_number:    safeString(data['employee.id']),
      passport:     safeString(data['employee.passport']),
      birth_date:   safeString(data['employee.birth_date']),
      aliya_date:   safeString(data['employee.immigration_date']),
      address:      safeString(data['employee.address.street']),
      house_no:     safeString(data['employee.address.house_no']),
      city:         safeString(data['employee.address.city']),
      postal_code:  safeString(data['employee.address.zip']),
      mobile_phone: (function(p){ return p.startsWith('0') ? p.slice(1) : p; })(safeString(data['employee.mobile'])),
      email:        safeString(data['employee.email']),
      gender:       !!data['employee.gender.male'] ? 'זכר' : !!data['employee.gender.female'] ? 'נקבה' : '',
      health_fund:  safeString(data['employee.health_fund.name']),
      signature:    safeString(data['signature.applicant_signature']),
    },

    // ── Section C — Children ──────────────────────────────────────────────
    children: {
      count: (data['children'] || []).length,
      items: data['children'] || [],
    },

    // ── Section D — Income type ───────────────────────────────────────────
    income: {
      monthly:     !!data['income.main.monthly_salary'],
      additional:  !!data['income.main.additional_job'],
      partial:     !!data['income.main.partial_salary'],
      daily:       !!data['income.main.daily_worker'],
      pension:     !!data['income.main.pension'],
      scholarship: !!data['income.main.scholarship'],
      summary:     buildIncomeTypesSummary(data),
    },

    // ── Section E — Other income ──────────────────────────────────────────
    other_income: {
      has_other_income:    !data['income.other.none'],
      count:               (data['other_income'] || []).length,
      items:               data['other_income'] || [],
      no_study_fund_other: !!data['income.other.no_training_fund'],
      no_pension_other:    !!data['income.other.no_pension'],
      summary:             buildOtherIncomeSummary(data),
    },

    // ── Section F — Spouse ────────────────────────────────────────────────
    spouse: {
      has_spouse:      !!(safeString(data['spouse.last_name']) || safeString(data['spouse.id'])),
      last_name:       safeString(data['spouse.last_name']),
      first_name:      safeString(data['spouse.first_name']),
      id_number:       safeString(data['spouse.id']),
      passport:        safeString(data['spouse.passport']),
      birth_date:      safeString(data['spouse.birth_date']),
      aliya_date:      safeString(data['spouse.immigration_date']),
      has_income:      !!data['spouse.has_income.yes'] ? 'כן' : 'לא',
      summary:         buildSpouseSummary(data),
    },

    // ── Section H — Reliefs ───────────────────────────────────────────────
    reliefs: {
      relief_1_resident:              !!data['credits.1_israeli_resident'],
      relief_2_disabled:              !!data['credits.2a_disability_100_or_blind'],
      relief_2_1_allowance:           !!data['credits.2b_monthly_benefit'],
      relief_3_settlement:            !!data['credits.3_eligible_locality'],
      relief_4_new_immigrant:         !!data['credits.4_new_immigrant'],
      relief_5_spouse:                !!data['credits.5_spouse_no_income'],
      relief_6_single_parent:         !!data['credits.6_single_parent_family'],
      relief_7_children_custody:      !!data['credits.7_children_in_custody'],
      relief_8_children_general:      !!data['credits.8_children_not_in_custody'],
      relief_9_sole_parent:           !!data['credits.9_single_parent'],
      relief_10_children_not_custody: !!data['credits.10_children_not_in_custody_maintenance'],
      relief_11_disabled_children:    !!data['credits.11_disabled_child'],
      relief_12_alimony:              !!data['credits.12_spousal_support'],
      relief_13_age_16_18:            !!data['credits.13_age_16_18'],
      relief_14_discharged_soldier:   !!data['credits.14_released_soldier_or_service'],
      relief_15_academic:             !!data['credits.15_graduation'],
      relief_16_reserve:              !!data['credits.16_reserve_combat'],
      relief_17_no_income:            !!data['tax_coordination.no_income_until_start'],
      relief_wants:                   !!data['income.credit_request.get_credits_here'],
      relief_has_other:               !!data['income.credit_request.get_credits_elsewhere'],
      dates: {
        relief_3_date:            safeString(data['credits.3_from_date']),
        relief_4_date:            safeString(data['credits.4_from_date']),
        relief_4_no_income_until: safeString(data['credits.4_no_income_until']),
        relief_14_start:          safeString(data['credits.14_service_start']),
        relief_14_end:            safeString(data['credits.14_service_end']),
        relief_16_days:           safeString(data['credits.16_reserve_days_prev_year']),
      },
      summary: buildReliefsSummary(data),
    },

    // ── Section T — Tax coordination ──────────────────────────────────────
    tax_coordination: {
      has_tax_coordination: !!data['tax_coordination.has_additional_income'],
      approved:             !!data['tax_coordination.approval_attached'],
      summary:              buildTaxCoordinationSummary(data),
    },

    // ── Section Z — Changes ───────────────────────────────────────────────
    changes: {
      count: (data['changes'] || []).length,
      items: data['changes'] || [],
    },

    // ── Declaration ───────────────────────────────────────────────────────
    declaration: {
      date:      safeString(data['signature.date']),
      confirmed: !!data['signature.declaration'],
    },

  };

  const MAX_ATTEMPTS = 3;
  let lastError = null;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      Logger.log(`sendToMake: attempt ${attempt}/${MAX_ATTEMPTS} row=${rowNum}`);
      const resp = UrlFetchApp.fetch(CONFIG.MAKE_WEBHOOK_URL, {
        method: 'post',
        contentType: 'application/json',
        payload: JSON.stringify(payload),
        muteHttpExceptions: true,
        followRedirects: true,
      });
      const code = resp.getResponseCode();
      const body = resp.getContentText().slice(0, 200);
      Logger.log(`sendToMake: status=${code} body=${body}`);

      if (code >= 200 && code < 300) {
        updateMakeStatus_(rowNum, '✅ הושלם · נשלח ל-Make');
        return;  // success
      }
      lastError = `HTTP ${code}: ${body}`;
    } catch(err) {
      lastError = String(err);
      Logger.log(`sendToMake attempt ${attempt} exception: ${lastError}`);
    }
    if (attempt < MAX_ATTEMPTS) Utilities.sleep(2000 * attempt);
  }

  Logger.log(`sendToMake FAILED after ${MAX_ATTEMPTS} attempts: ${lastError}`);
  logError_('sendToMake', lastError, rowNum);
  // Status stays "✅ הושלם" — form itself succeeded, only Make delivery failed
}


/* ==============================
   Make Utilities
============================== */

/**
 * Write status to col 39 (סטטוס) for a given row. Silently swallowed on error.
 */
function updateMakeStatus_(rowNum, status) {
  if (!rowNum) return;
  try {
    const ss    = getSpreadsheet_();
    const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
    if (sheet) sheet.getRange(rowNum, 39).setValue(status);
  } catch(e) {
    Logger.log('updateMakeStatus_ error: ' + String(e));
  }
}

/**
 * Append an error row to the "שגיאות" sheet tab.
 * Creates the tab (with header) if it does not exist yet.
 */
function logError_(functionName, errorMsg, rowNum) {
  try {
    const ss       = getSpreadsheet_();
    let errSheet   = ss.getSheetByName('שגיאות');
    if (!errSheet) {
      errSheet = ss.insertSheet('שגיאות');
      const hdr = errSheet.getRange(1, 1, 1, 4);
      hdr.setValues([['תאריך', 'פונקציה', 'שורה בגיליון', 'שגיאה']]);
      hdr.setBackground('#c00000').setFontColor('white').setFontWeight('bold');
    }
    errSheet.appendRow([
      Utilities.formatDate(new Date(), CONFIG.TIMEZONE, 'yyyy-MM-dd HH:mm:ss'),
      functionName,
      rowNum || '',
      errorMsg || '',
    ]);
  } catch(e) {
    Logger.log('logError_ itself failed: ' + String(e));
  }
}

/**
 * שולח Webhook ל-Make (Scenario A) כדי להזמין עובד חדש למלא טופס 101.
 * Make שולח הודעת WhatsApp עם לינק לטופס.
 *
 * @param {number} rowNum    - מספר שורה בגיליון (אם קיים, מעדכן סטטוס)
 * @param {string} name      - שם העובד
 * @param {string} phone     - טלפון נייד מנורמל (0XXXXXXXXX)
 * @param {string} employer  - שם המעסיק
 * @param {string} taxYear   - שנת המס
 */
function notifyNewEmployee_(rowNum, name, phone, employer, taxYear) {
  const inviteUrl = CONFIG.MAKE_INVITE_WEBHOOK_URL;
  if (!inviteUrl || !String(inviteUrl).trim()) {
    Logger.log('notifyNewEmployee_: MAKE_INVITE_WEBHOOK_URL not configured — skipped');
    return;
  }

  const payload = {
    action:   'invite',
    sentAt:   new Date().toISOString(),
    rowNum:   rowNum || null,
    employee: { name, phone },
    employer,
    taxYear,
    formUrl:  CONFIG.FORM_PUBLIC_URL || '',
  };

  try {
    const resp = UrlFetchApp.fetch(inviteUrl, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    const code = resp.getResponseCode();
    Logger.log(`notifyNewEmployee_: Make invite status=${code} row=${rowNum} phone=${phone}`);
    if (rowNum && code >= 200 && code < 300) {
      updateMakeStatus_(rowNum, '📨 הזמנה נשלחה');
    }
  } catch(err) {
    Logger.log('notifyNewEmployee_ error: ' + String(err));
    logError_('notifyNewEmployee_', String(err), rowNum);
  }
}

/**
 * Visual QA via Claude Anthropic API.
 * Called by Make before sending WhatsApp confirmation to validate the generated PDF.
 *
 * Returns: { success, quality, passed, issues, summary }
 * If no API key is configured → { success:true, skipped:true, quality:10, passed:true }
 * On error → { success:false, error:"..." }
 */
function validatePdfAction_(params) {
  const fileId = safeString((params && params.fileId) || '');
  if (!fileId) return { success: false, error: 'fileId נדרש' };

  // Script Properties override CONFIG (preferred — keeps key out of source code)
  const apiKey =
    PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY') ||
    CONFIG.ANTHROPIC_API_KEY || '';

  if (!apiKey || !String(apiKey).trim()) {
    Logger.log('validatePdfAction_: no ANTHROPIC_API_KEY — skipped');
    return { success: true, skipped: true, quality: 10, passed: true, summary: 'QA skipped — no API key' };
  }

  try {
    const pdfBytes = DriveApp.getFileById(fileId).getBlob().getBytes();
    const b64 = Utilities.base64Encode(pdfBytes);

    const QA_PROMPT =
      'You are reviewing a generated Hebrew tax form (Israeli Form 101 / \u05d8\u05d5\u05e4\u05e1 101). ' +
      'The form has 2 pages. Examine carefully and identify: ' +
      '1. Text fields in wrong position or missing. ' +
      '2. Checkmarks at incorrect locations or missing. ' +
      '3. Text overflow or clipping. ' +
      '4. Elements misaligned with form background. ' +
      'Return ONLY valid JSON (no markdown, no explanation): ' +
      '{"issues":[{"field":"...","page":1,"problem":"..."}],' +
      '"overall_quality":1,"summary":"..."} ' +
      'Score: 10=perfect, 8+=production-ready, <8=needs fix.';

    const reqBody = {
      model: 'claude-sonnet-4-6',
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'document',
            source: { type: 'base64', media_type: 'application/pdf', data: b64 },
          },
          { type: 'text', text: QA_PROMPT },
        ],
      }],
    };

    const resp = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
      method: 'post',
      contentType: 'application/json',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-beta': 'pdfs-2024-09-25',
      },
      payload: JSON.stringify(reqBody),
      muteHttpExceptions: true,
    });

    const httpCode = resp.getResponseCode();
    if (httpCode !== 200) {
      const errText = resp.getContentText().slice(0, 300);
      Logger.log('validatePdfAction_: Anthropic API error ' + httpCode + ': ' + errText);
      return { success: false, error: 'Anthropic API returned ' + httpCode + ': ' + errText };
    }

    let parsed = {};
    try {
      const apiResp = JSON.parse(resp.getContentText());
      const text = (apiResp.content && apiResp.content[0] && apiResp.content[0].text) || '{}';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : {};
    } catch(parseErr) {
      Logger.log('validatePdfAction_: JSON parse error: ' + String(parseErr));
      return { success: false, error: 'Failed to parse Claude response: ' + String(parseErr) };
    }

    const quality = typeof parsed.overall_quality === 'number' ? parsed.overall_quality : 10;
    const passed  = quality >= 7;   // 7/10 = readable with minor positioning issues; <7 = serious problem
    const issues  = Array.isArray(parsed.issues) ? parsed.issues : [];
    const summary = safeString(parsed.summary);

    Logger.log('validatePdfAction_: quality=' + quality + ' passed=' + passed +
               ' issues=' + issues.length + ' fileId=' + fileId);
    return { success: true, quality, passed, issues, summary };

  } catch(err) {
    Logger.log('validatePdfAction_ error: ' + String(err));
    return { success: false, error: String(err) };
  }
}

/* ==============================
   Utilities
============================== */

function safeString(v) {
  if (v === null || v === undefined) return '';
  return String(v).trim();
}

/**
 * Normalize an Israeli phone number to 0XXXXXXXXX format (text string).
 * - Strips spaces, dashes, dots, parentheses
 * - Converts +972 / 972 country prefix to leading 0
 * - Adds leading 0 if number is 9 digits (e.g. 500000001 → 0500000001)
 */
function normalizePhone_(v) {
  let s = safeString(v).replace(/[\s\-\.\(\)]/g, '');
  if (!s) return '';
  if (s.startsWith('+972')) s = '0' + s.slice(4);
  else if (s.startsWith('972') && s.length >= 12) s = '0' + s.slice(3);
  else if (/^\d{9}$/.test(s)) s = '0' + s;
  return s;
}

function toBoolean(v) {
  if (v === true || v === false) return v;
  const s = String(v).toLowerCase().trim();
  return (s === 'true' || s === '1' || s === 'yes' || s === 'on' || s === 'checked' || s === 'כן');
}

function sanitizeFilePart_(s) {
  return safeString(s).replace(/[\\\/:*?"<>|]+/g, '').replace(/\s+/g, '_');
}

function formatTimestamp_(iso) {
  try {
    const d = iso ? new Date(iso) : new Date();
    return Utilities.formatDate(d, CONFIG.TIMEZONE, 'yyyy-MM-dd HH:mm:ss');
  } catch (e) {
    return safeString(iso);
  }
}

