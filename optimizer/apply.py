#!/usr/bin/env python3
"""
Applies a proposed system_prompt or script_flow change to the database.
Used by the optimizer after eval approves an experiment.

Usage:
  python apply.py --what prompt --file new_prompt.txt
  python apply.py --what flow --flow-id <uuid> --file new_flow.md
  python apply.py --what prompt --restore   # rolls back to backup
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

DB_HOST = "172.18.0.5"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASS = "W7f2Qm9rL4s8Tz1N6v3Kp5Hx0Cd7Bj2A"
DB_NAME = "agents"
AGENT_ID = "176548eb-cce1-4ca8-8775-1f24d45a1b6d"

BACKUPS_DIR = Path(__file__).parent / "backups"
BACKUPS_DIR.mkdir(exist_ok=True)


async def get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME,
    )


async def backup_prompt(conn: asyncpg.Connection) -> Path:
    prompt = await conn.fetchval("SELECT system_prompt FROM agents WHERE id = $1", AGENT_ID)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = BACKUPS_DIR / f"prompt_{ts}.txt"
    path.write_text(prompt or "", encoding="utf-8")
    print(f"Backed up current prompt → {path}")
    return path


async def apply_prompt(new_text: str) -> None:
    conn = await get_conn()
    await backup_prompt(conn)
    await conn.execute(
        "UPDATE agents SET system_prompt = $1, updated_at = NOW() WHERE id = $2",
        new_text, AGENT_ID,
    )
    print(f"Applied new system_prompt ({len(new_text)} chars)")
    await conn.close()


async def restore_prompt(backup_path: Path) -> None:
    text = backup_path.read_text(encoding="utf-8")
    conn = await get_conn()
    await conn.execute(
        "UPDATE agents SET system_prompt = $1, updated_at = NOW() WHERE id = $2",
        text, AGENT_ID,
    )
    print(f"Restored prompt from {backup_path}")
    await conn.close()


async def apply_flow(flow_id: str, new_compiled: str) -> None:
    conn = await get_conn()
    # backup
    old = await conn.fetchval("SELECT compiled_text FROM script_flows WHERE id = $1", flow_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = BACKUPS_DIR / f"flow_{flow_id[:8]}_{ts}.md"
    path.write_text(old or "", encoding="utf-8")
    print(f"Backed up flow → {path}")

    await conn.execute(
        "UPDATE script_flows SET compiled_text = $1, updated_at = NOW() WHERE id = $2",
        new_compiled, flow_id,
    )
    print(f"Applied new compiled_text for flow {flow_id[:8]}... ({len(new_compiled)} chars)")
    await conn.close()


async def show_current() -> None:
    conn = await get_conn()
    prompt = await conn.fetchval("SELECT system_prompt FROM agents WHERE id = $1", AGENT_ID)
    flows = await conn.fetch(
        "SELECT id, name, flow_status FROM script_flows WHERE agent_id = $1", AGENT_ID
    )
    print(f"Current prompt: {len(prompt or '')} chars")
    print("Script flows:")
    for f in flows:
        ct = await conn.fetchval("SELECT compiled_text FROM script_flows WHERE id = $1", f['id'])
        print(f"  {f['id']}  {f['name']}  [{f['flow_status']}]  compiled={len(ct or '')} chars")
    await conn.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--what", choices=["prompt", "flow", "status"], default="status")
    parser.add_argument("--file", help="path to new content")
    parser.add_argument("--flow-id", help="UUID of script_flow to update")
    parser.add_argument("--restore", help="path to backup file to restore")
    args = parser.parse_args()

    if args.what == "status":
        await show_current()
    elif args.what == "prompt":
        if args.restore:
            await restore_prompt(Path(args.restore))
        else:
            assert args.file, "--file required"
            text = Path(args.file).read_text(encoding="utf-8")
            await apply_prompt(text)
    elif args.what == "flow":
        assert args.flow_id and args.file, "--flow-id and --file required"
        text = Path(args.file).read_text(encoding="utf-8")
        await apply_flow(args.flow_id, text)


if __name__ == "__main__":
    asyncio.run(main())
