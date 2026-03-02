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
  SPREADSHEET_ID: '',

  // תיקיית אב ב-Drive לשמירת PDFs
  MAIN_FOLDER: 'HR_101',

  // Webhook של Make (אופציונלי)
  MAKE_WEBHOOK_URL: '',

  // פרטי HR להודעות (אופציונלי)
  HR_PHONE: '',
  HR_EMAIL: '',

  TIMEZONE: 'Asia/Jerusalem',
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

    const raw = JSON.parse(e.postData.contents);
    const data = normalizePayload(raw);

    // 1) שמירה ל-Sheet
    const rowNum = saveToSheet(data);

    // 2) יצירת PDF
    const pdfFile = createPDF(data);

    // 3) עדכון שורה עם פרטי PDF
    updateSheetAfterPdf(rowNum, pdfFile);

    // 4) Webhook ל-Make (אם הוגדר)
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
   Normalization
============================== */

function normalizePayload(raw) {
  const data = raw || {};
  data.submitted_at = data.submitted_at || new Date().toISOString();
  data.taxYear = safeString(data.taxYear) || String(new Date().getFullYear());

  // Arrays
  data.children = Array.isArray(data.children) ? data.children : extractChildrenFromFlatFields(data);
  data.additional_incomes = Array.isArray(data.additional_incomes) ? data.additional_incomes : extractAdditionalIncomesFromFlatFields(data);
  data.changes = Array.isArray(data.changes) ? data.changes : extractChangesFromFlatFields(data);

  // Booleans from checkboxes
  const boolKeys = [
    'income_type_monthly','income_type_additional','income_type_partial','income_type_daily','income_type_pension','income_type_scholarship',
    'has_other_income','other_income_monthly','other_income_additional','other_income_partial','other_income_daily','other_income_pension','other_income_scholarship',
    'no_study_fund_other','no_pension_other',
    'has_spouse','spouse_has_income',
    'has_tax_coordination','tax_coordination_approved',
    'confirm_declaration',
    // reliefs (דוגמאות – אם קיימים בטופס)
    'relief_1_resident','relief_2_disabled','relief_2_1_allowance','relief_3_settlement','relief_4_new_immigrant','relief_5_spouse','relief_6_single_parent',
    'relief_7_children_custody','relief_8_children_general','relief_9_sole_parent','relief_10_children_not_custody','relief_11_disabled_children',
    'relief_12_alimony','relief_13_age_16_18','relief_14_discharged_soldier','relief_15_academic','relief_16_reserve','relief_17_no_income',
  ];
  boolKeys.forEach(k => { if (k in data) data[k] = toBoolean(data[k]); });

  // text radios/selects: keep as string
  ['gender','marital_status','israeli_resident','kibbutz_member','health_fund'].forEach(k => { if (k in data) data[k] = safeString(data[k]); });

  // Normalize phone numbers to IL format (0XXXXXXXXX)
  ['mobile_phone','employer_phone'].forEach(k => { if (k in data) data[k] = normalizePhone_(data[k]); });

  // Build summaries for PDF overlay (פשוט, כדי לעבוד מייד; אפשר לשדרג לסימון checkbox מדויק אחרי כיול)
  data.summary_income_types = buildIncomeTypesSummary(data);
  data.summary_other_income = buildOtherIncomeSummary(data);
  data.summary_spouse = buildSpouseSummary(data);
  data.summary_reliefs = buildReliefsSummary(data);
  data.summary_tax_coordination = buildTaxCoordinationSummary(data);

  return data;
}

function buildIncomeTypesSummary(d) {
  const a = [];
  if (d.income_type_monthly) a.push('משכורת חודשית');
  if (d.income_type_additional) a.push('משכורת נוספת');
  if (d.income_type_partial) a.push('משכורת חלקית');
  if (d.income_type_daily) a.push('שכר עבודה (יומי/שבועי)');
  if (d.income_type_pension) a.push('קצבה');
  if (d.income_type_scholarship) a.push('מלגה');
  return a.length ? ('סוגי הכנסה ממעסיק זה: ' + a.join(', ')) : '';
}

