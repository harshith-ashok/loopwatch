from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).with_name("catalog.yaml")


@dataclass(frozen=True)
class CatalogAction:
    name: str
    risk: str
    mode: str
    targets: tuple[str, ...]
    rollback: str


@lru_cache
def load_catalog() -> dict[str, CatalogAction]:
    raw = yaml.safe_load(CATALOG_PATH.read_text())["actions"]
    return {
        name: CatalogAction(name, v["risk"], v["mode"], tuple(v["targets"]), v["rollback"])
        for name, v in raw.items()
    }


def action_names() -> list[str]:
    return list(load_catalog())
