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
O Garmin respondeu 429 (bloqueio temporário). Isso acontece por excesso de
tentativas e pode ser disparado pelo IP, não só por senha errada.
  - espere de 1 a 3 horas sem tentar de novo;
  - confira email e senha (login errado também conta como tentativa);
  - se puder, troque de IP (reinicie o roteador ou use o 4G do celular).
"""


def verificar(destino: Path):
    """Prova que o token salvo funciona. Devolve a api conectada, ou None."""
    try:
        api = Garmin()
        api.login(str(destino))
        nome = api.get_full_name()
    except Exception as exc:  # noqa: BLE001
        print(f"\nO token não funciona: {exc}")
        if "429" in str(exc):
            print(AVISO_429)
        return None
    if not nome:
        print("\nO token foi gravado, mas a API não devolveu o perfil.")
        return None
    print(f"\nToken válido. Conectado como: {nome}")
    return api


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    destino = garmin_tokenstore()
    print(f"Token do Garmin em: {destino}")

    if destino.exists():
        print("Já existe um token. Testando antes de pedir senha...")
        if verificar(destino) is not None:
            print("Nada a fazer: o login já está válido.")
            return 0
        print("Vamos refazer o login.\n")

    print("Login no Garmin Connect. Nada disto sai desta máquina além do próprio login.")
    email = input("Email: ").strip()
    senha = getpass("Senha (não aparece na tela): ")
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        api = Garmin(email=email, password=senha,
                     prompt_mfa=lambda: input("Código MFA: ").strip())
        api.login(str(destino))
    except Exception as exc:  # noqa: BLE001
        print(f"\nFalhou: {exc}")
        if "429" in str(exc):
            print(AVISO_429)
        return 1
    finally:
        del senha

    if verificar(destino) is None:
        print("\nNÃO prossiga até este login funcionar.")
        return 1
    print("A sincronização usa só este token; a senha não foi gravada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