function buildOtherIncomeSummary(d) {
  if (!d.has_other_income) return 'אין הכנסות אחרות (לפי הצהרה)';
  const a = [];
  if (d.other_income_monthly) a.push('משכורת חודשית');
  if (d.other_income_additional) a.push('משכורת נוספת');
  if (d.other_income_partial) a.push('משכורת חלקית');
  if (d.other_income_daily) a.push('שכר עבודה (יומי/שבועי)');
  if (d.other_income_pension) a.push('קצבה');
  if (d.other_income_scholarship) a.push('מלגה');
  const parts = [];
  parts.push('יש הכנסות אחרות: ' + (a.length ? a.join(', ') : 'כן'));
  if (Array.isArray(d.additional_incomes) && d.additional_incomes.length) {
    const txt = d.additional_incomes
      .map(x => `${safeString(x.employer)||''} ₪${safeString(x.amount)||''} (מס:${safeString(x.tax)||''})`)
      .filter(Boolean)
      .join(' | ');
    if (txt) parts.push('פירוט מעסיקים נוספים: ' + txt);
  }
  if (d.no_study_fund_other) parts.push('ללא קרן השתלמות במקום אחר');
  if (d.no_pension_other) parts.push('ללא קופת גמל/פנסיה במקום אחר');
  return parts.join(' · ');
}

function buildSpouseSummary(d) {
  if (!d.has_spouse) return '';
  const parts = [];
  parts.push(`בן/בת זוג: ${safeString(d.spouse_last_name)||''} ${safeString(d.spouse_first_name)||''}`.trim());
  const idp = safeString(d.spouse_id_number) || safeString(d.spouse_passport_number);
  if (idp) parts.push('ת"ז/דרכון: ' + idp);
  if (d.spouse_birth_date) parts.push('ת. לידה: ' + safeString(d.spouse_birth_date));
  if (d.spouse_aliya_date) parts.push('ת. עליה: ' + safeString(d.spouse_aliya_date));
  parts.push('יש לבן/בת הזוג הכנסה: ' + (d.spouse_has_income ? 'כן' : 'לא'));
  return parts.join(' · ');
}

function buildReliefsSummary(d) {
  const items = [];
  if (d.relief_1_resident) items.push('1. תושב/ת ישראל');
  if (d.relief_2_disabled) items.push('2. נכות');
  if (d.relief_2_1_allowance) items.push('2.1 מקבל/ת קצבה');
  if (d.relief_3_settlement) items.push('3. יישוב מזכה');
  if (d.relief_4_new_immigrant) items.push('4. עולה חדש/ה / תושב/ת חוזר/ת');
  if (d.relief_5_spouse) items.push('5. בן/בת זוג ללא הכנסה / נכה');
  if (d.relief_6_single_parent) items.push('6. הורה יחיד');
  if (d.relief_7_children_custody) items.push('7. ילדים בחזקתי');
  if (d.relief_8_children_general) items.push('8. ילדים');
  if (d.relief_9_sole_parent) items.push('9. הורה עצמאי/ת');
  if (d.relief_10_children_not_custody) items.push('10. ילדים לא בחזקתי');
  if (d.relief_11_disabled_children) items.push('11. ילד נכה');
  if (d.relief_12_alimony) items.push('12. מזונות');
  if (d.relief_13_age_16_18) items.push('13. ילדים בגיל 16–18');
  if (d.relief_14_discharged_soldier) items.push('14. חייל משוחרר/ת');
  if (d.relief_15_academic) items.push('15. השכלה אקדמית');
  if (d.relief_16_reserve) items.push('16. שירות מילואים');
  if (d.relief_17_no_income) items.push('17. אין הכנסה');
  return items.length ? ('בקשות להקלות מס: ' + items.join(' · ')) : '';
}

