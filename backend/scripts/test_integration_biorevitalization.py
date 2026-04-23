"""Smoke-тест публичного интеграционного API на сценарии «Биоревитализация».

Прогоняет последовательность клиентских реплик в одной сессии и печатает,
что ответил агент и сколько занял каждый запрос. Цель — проверить, что
 шаблон потока (`SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION`) реально применяется
 в живом диалоге через `search_script_flows` / script flow retriever.

Использование:
    python -m backend.scripts.test_integration_biorevitalization \
        --base-url https://agentsapp.integration-ai.ru \
        --api-key mJG-n26MynD4Vh1gMA1AR5jS9ioUVI2YXCmNt_6srgQ

Можно задать через env: INTEGRATION_BASE_URL, INTEGRATION_API_KEY.
Зависимости: только httpx (уже в requirements.txt).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from uuid import uuid4

import httpx


DEFAULT_SCENARIO: list[str] = [
    "Здравствуйте! У вас есть биоревитализация?",
    "На инъекционную, расскажите подробнее",
    "А какая стоимость?",
    "Дорого, в соседней клинике дешевле",
    "Хорошо, давайте в четверг",
]


async def send(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    session_id: str,
    message: str,
) -> dict:
    url = f"{base_url.rstrip('/')}/api/v1/integrations/chat"
    started = time.perf_counter()
    resp = await client.post(
        url,
        headers={"x-api-key": api_key, "content-type": "application/json"},
        json={"message": message, "session_id": session_id},
        timeout=120.0,
    )
    elapsed = time.perf_counter() - started
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    return {"status": resp.status_code, "elapsed": elapsed, "body": data}


async def fetch_history(
    client: httpx.AsyncClient, base_url: str, api_key: str, session_id: str
) -> dict:
    url = f"{base_url.rstrip('/')}/api/v1/integrations/chat/history"
    resp = await client.get(
        url,
        headers={"x-api-key": api_key},
        params={"session_id": session_id, "limit": 200},
        timeout=30.0,
    )
    try:
        return {"status": resp.status_code, "body": resp.json()}
    except Exception:
        return {"status": resp.status_code, "body": resp.text}


def _print_turn(idx: int, user: str, result: dict) -> None:
    print("\n" + "=" * 80)
    print(f"TURN {idx} ({result['elapsed']:.2f}s, HTTP {result['status']})")
    print(f"USER : {user}")
    body = result.get("body") or {}
    if isinstance(body, dict):
        if "response" in body:
            print(f"AGENT: {body.get('response') or '<empty>'}")
            run_id = body.get("run_id")
            sid = body.get("session_id")
            if run_id:
                print(f"  run_id    : {run_id}")
            if sid:
                print(f"  session_id: {sid}")
        else:
            print(f"BODY : {body}")
    else:
        print(f"BODY : {body}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=os.environ.get(
            "INTEGRATION_BASE_URL", "https://agentsapp.integration-ai.ru"
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("INTEGRATION_API_KEY"),
    )
    parser.add_argument(
        "--session-id",
        default=f"biorev-test-{uuid4().hex[:8]}",
        help="Session id (одна и та же для всех реплик).",
    )
    parser.add_argument(
        "--message",
        action="append",
        help="Переопределить сценарий: можно передать несколько --message.",
    )
    parser.add_argument(
        "--show-history",
        action="store_true",
        help="После всех реплик запросить /chat/history и распечатать.",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: --api-key или env INTEGRATION_API_KEY обязателен", file=sys.stderr)
        return 2

    scenario = args.message or DEFAULT_SCENARIO
    print(f"Base URL  : {args.base_url}")
    print(f"Session   : {args.session_id}")
    print(f"Turns     : {len(scenario)}")

    async with httpx.AsyncClient() as client:
        for i, msg in enumerate(scenario, 1):
            try:
                result = await send(
                    client, args.base_url, args.api_key, args.session_id, msg
                )
            except httpx.HTTPError as exc:
                print(f"\nTURN {i} FAILED: {exc!r}")
                return 1
            _print_turn(i, msg, result)

        if args.show_history:
            print("\n" + "#" * 80)
            print("HISTORY")
            hist = await fetch_history(
                client, args.base_url, args.api_key, args.session_id
            )
            print(hist)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
