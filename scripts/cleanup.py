"""
List and optionally delete test rows from the Google Sheet.

Test rows = rows whose מספר זהות matches TEST_ID_NUMBERS in Code.gs (default: 123456789).

Usage:
    python -m scripts.cleanup            # list test rows only
    python -m scripts.cleanup --delete   # list + prompt to delete via GAS
"""
import sys
import requests
from scripts.config import APPS_SCRIPT_URL


def list_test_rows() -> list[dict]:
    r = requests.get(APPS_SCRIPT_URL, params={"action": "listTestRows"}, timeout=30)
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"GAS error: {data}")
    return data["rows"]


def main() -> None:
    print("\n[CLEANUP] בודק שורות בדיקה בגיליון…")
    rows = list_test_rows()

    if not rows:
        print("  ✅ אין שורות בדיקה בגיליון.")
        return

    print(f"  נמצאו {len(rows)} שורות בדיקה:\n")
    for r in rows:
        print(f"    שורה {r['rowNum']:3d} | {r['name']:<20} | ת\"ז: {r['id']} | {r['date']}")

    if "--delete" not in sys.argv:
        print("\n  הרץ עם --delete כדי למחוק אותן.")
        return

    print("\n  ⚠  האם למחוק את כל השורות הללו? [y/N] ", end="", flush=True)
    ans = input().strip().lower()
    if ans != "y":
        print("  בוטל.")
        return

    # Trigger deleteTestRows via a POST (doPost would need an action param;
    # instead call it inline via the verify-style GET not available —
    # user should run deleteTestRows() directly in the Apps Script editor.)
    print("\n  ℹ  מחיקה אוטומטית דרך ה-API אינה זמינה (דורשת הרשאת עריכה).")
    print("  כדי למחוק: פתח Apps Script → הרץ את הפונקציה deleteTestRows()")
    print("  מספרי השורות למחיקה:", [r["rowNum"] for r in rows])


if __name__ == "__main__":
    main()
