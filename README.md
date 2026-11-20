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

Requirements: Python 3.11+, a MyWhoosh account, an [intervals.icu](https://intervals.icu) account
(free; created in step 1) and a Garmin Connect account.

### Step 1: connect MyWhoosh to intervals.icu

This part happens on the MyWhoosh and intervals.icu websites; no code is involved.

1. **Create an intervals.icu account** at [intervals.icu](https://intervals.icu) → *Sign up*.
   Signing up with **email and password** is recommended over "Login with Strava/Garmin", so the
   account does not depend on another service.
2. **Do not connect Garmin in intervals.icu.** This tool uploads the ride to Garmin. If intervals.icu
   is also linked to Garmin, the same ride comes back to intervals.icu as a duplicate.
3. **Open MyWhoosh's *Connections* page** (your MyWhoosh account settings). It lists the supported
   services: Strava, TrainingPeaks, intervals.icu and others.
4. **Click *Connect* under the intervals.icu icon.** It is the red circle with a white heartbeat line.
   The icons have no labels.
5. **Sign in with the intervals.icu account from step 1 and authorize MyWhoosh.**
6. **Confirm it worked:** do a short test ride (a few minutes is enough) and check that it shows up
   in intervals.icu under *Activities*, usually within a few minutes.

> **Only new rides are sent.** MyWhoosh does not send your history when you connect. To include an
> older ride, export its FIT file and upload it to intervals.icu manually. The tool also picks up
> manual uploads, as long as the file came from MyWhoosh and the ride is less than 14 days old.

### Step 2: install the tool

```powershell
git clone https://github.com/m-diniz/mywhoosh-to-garmin.git
cd mywhoosh-to-garmin
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and fill in `INTERVALS_ATHLETE_ID`, found in intervals.icu → *Settings* →
*Developer Settings* (format `i123456`).

### Step 3: credentials (once)

1. **intervals.icu API key:** in *Settings* → *Developer Settings*, click *Generate* next to
   *API Key*. Then run the command below and paste the key when asked. It is hidden while you
   type and stored in Windows Credential Manager.
   `venv\Scripts\python.exe main.py --setup`
2. **Garmin login** (asks for email, password and the MFA code, if enabled):
   `venv\Scripts\python.exe scripts\login_garmin.py`

> Both commands need keyboard input. Run them in a regular PowerShell window, not in tools that
> don't provide an interactive terminal.

### Step 4: test

1. `venv\Scripts\python.exe main.py --list` shows what intervals.icu has, without uploading
   anything. Your test ride should appear with `filter = yes`.
2. `venv\Scripts\python.exe main.py` uploads new activities from the last 14 days. Check that the
   ride shows up in Garmin Connect.

If `--list` is empty, intervals.icu has not received any ride from MyWhoosh yet. Review Step 1, and
check that `INTERVALS_ATHLETE_ID` matches the account MyWhoosh is connected to. If you connected
through Strava or Google, you may have ended up in a different intervals.icu account.

### Step 5: automate

Every 15 min and at Windows logon:
`powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1`
To remove it: the same command with `-Remover`.

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
