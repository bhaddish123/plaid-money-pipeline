"""Export transactions for the Money Breakdown page, one JSON file per month.

  python3 export_txns.py            all months
  python3 export_txns.py 2026-09    that month and later

Writes data/out/txns/YYYY-MM.json = {"month", "rows": [[date, payee, merchant, amount, desc]]}.
amount uses bank sign (money in positive). desc is the bank description with reference
numbers and account digits removed; it's what categorization rules match against.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ns = {"__file__": str(ROOT / "report.py")}
exec((ROOT / "report.py").read_text().split("def summarize")[0], ns)  # parses data/transactions.csv into rows


def sanitize(desc):
    d = re.sub(r"(?i)\b(REF ?#|Ref#|REF\*)\s*\S*", "", desc)
    d = re.sub(r"XXXXXX\d+|\bS\d{9,}\b|\bP\d{9,}\b|\b\d{9,}\b", "", d)
    d = re.sub(r"\bCARD ?\d{4}\b", "", d)
    return re.sub(r"\s+", " ", d).strip()


since = sys.argv[1] if len(sys.argv) > 1 else "0000-00"
by_month = defaultdict(list)
for r in ns["rows"]:
    m = r["d"].isoformat()[:7]
    if m >= since:
        by_month[m].append([r["d"].isoformat(), r["name"], r["merchant"], round(r["amt"], 2), sanitize(r["desc"])])

out = ROOT / "data" / "out" / "txns"
out.mkdir(parents=True, exist_ok=True)
for m, rows in sorted(by_month.items()):
    (out / f"{m}.json").write_text(json.dumps({"month": m, "rows": sorted(rows)}))
print(json.dumps({"months": sorted(by_month), "rows": sum(map(len, by_month.values()))}))
