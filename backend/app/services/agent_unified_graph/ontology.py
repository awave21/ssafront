"""Контракт типов для единого графа (онтология уровня продукта).

Значения используются в ``entity_type`` / ``relation_type`` и при будущем
LLM-извлечении (allowed_nodes / triplets).
"""

from __future__ import annotations

# Слой происхождения — для выборочного удаления / обхода.
ORIGIN_SQNS = "sqns"
ORIGIN_KNOWLEDGE = "knowledge"
ORIGIN_DIRECTORY = "directory"
ORIGIN_SCRIPT_BRIDGE = "script_bridge"

# Происхождение факта: gold — из таблиц / структуры; silver — из LLM.
PROVENANCE_GOLD = "gold"
PROVENANCE_SILVER = "silver"

# --- Узлы (entity_type) ---
ENTITY_SQNS_SERVICE = "SqnsService"
ENTITY_SQNS_SERVICE_CATEGORY = "SqnsServiceCategory"
ENTITY_SQNS_SPECIALIST = "SqnsSpecialist"  # ресурс (sqns_resources), выполняющий услуги
ENTITY_SQNS_EMPLOYEE = "SqnsEmployee"
ENTITY_KNOWLEDGE_FILE = "KnowledgeFile"
ENTITY_KNOWLEDGE_CHUNK = "KnowledgeChunk"
ENTITY_DIRECTORY = "Directory"
ENTITY_DIRECTORY_ITEM = "DirectoryItem"
ENTITY_SCRIPT_FLOW_STEP = "ScriptFlowStep"

# --- Рёбра (relation_type) ---
REL_SPECIALIST_PERFORMS_SERVICE = "SPECIALIST_PERFORMS_SERVICE"
REL_SERVICE_IN_CATEGORY = "SERVICE_IN_CATEGORY"
REL_KNOWLEDGE_FILE_CONTAINS_CHUNK = "KNOWLEDGE_FILE_CONTAINS_CHUNK"
REL_DIRECTORY_CONTAINS_ITEM = "DIRECTORY_CONTAINS_ITEM"
REL_DIRECTORY_ITEM_ABOUT_SERVICE = "DIRECTORY_ITEM_ABOUT_SERVICE"
REL_DIRECTORY_ITEM_ABOUT_SPECIALIST = "DIRECTORY_ITEM_ABOUT_SPECIALIST"
REL_SCRIPT_NODE_TARGETS_SERVICE = "SCRIPT_NODE_TARGETS_SERVICE"
REL_SCRIPT_NODE_TARGETS_SPECIALIST = "SCRIPT_NODE_TARGETS_SPECIALIST"

# Шаблоны для будущего LLM (как в LangChain allowed_relationships):
# (source_entity_type, relation_type, target_entity_type)
LLM_RELATIONSHIP_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (ENTITY_KNOWLEDGE_CHUNK, "MENTIONS", ENTITY_SQNS_SERVICE),
    (ENTITY_DIRECTORY_ITEM, "ABOUT", ENTITY_SQNS_SERVICE),
    (ENTITY_DIRECTORY_ITEM, "ABOUT", ENTITY_SQNS_SPECIALIST),
)
