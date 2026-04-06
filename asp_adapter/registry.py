from typing import Any, Dict

_registry: Dict[str, Any] = {}


def register(rowid: str, entity: Any) -> None:
    _registry[rowid] = entity


def lookup(rowid: str) -> Any:
    return _registry.get(rowid)


def unregister(rowid: str) -> None:
    _registry.pop(rowid, None)


def clear() -> None:
    _registry.clear()
