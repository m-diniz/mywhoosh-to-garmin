#!/usr/bin/env python3
"""
MyWhoosh to Garmin Connect Activity Sync

Caminho: MyWhoosh → intervals.icu (conexão oficial do app) → esta ferramenta →
Garmin Connect. Baixa o FIT original do intervals.icu, ajusta o dispositivo para
Garmin Edge 840 e envia ao Garmin Connect, sem duplicar.

(A API do MyWhoosh foi abandonada: aceita uma sessão por conta e recusava o
login enquanto o app estivesse logado.)

Uso:
    python main.py --setup          # uma vez: guarda a chave do intervals.icu no Windows
    python scripts/login_garmin.py  # uma vez: login no Garmin (com MFA), salva só o token
    python main.py --list           # mostra o que o intervals.icu tem (nada é enviado)
    python main.py                  # sincroniza tudo que é novo (é o que a tarefa agendada roda)

Códigos de saída: 0 ok, 1 erro, 2 configuração faltando, 3 refazer login do Garmin,
4 Garmin limitou requisições (429).
Problemas viram notificação do Windows (uma vez por problema; ver services/notify.py).
"""

import os
import sys
import logging
import warnings
import argparse
from datetime import datetime
from getpass import getpass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# Suppress urllib3 LibreSSL warning on macOS
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

from services.intervals_service import IntervalsService
from services.fit_file_service import FitFileService
from services.garmin_service import GarminService, GarminTokenInvalid, is_rate_limited
from services.activity_processor import ActivityProcessor
from services.sync_state import SyncState
from services import credentials
from services.notify import Alerts, toast

# O Agendador de Tarefas não roda na pasta do projeto: tudo relativo a este arquivo.
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / 'sync.log'
STATE_FILE = BASE_DIR / 'state.json'
ALERTS_FILE = BASE_DIR / '.alerts.json'


def list_activities(source_service: IntervalsService) -> int:
    """Diagnóstico: o que o intervals.icu devolve, com a origem de cada atividade."""
    source_service.authenticate()
    filtro = source_service.source
    source_service.source = None
    items = source_service.get_activities(limit=50)
    state = SyncState(STATE_FILE)
    print(f"\n{'data':19}  {'id':12}  {'origem':40}  {'filtro':6}  {'enviada':7}  nome")
    for item in items:
        raw = item['raw']
        origem = IntervalsService.activity_source(raw).strip() or '-'
        passa = 'sim' if not filtro or filtro in origem else 'não'
        enviada = 'sim' if state.is_synced(str(item['id'])) else '-'
        print(f"{str(item['date'])[:19]:19}  {str(item['id'])[:12]:12}  {origem[:40]:40}  "
              f"{passa:6}  {enviada:7}  {item['name']}")
    print(f"\nFiltro de origem: {filtro or 'nenhum (ALL)'}  (INTERVALS_SOURCE no .env)")
    return 0


def setup_logging(log_level: str = 'INFO') -> None:
    """Console + sync.log com rotação (1 MB x 3)."""
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if sys.stdout is not None:  # pythonw (tarefa agendada) não tem console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3,
                                       encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def intervals_source() -> str | None:
    """Filtro de origem no intervals.icu ('ALL' = sem filtro)."""
    value = os.getenv('INTERVALS_SOURCE', 'MYWHOOSH').strip()
    return None if value.upper() in ('', 'ALL') else value


def load_config() -> dict:
    """Lê o .env (só dados não secretos) e a chave do intervals.icu do keyring."""
    load_dotenv(BASE_DIR / '.env')
    athlete_id = os.getenv('INTERVALS_ATHLETE_ID')
    if not athlete_id:
        raise credentials.CredentialsMissing(
            "INTERVALS_ATHLETE_ID não está no .env (ex.: i000000)."
        )
    return {
        'intervals_athlete_id': athlete_id,
        'intervals_api_key': credentials.get_intervals_api_key(athlete_id),
        'intervals_source': intervals_source(),
        'garmin_tokenstore': credentials.garmin_tokenstore(),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'limit': int(os.getenv('SYNC_LIMIT', '20')),
        'max_age_days': int(os.getenv('SYNC_MAX_AGE_DAYS', '14')),
    }


