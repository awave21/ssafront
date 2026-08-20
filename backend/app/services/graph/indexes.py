"""Graph indexes initialization: Vector + Fulltext indexes for Neo4j."""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.services.runtime.neo4j_client import get_neo4j_driver

logger = structlog.get_logger(__name__)


async def ensure_graph_indexes() -> None:
    """Create vector and fulltext indexes for graph nodes if not exist.

    Called during app startup to ensure all indexes are ready before queries.
    Idempotent: safe to call multiple times.
    """
    settings = get_settings()
    if not settings.neo4j_enabled:
        return

    driver = get_neo4j_driver()
    if driver is None:
        logger.warning("ensure_graph_indexes_skipped_no_driver")
        return

    database = settings.neo4j_database or None

    def _create_indexes(tx) -> None:
        # Vector indexes (already created by sync functions, but ensure they exist)
        try:
            tx.run(
                """
                CREATE VECTOR INDEX flow_node_embedding IF NOT EXISTS
                FOR (n:FlowNode) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
            logger.info("vector_index_flow_node_embedding_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector_index_flow_node_embedding_failed", error=str(exc))

        try:
            tx.run(
                """
                CREATE VECTOR INDEX graph_node_embedding IF NOT EXISTS
                FOR (n:GraphNode) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
            logger.info("vector_index_graph_node_embedding_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector_index_graph_node_embedding_failed", error=str(exc))

        try:
            tx.run(
                """
                CREATE VECTOR INDEX service_embedding IF NOT EXISTS
                FOR (n:Service) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
            logger.info("vector_index_service_embedding_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector_index_service_embedding_failed", error=str(exc))

        try:
            tx.run(
                """
                CREATE VECTOR INDEX specialist_embedding IF NOT EXISTS
                FOR (n:Specialist) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
            logger.info("vector_index_specialist_embedding_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector_index_specialist_embedding_failed", error=str(exc))

        # Fulltext index for text search on all major node types
        try:
            tx.run(
                """
                CREATE FULLTEXT INDEX node_text IF NOT EXISTS
                FOR (n:FlowNode|GraphNode|Service|Specialist)
                ON EACH [n.title, n.name, n.content_text, n.description]
                """
            )
            logger.info("fulltext_index_node_text_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("fulltext_index_node_text_failed", error=str(exc))

        # Multi-label vector index via shared :Searchable label.
        # Один HNSW поверх всех 4 типов — retriever ходит сюда и ищет везде сразу.
        try:
            tx.run(
                """
                CREATE VECTOR INDEX node_searchable_embedding IF NOT EXISTS
                FOR (n:Searchable) ON (n.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
            logger.info("vector_index_node_searchable_embedding_created")
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector_index_node_searchable_embedding_failed", error=str(exc))

    try:
        with driver.session(database=database) as session:
            session.execute_write(_create_indexes)
        logger.info("graph_indexes_initialization_completed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_graph_indexes_failed", error=str(exc))
