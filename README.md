# MyWhoosh → Garmin Connect (via intervals.icu)

Automatically sends your **MyWhoosh** rides to **Garmin Connect**, with power, heart rate and cadence,
and they count toward Garmin's Training Effect and training load.

> **Modified fork** of [marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin)
> by Marcelo Rodrigo, distributed under the same **GPL-3.0** license. Modified by
> [m-diniz](https://github.com/m-diniz) starting 2026-11-20. The changes are listed under
> [Differences from the original](#differences-from-the-original) and in the git history.

> **Note:** messages, logs and notifications are in English; code comments and docstrings are in Portuguese.

## How it works

```
MyWhoosh ──(official connection)──► intervals.icu ──(this tool, every 15 min)──► Garmin Connect
```

1. MyWhoosh sends each ride to intervals.icu (Connections → intervals.icu).
2. The tool fetches new MyWhoosh activities from intervals.icu and downloads the **original FIT file**.
3. It changes only the device identification to **Garmin Edge 840**. The data itself is not modified.
   This is what makes Garmin compute Training Effect, training load and training status.
4. It uploads the ride to Garmin Connect, avoids duplicates, and shows a Windows notification.

**Why not the MyWhoosh API?** It allows a single session per account and refuses logins
("You are already logged in from another device") while the app is logged in on any device, even
after logging out of it. In practice it would fight your own app for the session.

## Security

| Secret | Where it lives |
|---|---|
| intervals.icu API key | Windows Credential Manager (`keyring`). Revocable in intervals.icu. |
| Garmin password and MFA code | Never stored. Typed once; only the token is kept, in `~/.garminconnect-mywhoosh`. |
| MyWhoosh password | Not used. |

`.env` holds only non-secret settings, such as the Athlete ID. `.env`, `state.json`,
`.alerts.json` and `sync.log` are git-ignored.

## Installation (Windows)

Requirements: Python 3.11+, an [intervals.icu](https://intervals.icu) account (free) and a Garmin Connect account.

```powershell
git clone https://github.com/m-diniz/mywhoosh-to-garmin.git
cd mywhoosh-to-garmin
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # fill in INTERVALS_ATHLETE_ID
```

1. **MyWhoosh:** Connections → intervals.icu → *Connect*.
   Do **not** connect Garmin in intervals.icu, or the ride will come back as a duplicate.
2. **intervals.icu API key** (Settings → Developer Settings → API Key):
   `venv\Scripts\python.exe main.py --setup`
3. **Garmin login** (asks for email, password and the MFA code, if enabled):
   `venv\Scripts\python.exe scripts\login_garmin.py`
4. **Test:**
   `venv\Scripts\python.exe main.py --list` shows what intervals.icu has, without uploading anything.
   `venv\Scripts\python.exe main.py` uploads new activities from the last 14 days.
5. **Automate** (every 15 min and at Windows logon):
   `powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1`
   To remove it: the same command with `-Remover`.

> Steps 2 and 3 need keyboard input. Run them in a regular PowerShell window, not in tools that
> don't provide an interactive terminal.

## Day-to-day use

Nothing to do: ride, and the activity shows up on Garmin within about 20 minutes.

- **Notifications:** the tool tells you when a ride is uploaded. It also tells you when it needs you:
  an expired Garmin token or a rejected intervals.icu key. Transient failures, such as network or
  service outages, only trigger an alert if they last more than 1 hour. Each problem is reported only once.
- **Log:** `sync.log`, with automatic rotation.
- **No duplicates:** `state.json` records what has already been uploaded. The tool also checks
  whether Garmin already has an activity at the same time.

| Exit code | Meaning |
|---|---|
| 0 | ok |
| 1 | upload failed (retried on the next run) |
| 2 | configuration or intervals.icu key problem |
| 3 | run `scripts\login_garmin.py` again |
| 4 | Garmin rate-limited the requests (429); retried automatically |

### Optional settings (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `INTERVALS_SOURCE` | `MYWHOOSH` | Upload only activities whose source/device contains this text (`ALL` = everything) |
| `SYNC_MAX_AGE_DAYS` | `14` | Ignore older activities |
| `SYNC_LIMIT` | `20` | Maximum activities considered per run |
| `GARMIN_TOKENSTORE` | `~/.garminconnect-mywhoosh` | Garmin token folder |
| `LOG_LEVEL` | `INFO` | Log level |

The emulated device (Edge 840: manufacturer 1, product 4024, software 20.19) can be changed in
`services/fit_file_service.py`.

## Development

```powershell
venv\Scripts\python.exe -m pytest -q
```

Architecture and project rules are described in [AGENTS.md](AGENTS.md).

## Differences from the original

Compared with [marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin):

- **Source:** intervals.icu instead of the MyWhoosh API, because of the one-session-per-account limit.
  The MyWhoosh API client and the unused Zwift client were removed.
- **Garmin login:** `garminconnect` 0.3.x, token-only, with MFA support. The old `garth`-based
  flow no longer works.
- **Credentials:** no passwords in `.env`. The key is stored in the system keyring.
- **Sync:** uploads every new activity, not just the latest one. Uses `state.json`, pauses between
  uploads, and stops when Garmin responds with 429.
- **Windows:** scheduled task, notifications and log rotation.
- Kept from the original: the FIT rewrite to Garmin Edge 840 (`fit_file_service.py`) and the
  duplicate check on Garmin.

## License and credits

**GNU General Public License v3.0**, see [LICENSE](LICENSE).

- Original project: © Marcelo Rodrigo ([marcelorodrigo/mywhoosh-to-garmin](https://github.com/marcelorodrigo/mywhoosh-to-garmin)).
- Modifications: © 2026 [m-diniz](https://github.com/m-diniz), under the same license.
- Community API documentation: [mywhoosh-community/mywhoosh-api](https://github.com/mywhoosh-community/mywhoosh-api).
- Libraries: [python-garminconnect](https://github.com/cyberjunky/python-garminconnect), [fit-tool](https://pypi.org/project/fit-tool/), [keyring](https://pypi.org/project/keyring/).

Personal project, not affiliated with MyWhoosh, Garmin or intervals.icu. Use at your own risk.