function buildTaxCoordinationSummary(d) {
  if (!d.has_tax_coordination) return '';
  const parts = [];
  parts.push('תיאום מס: כן');
  if (d.tax_coordination_approved) parts.push('אישור פקיד שומה: כן');
  // אם קיימים שדות flat של טבלת תיאום מס (tax_coord_1_*), אפשר להוסיף כאן פירוט בעתיד
  return parts.join(' · ');
}

function extractChildrenFromFlatFields(data) {
  const results = [];
  for (let i = 1; i <= 10; i++) {
    const child = {
      name: safeString(data[`child_${i}_name`]),
      id: safeString(data[`child_${i}_id`]),
      birth_date: safeString(data[`child_${i}_birth_date`]),
      in_custody: toBoolean(data[`child_${i}_in_custody`]),
      receives_allowance: toBoolean(data[`child_${i}_receives_allowance`]),
    };
    if (child.name || child.id || child.birth_date) results.push(child);
  }
  return results;
}

function extractAdditionalIncomesFromFlatFields(data) {
  const results = [];
  for (let i = 1; i <= 20; i++) {
    const item = {
      employer: safeString(data[`add_income_${i}_employer`]),
      address: safeString(data[`add_income_${i}_address`]),
      tax_id: safeString(data[`add_income_${i}_tax_id`]),
      type: safeString(data[`add_income_${i}_type`]),
      amount: safeString(data[`add_income_${i}_amount`]),
      tax: safeString(data[`add_income_${i}_tax`]),
    };
    if (item.employer || item.amount || item.tax) results.push(item);
  }
  return results;
}

