"""Шаблон системного промпта нового агента по умолчанию.

В режиме runtime_bridges_mode=manual оркестровочные инструкции должны быть
видны в system_prompt пользователю — они хранятся здесь как единственный источник
правды и подставляются при создании агента если промпт не задан.

Тексты блоков синхронизированы с:
- DIAGNOSE_PROMPT_BRIDGE,
- SCRIPT_FLOWS_PROMPT_BRIDGE,
- SQNS_PROMPT_BRIDGE.

При изменении поведения инструментов обновите и константы в diagnose_tool /
script_flow_tool / tool_texts И этот файл (или вынесите общую сборку в один helper).
"""

from __future__ import annotations

from app.services.runtime.diagnose_tool import DIAGNOSE_PROMPT_BRIDGE
from app.services.runtime.script_flow_tool import SCRIPT_FLOWS_PROMPT_BRIDGE
from app.services.sqns.tool_texts import SQNS_PROMPT_BRIDGE


__DEFAULT_INTRO = """Ты виртуальный ассистент организации. Отвечай профессионально, кратко и по делу.

Ниже — правила оркестровки инструментов: когда и в каком порядке их вызывать. Следуй им при каждом сообщении клиента."""

_SQNS_SCOPE_NOTE = (
    "Запись через SQNS (ниже): применяй этот блок только если в списке доступных "
    "инструментов есть имена с префиксом sqns_. Если таких инструментов нет — раздел можно игнорировать."
)

_SEPARATOR = "\n\n"


def build_default_agent_system_prompt(*, include_sqns: bool = True) -> str:
    """Полный стартовый системный промпт для нового агента (режим manual).

    Тексты блоков совпадают с тем, что раньше инжектировалось как «bridge» в режиме auto.
    """
    core = [
        _DEFAULT_INTRO,
        DIAGNOSE_PROMPT_BRIDGE,
        SCRIPT_FLOWS_PROMPT_BRIDGE,
    ]
    if include_sqns:
        core.append(_SQNS_SCOPE_NOTE)
        core.append(SQNS_PROMPT_BRIDGE)
    return _SEPARATOR.join(p.strip() for p in core if p and str(p).strip())
