# plaid-money-pipeline

A personal finance pipeline: bank transactions in through the Plaid Transactions API, categorized weekly and monthly breakdowns out, with no paid aggregator app and no third-party Python dependencies.

```
Bank ──Plaid API──▶ GitHub Actions (every 12h) ──▶ private repo: data/out/txns/YYYY-MM.json
                                                          │
                                consumer (read-only token) ◀┘
                                          │
                                          ▼
                    Money Breakdown page: live totals, tap-to-recategorize
```

The **public** copy of this project ships code only. Transaction data is intended to live in a **private** repo. This public clone does not include a `data/` directory.

---

## What each file does

| File | Purpose |
|---|---|
| `link.py` | One-time bank link. Serves Plaid Link on `127.0.0.1`, exchanges the public token for an access token, and writes the token file with mode `0600`. The exchange endpoint requires a per-run random nonce (`secrets.compare_digest`) and binds to loopback only. |
| `sync.py` | Incremental pull with `/transactions/sync` and a persisted cursor. Handles added, modified, and removed transactions. The cursor is saved only after a full successful pass, so a failure does not skip data. Writes use `tmp` + `os.replace`. |
| `report.py` | Regex rules plus one-off overrides (`rules.json`) classify transactions as income, expense, or ignored transfers, then summarize a week or a month. |
| `export_txns.py` | Monthly JSON for the web page. Descriptions are sanitized: reference numbers, masked account digits, and card suffixes are stripped. |
| `plaid_common.py` | Shared Plaid HTTP helpers and config loading. |
| `install_schedule.sh` | Optional local scheduler setup. |
| `.github/workflows/sync.yml` | Runs at `17 0,12 * * *` (every 12 hours) and on `workflow_dispatch`. Commits under `data/` only when something changed. |
| `.env.example` | Documents `PLAID_CLIENT_ID`, `PLAID_SECRET`, and `PLAID_ENV` (no values). |
| `requirements.txt` | Standard library only (Python 3.10+ / CI uses 3.12). |

---

## Security decisions (as implemented)

| Risk | Mitigation in this repo |
|---|---|
| Plaid secret / access token leakage | Stored as GitHub Actions encrypted secrets, or a local `0600` file (`.plaid_token.json` is gitignored). Script output is redirected to `/dev/null` in CI. |
| Bank data exposure | Data is meant to live in a **private** repo. Exports strip reference numbers and account digits. `data/out/changes.json` is gitignored. |
| Consumer of the data | Designed to read through a fine-grained GitHub token scoped to one repo, Contents: read-only. |
| Local link page abuse | Nonce on the exchange endpoint; loopback only. |
| Partial sync corrupting state | Atomic writes; cursor committed only after the loop completes. |
| Workflow privilege | `permissions: contents: write` only, a `concurrency` group, 10-minute timeout, `cancel-in-progress: false`. |

---

## Setup

1. Create a Plaid developer account. The README notes that the Trial plan allows 10 free production Items.
2. Locally: copy `.env.example` to `.env` and run `python3 link.py` to log in to your bank on Plaid's screen.
3. In a **private** GitHub repo, add Actions secrets: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ACCESS_TOKEN` (from `.plaid_token.json`).
4. Push the code and `data/`, then run **Actions → plaid-sync → Run workflow**.

```bash
python3 link.py          # one-time, local
python3 sync.py          # pull transactions
python3 report.py        # weekly / monthly summary (see --help in the script)
python3 export_txns.py 2026-10
```

The workflow sets `PLAID_ENV: production`. Use `PLAID_ENV=sandbox` in `.env` when testing with fake data.

---

## Stack

Python 3 standard library only (no Plaid SDK) · GitHub Actions · Plaid Transactions API