function extractChangesFromFlatFields(data) {
  const results = [];
  for (let i = 1; i <= 10; i++) {
    const item = {
      date: safeString(data[`change_${i}_date`]),
      details: safeString(data[`change_${i}_details`]),
      notification_date: safeString(data[`change_${i}_notification`]),
      signature: safeString(data[`change_${i}_signature`]),
    };
    if (item.date || item.details || item.notification_date) results.push(item);
  }
  return results;
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

    const row = [
    // מטא מערכת
    formatTimestamp_(data.submitted_at),      // 1:  תאריך הגשה
    data.taxYear,                             // 2:  שנת מס
    // סעיף א׳ — פרטי המעסיק
    safeString(data.employer_name),           // 3:  שם המעסיק
    safeString(data.employer_tax_id),         // 4:  מספר תיק ניכויים
    safeString(data.employer_phone),          // 5:  טלפון המעסיק
    safeString(data.employer_address),        // 6:  כתובת המעסיק
    safeString(data.start_date),              // 7:  תאריך תחילת עבודה
    // סעיף ב׳ — פרטי העובד
    safeString(data.last_name),               // 8:  שם משפחה
    safeString(data.first_name),              // 9:  שם פרטי
    safeString(data.id_number),               // 10: מספר זהות
    safeString(data.passport_number),         // 11: מספר דרכון
    safeString(data.birth_date),              // 12: תאריך לידה
    safeString(data.aliya_date),              // 13: תאריך עלייה
    safeString(data.address),                 // 14: כתובת עובד
    safeString(data.postal_code),             // 15: מיקוד
    safeString(data.mobile_phone),            // 16: טלפון נייד
    safeString(data.email),                   // 17: אימייל
    safeString(data.gender),                  // 18: מין
    safeString(data.marital_status),          // 19: מצב משפחתי
    safeString(data.israeli_resident),        // 20: תושב ישראל
    safeString(data.kibbutz_member),          // 21: חבר קיבוץ/מושב שיתופי
    safeString(data.health_fund),             // 22: קופת חולים
    // סעיף ג׳ — ילדים
    data.children.length,                     // 23: מספר ילדים
    JSON.stringify(data.children),            // 24: ילדים (JSON)
    // סעיף ד׳ — סוג ההכנסה
    safeString(data.summary_income_types),    // 25: סוג הכנסה ממעסיק
    // סעיף ה׳ — הכנסות ממעסיקים אחרים
    data.has_other_income ? 'כן' : 'לא',     // 26: יש הכנסות אחרות
    data.additional_incomes.length,           // 27: מספר הכנסות נוספות
    JSON.stringify(data.additional_incomes),  // 28: הכנסות נוספות (JSON)
    data.no_study_fund_other ? 'כן' : 'לא', // 29: ללא קרן השתלמות אחרת
    data.no_pension_other ? 'כן' : 'לא',    // 30: ללא פנסיה/גמל אחרת
    // סעיף ו׳ — בן/בת זוג
    data.has_spouse ? 'כן' : 'לא',           // 31: יש בן/בת זוג
    safeString(data.summary_spouse),          // 32: פרטי בן/בת זוג
    // סעיף ח׳ — זכאויות
    safeString(data.summary_reliefs),         // 33: זכאויות - סיכום
    // סעיף ת׳ — תיאום מס
    data.has_tax_coordination ? 'כן' : 'לא', // 34: יש תיאום מס
    // סעיף ז׳ — שינויים
    JSON.stringify(data.changes),             // 35: שינויים במהלך השנה (JSON)
    // הצהרה
    safeString(data.declaration_date),        // 36: תאריך הצהרה
    // מערכת / PDF
    '',                                       // 37: קישור PDF
    '',                                       // 38: מזהה קובץ ב-Drive
    'ממתין ל-PDF',                           // 39: סטטוס
    // פנימי
    JSON.stringify(buildSummary(data)),        // 40: סיכום
    JSON.stringify(data),                     // 41: JSON מלא
  ];

  sheet.appendRow(row);
  const newRow = sheet.getLastRow();

  // Re-write phone cells as explicit text so Sheets stores '0XXXXXXXXX', not integer
  // (appendRow auto-coerces numeric-looking strings to numbers; setValue after the fact preserves string)
  const phoneEmployer = row[4];   // col 5
  const phoneMobile   = row[15];  // col 16
  if (phoneEmployer) sheet.getRange(newRow, 5).setNumberFormat('@').setValue(String(phoneEmployer));
  if (phoneMobile)   sheet.getRange(newRow, 16).setNumberFormat('@').setValue(String(phoneMobile));

  return newRow;
}


function buildSummary(data) {
  const parts = [];
  const fullName = [safeString(data.last_name), safeString(data.first_name)].filter(Boolean).join(' ');
  if (fullName) parts.push('עובד: ' + fullName);
  if (safeString(data.id_number)) parts.push('ת"ז: ' + safeString(data.id_number));
  if (safeString(data.employer_name)) parts.push('מעסיק: ' + safeString(data.employer_name));
  if (safeString(data.start_date)) parts.push('תחילת עבודה: ' + safeString(data.start_date));
  parts.push('ילדים: ' + (Array.isArray(data.children) ? data.children.length : 0));
  parts.push('הכנסות נוספות: ' + (Array.isArray(data.additional_incomes) ? data.additional_incomes.length : 0));
  if (data.has_spouse) parts.push('יש בן/בת זוג');
  if (data.has_other_income) parts.push('יש הכנסות אחרות');
  if (data.has_tax_coordination) parts.push('יש תיאום מס');
  return {
    full_name: fullName,
    id_number: safeString(data.id_number),
    employer_name: safeString(data.employer_name),
    start_date: safeString(data.start_date),
    children_count: Array.isArray(data.children) ? data.children.length : 0,
    additional_incomes_count: Array.isArray(data.additional_incomes) ? data.additional_incomes.length : 0,
    has_spouse: !!data.has_spouse,
    has_other_income: !!data.has_other_income,
    has_tax_coordination: !!data.has_tax_coordination,
    text: parts.join(' | ')
  };
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
  const year = safeString(data.taxYear) || String(new Date().getFullYear());
  const last = sanitizeFilePart_(data.last_name || 'ללא');
  const first = sanitizeFilePart_(data.first_name || 'שם');
  const id = sanitizeFilePart_(data.id_number || '');
  return `טופס_101_${year}_${last}_${first}${id ? '_' + id : ''}.pdf`;
}