def run_setup() -> int:
    """Guarda a chave de API do intervals.icu no Windows Credential Manager e testa."""
    load_dotenv(BASE_DIR / '.env')
    athlete_id = os.getenv('INTERVALS_ATHLETE_ID') or input("Athlete ID do intervals.icu: ").strip()
    api_key = getpass("Chave de API do intervals.icu (não aparece na tela): ").strip()
    try:
        IntervalsService(athlete_id, api_key).authenticate()
    except Exception as e:
        print(f"\nintervals.icu recusou: {e}\nNada foi gravado.", file=sys.stderr)
        return 1
    credentials.set_intervals_api_key(athlete_id, api_key)
    del api_key
    print(f"\nChave ok. Guardada no Gerenciador de Credenciais do Windows "
          f"(serviço '{credentials.KEYRING_SERVICE}').")
    email = os.getenv('MYWHOOSH_EMAIL')
    if email and credentials.forget_mywhoosh_password(email):
        print("A senha antiga do MyWhoosh foi apagada do Gerenciador de Credenciais.")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(
        description='Sync MyWhoosh rides (via intervals.icu) to Garmin Connect'
    )
    parser.add_argument('--setup', action='store_true',
                        help='Guardar a chave de API do intervals.icu no Windows Credential Manager')
    parser.add_argument('--list', action='store_true',
                        help='Listar as atividades do intervals.icu e a origem de cada uma (não envia nada)')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='Quantas atividades recentes considerar (padrão 20)')
    parser.add_argument('--max-age-days', type=int, metavar='D',
                        help='Ignorar atividades mais antigas que D dias (padrão 14)')
    args = parser.parse_args()

    if args.setup:
        return run_setup()

    alerts = Alerts(ALERTS_FILE)
    try:
        config = load_config()
    except (credentials.CredentialsMissing, ValueError) as e:
        print(f"\n❌ Configuração: {e}\n", file=sys.stderr)
        if not args.list:
            alerts.problem("config", "MyWhoosh → Garmin parado",
                           "Falta configuração (chave do intervals.icu?). Rode main.py --setup.")
        return 2

    setup_logging(config['log_level'])
    logger = logging.getLogger(__name__)
    logger.info(f"=== MyWhoosh → Garmin, {datetime.now():%Y-%m-%d %H:%M:%S} ===")

    max_age_days = args.max_age_days or config['max_age_days']
    source_service = IntervalsService(
        config['intervals_athlete_id'], config['intervals_api_key'],
        source=config['intervals_source'], lookback_days=max(max_age_days, 1) + 1,
    )
    processor = ActivityProcessor(
        source_service,
        FitFileService(),
        GarminService(config['garmin_tokenstore']),
    )

    try:
        if args.list:
            return list_activities(source_service)

        stats = processor.sync_new_activities(
            SyncState(STATE_FILE),
            limit=args.limit or config['limit'],
            max_age_days=max_age_days,
        )
        if stats['uploaded']:
            names = ", ".join(stats['uploaded'])
            toast("Pedalada enviada ao Garmin Connect", names)
        if stats['rate_limited']:
            alerts.problem("rate_limit", "MyWhoosh → Garmin com atraso",
                           "O Garmin limitou as requisições há mais de 1 hora. Tento de novo sozinho.",
                           generic=True)
            return 4
        if stats['errors']:
            alerts.problem("upload_errors", "MyWhoosh → Garmin com falhas",
                           "Algumas pedaladas não subiram há mais de 1 hora. Veja sync.log.",
                           generic=True)
            return 1
        alerts.ok()
        return 0

    except GarminTokenInvalid as e:
        logger.error(str(e))
        alerts.problem("garmin_token", "Refaça o login do Garmin",
                       "As pedaladas pararam de subir: o token do Garmin expirou. "
                       "Rode scripts\\login_garmin.py.")
        return 3
    except PermissionError as e:
        logger.error(str(e))
        alerts.problem("intervals_key", "Chave do intervals.icu recusada",
                       "As pedaladas pararam de subir. Gere outra chave e rode main.py --setup.")
        return 2
    except KeyboardInterrupt:
        print("\n\n⚠ Interrompido\n", file=sys.stderr)
        return 130
    except Exception as e:
        if is_rate_limited(e):
            logger.error("Garmin limitou as requisições (429). Tente de novo em algumas horas.")
            alerts.problem("rate_limit", "MyWhoosh → Garmin com atraso",
                           "O Garmin limitou as requisições há mais de 1 hora. Tento de novo sozinho.",
                           generic=True)
            return 4
        logger.exception(f"Erro inesperado: {e}")
        alerts.problem("unexpected", "MyWhoosh → Garmin com falhas",
                       f"Erro há mais de 1 hora: {str(e)[:120]}. Veja sync.log.", generic=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
