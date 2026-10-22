# plaid-sync

A personal finance pipeline: bank transactions → categorized weekly and monthly breakdowns, with no paid aggregator app.

```
Wells Fargo ──Plaid API──▶ GitHub Actions (every 12h) ──▶ private repo: data/out/txns/YYYY-MM.json
                                                               │
                                     Claude scheduled task ◀───┘  (read-only token)
                                               │
                                               ▼
                         Money Breakdown page (phone/desktop): live totals, tap-to-recategorize
```

## What it does

- **`link.py`**: one-time bank link. It serves Plaid Link on `127.0.0.1` and exchanges the public token for an access token. The resulting token file is written `0600`.
- **`sync.py`**: incremental pull with `/transactions/sync` and a persisted cursor. It handles added, modified, and removed transactions. The cursor is saved only after a full successful pass, so a failure never skips data.
- **`report.py`**: regex rules plus one-off overrides turn transactions into income, expense, and ignored transfers, then summarize a week or a month.
- **`export_txns.py`**: monthly JSON for the web page. Descriptions are sanitized: reference numbers, masked account digits, and card suffixes are removed.
- **`.github/workflows/sync.yml`**: runs the sync every 12 hours and commits only when something changed.

## Security decisions

| Risk | Mitigation |
|---|---|
| Plaid secret / access token leakage | Stored only as GitHub Actions encrypted secrets (or a local `0600` file). Never committed, never printed: script output goes to `/dev/null` in CI. |
| Bank data exposure | Data lives in a **private** repo. The public copy of this project ships code only. Exports strip reference numbers and account digits. |
| Consumer of the data | Reads through a fine-grained GitHub token scoped to **one repo, Contents: read-only**. |
| Local link page abuse (CSRF from other local sites) | The exchange endpoint requires a per-run random nonce embedded in the page (`secrets.compare_digest`). It binds to loopback only. |
| Partial sync corrupting state | Atomic writes (`tmp` + `os.replace`). The cursor is committed only after the loop completes. |
| Workflow privilege | `permissions: contents: write` only, a `concurrency` group, and a 10-minute timeout. |

## Setup

1. Create a Plaid developer account. The Trial plan allows 10 free production Items.
2. Locally: copy `.env.example` to `.env` and run `python3 link.py` to log in to your bank on Plaid's screen.
3. In a **private** GitHub repo, add these Actions secrets: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ACCESS_TOKEN` (from `.plaid_token.json`).
4. Push the code and `data/`, then go to Actions → plaid-sync → Run workflow.

Stack: Python 3 standard library only (no SDK), GitHub Actions, Plaid Transactions API.
