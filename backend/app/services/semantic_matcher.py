from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SemanticMatchResult:
    matched: bool
    score: float
    reason: str
    intent: str | None = None


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Zа-яА-Я0-9_]+", text.lower()) if len(token) > 1}


def _jaccard_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = a.intersection(b)
    union = a.union(b)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def semantic_match_text(
    text: str,
    *,
    intents: list[dict] | None = None,
    examples: list[str] | None = None,
    threshold: float = 0.6,
) -> SemanticMatchResult:
    tokens = _tokenize(text)
    best_score = 0.0
    best_reason = "no semantic examples configured"
    best_intent: str | None = None

    if intents:
        for intent in intents:
            intent_name = str(intent.get("name", "unknown_intent"))
            intent_examples = intent.get("examples", [])
            if not isinstance(intent_examples, list):
                continue
            for example in intent_examples:
                if not isinstance(example, str):
                    continue
                score = _jaccard_score(tokens, _tokenize(example))
                if score > best_score:
                    best_score = score
                    best_reason = f"best_intent={intent_name}, best_example={example}"
                    best_intent = intent_name
    if examples:
        for example in examples:
            if not isinstance(example, str):
                continue
            score = _jaccard_score(tokens, _tokenize(example))
            if score > best_score:
                best_score = score
                best_reason = f"best_example={example}"
                best_intent = None

    matched = best_score >= threshold
    return SemanticMatchResult(
        matched=matched,
        score=best_score,
        reason=best_reason,
        intent=best_intent,
    )
