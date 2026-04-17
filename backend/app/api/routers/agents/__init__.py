from app.api.routers.agents.base import router as base_router
from app.api.routers.agents.analysis import router as analysis_router
from app.api.routers.agents.analytics import router as analytics_router
from app.api.routers.agents.channels import router as channels_router
from app.api.routers.agents.directories import router as directories_router
from app.api.routers.agents.direct_questions import router as direct_questions_router
from app.api.routers.agents.sqns import _build_sqns_client, router as sqns_router
from app.api.routers.agents.dialogs import router as dialogs_router
from app.api.routers.agents.messages import router as messages_router
from app.api.routers.agents.prompt_history import router as prompt_history_router
from app.api.routers.agents.prompt_training import router as prompt_training_router
from app.api.routers.agents.function_rules import router as function_rules_router
from app.api.routers.agents.script_flows import router as script_flows_router
from app.api.routers.agents.user_states import router as user_states_router
from app.api.routers.agents.knowledge_files import router as knowledge_files_router

router = base_router
router.include_router(channels_router)
router.include_router(directories_router, prefix="/{agent_id}/directories", tags=["directories"])
router.include_router(
    direct_questions_router,
    prefix="/{agent_id}/knowledge/direct-questions",
    tags=["direct-questions"],
)
router.include_router(
    knowledge_files_router,
    prefix="/{agent_id}/knowledge/files",
    tags=["knowledge-files"],
)
router.include_router(sqns_router)
router.include_router(dialogs_router, prefix="/{agent_id}/dialogs", tags=["dialogs"])
router.include_router(messages_router, prefix="/{agent_id}/dialogs", tags=["messages"])
router.include_router(prompt_history_router, prefix="/{agent_id}", tags=["prompt-history"])
router.include_router(prompt_training_router, prefix="/{agent_id}", tags=["prompt-training"])
router.include_router(function_rules_router, prefix="/{agent_id}", tags=["function-rules"])
router.include_router(script_flows_router, prefix="/{agent_id}", tags=["script-flows"])
router.include_router(user_states_router, prefix="/{agent_id}", tags=["user-states"])
router.include_router(analysis_router, prefix="/{agent_id}", tags=["analysis"])
router.include_router(analytics_router, prefix="/{agent_id}", tags=["analytics"])

__all__ = ["router", "_build_sqns_client"]
