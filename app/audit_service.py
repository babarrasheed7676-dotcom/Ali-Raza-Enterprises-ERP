import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported audit JSON value: {type(value).__name__}")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def _check_length(field: str, value: str | None, maximum: int) -> None:
    if value is not None and len(value) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters.")


def write_audit_log(
    conn: Any,
    *,
    user: Mapping[str, Any],
    request: Any,
    action: str,
    table_name: str,
    record_id: int | str,
    document_no: str | None = None,
    old_values: Mapping[str, Any] | None = None,
    new_values: Mapping[str, Any] | None = None,
    reason: str | None = None,
    module: str = "PURCHASING",
) -> None:
    """Insert an audit row using the caller's existing transaction."""
    record_id_text = str(record_id)

    if not action or not action.strip():
        raise ValueError("Audit action is required.")

    _check_length("action", action, 50)
    _check_length("module", module, 100)
    _check_length("table_name", table_name, 150)
    _check_length("record_id", record_id_text, 100)
    _check_length("document_no", document_no, 100)

    client = getattr(request, "client", None)
    ip_address = getattr(client, "host", None)

    headers = getattr(request, "headers", {})
    device_info = headers.get("user-agent") if headers else None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO core.audit_log (
                company_id, user_id, action, module, table_name,
                record_id, document_no, old_values, new_values,
                reason, ip_address, device_info
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(user["company_id"]),
                int(user["id"]),
                action,
                module,
                table_name,
                record_id_text,
                document_no,
                Jsonb(dict(old_values), dumps=_json_dumps) if old_values is not None else None,
                Jsonb(dict(new_values), dumps=_json_dumps) if new_values is not None else None,
                reason,
                ip_address,
                device_info,
            ),
        )
