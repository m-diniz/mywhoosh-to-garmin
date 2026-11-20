"""Onde ficam os segredos.

- Senha do MyWhoosh: Windows Credential Manager (via `keyring`), cifrada pelo
  DPAPI e ligada ao usuário do Windows. Nunca no `.env`.
- Garmin: só o token OAuth, numa pasta própria. A senha e o MFA do Garmin são
  digitados uma vez em `scripts/login_garmin.py` e não são gravados.
"""

from __future__ import annotations

import os
from pathlib import Path

import keyring
import keyring.errors

KEYRING_SERVICE = "mywhoosh-to-garmin"

# Pasta própria: não colide com o token padrão de outros scripts (~/.garminconnect).
DEFAULT_GARMIN_TOKENSTORE = "~/.garminconnect-mywhoosh"


class CredentialsMissing(ValueError):
    """Falta configurar um segredo. A mensagem diz qual comando rodar."""


def garmin_tokenstore() -> Path:
    return Path(os.getenv("GARMIN_TOKENSTORE", DEFAULT_GARMIN_TOKENSTORE)).expanduser()


def get_mywhoosh_password(email: str) -> str:
    password = keyring.get_password(KEYRING_SERVICE, email)
    if not password:
        raise CredentialsMissing(
            f"Senha do MyWhoosh de '{email}' não está no Gerenciador de Credenciais. "
            "Rode `python main.py --setup` uma vez."
        )
    return password


def set_mywhoosh_password(email: str, password: str) -> None:
    keyring.set_password(KEYRING_SERVICE, email, password)


def _intervals_user(athlete_id: str) -> str:
    return f"intervals.icu:{athlete_id}"


def get_intervals_api_key(athlete_id: str) -> str:
    key = keyring.get_password(KEYRING_SERVICE, _intervals_user(athlete_id))
    if not key:
        raise CredentialsMissing(
            f"Chave de API do intervals.icu ({athlete_id}) não está no Gerenciador de "
            "Credenciais. Rode `python main.py --setup` uma vez."
        )
    return key


def set_intervals_api_key(athlete_id: str, api_key: str) -> None:
    keyring.set_password(KEYRING_SERVICE, _intervals_user(athlete_id), api_key)


def forget_mywhoosh_password(email: str) -> bool:
    """Apaga a senha do MyWhoosh, se tiver ficado guardada. True se apagou."""
    try:
        keyring.delete_password(KEYRING_SERVICE, email)
        return True
    except keyring.errors.PasswordDeleteError:
        return False
