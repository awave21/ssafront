from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_neo4j_driver() -> Any | None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return None
    if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
        return None
    try:
        from neo4j import GraphDatabase

        return GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    except Exception:
        return None

