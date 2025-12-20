import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Connector:
    name: str
    kind: str  # e.g., "ocr", "nlp", "llm", "telemetry", "storage"
    endpoint: str
    auth_token: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConnectionRegistry:
    """
    Registry that holds real external service connections (OCR, LLM, etc).
    Backed by a JSON file for persistence; can be swapped for DB/secret store.
    """

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._connectors: Dict[str, Connector] = {}
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            return
        with self.config_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        loaded: Dict[str, Connector] = {}
        for item in raw:
            auth = item.get("auth_token") or os.getenv(
                item.get("auth_env") or "", None
            )
            loaded[item["name"]] = Connector(
                name=item["name"],
                kind=item["kind"],
                endpoint=item["endpoint"],
                auth_token=auth,
                metadata=item.get("metadata", {}),
            )
        self._connectors = loaded

    def save(self) -> None:
        payload = []
        for c in self._connectors.values():
            entry = asdict(c)
            payload.append(entry)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def register(self, connector: Connector) -> None:
        self._connectors[connector.name] = connector
        self.save()

    def get(self, name: str) -> Optional[Connector]:
        return self._connectors.get(name)

    def list(self, kind: Optional[str] = None) -> Dict[str, Connector]:
        if kind is None:
            return dict(self._connectors)
        return {k: v for k, v in self._connectors.items() if v.kind == kind}


default_config_path = Path(__file__).resolve().parents[2] / "data" / "connectors.json"
registry = ConnectionRegistry(default_config_path)
