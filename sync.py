"""Pull new/changed transactions from Plaid and write data/transactions.csv.

Amounts use bank sign convention (money in = positive, money out = negative),
matching the Wells Fargo CSV, so Claude's existing rules apply unchanged.
Prints a one-line JSON summary on the last line of output.
"""
import csv
import json
import sys

from plaid_common import DATA_DIR, PlaidError, load_env, load_token, plaid, write_private

env = load_env()
tok = load_token()
DATA_DIR.mkdir(exist_ok=True)
STATE = DATA_DIR / "state.json"
STORE = DATA_DIR / "transactions.json"
OUT = DATA_DIR / "transactions.csv"

state = json.loads(STATE.read_text()) if STATE.exists() else {"cursor": None}
store = json.loads(STORE.read_text()) if STORE.exists() else {}

try:
    accounts = {
        a["account_id"]: f'{a.get("subtype") or a.get("type")} ...{a.get("mask") or ""}'.strip()
        for a in plaid(env, "/accounts/get", {"access_token": tok["access_token"]})["accounts"]
    }
    cursor, added, modified, removed = state["cursor"], 0, 0, 0
    while True:
        body = {"access_token": tok["access_token"], "count": 500,
                "options": {"include_original_description": True}}
        if cursor:
            body["cursor"] = cursor
        r = plaid(env, "/transactions/sync", body)
        for t in r["added"] + r["modified"]:
            store[t["transaction_id"]] = {
                "date": t["date"],
                "description": t.get("original_description") or t.get("name") or "",
                "merchant": t.get("merchant_name") or "",
                "amount": round(-float(t["amount"]), 2),  # Plaid: positive = outflow
                "account": accounts.get(t["account_id"], t["account_id"][-6:]),
                "pending": bool(t.get("pending")),
            }
        added += len(r["added"])
        modified += len(r["modified"])
        for t in r["removed"]:
            if store.pop(t["transaction_id"], None) is not None:
                removed += 1
        cursor = r["next_cursor"]
        if not r["has_more"]:
            break
except PlaidError as e:
    if e.code == "ITEM_LOGIN_REQUIRED":
        sys.exit("Wells Fargo needs you to log in again. Run: python link.py --update")
    if e.code == "PRODUCT_NOT_READY":
        sys.exit("Plaid is still pulling your history. Try again in a few minutes.")
    sys.exit(f"Plaid error {e}")

# Save cursor only after the full loop succeeded, so a failure never skips transactions.
write_private(STORE, store)
write_private(STATE, {"cursor": cursor})

rows = sorted((v for v in store.values() if not v["pending"]), key=lambda v: v["date"])
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["DATE", "DESCRIPTION", "MERCHANT", "AMOUNT", "ACCOUNT"])
    for v in rows:
        w.writerow([v["date"], v["description"], v["merchant"], f'{v["amount"]:.2f}', v["account"]])

print(json.dumps({
    "ok": True, "added": added, "modified": modified, "removed": removed,
    "posted_total": len(rows),
    "first_date": rows[0]["date"] if rows else None,
    "last_date": rows[-1]["date"] if rows else None,
    "csv": str(OUT),
}))
