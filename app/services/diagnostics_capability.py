from __future__ import annotations

from typing import Dict, Optional

from .connection_registry import registry


_IOT_HINTS = (
    "iot",
    "smart",
    "wifi",
    "wi-fi",
    "bluetooth",
    "zigbee",
    "zwave",
    "connected",
    "cloud",
    "telematics",
    "obd",
    "matter",
    "thread",
)


def infer_capability(
    *,
    product_name: Optional[str],
    brand: Optional[str],
    model_code: Optional[str],
    alternatives: Optional[dict] = None,
) -> Dict[str, object]:
    text = " ".join(
        [
            (product_name or ""),
            (brand or ""),
            (model_code or ""),
        ]
    ).lower()
    alt = alternatives or {}

    connector_present = bool(registry.list("remote_diagnostics")) or bool(registry.list("telemetry"))
    explicit_iot = bool(alt.get("iot_enabled") or alt.get("supports_remote_diag"))
    keyword_iot = any(k in text for k in _IOT_HINTS)

    is_iot = bool(explicit_iot or keyword_iot)

    if is_iot and connector_present:
        return {
            "mode": "remote",
            "is_iot": True,
            "connector_ready": True,
            "reason": "Product appears IoT-capable and remote connector is available.",
            "recommended_action": "Request remote health check",
        }
    if is_iot and not connector_present:
        return {
            "mode": "guided",
            "is_iot": True,
            "connector_ready": False,
            "reason": "Product appears IoT-capable but remote connector is not configured yet.",
            "recommended_action": "Use guided diagnostics for now",
        }
    return {
        "mode": "guided",
        "is_iot": False,
        "connector_ready": connector_present,
        "reason": "Product appears non-IoT based on current product/model data.",
        "recommended_action": "Use guided diagnostics",
    }
