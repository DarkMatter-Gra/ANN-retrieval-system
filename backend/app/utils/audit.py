"""审计日志：先以 JSONL 形式落盘，等 audit_logs 表落地后再切到 DB。"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_AUDIT_FILE = Path(settings.report_path) / "audit.log.jsonl"
_AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)


def write_audit(
    operator_user_id: int,
    action: str,
    resource_type: str,
    resource_id: str,
    payload: dict | None = None,
    ip_address: str | None = None,
) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "operator_user_id": operator_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
        "payload": payload or {},
        "ip_address": ip_address,
    }
    with _AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
