#!/usr/bin/env python3
r"""Login no Garmin Connect, uma única vez, neste terminal.

    venv\Scripts\python.exe scripts\login_garmin.py

Pede email, senha e código MFA de forma interativa e salva SÓ o token OAuth
(por padrão em ~/.garminconnect-mywhoosh, ou GARMIN_TOKENSTORE no .env). A
senha não é ecoada, não vai em argumento de linha de comando e não é gravada.

Mesmo padrão de login por token usado em outros projetos pessoais.
"""

from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv  # noqa: E402
from garminconnect import Garmin  # noqa: E402

from services.credentials import garmin_tokenstore  # noqa: E402

AVISO_429 = """
Garmin responded 429 (temporary block). It happens after too many attempts
and can be triggered by the IP address, not only by a wrong password.
  - wait 1 to 3 hours before trying again;
  - double-check email and password (failed logins also count as attempts);
  - if possible, change IP (restart the router or use your phone's mobile data).
"""


def verificar(destino: Path):
    """Prova que o token salvo funciona. Devolve a api conectada, ou None."""
    try:
        api = Garmin()
        api.login(str(destino))
        nome = api.get_full_name()
    except Exception as exc:  # noqa: BLE001
        print(f"\nThe token does not work: {exc}")
        if "429" in str(exc):
            print(AVISO_429)
        return None
    if not nome:
        print("\nThe token was saved, but the API did not return the profile.")
        return None
    print(f"\nToken valid. Connected as: {nome}")
    return api


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    destino = garmin_tokenstore()
    print(f"Garmin token in: {destino}")

    if destino.exists():
        print("A token already exists. Testing it before asking for the password...")
        if verificar(destino) is not None:
            print("Nothing to do: the login is already valid.")
            return 0
        print("Logging in again.\n")

    print("Garmin Connect login. Nothing here leaves this machine except the login itself.")
    email = input("Email: ").strip()
    senha = getpass("Password (hidden while typing): ")
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        api = Garmin(email=email, password=senha,
                     prompt_mfa=lambda: input("MFA code: ").strip())
        api.login(str(destino))
    except Exception as exc:  # noqa: BLE001
        print(f"\nFailed: {exc}")
        if "429" in str(exc):
            print(AVISO_429)
        return 1
    finally:
        del senha

    if verificar(destino) is None:
        print("\nDo NOT continue until this login works.")
        return 1
    print("The sync uses only this token; the password was not saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
