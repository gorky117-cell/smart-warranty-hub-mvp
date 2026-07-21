import os
from typing import Optional


def env_truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def current_environment() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or ""
    ).strip().lower()


def is_production() -> bool:
    return current_environment() in ("prod", "production")


def insecure_defaults_allowed() -> bool:
    explicit = os.getenv("ALLOW_INSECURE_DEFAULTS")
    if explicit is not None:
        return env_truthy(explicit)
    return not is_production()


def is_multi_instance_runtime() -> bool:
    if env_truthy(os.getenv("SWH_MULTI_INSTANCE")):
        return True
    for name in ("WEB_CONCURRENCY", "RAILWAY_REPLICA_COUNT", "RAILWAY_SERVICE_REPLICAS", "APP_INSTANCE_COUNT"):
        value = (os.getenv(name) or "").strip()
        if value.isdigit() and int(value) > 1:
            return True
    return False


def scheduler_enabled_by_env() -> tuple[bool, str]:
    explicit = os.getenv("SCHEDULER_ENABLED")
    if explicit is not None:
        enabled = env_truthy(explicit)
        return enabled, f"SCHEDULER_ENABLED={explicit}"
    if is_multi_instance_runtime():
        return False, "multi-instance runtime without explicit SCHEDULER_ENABLED=1"
    return True, "default enabled for local/demo/single-instance runtime"
