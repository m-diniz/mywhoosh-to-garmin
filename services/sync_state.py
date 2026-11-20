"""IDs de atividades do MyWhoosh que já estão no Garmin.

Um ID só entra aqui depois que o Garmin confirmou (upload aceito, 409 de
duplicata, ou duplicata achada pela checagem de horário). Se a execução cair
no meio, a próxima passada tenta de novo só o que faltou.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


class SyncState:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._synced: dict[str, str] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._synced = dict(data.get("synced", {}))

    def is_synced(self, activity_id: str) -> bool:
        return str(activity_id) in self._synced

    def mark_synced(self, activity_id: str, how: str) -> None:
        """Grava na hora (escrita atômica): uma queda depois não perde o registro."""
        self._synced[str(activity_id)] = f"{datetime.now().isoformat(timespec='seconds')} {how}"
        self._save()

    def __len__(self) -> int:
        return len(self._synced)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"synced": self._synced}, f, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
