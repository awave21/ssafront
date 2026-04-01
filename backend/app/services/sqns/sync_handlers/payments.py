from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sqns_service import SqnsPayment
from app.services.sqns.client import SQNSClient
from app.services.sqns.sync_handlers.common import build_payment_external_id, parse_datetime, parse_decimal, parse_int
from app.services.sqns.sync_handlers.visit_commodity_lines import replace_payment_commodity_lines

logger = structlog.get_logger(__name__)


class SqnsPaymentsSyncHandler:
    def __init__(self, db: AsyncSession, client: SQNSClient, agent_id: UUID):
        self.db = db
        self.client = client
        self.agent_id = agent_id

    async def sync(
        self,
        *,
        date_from: str,
        date_to: str,
    ) -> dict[str, int]:
        synced_at = datetime.now(timezone.utc)
        payments = await self.client.list_all_payments(
            date_from,
            date_to,
            page_size=100,
        )
        payments_synced = 0

        for payment in payments:
            if not isinstance(payment, dict):
                continue
            external_id = build_payment_external_id(payment)

            stmt = insert(SqnsPayment).values(
                id=uuid4(),
                agent_id=self.agent_id,
                external_id=external_id,
                payment_date=parse_datetime(payment.get("date")),
                payment_method=str(payment.get("paymentMethod")).strip()
                if payment.get("paymentMethod") is not None
                else None,
                payment_type_id=str(payment.get("paymentTypeId")).strip()
                if payment.get("paymentTypeId") is not None
                else None,
                payment_type_handle=str(payment.get("paymentTypeHandle")).strip()
                if payment.get("paymentTypeHandle") is not None
                else None,
                payment_type_name=str(payment.get("paymentTypeName")).strip()
                if payment.get("paymentTypeName") is not None
                else None,
                organization_external_id=str(payment.get("organizationId")).strip()
                if payment.get("organizationId") is not None
                else None,
                client_external_id=str(payment.get("clientId")).strip()
                if payment.get("clientId") is not None
                else None,
                visit_external_id=str(payment.get("visitId")).strip()
                if payment.get("visitId") is not None
                else None,
                amount=parse_decimal(payment.get("amount")),
                comment=str(payment.get("comment")).strip() if payment.get("comment") is not None else None,
                raw_data=payment,
                synced_at=synced_at,
                created_at=synced_at,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_sqns_payments_agent_external",
                set_={
                    "payment_date": stmt.excluded.payment_date,
                    "payment_method": stmt.excluded.payment_method,
                    "payment_type_id": stmt.excluded.payment_type_id,
                    "payment_type_handle": stmt.excluded.payment_type_handle,
                    "payment_type_name": stmt.excluded.payment_type_name,
                    "organization_external_id": stmt.excluded.organization_external_id,
                    "client_external_id": stmt.excluded.client_external_id,
                    "visit_external_id": stmt.excluded.visit_external_id,
                    "amount": stmt.excluded.amount,
                    "comment": stmt.excluded.comment,
                    "raw_data": stmt.excluded.raw_data,
                    "synced_at": stmt.excluded.synced_at,
                    "updated_at": synced_at,
                },
            )
            await self.db.execute(stmt)
            visit_ext = parse_int(payment.get("visitId"))
            await replace_payment_commodity_lines(
                self.db,
                agent_id=self.agent_id,
                payment_external_id=external_id,
                visit_external_id=visit_ext,
                payment_raw=payment,
            )
            payments_synced += 1

        logger.info(
            "sqns_sync_payments_completed",
            agent_id=str(self.agent_id),
            payments_synced=payments_synced,
            date_from=date_from,
            date_to=date_to,
        )
        return {"payments_synced": payments_synced}
