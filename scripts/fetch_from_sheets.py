"""
fetch_from_sheets.py
====================
קורא שורות מ-Google Sheets "מעקב טופס 101" ומוציא JSON מוכן ל-sheets_to_pdf.py.

אימות: משתמש ב-~/.clasprc.json (נוצר ע"י `clasp login`).
       לחלופין: service account דרך GOOGLE_APPLICATION_CREDENTIALS.

שימוש:
  # שורה לפי מספר שורה (1=כותרות, 2=ראשונה)
  python scripts/fetch_from_sheets.py --row 2

  # שורה לפי מספר זהות
  python scripts/fetch_from_sheets.py --id 123456789

  # השורה האחרונה
  python scripts/fetch_from_sheets.py --last

  # רשימת כל השורות
  python scripts/fetch_from_sheets.py --list

  # שמור JSON לקובץ
  python scripts/fetch_from_sheets.py --last --out output.json

  # מלא PDF ישירות
  python scripts/fetch_from_sheets.py --last --fill

  # שמור JSON ומלא PDF
  python scripts/fetch_from_sheets.py --id 123456789 --out row.json --fill
"""

import argparse, json, os, sys, subprocess, tempfile
from datetime import datetime

# ── Google API ────────────────────────────────────────────────────────────────
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("❌ חסר: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASPRC_PATH   = os.path.expanduser('~/.clasprc.json')
SHEETS_TO_PDF  = os.path.join(ROOT, 'scripts', 'sheets_to_pdf.py')

# Import SPREADSHEET_ID and SHEET_NAME from config
sys.path.insert(0, ROOT)
from scripts.config import SPREADSHEET_ID
SHEET_NAME = 'מעקב טופס 101'

# ── Column map (41 columns, 1-based) ─────────────────────────────────────────
# Maps column index → data key used by sheets_to_pdf.py
COL_MAP = {
    1:  'submitted_at',
    2:  'taxYear',
    3:  'employer_name',
    4:  'employer_tax_id',
    5:  'employer_phone',
    6:  'employer_address',
    7:  'start_date',
    8:  'last_name',
    9:  'first_name',
    10: 'id_number',
    11: 'passport_number',
    12: 'birth_date',
    13: 'aliya_date',
    14: 'address',
    15: 'postal_code',
    16: 'mobile_phone',
    17: 'email',
    18: 'gender',
    19: 'marital_status',
    20: 'israeli_resident',
    21: 'kibbutz_member',
    22: 'health_fund',
    23: 'children_count',
    24: 'children_json',
    25: 'summary_income_types',
    26: 'has_other_income',
    27: 'additional_incomes_count',
    28: 'additional_incomes_json',
    29: 'no_study_fund_other',
    30: 'no_pension_other',
    31: 'has_spouse',
    32: 'summary_spouse',
    33: 'summary_reliefs',
    34: 'has_tax_coordination',
    35: 'changes_json',
    36: 'declaration_date',
    37: 'pdf_link',
    38: 'drive_file_id',
    39: 'status',
    40: 'summary_json',
    41: 'full_json',
}

# ── Authentication ────────────────────────────────────────────────────────────

SHEETS_SCOPE    = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SAVED_CREDS     = os.path.expanduser('~/.form101_sheets_credentials.json')


def get_credentials():
    """Returns valid Google credentials for Sheets API.

    Priority:
      1. GOOGLE_APPLICATION_CREDENTIALS (service account JSON)
      2. ~/.form101_sheets_credentials.json  (saved OAuth token, created on first run)
      3. Browser OAuth flow using clasp's client_id/secret (one-time setup)
    """
    # ── Option 1: service account ──────────────────────────────────────────
    sa_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if sa_path and os.path.exists(sa_path):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=SHEETS_SCOPE)
        print(f"🔑 Auth: service account ({os.path.basename(sa_path)})")
        return creds

    # ── Option 2: saved OAuth token ────────────────────────────────────────
    creds = None
    if os.path.exists(SAVED_CREDS):
        creds = Credentials.from_authorized_user_file(SAVED_CREDS, SHEETS_SCOPE)

    if creds and creds.valid:
        print(f"🔑 Auth: saved token ({SAVED_CREDS})")
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
        print(f"🔑 Auth: token refreshed")
        return creds

    # ── Option 3: browser OAuth flow (one-time) ────────────────────────────
    # Read client_id/secret from ~/.clasprc.json (same Google Cloud project)
    if not os.path.exists(CLASPRC_PATH):
        _print_auth_help()
        sys.exit(1)

    with open(CLASPRC_PATH, encoding='utf-8') as f:
        clasprc = json.load(f)

    tok = next(iter(clasprc.get('tokens', {}).values()), {})
    client_id     = tok.get('client_id')
    client_secret = tok.get('client_secret')

    if not client_id or not client_secret:
        _print_auth_help()
        sys.exit(1)

    # Build OAuth2 flow
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ חסר: pip install google-auth-oauthlib")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }

    print("\n🌐 נדרשת הרשאה ל-Google Sheets (פעם ראשונה בלבד)")
    print("   דפדפן יפתח — אשר גישה לחשבון Google שלך")
    print(f"   האישור ישמר ב: {SAVED_CREDS}\n")

    flow  = InstalledAppFlow.from_client_config(client_config, SHEETS_SCOPE)
    creds = flow.run_local_server(port=0, prompt='consent')

    _save_creds(creds)
    print(f"🔑 Auth: OAuth flow הושלם, token נשמר")
    return creds


