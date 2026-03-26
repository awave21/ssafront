from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

logger = structlog.get_logger("app.services.runtime")


def _normalize_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}
    if hasattr(raw_args, "model_dump"):
        try:
            dumped = raw_args.model_dump(mode="json")
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    if hasattr(raw_args, "dict"):
        try:
            dumped = raw_args.dict()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    return {}


def _build_dedupe_key(tool_name: str, tool_call_id: str | None, args: dict[str, Any]) -> str:
    if tool_call_id:
        return f"id:{tool_call_id}"
    try:
        return f"payload:{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=True)}"
    except Exception:
        return f"payload:{tool_name}:{str(args)}"


def _tool_return_body_for_history(raw_result: Any) -> dict[str, Any] | None:
    """Full tool output as JSON-serializable dict for tool_call_logs fallback (e.g. MCP / toolset tools)."""
    if raw_result is None:
        return None
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, list):
        return {"items": raw_result}
    if isinstance(raw_result, (str, int, float, bool)):
        return {"value": raw_result}
    return {"value": str(raw_result)}


def _normalize_tool_return(raw_result: Any) -> dict[str, Any]:
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str):
        try:
            parsed = json.loads(raw_result)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}
    if hasattr(raw_result, "model_dump"):
        try:
            dumped = raw_result.model_dump(mode="json")
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    if hasattr(raw_result, "dict"):
        try:
            dumped = raw_result.dict()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            return {}
    return {}


def extract_tools_called(
    result: Any,
    new_messages: list[Any],
    trace_id: str,
) -> list[dict[str, Any]]:
    tools_called: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    call_index_by_id: dict[str, int] = {}
    try:
        for msg in new_messages:
            if hasattr(msg, "parts") and msg.parts:
                for part in msg.parts:
                    part_kind = getattr(part, "part_kind", None)
                    is_tool_call = (
                        part_kind == "tool-call"
                        or part_kind == "tool_call"
                        or isinstance(part, ToolCallPart)
                        or (hasattr(part, "tool_name") and part.tool_name is not None)
                    )

                    if is_tool_call:
                        tool_name = getattr(part, "tool_name", None) or getattr(part, "name", None)
                        tool_call_id = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                        args = _normalize_args(getattr(part, "args", None) or getattr(part, "arguments", None))

                        if tool_name:
                            dedupe_key = _build_dedupe_key(
                                str(tool_name),
                                str(tool_call_id) if tool_call_id else None,
                                args,
                            )
                            if dedupe_key in seen_keys:
                                continue
                            seen_keys.add(dedupe_key)
                            tools_called.append(
                                {
                                    "name": str(tool_name),
                                    "tool_call_id": str(tool_call_id) if tool_call_id else None,
                                    "args": args,
                                    "source": "new_messages",
                                }
                            )
                            if tool_call_id:
                                call_index_by_id[str(tool_call_id)] = len(tools_called) - 1
                            logger.debug(
                                "tool_call_found",
                                trace_id=trace_id,
                                tool_name=tool_name,
                                tool_call_id=tool_call_id,
                            )

        # Enrich calls with actual execution args from tool-return payload.
        # This is useful when defaults/static params are merged server-side.
        # IMPORTANT: we only create tool calls from current-run new_messages.
        # all_messages can be used only for enrichment of already discovered
        # current-run calls (typically by matching tool_call_id).
        all_sources: list[tuple[list[Any], bool]] = [(new_messages, True)]
        if hasattr(result, "all_messages"):
            try:
                all_msgs = result.all_messages()
                if isinstance(all_msgs, list):
                    all_sources.append((all_msgs, False))
            except Exception:
                pass

        for source, allow_name_fallback in all_sources:
            for msg in source:
                if not (hasattr(msg, "parts") and msg.parts):
                    continue
                for part in msg.parts:
                    part_kind = getattr(part, "part_kind", None)
                    if not (
                        part_kind in ("tool-return", "tool_return")
                        or isinstance(part, ToolReturnPart)
                    ):
                        continue

                    tool_call_id = getattr(part, "tool_call_id", None) or getattr(part, "id", None)
                    raw_return = getattr(part, "content", None) or getattr(part, "result", None)
                    payload = _normalize_tool_return(raw_return)
                    returned_args = _normalize_args(payload.get("args"))

                    target_index: int | None = None
                    if tool_call_id and str(tool_call_id) in call_index_by_id:
                        target_index = call_index_by_id[str(tool_call_id)]
                    elif allow_name_fallback:
                        returned_tool_name = payload.get("tool_name")
                        if isinstance(returned_tool_name, str):
                            for idx in range(len(tools_called) - 1, -1, -1):
                                if tools_called[idx].get("name") == returned_tool_name:
                                    target_index = idx
                                    break

                    if target_index is None:
                        continue

                    body = _tool_return_body_for_history(raw_return)
                    if body is not None:
                        tools_called[target_index]["result"] = body

                    if returned_args:
                        existing_args = tools_called[target_index].get("args")
                        if isinstance(existing_args, dict) and existing_args and existing_args != returned_args:
                            tools_called[target_index]["llm_args"] = existing_args
                        tools_called[target_index]["args"] = returned_args
                        tools_called[target_index]["execution_args"] = returned_args

                    reaction_messages_raw = payload.get("__post_tool_reaction_messages")
                    if isinstance(reaction_messages_raw, list):
                        reaction_messages = [str(item).strip() for item in reaction_messages_raw if str(item).strip()]
                        if reaction_messages:
                            tools_called[target_index]["post_tool_reaction_messages"] = reaction_messages
    except Exception as exc:
        logger.warning(
            "tools_called_extraction_error",
            trace_id=trace_id,
            error=str(exc),
        )

    return tools_called