function getDestinationFolder_(data) {
  const main = getOrCreateFolder_(CONFIG.MAIN_FOLDER);
  const yearFolder = getOrCreateFolder_(String(data.taxYear || new Date().getFullYear()), main);

  // אופציונלי: תיקיית מעסיק
  const employerFolderName = sanitizeFilePart_(data.employer_name || '').trim();
  if (employerFolderName) {
    return getOrCreateFolder_(employerFolderName, yearFolder);
  }
  return yearFolder;
}

function getOrCreateFolder_(name, parent) {
  const p = parent || DriveApp.getRootFolder();
  const it = p.getFoldersByName(name);
  if (it.hasNext()) return it.next();
  return p.createFolder(name);
}


function buildPdfViewModel(data) {
  return {
    taxYear: safeString(data.taxYear),

    full_name: [safeString(data.last_name), safeString(data.first_name)].filter(Boolean).join(' '),
    employer_name: safeString(data.employer_name),
    employer_tax_id: safeString(data.employer_tax_id),
    employer_address: safeString(data.employer_address),
    employer_phone: safeString(data.employer_phone),

    last_name: safeString(data.last_name),
    first_name: safeString(data.first_name),
    id_number: safeString(data.id_number),
    passport_number: safeString(data.passport_number),
    birth_date: safeString(data.birth_date),
    aliyah_date: safeString(data.aliya_date),
    address: safeString(data.address),
    postal_code: safeString(data.postal_code),
    mobile_phone: safeString(data.mobile_phone),
    email: safeString(data.email),

    gender: safeString(data.gender),
    marital_status: safeString(data.marital_status),
    israeli_resident: safeString(data.israeli_resident),
    kibbutz_member: safeString(data.kibbutz_member),
    health_fund: safeString(data.health_fund),

    start_date: safeString(data.start_date),
    has_other_income: !!data.has_other_income,
    has_spouse: !!data.has_spouse,
    spouse_has_income: safeString(data.spouse_has_income),
    has_tax_coordination: !!data.has_tax_coordination,
    tax_coordination_approved: !!data.tax_coordination_approved,
    confirm_declaration: !!data.confirm_declaration,
    declaration_date: safeString(data.declaration_date),
    signature: safeString(data.signature),

    children: Array.isArray(data.children) ? data.children : [],
    additional_incomes: Array.isArray(data.additional_incomes) ? data.additional_incomes : [],
    changes: Array.isArray(data.changes) ? data.changes : [],

    relief_dates: {
      relief_3_date: safeString(data.relief_3_date),
      relief_4_date: safeString(data.relief_4_date),
      relief_4_no_income_until: safeString(data.relief_4_no_income_until),
      relief_14_start: safeString(data.relief_14_start),
      relief_14_end: safeString(data.relief_14_end),
      relief_16_days: safeString(data.relief_16_days)
    },

    flags: {
      income_type_monthly: !!data.income_type_monthly,
      income_type_additional: !!data.income_type_additional,
      income_type_partial: !!data.income_type_partial,
      income_type_daily: !!data.income_type_daily,
      income_type_pension: !!data.income_type_pension,
      income_type_scholarship: !!data.income_type_scholarship,

      other_income_monthly: !!data.other_income_monthly,
      other_income_additional: !!data.other_income_additional,
      other_income_partial: !!data.other_income_partial,
      other_income_daily: !!data.other_income_daily,
      other_income_pension: !!data.other_income_pension,
      other_income_scholarship: !!data.other_income_scholarship,
      no_study_fund_other: !!data.no_study_fund_other,
      no_pension_other: !!data.no_pension_other,

      relief_1_resident: !!data.relief_1_resident,
      relief_2_disabled: !!data.relief_2_disabled,
      relief_2_1_allowance: !!data.relief_2_1_allowance,
      relief_3_settlement: !!data.relief_3_settlement,
      relief_4_new_immigrant: !!data.relief_4_new_immigrant,
      relief_5_spouse: !!data.relief_5_spouse,
      relief_6_single_parent: !!data.relief_6_single_parent,
      relief_7_children_custody: !!data.relief_7_children_custody,
      relief_8_children_general: !!data.relief_8_children_general,
      relief_9_sole_parent: !!data.relief_9_sole_parent,
      relief_10_children_not_custody: !!data.relief_10_children_not_custody,
      relief_11_disabled_children: !!data.relief_11_disabled_children,
      relief_12_alimony: !!data.relief_12_alimony,
      relief_13_age_16_18: !!data.relief_13_age_16_18,
      relief_14_discharged_soldier: !!data.relief_14_discharged_soldier,
      relief_15_academic: !!data.relief_15_academic,
      relief_16_reserve: !!data.relief_16_reserve,
      relief_17_no_income: !!data.relief_17_no_income
    }
  };
}


