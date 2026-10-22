"""Summarize data/transactions.csv for a period using rules.json. Stdlib only.

  python3 report.py week 2026-10-19     Monday-to-Sunday week starting that Monday
  python3 report.py month 2026-10       calendar month

Prints JSON: totals, categories, unlabeled items, and the trailing 8-week (or 3-month)
category averages so the caller can write flags and tips.
txns maps each category (and "Needs label") to [date, payee, amount] rows; expenses are positive.
"""
import collections
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_cfg = json.loads((ROOT / "rules.json").read_text())


def _rule(r):
    """Rules are [regex, category, kind] or {"rx", "cat", "kind"} (the Money Breakdown page's format)."""
    return (r["rx"], r["cat"], r["kind"]) if isinstance(r, dict) else tuple(r[:3])


RULES = [(re.compile(rx), cat, kind) for rx, cat, kind in map(_rule, _cfg["rules"])]
# One-off fixes keyed by (date, payee as shown on the page, absolute amount).
OVERRIDES = {(o["date"], o["name"], round(abs(float(o["amount"])), 2)): (o.get("cat") or o["category"], o["kind"])
             for o in _cfg.get("overrides", [])}


def classify(desc, merchant=""):
    """Rules match the bank description, or Plaid's merchant name when there is one."""
    for rx, cat, kind in RULES:
        if rx.search(desc) or (merchant and rx.search(merchant)):
            return cat, kind
    return None, "ask"


def txn_date(posted, desc):
    """Use the 'AUTHORIZED ON MM/DD' date when present, so purchases land on the day made."""
    m = re.search(r"AUTHORIZED ON (\d\d)/(\d\d)", desc)
    if m:
        try:
            d = dt.date(posted.year, int(m.group(1)), int(m.group(2)))
            return d.replace(year=d.year - 1) if d > posted else d
        except ValueError:
            pass
    return posted


def clean_name(merchant, desc):
    """Readable payee without reference numbers or account digits."""
    if merchant:
        return merchant[:40]
    d = re.sub(r"^(PURCHASE|RECURRING PAYMENT)( AUTHORIZED ON \d\d/\d\d)? ", "", desc)
    d = re.sub(r"(?i)\b(REF ?#|Ref#|REF\*).*$", "", d)
    d = re.sub(r"\bEDI PAYMNT.*$", "payout", d)
    d = re.sub(r"\b(?=\w*\d)(?=\w*[A-Z])\w{8,}\b", "", d)
    d = re.sub(r"XXXXXX\d+|\bS\d{9,}\b.*$|\bCARD ?\d{4}.*$|\d{6,}", "", d)
    return re.sub(r"\s+", " ", d).strip(" /-")[:40]


rows = []
for r in csv.DictReader(open(ROOT / "data" / "transactions.csv")):
    desc = re.sub(r"\s+", " ", r["DESCRIPTION"]).strip()
    merchant = r.get("MERCHANT") or ""
    d, name, amt = txn_date(dt.date.fromisoformat(r["DATE"]), desc), clean_name(merchant, desc), float(r["AMOUNT"])
    cat, kind = OVERRIDES.get((d.isoformat(), name, round(abs(amt), 2))) or classify(desc, merchant)
    rows.append(dict(d=d, desc=desc, name=name, merchant=merchant, amt=amt, cat=cat, kind=kind))


def summarize(a, b):
    inc, exp, ask = collections.Counter(), collections.Counter(), collections.defaultdict(float)
    txns = collections.defaultdict(list)
    for r in rows:
        if not (a <= r["d"] <= b) or r["kind"] == "ignore":
            continue
        key = r["cat"] if r["kind"] != "ask" else "Needs label"
        amt = r["amt"] if r["kind"] == "income" else -r["amt"] if r["kind"] == "expense" else r["amt"]
        txns[key].append([r["d"].isoformat(), r["name"], round(amt, 2)])
        if r["kind"] == "ask":
            ask[r["name"]] += r["amt"]
        elif r["kind"] == "income":
            inc[r["cat"]] += r["amt"]
        else:
            exp[r["cat"]] -= r["amt"]
    I, E = round(sum(inc.values()), 2), round(sum(exp.values()), 2)
    return dict(start=str(a), end=str(b), income=I, expenses=E, net=round(I - E, 2),
                income_cats=[[k, round(v, 2)] for k, v in inc.most_common()],
                expense_cats=[[k, round(v, 2)] for k, v in exp.most_common()],
                unlabeled=[[k, round(v, 2)] for k, v in sorted(ask.items(), key=lambda x: x[1])],
                txns={k: sorted(v) for k, v in txns.items()})


def month_bounds(y, m):
    start = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return start, nxt - dt.timedelta(days=1)


def avg(periods):
    tot = collections.Counter()
    for a, b in periods:
        for k, v in summarize(a, b)["expense_cats"]:
            tot[k] += v
    return {k: round(v / len(periods), 2) for k, v in tot.most_common()}


mode, arg = sys.argv[1], sys.argv[2]
if mode == "week":
    a = dt.date.fromisoformat(arg)
    if a.weekday() != 0:
        sys.exit("week start must be a Monday")
    out = summarize(a, a + dt.timedelta(days=6))
    out.update(type="week", label="Week of " + a.strftime("%b %-d"))
    out["avg_prev_8_weeks"] = avg([(a - dt.timedelta(weeks=i), a - dt.timedelta(weeks=i) + dt.timedelta(days=6)) for i in range(1, 9)])
elif mode == "month":
    y, m = map(int, arg.split("-"))
    a, b = month_bounds(y, m)
    out = summarize(a, b)
    out.update(type="month", label=a.strftime("%B %Y"))
    prev = []
    for i in range(1, 4):
        pm, py = (m - i - 1) % 12 + 1, y + (m - i - 1) // 12
        prev.append(month_bounds(py, pm))
    out["avg_prev_3_months"] = avg(prev)
    out["net_prev_3_months"] = [summarize(*p)["net"] for p in prev]
else:
    sys.exit("mode must be week or month")

out["data_last_date"] = max(r["d"] for r in rows).isoformat() if rows else None
print(json.dumps(out))
