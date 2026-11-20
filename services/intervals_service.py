"""Origem das atividades: intervals.icu (que recebe do MyWhoosh pela conexão oficial).

Por que não a API do MyWhoosh: ela aceita uma sessão por conta e recusa o
login ("already logged in from another device") enquanto o app estiver logado,
ou seja, brigaria com o app do tablet. O intervals.icu usa uma chave de API
fixa e revogável, sem sessão.

Expõe a mesma interface que MyWhooshService usa no ActivityProcessor:
authenticate(), get_activities(limit), download_activity(activity).
"""

from __future__ import annotations

import gzip
import logging
import os
import tempfile
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

API = "https://intervals.icu/api/v1"


class IntervalsService:
    def __init__(self, athlete_id: str, api_key: str, source: Optional[str] = "MYWHOOSH",
                 lookback_days: int = 30):
        """
        Args:
            athlete_id: ex. "i000000" (Settings → Developer Settings)
            api_key: chave de API do intervals.icu
            source: só atividades cuja origem contém este texto (None = todas)
            lookback_days: janela de busca na API
        """
        self.athlete_id = athlete_id
        self.source = source.upper() if source else None
        self.lookback_days = lookback_days
        self.session = requests.Session()
        # Autenticação Basic com usuário literal "API_KEY" (padrão do intervals.icu).
        self.session.auth = ("API_KEY", api_key)
        self.session.headers["User-Agent"] = "mywhoosh-to-garmin"
        self.logger = logging.getLogger(__name__)

    def _get(self, path: str, **params) -> requests.Response:
        response = self.session.get(f"{API}{path}", params=params or None, timeout=60)
        if response.status_code in (401, 403):
            raise PermissionError(
                "intervals.icu rejected the API key (401/403). "
                "Generate a new one in Settings → Developer Settings and run `main.py --setup`."
            )
        response.raise_for_status()
        return response

    def authenticate(self) -> None:
        """Valida a chave lendo o perfil do atleta."""
        data = self._get(f"/athlete/{self.athlete_id}").json()
        self.logger.info(f"intervals.icu: connected as {data.get('name') or self.athlete_id}")

    @staticmethod
    def activity_source(activity: Dict[str, Any]) -> str:
        return " ".join(str(activity.get(k) or "") for k in
                        ("source", "device_name", "external_id")).upper()

    def get_activities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Atividades recentes da origem configurada, mais novas primeiro.

        Cada item vem no formato que o ActivityProcessor espera
        ('id', 'name', 'date'), com o registro original em 'raw'.
        """
        newest = date.today() + timedelta(days=1)
        oldest = date.today() - timedelta(days=self.lookback_days)
        items = self._get(f"/athlete/{self.athlete_id}/activities",
                          oldest=oldest.isoformat(), newest=newest.isoformat()).json()
        result = []
        for a in items:
            if self.source and self.source not in self.activity_source(a):
                continue
            result.append({
                'id': a.get('id'),
                'name': a.get('name') or 'Ride',
                'date': a.get('start_date_local'),
                'raw': a,
            })
        result.sort(key=lambda x: x['date'] or '', reverse=True)
        self.logger.info(f"intervals.icu: {len(result)} activity(ies) "
                         f"{'from ' + self.source + ' ' if self.source else ''}"
                         f"in the last {self.lookback_days} days")
        return result[:limit]

    def download_activity(self, activity: Dict[str, Any]) -> str:
        """Baixa o arquivo ORIGINAL (o FIT que o MyWhoosh enviou), descompactado."""
        activity_id = activity['id']
        content = self._get(f"/activity/{activity_id}/file").content
        if content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        if len(content) < 12 or content[8:12] != b".FIT":
            raise RuntimeError(
                f"The original file of {activity_id} is not a FIT file "
                f"(header {content[:12].hex()})."
            )
        path = os.path.join(tempfile.gettempdir(),
                            f"intervals_{activity_id}_{int(time.time())}.fit")
        with open(path, "wb") as f:
            f.write(content)
        self.logger.info(f"Downloaded {len(content):,} bytes for {activity_id}")
        return path
