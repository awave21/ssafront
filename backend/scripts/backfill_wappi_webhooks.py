#!/usr/bin/env python3
"""
Массовая настройка webhook для подключенных WAPPI-каналов.

По умолчанию выбираются только авторизованные каналы с привязанным WAPPI profile_id:
  - type in ("whatsapp", "telegram_phone", "max")
  - is_deleted = false
  - phone_is_authorized = true

Для каждого канала:
  1) выставляется webhook url + auth (секрет),
  2) выставляются webhook types.

Примеры:
  PYTHONPATH=/app python /app/scripts/backfill_wappi_webhooks.py --dry-run
  PYTHONPATH=/app python /app/scripts/backfill_wappi_webhooks.py
  PYTHONPATH=/app python /app/scripts/backfill_wappi_webhooks.py --include-unauthorized --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.models.channel import Channel
from app.services.wappi import ChannelProfileBindingError, configure_channel_webhook

_WAPPI_PHONE_CHANNEL_TYPES = ("whatsapp", "telegram_phone", "max")


def _build_phone_channel_webhook_url(*, settings: Settings, channel_id: UUID) -> str:
    base_url = (settings.public_base_url or "").rstrip("/")
    if not base_url:
        raise RuntimeError("PUBLIC_BASE_URL is not configured")
    endpoint = f"{settings.api_prefix}/webhooks/channels/phone/{channel_id}"
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{base_url}{endpoint}"


def _parse_channel_ids(raw_values: list[str]) -> set[UUID]:
    parsed: set[UUID] = set()
    for raw_value in raw_values:
        value = (raw_value or "").strip()
        if not value:
            continue
        parsed.add(UUID(value))
    return parsed


async def _collect_target_channel_ids(
    *,
    session_factory: async_sessionmaker,
    include_unauthorized: bool,
    explicit_ids: set[UUID],
) -> list[UUID]:
    async with session_factory() as db:
        stmt = (
            select(Channel.id)
            .where(
                Channel.is_deleted.is_(False),
                Channel.type.in_(_WAPPI_PHONE_CHANNEL_TYPES),
                Channel.wappi_profile_id.is_not(None),
                Channel.wappi_profile_id != "",
            )
            .order_by(Channel.created_at.asc())
        )
        if not include_unauthorized:
            stmt = stmt.where(Channel.phone_is_authorized.is_(True))
        if explicit_ids:
            stmt = stmt.where(Channel.id.in_(explicit_ids))
        rows = await db.execute(stmt)
        return list(rows.scalars().all())


async def _process_channel(
    *,
    session_factory: async_sessionmaker,
    settings: Settings,
    channel_id: UUID,
    dry_run: bool,
    rotate_secret: bool,
) -> tuple[bool, str]:
    async with session_factory() as db:
        channel = await db.get(Channel, channel_id)
        if channel is None:
            return False, "Канал не найден"
        profile_id = (channel.wappi_profile_id or "").strip()
        if not profile_id:
            return False, "Нет привязанного profile_id"

        webhook_url = _build_phone_channel_webhook_url(settings=settings, channel_id=channel.id)
        if dry_run:
            secret_mode = "rotate" if rotate_secret else "reuse-or-generate"
            return True, (
                f"DRY-RUN channel_id={channel.id} type={channel.type} "
                f"profile_id={profile_id} webhook_url={webhook_url} secret_mode={secret_mode}"
            )

        try:
            await configure_channel_webhook(
                db=db,
                channel=channel,
                webhook_url=webhook_url,
                rotate_secret=rotate_secret,
            )
            await db.commit()
            return True, f"OK channel_id={channel.id} type={channel.type} profile_id={profile_id}"
        except ChannelProfileBindingError as exc:
            await db.rollback()
            return False, f"FAIL channel_id={channel.id} type={channel.type} profile_id={profile_id}: {exc}"
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            return False, f"FAIL channel_id={channel.id} type={channel.type} profile_id={profile_id}: {exc}"


async def main(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        explicit_ids = _parse_channel_ids(args.channel_id)
        channel_ids = await _collect_target_channel_ids(
            session_factory=session_factory,
            include_unauthorized=args.include_unauthorized,
            explicit_ids=explicit_ids,
        )
        if args.limit > 0:
            channel_ids = channel_ids[: args.limit]

        print(f"Найдено каналов для обработки: {len(channel_ids)}")
        if not channel_ids:
            return 0

        success_count = 0
        failed_count = 0
        rotate_secret = not args.reuse_secret
        for index, channel_id in enumerate(channel_ids, start=1):
            ok, message = await _process_channel(
                session_factory=session_factory,
                settings=settings,
                channel_id=channel_id,
                dry_run=args.dry_run,
                rotate_secret=rotate_secret,
            )
            prefix = f"[{index}/{len(channel_ids)}]"
            print(f"{prefix} {message}")
            if ok:
                success_count += 1
            else:
                failed_count += 1

        print(
            f"Итог: success={success_count}, failed={failed_count}, "
            f"dry_run={args.dry_run}, rotate_secret={rotate_secret}"
        )
        return 1 if failed_count > 0 else 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-unauthorized",
        action="store_true",
        help="Включить неавторизованные каналы (по умолчанию только авторизованные).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, что будет сделано, без внешних вызовов и без записи в БД.",
    )
    parser.add_argument(
        "--reuse-secret",
        action="store_true",
        help="Не ротировать секрет: использовать существующий (или сгенерировать, если пустой).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Ограничить количество каналов для обработки.",
    )
    parser.add_argument(
        "--channel-id",
        action="append",
        default=[],
        help="Обработать только указанные channel_id (можно передать флаг несколько раз).",
    )
    parsed_args = parser.parse_args()
    raise SystemExit(asyncio.run(main(parsed_args)))
