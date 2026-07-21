import importlib


def test_insecure_defaults_are_not_allowed_by_default_in_production(monkeypatch):
    safety = importlib.import_module("app.services.runtime_safety")
    monkeypatch.delenv("ALLOW_INSECURE_DEFAULTS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    assert safety.is_production() is True
    assert safety.insecure_defaults_allowed() is False


def test_insecure_defaults_remain_allowed_for_local_compatibility(monkeypatch):
    safety = importlib.import_module("app.services.runtime_safety")
    monkeypatch.delenv("ALLOW_INSECURE_DEFAULTS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    assert safety.is_production() is False
    assert safety.insecure_defaults_allowed() is True


def test_explicit_scheduler_setting_wins(monkeypatch):
    safety = importlib.import_module("app.services.runtime_safety")
    monkeypatch.setenv("SCHEDULER_ENABLED", "1")
    monkeypatch.setenv("WEB_CONCURRENCY", "4")

    enabled, reason = safety.scheduler_enabled_by_env()

    assert enabled is True
    assert "SCHEDULER_ENABLED=1" in reason


def test_scheduler_defaults_off_for_multi_instance_runtime(monkeypatch):
    safety = importlib.import_module("app.services.runtime_safety")
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    enabled, reason = safety.scheduler_enabled_by_env()

    assert enabled is False
    assert "multi-instance" in reason
