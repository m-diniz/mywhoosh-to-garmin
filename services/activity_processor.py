"""Orquestra a sincronização: origem (intervals.icu) → ajuste do FIT → Garmin Connect."""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Protocol, List, Dict, Any

from services.fit_file_service import FitFileService
from services.garmin_service import GarminService, is_rate_limited
from services.sync_state import SyncState

# Pausa entre uploads: o Garmin bloqueia o IP por horas quando recebe rajadas
# (valor que já se mostrou seguro na prática).
PAUSE_BETWEEN_UPLOADS_S = 1.5


class ActivitySource(Protocol):
    """O que o processador precisa da origem (ver services/intervals_service.py)."""

    def authenticate(self) -> None: ...
    def get_activities(self, limit: int = 20) -> List[Dict[str, Any]]: ...
    def download_activity(self, activity: Dict[str, Any]) -> str: ...


class ActivityProcessor:
    def __init__(self, source_service: ActivitySource, fit_file_service: FitFileService,
                 garmin_service: GarminService):
        self.source_service = source_service
        self.fit_file_service = fit_file_service
        self.garmin_service = garmin_service
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def activity_key(activity: dict) -> Optional[str]:
        key = activity.get('id') or activity.get('_id') or activity.get('activityFileId')
        return str(key) if key else None

    @staticmethod
    def _date_str(activity: dict):
        return (activity.get('date') or activity.get('startTime')
                or activity.get('createdAt') or activity.get('timestamp'))

    def _parse_activity_date(self, date_str) -> Optional[datetime]:
        """Aceita timestamp Unix (s ou ms) ou ISO 8601; devolve None se não entender."""
        if not date_str:
            return None
        try:
            timestamp = float(date_str)
            if timestamp > 100_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp)
        except (ValueError, TypeError, OSError):
            pass
        try:
            parsed = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        except ValueError:
            self.logger.warning(f"Could not parse date: {date_str}")
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    def sync_new_activities(self, state: SyncState, limit: int = 20,
                            max_age_days: int = 14) -> dict:
        """Envia ao Garmin toda atividade recente que ainda não foi enviada.

        - Considera as `limit` atividades mais recentes, com até `max_age_days`
          dias (assim a primeira execução não sobe o histórico inteiro).
        - Pula o que já está em `state`. O que já estiver no Garmin (checagem de
          horário ou 409) é só registrado no estado, sem novo upload.
        - Envia da mais antiga para a mais nova, com pausa entre uploads.
        - Num 429 do Garmin, para e deixa o resto para a próxima execução.

        Returns:
            {'total', 'synced', 'skipped', 'errors', 'rate_limited', 'uploaded'}
            ('uploaded' = nomes das atividades enviadas nesta execução)
        """
        stats = {'total': 0, 'synced': 0, 'skipped': 0, 'errors': 0,
                 'rate_limited': False, 'uploaded': []}

        self.source_service.authenticate()
        activities = self.source_service.get_activities(limit=limit)[:limit]
        cutoff = datetime.now() - timedelta(days=max_age_days)

        pending = []
        for activity in activities:
            key = self.activity_key(activity)
            if key is None:
                self.logger.warning(f"Atividade sem id, ignorada: {activity}")
                continue
            if state.is_synced(key):
                continue
            when = self._parse_activity_date(self._date_str(activity))
            if when is not None and when < cutoff:
                continue
            pending.append((when or datetime.max, key, activity, when))

        if not pending:
            self.logger.info("Nada novo para enviar.")
            return stats

        pending.sort(key=lambda item: item[0])  # mais antiga primeiro
        self.logger.info(f"{len(pending)} atividade(s) nova(s) para enviar")
        self.garmin_service.authenticate()

        for index, (_, key, activity, when) in enumerate(pending):
            stats['total'] += 1
            name = activity.get('name', activity.get('title', 'Unknown Activity'))
            self.logger.info(f"--- {name} (ID {key}, {when}) ---")
            original_file_path = modified_file_path = None
            try:
                if when is not None and self.garmin_service.check_duplicate_activity(when, name):
                    self.logger.info("Já está no Garmin; registrado sem novo upload")
                    state.mark_synced(key, "duplicate")
                    stats['skipped'] += 1
                    continue

                if index > 0:
                    time.sleep(PAUSE_BETWEEN_UPLOADS_S)
                original_file_path = self.source_service.download_activity(activity)
                modified_file_path = self.fit_file_service.modify_device_info(original_file_path)
                response = self.garmin_service.upload_activity(modified_file_path)

                if isinstance(response, dict) and response.get('status') == 'skipped':
                    state.mark_synced(key, "409")
                    stats['skipped'] += 1
                else:
                    state.mark_synced(key, "uploaded")
                    stats['synced'] += 1
                    stats['uploaded'].append(name)
                    self.logger.info("✓ Enviada ao Garmin Connect")
            except Exception as e:
                if is_rate_limited(e):
                    self.logger.warning("Garmin respondeu 429; o restante fica para a próxima execução")
                    stats['rate_limited'] = True
                    break
                self.logger.exception(f"✗ Falha ao enviar {key}: {e}")
                stats['errors'] += 1
            finally:
                if original_file_path:
                    self.fit_file_service.cleanup_file(original_file_path)
                if modified_file_path:
                    self.fit_file_service.cleanup_file(modified_file_path)

        self.logger.info(
            f"Resumo: {stats['synced']} enviada(s), {stats['skipped']} já existente(s), "
            f"{stats['errors']} erro(s)" + (" — interrompido por 429" if stats['rate_limited'] else "")
        )
        return stats
