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
  const action = (e && e.parameter && e.parameter.action) ? e.parameter.action : '';

  if (action === 'verify')   return handleVerify_();
  if (action === 'getPdf')   return handleGetPdf_(e.parameter.id || '');

  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', service: 'form-101', version: '6.0' }))
    .setMimeType(ContentService.MimeType.JSON);
}

/* ---------- Verification helpers (used by the automation pipeline) ---------- */

function handleVerify_() {
  const out = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);
  try {
    const ss = getSpreadsheet_();
    if (!ss) throw new Error('Spreadsheet not found');
    const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
    if (!sheet) throw new Error('Sheet not found');

    const lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      out.setContent(JSON.stringify({ success: true, rows: 0, data: null }));
      return out;
    }

    const ncols   = sheet.getLastColumn();
    const headers = sheet.getRange(1, 1, 1, ncols).getValues()[0];
    const values  = sheet.getRange(lastRow, 1, 1, ncols).getValues()[0];

    const row = {};
    headers.forEach(function(h, i) { row[String(h)] = values[i]; });

    out.setContent(JSON.stringify({ success: true, rows: lastRow - 1, data: row }));
  } catch (err) {
    out.setContent(JSON.stringify({ success: false, error: String(err) }));
  }
  return out;
}

function handleGetPdf_(fileId) {
  const out = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);
  try {
    if (!fileId) throw new Error('fileId is required');
    const file   = DriveApp.getFileById(fileId);
    const bytes  = file.getBlob().getBytes();
    const b64    = Utilities.base64Encode(bytes);
    out.setContent(JSON.stringify({ success: true, name: file.getName(), data: b64 }));
  } catch (err) {
    out.setContent(JSON.stringify({ success: false, error: String(err) }));
  }
  return out;
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
    sendToMake(data, pdfFile);

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
    'תאריך הגשה','שנת מס','שם משפחה','שם פרטי','מספר זהות','מספר דרכון','טלפון נייד','אימייל',
    'שם המעסיק','מספר תיק ניכויים','טלפון המעסיק','כתובת המעסיק','תאריך תחילת עבודה',
    'מין','מצב משפחתי','תושב ישראל','חבר קיבוץ/מושב שיתופי','קופת חולים',
    'מספר ילדים','מספר הכנסות נוספות','יש בן/בת זוג','יש הכנסות אחרות','יש תיאום מס',
    'תאריך הצהרה','קישור PDF','מזהה קובץ ב-Drive','סטטוס',
    'ילדים (JSON)','הכנסות נוספות (JSON)','שינויים במהלך השנה (JSON)','סיכום','JSON מלא'
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

  const submittedAt = formatTimestamp_(data.submitted_at);
  const fullJson = JSON.stringify(data);

    const row = [
    formatTimestamp_(data.submitted_at),
    data.taxYear,
    safeString(data.last_name),
    safeString(data.first_name),
    safeString(data.id_number),
    safeString(data.passport_number),
    safeString(data.mobile_phone),
    safeString(data.email),
    safeString(data.employer_name),
    safeString(data.employer_tax_id),
    safeString(data.employer_phone),
    safeString(data.employer_address),
    safeString(data.start_date),
    safeString(data.gender),
    safeString(data.marital_status),
    safeString(data.israeli_resident),
    safeString(data.kibbutz_member),
    safeString(data.health_fund),
    data.children.length,
    data.additional_incomes.length,
    data.has_spouse ? 'כן' : 'לא',
    data.has_other_income ? 'כן' : 'לא',
    data.has_tax_coordination ? 'כן' : 'לא',
    safeString(data.declaration_date),
    '',
    '',
    'ממתין ל-PDF',
    JSON.stringify(data.children),
    JSON.stringify(data.additional_incomes),
    JSON.stringify(data.changes),
    JSON.stringify(buildSummary(data)),
    JSON.stringify(data)
  ];

  sheet.appendRow(row);
  return sheet.getLastRow();
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

  // עמודות 25-27 לפי headers למעלה (קישור PDF, ID, סטטוס)
  // (שמור בהתאם לסדר headers)
  sheet.getRange(rowNum, 25).setValue(pdfFile.getUrl());
  sheet.getRange(rowNum, 26).setValue(pdfFile.getId());
  sheet.getRange(rowNum, 27).setValue('✅ הושלם');
}

/* ==============================
   PDF
============================== */

function createPDF(data) {
  // חובה: קובץ HTML בשם PDFTemplate בפרויקט
  const template = HtmlService.createTemplateFromFile('PDFTemplate');
  template.data = data;
  template.pdf = buildPdfViewModel(data);
  template.data = data;

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

function sendToMake(data, pdfFile) {
  if (!CONFIG.MAKE_WEBHOOK_URL || !String(CONFIG.MAKE_WEBHOOK_URL).trim()) return;

  const payload = {
    employee: {
      first_name: safeString(data.first_name),
      last_name: safeString(data.last_name),
      id_number: safeString(data.id_number),
      mobile_phone: safeString(data.mobile_phone),
      email: safeString(data.email),
    },
    employer: {
      employer_name: safeString(data.employer_name),
      employer_tax_id: safeString(data.employer_tax_id),
    },
    meta: {
      submitted_at: safeString(data.submitted_at),
      taxYear: safeString(data.taxYear),
    },
    pdf: {
      url: pdfFile ? pdfFile.getUrl() : '',
      id: pdfFile ? pdfFile.getId() : '',
      name: pdfFile ? pdfFile.getName() : '',
    },
    data, // JSON מלא
  };

  try {
    UrlFetchApp.fetch(CONFIG.MAKE_WEBHOOK_URL, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
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
