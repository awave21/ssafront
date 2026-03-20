"""Reference pydantic_evals dataset for agent analysis quality checks.

This module is intentionally not named `test_*.py` so it doesn't run in CI
as a mandatory unit test. Use it for manual/periodic quality evaluation.
"""

from __future__ import annotations

from pydantic import BaseModel

try:
    from pydantic_evals import Case, Dataset
    from pydantic_evals.evaluators import Contains, IsInstance
except Exception:  # pragma: no cover - optional dependency
    Dataset = None
    Case = None
    Contains = None
    IsInstance = None


class EvalRecommendation(BaseModel):
    category: str
    suggestion: str


def build_agent_analysis_eval_dataset():
    if Dataset is None:
        raise RuntimeError("pydantic_evals is not installed")

    return Dataset(
        cases=[
            Case(
                name="tool_description_fix_case",
                inputs={
                    "dialog_excerpt": "Agent used get_order('#123') and failed, manager used get_order('123').",
                },
                expected_output=EvalRecommendation(
                    category="tool_description_fix",
                    suggestion="Clarify order_id format: digits only.",
                ),
            ),
            Case(
                name="missing_tool_case",
                inputs={
                    "dialog_excerpt": "Users repeatedly ask to cancel subscription; manager does it manually.",
                },
                expected_output=EvalRecommendation(
                    category="tool_needed",
                    suggestion="Add cancel_subscription tool.",
                ),
            ),
        ],
        evaluators=[
            IsInstance(type_name="EvalRecommendation"),
            Contains(value="category"),
        ],
    )
