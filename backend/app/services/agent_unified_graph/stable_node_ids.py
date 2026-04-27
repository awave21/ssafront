"""Стабильные graph_node_id для склейки слоёв (SQNS, БЗ, LLM)."""

from __future__ import annotations

from uuid import UUID


def sqns_service_node_id(service_row_id: UUID) -> str:
    return f"sqns:service:{service_row_id}"


def sqns_service_category_node_id(category_row_id: UUID) -> str:
    return f"sqns:service-category:{category_row_id}"


def sqns_specialist_resource_node_id(resource_row_id: UUID) -> str:
    return f"sqns:specialist:{resource_row_id}"


def sqns_employee_node_id(employee_row_id: UUID) -> str:
    return f"sqns:employee:{employee_row_id}"


def knowledge_file_node_id(file_id: UUID) -> str:
    return f"kb:file:{file_id}"


def knowledge_chunk_node_id(chunk_row_id: UUID) -> str:
    return f"kb:chunk:{chunk_row_id}"


def directory_node_id(directory_id: UUID) -> str:
    return f"dir:directory:{directory_id}"


def directory_item_node_id(item_id: UUID) -> str:
    return f"dir:item:{item_id}"


def script_flow_step_node_id(flow_id: UUID, vue_node_id: str) -> str:
    return f"script:flow:{flow_id}:node:{vue_node_id}"