def _save_creds(creds):
    with open(SAVED_CREDS, 'w') as f:
        f.write(creds.to_json())


def _print_auth_help():
    print("❌ לא ניתן לאמת — אפשרויות:")
    print()
    print("  אפשרות A — Service Account (מומלץ לשרת):")
    print("    1. Google Cloud Console → IAM → Service Accounts → Create")
    print("    2. הורד JSON key")
    print("    3. שתף את הגיליון עם כתובת המייל של ה-service account")
    print("    4. export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    print()
    print("  אפשרות B — OAuth (למשתמש בודד):")
    print("    הרץ `clasp login` ואז נסה שוב")


def get_service():
    creds = get_credentials()
    return build('sheets', 'v4', credentials=creds, cache_discovery=False)

# ── Sheets helpers ────────────────────────────────────────────────────────────

def fetch_all_rows(service) -> tuple[list, list]:
    """Returns (headers, data_rows) — headers is row 1, data_rows start from row 2."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'",
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    values = result.get('values', [])
    if not values:
        return [], []
    headers   = values[0]
    data_rows = values[1:]
    return headers, data_rows


def row_to_dict(row: list) -> dict:
    """Converts a flat Sheets row (list) → keyed dict using COL_MAP."""
    result = {}
    for col_idx, key in COL_MAP.items():
        i = col_idx - 1  # 0-based
        val = row[i] if i < len(row) else ''
        result[key] = val

    # Parse full_json if present
    raw_fj = result.get('full_json', '')
    if raw_fj and isinstance(raw_fj, str):
        try:
            result['full_json'] = json.loads(raw_fj)
        except json.JSONDecodeError:
            result['full_json'] = None

    return result


def find_by_id(data_rows: list, id_number: str) -> tuple[int, list | None]:
    """Search for a row by employee ID (column 10, index 9). Returns (sheet_row_num, row)."""
    id_col = 9  # 0-based, column 10
    for i, row in enumerate(data_rows):
        if i < len(data_rows) and len(row) > id_col:
            if str(row[id_col]) == str(id_number):
                return i + 2, row  # +2: 1-based + header row
    return -1, None

# ── Output helpers ────────────────────────────────────────────────────────────

def print_list(data_rows: list):
    """Print a summary table of all rows."""
    print(f"\n{'שורה':<6}  {'ת.ז.':<12}  {'שם':<20}  {'מעסיק':<20}  {'סטטוס':<25}")
    print('─' * 90)
    id_col     = 9   # 0-based
    fname_col  = 8
    lname_col  = 7
    emp_col    = 2
    status_col = 38
    for i, row in enumerate(data_rows):
        def c(idx): return str(row[idx]) if idx < len(row) else ''
        row_num = i + 2
        name    = f"{c(lname_col)} {c(fname_col)}".strip()
        print(f"{row_num:<6}  {c(id_col):<12}  {name:<20}  {c(emp_col):<20}  {c(status_col):<25}")
    print(f"\nסה\"כ: {len(data_rows)} שורות\n")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='קריאת שורה מ-Sheets → JSON')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--row',  type=int,  help='מספר שורה (2=ראשונה אחרי כותרות)')
    group.add_argument('--id',   type=str,  help='מספר זהות עובד')
    group.add_argument('--last', action='store_true', help='השורה האחרונה')
    group.add_argument('--list', action='store_true', help='רשימת כל השורות')
    parser.add_argument('--out',  type=str, help='שמור JSON לקובץ')
    parser.add_argument('--fill', action='store_true', help='מלא PDF עם sheets_to_pdf.py')
    args = parser.parse_args()

    service = get_service()
    headers, data_rows = fetch_all_rows(service)

    if not data_rows:
        print("⚠️  הגיליון ריק או לא נמצא")
        sys.exit(1)

    print(f"📊 נמצאו {len(data_rows)} שורות ב-'{SHEET_NAME}'")

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        print_list(data_rows)
        return

    # ── Select row ────────────────────────────────────────────────────────────
    sheet_row_num = None
    raw_row       = None

    if args.last:
        raw_row       = data_rows[-1]
        sheet_row_num = len(data_rows) + 1   # +1 for header
        print(f"📌 בוחר שורה אחרונה: {sheet_row_num}")

    elif args.row:
        idx = args.row - 2  # convert sheet row → data_rows index
        if idx < 0 or idx >= len(data_rows):
            print(f"❌ שורה {args.row} לא קיימת (טווח: 2–{len(data_rows)+1})")
            sys.exit(1)
        raw_row       = data_rows[idx]
        sheet_row_num = args.row
        print(f"📌 בוחר שורה: {sheet_row_num}")

    elif args.id:
        sheet_row_num, raw_row = find_by_id(data_rows, args.id)
        if raw_row is None:
            print(f"❌ לא נמצאה שורה עם ת.ז. {args.id}")
            sys.exit(1)
        print(f"📌 נמצאה שורה {sheet_row_num} לת.ז. {args.id}")

    # ── Convert to dict ───────────────────────────────────────────────────────
    row_dict = row_to_dict(raw_row)
    row_dict['_sheet_row'] = sheet_row_num

    # Summary
    name   = f"{row_dict.get('last_name','')} {row_dict.get('first_name','')}".strip()
    status = row_dict.get('status', '')
    mode   = 'A (full_json)' if row_dict.get('full_json') else 'B (summaries)'
    print(f"👤 {name}  |  ת.ז.: {row_dict.get('id_number','')}  |  {status}")
    print(f"🔧 Mode: {mode}")

    # ── Output ────────────────────────────────────────────────────────────────
    json_str = json.dumps(row_dict, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f"💾 נשמר: {args.out}")

    if args.fill:
        # Write to temp file if no --out given
        if args.out:
            json_path = args.out
        else:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                              encoding='utf-8', delete=False)
            tmp.write(json_str)
            tmp.close()
            json_path = tmp.name

        id_str  = row_dict.get('id_number', f'row{sheet_row_num}')
        out_pdf = os.path.join(ROOT, 'NEW 3', f'filled_{id_str}.pdf')

        print(f"📄 ממלא PDF → {out_pdf}")
        result = subprocess.run(
            [sys.executable, SHEETS_TO_PDF, '--data', json_path, '--out', out_pdf],
            cwd=ROOT
        )

        if not args.out:
            os.unlink(json_path)  # cleanup temp

        if result.returncode != 0:
            print("❌ sheets_to_pdf.py נכשל")
            sys.exit(1)

    elif not args.out:
        # Default: print JSON to stdout
        print()
        print(json_str)


if __name__ == '__main__':
    main()
