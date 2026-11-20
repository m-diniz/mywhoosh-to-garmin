"""Notificações do Windows (toast), sem dependências extras.

A tarefa roda a cada 15 min sem janela. Sem isto, um token vencido faria as
pedaladas pararem de subir em silêncio. Para não incomodar, cada problema é
avisado UMA vez: o aviso só se repete se o problema mudar, e é esquecido na
primeira execução que dá certo.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)

# AppId do Windows PowerShell: já registrado no Windows, dispensa instalar nada.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

# Título e texto vão por variável de ambiente, nunca colados no comando.
_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$env:TOAST_TITLE</text><text>$env:TOAST_BODY</text></binding></visual></toast>")
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TOAST_APPID).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
"""

# Falhas genéricas (rede, intervals.icu fora do ar) só viram aviso se persistirem.
GENERIC_FAILURES_BEFORE_ALERT = 4  # 4 x 15 min = 1 hora


def toast(title: str, body: str) -> bool:
    """Mostra a notificação. Nunca levanta exceção: avisar não pode derrubar a sincronização."""
    if sys.platform != "win32":
        return False
    env = dict(os.environ, TOAST_TITLE=escape(title), TOAST_BODY=escape(body), TOAST_APPID=APP_ID)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", _SCRIPT],
            env=env, capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.warning(f"Could not show the notification: {e}")
        return False


class Alerts:
    """Lembra qual problema já foi avisado (arquivo .alerts.json ao lado do projeto)."""

    def __init__(self, path: Path | str, notifier=toast):
        self.path = Path(path)
        self.notifier = notifier
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def problem(self, key: str, title: str, body: str, generic: bool = False) -> None:
        """Registra um problema; avisa se ainda não avisou este mesmo problema."""
        if generic:
            self.data["generic_failures"] = self.data.get("generic_failures", 0) + 1
            if self.data["generic_failures"] < GENERIC_FAILURES_BEFORE_ALERT:
                self._save()
                return
        if self.data.get("alerted") != key:
            self.notifier(title, body)
            self.data["alerted"] = key
        self._save()

    def ok(self) -> None:
        """Execução bem-sucedida: esquece problemas anteriores."""
        if self.data:
            self.data = {}
            self._save()
