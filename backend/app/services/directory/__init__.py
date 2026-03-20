"""
Directory package — управление справочниками с pgvector-эмбеддингами.

Re-exports для обратной совместимости:
    from app.services.directory import search_directory_items
"""

from app.services.directory.service import (
    get_agent_directory_tools,
    search_directory_items,
    update_directory_embeddings,
)
from app.services.directory.importer import (
    import_file_data,
    parse_file_preview,
    suggest_column_mapping,
)

__all__ = [
    "get_agent_directory_tools",
    "import_file_data",
    "parse_file_preview",
    "search_directory_items",
    "suggest_column_mapping",
    "update_directory_embeddings",
]
