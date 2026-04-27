from __future__ import annotations

import json
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JsonStore(Generic[T]):
    def __init__(self, root: Path, collection: str, model: type[T]) -> None:
        self.path = root / f"{collection}.json"
        self.model = model
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def list(self, tenant_id: str | None = None) -> list[T]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        items = [self.model.model_validate(record) for record in records]
        if tenant_id is None:
            return items
        return [item for item in items if getattr(item, "tenant_id", None) == tenant_id]

    def get(self, item_id: str, tenant_id: str | None = None) -> T | None:
        for item in self.list(tenant_id):
            if getattr(item, "id", None) == item_id:
                return item
        return None

    def upsert(self, item: T) -> T:
        items = self.list()
        replaced = False
        next_items: list[T] = []
        for current in items:
            if getattr(current, "id", None) == getattr(item, "id", None):
                next_items.append(item)
                replaced = True
            else:
                next_items.append(current)
        if not replaced:
            next_items.append(item)
        self._write(next_items)
        return item

    def delete(self, item_id: str, tenant_id: str | None = None) -> bool:
        items = self.list()
        next_items = [
            item
            for item in items
            if not (
                getattr(item, "id", None) == item_id
                and (tenant_id is None or getattr(item, "tenant_id", None) == tenant_id)
            )
        ]
        if len(next_items) == len(items):
            return False
        self._write(next_items)
        return True

    def _write(self, items: list[T]) -> None:
        payload = [item.model_dump(mode="json") for item in items]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
