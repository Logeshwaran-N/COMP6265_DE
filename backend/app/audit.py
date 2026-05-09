from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List
from .catalogue import utc_now_iso
from .config import settings

AUDIT_PATH = settings.audit_log_path


def write_audit(event: Dict[str, Any]) -> str:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    audit_id = str(uuid.uuid4())[:12]
    event = {"audit_id": audit_id, "timestamp": utc_now_iso(), **event}
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return audit_id


def read_audit(limit: int = 50) -> List[Dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    lines = AUDIT_PATH.read_text().splitlines()[-limit:]
    return [json.loads(line) for line in reversed(lines) if line.strip()]