/* ==============================
   Make Webhook
============================== */

function sendToMake(data, pdfFile, rowNum) {
  if (!CONFIG.MAKE_WEBHOOK_URL || !String(CONFIG.MAKE_WEBHOOK_URL).trim()) return;

  const payload = {

    // ── Meta ──────────────────────────────────────────────────────────────
    meta: {
      form_version:   '101-v6',
      submitted_at:   safeString(data.submitted_at),
      tax_year:       safeString(data.taxYear),
      sheet_row:      rowNum || null,
      spreadsheet_id: CONFIG.SPREADSHEET_ID || null,
    },

    // ── PDF / Drive ────────────────────────────────────────────────────────
    pdf: {
      url:        pdfFile ? pdfFile.getUrl()  : '',
      id:         pdfFile ? pdfFile.getId()   : '',
      name:       pdfFile ? pdfFile.getName() : '',
      drive_path: pdfFile
        ? ('HR_101/' + safeString(data.taxYear) + '/' + safeString(data.employer_name))
        : '',
    },

    // ── Section A — Employer ──────────────────────────────────────────────
    employer: {
      name:       safeString(data.employer_name),
      tax_id:     safeString(data.employer_tax_id),
      phone:      safeString(data.employer_phone),
      address:    safeString(data.employer_address),
      start_date: safeString(data.start_date),
    },

    // ── Section B — Employee ──────────────────────────────────────────────
    employee: {
      last_name:        safeString(data.last_name),
      first_name:       safeString(data.first_name),
      full_name:        [safeString(data.last_name), safeString(data.first_name)].filter(Boolean).join(' '),
      id_number:        safeString(data.id_number),
      passport_number:  safeString(data.passport_number),
      birth_date:       safeString(data.birth_date),
      aliya_date:       safeString(data.aliya_date),
      address:          safeString(data.address),
      postal_code:      safeString(data.postal_code),
      mobile_phone:     safeString(data.mobile_phone),
      email:            safeString(data.email),
      gender:           safeString(data.gender),
      marital_status:   safeString(data.marital_status),
      israeli_resident: safeString(data.israeli_resident),
      kibbutz_member:   safeString(data.kibbutz_member),
      health_fund:      safeString(data.health_fund),
      signature:        safeString(data.signature),  // base64 data URL מהחתימה הדיגיטלית
    },

    // ── Section C — Children ──────────────────────────────────────────────
    children: {
      count: Array.isArray(data.children) ? data.children.length : 0,
      items: Array.isArray(data.children) ? data.children : [],
    },

    // ── Section D — Income type ───────────────────────────────────────────
    income: {
      monthly:     !!data.income_type_monthly,
      additional:  !!data.income_type_additional,
      partial:     !!data.income_type_partial,
      daily:       !!data.income_type_daily,
      pension:     !!data.income_type_pension,
      scholarship: !!data.income_type_scholarship,
      summary:     safeString(data.summary_income_types),
    },

    // ── Section E — Other income ──────────────────────────────────────────
    other_income: {
      has_other_income:    !!data.has_other_income,
      count:               Array.isArray(data.additional_incomes) ? data.additional_incomes.length : 0,
      items:               Array.isArray(data.additional_incomes) ? data.additional_incomes : [],
      no_study_fund_other: !!data.no_study_fund_other,
      no_pension_other:    !!data.no_pension_other,
      summary:             safeString(data.summary_other_income),
    },

    // ── Section F — Spouse ────────────────────────────────────────────────
    spouse: {
      has_spouse:      !!data.has_spouse,
      last_name:       safeString(data.spouse_last_name),
      first_name:      safeString(data.spouse_first_name),
      id_number:       safeString(data.spouse_id_number),
      passport_number: safeString(data.spouse_passport_number),
      birth_date:      safeString(data.spouse_birth_date),
      aliya_date:      safeString(data.spouse_aliya_date),
      has_income:      safeString(data.spouse_has_income),
      summary:         safeString(data.summary_spouse),
    },

    // ── Section H — Reliefs ───────────────────────────────────────────────
    reliefs: {
      relief_1_resident:              !!data.relief_1_resident,
      relief_2_disabled:              !!data.relief_2_disabled,
      relief_2_1_allowance:           !!data.relief_2_1_allowance,
      relief_3_settlement:            !!data.relief_3_settlement,
      relief_4_new_immigrant:         !!data.relief_4_new_immigrant,
      relief_5_spouse:                !!data.relief_5_spouse,
      relief_6_single_parent:         !!data.relief_6_single_parent,
      relief_7_children_custody:      !!data.relief_7_children_custody,
      relief_8_children_general:      !!data.relief_8_children_general,
      relief_9_sole_parent:           !!data.relief_9_sole_parent,
      relief_10_children_not_custody: !!data.relief_10_children_not_custody,
      relief_11_disabled_children:    !!data.relief_11_disabled_children,
      relief_12_alimony:              !!data.relief_12_alimony,
      relief_13_age_16_18:            !!data.relief_13_age_16_18,
      relief_14_discharged_soldier:   !!data.relief_14_discharged_soldier,
      relief_15_academic:             !!data.relief_15_academic,
      relief_16_reserve:              !!data.relief_16_reserve,
      relief_17_no_income:            !!data.relief_17_no_income,
      dates: {
        relief_3_date:            safeString(data.relief_3_date),
        relief_4_date:            safeString(data.relief_4_date),
        relief_4_no_income_until: safeString(data.relief_4_no_income_until),
        relief_14_start:          safeString(data.relief_14_start),
        relief_14_end:            safeString(data.relief_14_end),
        relief_16_days:           safeString(data.relief_16_days),
      },
      summary: safeString(data.summary_reliefs),
    },

    // ── Section T — Tax coordination ──────────────────────────────────────
    tax_coordination: {
      has_tax_coordination: !!data.has_tax_coordination,
      approved:             !!data.tax_coordination_approved,
      summary:              safeString(data.summary_tax_coordination),
    },

    // ── Section Z — Changes ───────────────────────────────────────────────
    changes: {
      count: Array.isArray(data.changes) ? data.changes.length : 0,
      items: Array.isArray(data.changes) ? data.changes : [],
    },

    // ── Declaration ───────────────────────────────────────────────────────
    declaration: {
      date:      safeString(data.declaration_date),
      confirmed: !!data.confirm_declaration,
    },

  };

  try {
    const resp = UrlFetchApp.fetch(CONFIG.MAKE_WEBHOOK_URL, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    Logger.log('MAKE webhook: status=' + resp.getResponseCode());
  } catch (e) {
    Logger.log('MAKE webhook error: ' + e);
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
