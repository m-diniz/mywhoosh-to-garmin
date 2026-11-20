# AI Agent Guide: MyWhoosh → Garmin Sync

## Purpose & flow

MyWhoosh → **intervals.icu** (MyWhoosh's official connection) → this tool → **Garmin Connect**.
The FIT file is attributed to a Garmin Edge 840 so Garmin computes Training Effect / training load.
Only the `file_id`/device fields change; records, laps and sessions are untouched.

Runs unattended every 15 min via Windows Task Scheduler (`scripts/agendar.ps1`, task `MyWhoosh2Garmin`).

**Why not the MyWhoosh API:** it allows one session per account and refuses login
(`LoginType: 4`, "You are already logged in from another device") while the app is logged in
anywhere, even after logging out of the devices. It fights the user's own app. Do not reintroduce it.

## Layout

| File | Role |
|------|------|
| `main.py` | CLI (`--setup`, `--list`, default = sync), config, logging, exit codes, alerts |
| `services/activity_processor.py` | `sync_new_activities()`: pick new items, dedupe, download, modify, upload |
| `services/intervals_service.py` | intervals.icu source: list (filtered by origin), download original FIT |
| `services/fit_file_service.py` | Rewrite device info to Garmin Edge 840 |
| `services/garmin_service.py` | Garmin auth **by saved token only**, duplicate check, upload |
| `services/sync_state.py` | `state.json`: IDs already on Garmin (atomic writes) |
| `services/credentials.py` | Keyring (Windows Credential Manager) + Garmin token path |
| `services/notify.py` | Windows toasts; each problem alerted once, reset on success |
| `scripts/login_garmin.py` | One-time interactive Garmin login (+MFA), saves token only |
| `scripts/agendar.ps1` | Create/remove the scheduled task |

## Secrets (never in files or logs)

- intervals.icu API key → Windows Credential Manager (service `mywhoosh-to-garmin`, user `intervals.icu:<athlete id>`).
- Garmin → OAuth token in `~/.garminconnect-mywhoosh`; password/MFA typed once, never stored.
- `.env` holds only non-secrets: `INTERVALS_ATHLETE_ID`, `INTERVALS_SOURCE`, `SYNC_*`, `LOG_LEVEL`.
- Git-ignored runtime files: `.env`, `state.json`, `.alerts.json`, `sync.log*`.

## Behaviour rules

- Origin filter: intervals.icu reports MyWhoosh rides with `source` = `OAUTH_CLIENT` (auto) or `UPLOAD`
  (manual) and `device_name` = `MYWHOOSH <n>`; the filter matches `MYWHOOSH` across source/device/external_id.
- Only activities newer than `SYNC_MAX_AGE_DAYS` (14) and not in `state.json`; oldest first.
- An ID enters `state.json` only after Garmin confirms (upload ok, 409, or time-window duplicate).
- 1.5 s between uploads; on Garmin 429 stop and leave the rest for the next run.
- Garmin is only contacted when there is something new.
- Interactive input (`getpass`) does not work through Claude Code's `!`; open a separate PowerShell window.

## Language

User-facing text (CLI output, logs, notifications, scripts) is in English. Code comments and docstrings are in Portuguese.

## Exit codes

0 ok · 1 errors · 2 config/intervals key · 3 redo `scripts/login_garmin.py` · 4 Garmin 429

## Testing

```powershell
venv\Scripts\python.exe -m pytest -q        # unit tests (all network mocked)
venv\Scripts\python.exe main.py --list      # read-only view of intervals.icu + sync state
```
`tests/test_smoke.py` compiles every entry point (catches syntax errors in files no test imports).

## Dependencies

Dependabot runs monthly, grouped (`.github/dependabot.yml`):
- `github-actions` and `python-safe` → auto-merged (squash) by `.github/workflows/dependabot-automerge.yml` once the `Tests` check passes.
- `python-sensitive` (`garminconnect`, `fit-tool`) → manual. Before merging, test with real data: Garmin token login (`scripts/login_garmin.py` with an existing token) and a FIT conversion of a real ride compared against the current version.
- Merging on GitHub does not update the local install: `git pull` + `venv\Scripts\pip install -r requirements.txt`.

## Commits

Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`). `upstream` = marcelorodrigo/mywhoosh-to-garmin.
