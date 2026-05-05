#!/usr/bin/env python3
"""
Evaluator for FACE CLINIC agent (autoresearch-style).

Fixed file — do not modify this during experiments.
The agent (optimizer) modifies system_prompt and script_flow compiled_text,
then calls:  python eval.py [--experiment-id <name>]

Outputs structured results to stdout + appends to results.tsv.

Scoring (0.0 – 1.0 per case, averaged = total_score):
  - format_score:    no lists, no banned phrases, within length
  - tool_score:      used expected tools, didn't skip required calls
  - content_score:   has next step, empathy where needed, no invented facts
  - booking_score:   moves toward booking (clarifies, doesn't block)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from test_cases import TEST_CASES

API_URL = "http://localhost:8000/api/v1/integrations/chat"
API_KEY = os.environ.get("OPTIMIZER_API_KEY", "EFzHRBGi1ZlJ8ZbsaGLfK3tdwnkCuld4sFvu9sLgGDI")
RESULTS_TSV = Path(__file__).parent / "results.tsv"

BANNED_PHRASES = [
    "у нас высокий сервис",
    "это очень популярная процедура",
    "давайте я вам всё расскажу",
    "сначала немного о нас",
    "к сожалению",
    "не дёшево, но",
    "понимаю, что дорого",
    "у них дешевле — значит хуже",
    "мы лучше конкурентов",
    "не экономьте на лице",
    "потом пожалеете",
    "там сделали неправильно",
    "у нас всегда есть места",
    "когда угодно",
]

LIST_PATTERNS = [
    r"^\s*[-•·]\s",           # bullet list
    r"^\s*\d+[.)]\s",         # numbered list
    r"\n\s*[-•·]\s",
    r"\n\s*\d+[.)]\s",
]


@dataclass
class CaseResult:
    case_id: str
    message: str
    response: str
    tools_used: list[str]
    latency_ms: int
    format_score: float
    tool_score: float
    content_score: float
    booking_score: float
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return (self.format_score + self.tool_score + self.content_score + self.booking_score) / 4


async def run_case(client: httpx.AsyncClient, case: dict, session_prefix: str) -> CaseResult:
    session_id = f"{session_prefix}-{case['id']}"
    t0 = time.monotonic()
    try:
        resp = await client.post(
            API_URL,
            headers={"x-api-key": API_KEY},
            json={"message": case["message"], "session_id": session_id},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        response: str = data.get("response", "") or ""
        raw_tools = data.get("tool_names", [])
    except Exception as exc:
        response = ""
        raw_tools = []
        errors = [f"HTTP error: {exc}"]
    else:
        errors = []

    latency_ms = int((time.monotonic() - t0) * 1000)

    if not isinstance(raw_tools, list):
        raw_tools = []
    tools_used = [
        (t["name"] if isinstance(t, dict) else t)
        for t in raw_tools
    ]

    format_score, format_errors = score_format(response, case)
    tool_score, tool_errors = score_tools(tools_used, case)
    content_score, content_errors = score_content(response, case)
    booking_score, booking_errors = score_booking(response, case)

    return CaseResult(
        case_id=case["id"],
        message=case["message"],
        response=response,
        tools_used=tools_used,
        latency_ms=latency_ms,
        format_score=format_score,
        tool_score=tool_score,
        content_score=content_score,
        booking_score=booking_score,
        errors=errors + format_errors + tool_errors + content_errors + booking_errors,
    )


def score_format(response: str, case: dict) -> tuple[float, list[str]]:
    errors: list[str] = []
    score = 1.0

    if not response:
        return 0.0, ["empty response"]

    # No lists
    if case.get("must_not_list"):
        for pat in LIST_PATTERNS:
            if re.search(pat, response, re.MULTILINE):
                errors.append("response contains list formatting")
                score -= 0.4
                break

    # Length limit
    max_len = case.get("max_length", 500)
    if len(response) > max_len:
        penalty = min(0.3, (len(response) - max_len) / max_len * 0.3)
        score -= penalty
        errors.append(f"response too long: {len(response)} > {max_len}")

    # Banned phrases
    resp_lower = response.lower()
    for phrase in BANNED_PHRASES:
        if phrase in resp_lower:
            score -= 0.2
            errors.append(f"banned phrase: '{phrase}'")

    return max(0.0, score), errors


def score_tools(tools_used: list[str], case: dict) -> tuple[float, list[str]]:
    errors: list[str] = []
    required = case.get("must_use_tools", [])
    if not required:
        return 1.0, []

    score = 1.0
    for tool in required:
        if tool not in tools_used:
            score -= 1.0 / len(required)
            errors.append(f"required tool not called: {tool}")

    return max(0.0, score), errors


def score_content(response: str, case: dict) -> tuple[float, list[str]]:
    errors: list[str] = []
    score = 1.0
    resp_lower = response.lower()

    if case.get("must_introduce") and not any(w in resp_lower for w in ["стилия", "администратор", "face clinic"]):
        score -= 0.3
        errors.append("no self-introduction")

    if case.get("must_show_empathy") and not any(
        w in resp_lower for w in ["понимаю", "понятно", "жаль", "волнение", "переживани"]
    ):
        score -= 0.25
        errors.append("no empathy signal")

    if case.get("must_not_bash_competition") and any(
        w in resp_lower for w in ["они хуже", "там плохо", "там неправильно", "у них плохое"]
    ):
        score -= 0.4
        errors.append("bashes competition")

    if case.get("must_not_apologize_for_price") and any(
        w in resp_lower for w in ["к сожалению дорого", "да, дорого", "понимаю, что дорого"]
    ):
        score -= 0.3
        errors.append("apologizes for price")

    if case.get("must_not_pressure") and any(
        w in resp_lower for w in ["обязательно", "не упустите", "последнее место", "срочно"]
    ):
        score -= 0.4
        errors.append("pressure tactics")

    if case.get("must_stay_in_scope") and not any(
        w in resp_lower for w in ["запись", "процедур", "услуг", "клиник", "косметолог"]
    ):
        score -= 0.3
        errors.append("did not redirect to scope")

    return max(0.0, score), errors


def score_booking(response: str, case: dict) -> tuple[float, list[str]]:
    errors: list[str] = []
    score = 1.0
    resp_lower = response.lower()

    if case.get("must_have_next_step") and not any(
        w in resp_lower for w in ["?", "запис", "подберём", "уточните", "расскажите", "когда"]
    ):
        score -= 0.4
        errors.append("no next step / question")

    if case.get("must_clarify_type") and not any(
        w in resp_lower for w in ["инъекционн", "безинъекционн", "аппаратн", "с уколами", "без уколов",
                                   "ультразвук", "комбинирован"]
    ):
        score -= 0.4
        errors.append("did not clarify service type")

    if case.get("must_ask_intent") and "?" not in response:
        score -= 0.3
        errors.append("no question asked to understand intent")

    if case.get("must_offer_slot_hold") and not any(
        w in resp_lower for w in ["забронир", "место", "слот", "запишем"]
    ):
        score -= 0.3
        errors.append("did not offer slot hold")

    if case.get("must_ask_what_service") and not any(
        w in resp_lower for w in ["услуг", "процедур", "что именно", "на что", "какой"]
    ):
        score -= 0.4
        errors.append("did not ask which service before booking")

    return max(0.0, score), errors


def print_results(results: list[CaseResult], experiment_id: str) -> float:
    total = sum(r.total for r in results) / len(results)
    print(f"\n{'='*60}")
    print(f"EXPERIMENT: {experiment_id}")
    print(f"{'='*60}")
    print(f"total_score:    {total:.4f}   (higher is better, max 1.0)")
    print(f"cases:          {len(results)}")
    print(f"avg_latency_ms: {sum(r.latency_ms for r in results) // len(results)}")
    print(f"")
    print(f"{'Case':<12} {'Format':>7} {'Tools':>7} {'Content':>8} {'Booking':>8} {'Total':>7}  Errors")
    print("-" * 80)
    for r in results:
        err_str = "; ".join(r.errors[:2]) if r.errors else "ok"
        print(
            f"{r.case_id:<12} {r.format_score:>7.2f} {r.tool_score:>7.2f} "
            f"{r.content_score:>8.2f} {r.booking_score:>8.2f} {r.total:>7.2f}  {err_str}"
        )
    print(f"{'='*60}")
    print(f"total_score: {total:.6f}")
    return total


def save_results(results: list[CaseResult], experiment_id: str, total: float, note: str = "") -> None:
    write_header = not RESULTS_TSV.exists()
    with RESULTS_TSV.open("a", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        if write_header:
            w.writerow(["experiment_id", "total_score", "n_cases", "note"])
        w.writerow([experiment_id, f"{total:.6f}", len(results), note])


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", default=f"exp_{int(time.time())}")
    parser.add_argument("--note", default="")
    parser.add_argument("--cases", nargs="*", help="run specific case IDs only")
    args = parser.parse_args()

    cases = TEST_CASES
    if args.cases:
        cases = [c for c in cases if c["id"] in args.cases]

    session_prefix = args.experiment_id

    print(f"Running {len(cases)} test cases...")
    results: list[CaseResult] = []

    async with httpx.AsyncClient() as client:
        for case in cases:
            print(f"  {case['id']}: {case['message'][:50]}...", end=" ", flush=True)
            result = await run_case(client, case, session_prefix)
            results.append(result)
            print(f"→ {result.total:.2f}")
            await asyncio.sleep(0.5)  # avoid debounce conflicts

    total = print_results(results, args.experiment_id)
    save_results(results, args.experiment_id, total, args.note)


if __name__ == "__main__":
    asyncio.run(main())
