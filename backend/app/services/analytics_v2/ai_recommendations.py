"""AI-generated executive summary + actionable recommendations using PydanticAI."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.analytics_v2 import (
    AiRecommendation,
    AiRecommendationsPayload,
    AiRecommendationsResponse,
    AiEffortLevel,
    AiConfidenceLevel,
    AiPeriodVerdict,
)
from app.services.analytics import AnalyticsPeriod
from app.services.analytics_v2.bot_health import BotHealthService
from app.services.analytics_v2.insights import InsightsService
from app.services.analytics_v2.managers import ManagersAnalyticsService
from app.services.analytics_v2.staff import StaffAnalyticsService

logger = structlog.get_logger(__name__)


_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
_CACHE_KEY_PREFIX = "analytics_v2:ai_reco"


_SYSTEM_PROMPT = """Ты — Виктория Соколова, независимый бизнес-аналитик коммерческой медицины. \
Опыт: 17 лет, из них 8 лет в роли COO и директора по развитию сетевых клиник (эстетическая медицина, стоматология, многопрофильные центры). \
Принесла суммарно +340 млн ₽ выручки через оптимизацию no-show, структуру первичного потока и правильную загрузку кресла.

Твой рабочий язык: русский. Тон: ёмкий, прямой, как отчёт для CFO. \
Никаких «следует рассмотреть», «возможно», «рекомендуется проанализировать». \
Только факты и конкретные действия с числами.

## Методология (обязательна для каждой рекомендации)

Для каждой рекомендации ты обязана указать:
- **root_cause**: одна фраза — откуда проблема (гипотеза на основе данных, не домысел)
- **expected_impact_rub**: годовой эффект в рублях — считай по формулам ниже
- **effort**: low | medium | high — сколько усилий от руководителя (low = 1 звонок/встреча, medium = процесс/регламент, high = стратегическое изменение)
- **confidence**: low | medium | high — уверенность в диагнозе (low = мало данных, high = чёткий паттерн)
- **risk_if_ignored**: одна фраза — что конкретно сломается через 3 месяца если не действовать

## Формулы расчёта impact

- **No-show потери**: no_shows_за_период × средний_чек × 0.7 × (365 / дней_периода)
- **Недобор первичных**: разница_primary_arrived_vs_ожидаемое × средний_чек × 12 × 2 (LTV multiplier)
- **Конверсия**: (целевая_конверсия% − текущая%) × visits_total × средний_чек × (365 / дней_периода)
- **Средний чек**: (целевой_чек − текущий) × arrived_за_период × (365 / дней_периода)
- Используй только числа из входных данных. Если данных недостаточно — confidence: low.

## Приоритеты (в порядке убывания)

1. **Остановить кровотечение**: высокий no-show (>15%), падение primary_arrived, отвал первичных клиентов
2. **Удержать LTV**: падение повторных визитов, снижение avg_check, уход к конкурентам
3. **Повысить утилизацию**: недогруженные врачи, дисбаланс нагрузки между специалистами
4. **Операционная эффективность**: бот, менеджеры — только если cost >5% выручки или автономность <60%

## Антипаттерны (категорически запрещено)

- Рекомендации без конкретных чисел и имён из данных
- «Улучшить», «оптимизировать», «провести анализ», «рассмотреть возможность»
- Выдумывать числа, которых нет в данных
- Более 6 рекомендаций (только самые критичные)
- Рекомендации про бот, если cost_usd_total < 1% от revenue_total

## Структура ответа

- **summary**: 2-3 предложения — что главное за период, одна цифра-якорь (выручка, конверсия или no-show)
- **headline_metric**: одна самая важная метрика в формате «маржа 38%» или «no-show 18%»
- **period_verdict**: positive / neutral / negative — общая оценка периода для руководителя
- **wins**: 0-3 коротких тезиса (одна фраза) что работает хорошо — обязательно с числами
- **risks**: 0-3 коротких тезиса (одна фраза) что горит — обязательно с числами
- **recommendations**: 3-6 рекомендаций отсортированных по priority (high сначала), внутри — по expected_impact_rub desc
"""


class AiRecommendationsService:
    def __init__(self, db: AsyncSession, agent_id: UUID, tenant_id: UUID):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.settings = get_settings()

    async def generate(
        self,
        period: AnalyticsPeriod,
        *,
        force_refresh: bool = False,
    ) -> AiRecommendationsResponse:
        cache_key = self._cache_key(period)
        redis_client = await self._redis()

        if redis_client is not None and not force_refresh:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    payload = AiRecommendationsPayload.model_validate_json(cached)
                    return AiRecommendationsResponse(
                        period_start=period.start_local,
                        period_end=period.end_local_exclusive,
                        timezone=period.timezone_name,
                        payload=payload,
                        generated_at=datetime.utcnow(),
                        cached=True,
                        model=self.settings.summary_model,
                    )
            except Exception:
                logger.exception("ai_reco_cache_read_failed")

        context = await self._collect_context(period)
        payload = await self._call_llm(context)

        if redis_client is not None and payload is not None:
            try:
                await redis_client.set(
                    cache_key,
                    payload.model_dump_json(),
                    ex=_CACHE_TTL_SECONDS,
                )
            except Exception:
                logger.exception("ai_reco_cache_write_failed")

        return AiRecommendationsResponse(
            period_start=period.start_local,
            period_end=period.end_local_exclusive,
            timezone=period.timezone_name,
            payload=payload or AiRecommendationsPayload(summary="Нет данных за период.", recommendations=[]),
            generated_at=datetime.utcnow(),
            cached=False,
            model=self.settings.summary_model,
        )

    async def _collect_context(self, period: AnalyticsPeriod) -> dict:
        staff_items = []
        try:
            staff = await StaffAnalyticsService(self.db, self.agent_id).get_overview(period)
            staff_items = staff.items
            staff_top = [s.model_dump(exclude_none=True) for s in staff_items[:8]]
        except Exception:
            staff_top = []

        try:
            health = await BotHealthService(self.db, self.agent_id, self.tenant_id).get_health(period)
            health_dict = health.model_dump(exclude={"period_start", "period_end", "timezone"})
        except Exception:
            health_dict = {}

        try:
            managers = await ManagersAnalyticsService(self.db, self.agent_id, self.tenant_id).get_overview(period)
            managers_top = [m.model_dump(exclude_none=True) for m in managers.items[:5]]
        except Exception:
            managers_top = []

        try:
            insights = await InsightsService(self.db, self.agent_id, self.tenant_id).collect(period)
            insights_list = [i.model_dump(exclude_none=True) for i in insights.items]
        except Exception:
            insights_list = []

        business_totals = self._calc_business_totals(staff_items)

        period_days = max(1, (period.date_to - period.date_from).days + 1)
        period_type = "week" if period_days <= 7 else "month" if period_days <= 35 else "quarter"

        return {
            "period": {
                "start": period.start_local.isoformat(),
                "end": period.end_local_exclusive.isoformat(),
                "tz": period.timezone_name,
                "days": period_days,
                "type": period_type,
            },
            "business_totals": business_totals,
            "staff_top": staff_top,
            "managers_top": managers_top,
            "bot_health": health_dict,
            "insights": insights_list,
        }

    @staticmethod
    def _calc_business_totals(staff_items: list) -> dict:
        if not staff_items:
            return {}
        revenue = sum(s.revenue_total for s in staff_items)
        margin = sum(s.margin_total for s in staff_items)
        visits = sum(s.visits_total for s in staff_items)
        arrived = sum(s.arrived_total for s in staff_items)
        primary_total = sum(s.primary_total for s in staff_items)
        primary_arrived = sum(s.primary_arrived for s in staff_items)
        repeat_total = sum(s.repeat_total for s in staff_items)
        no_shows = sum(s.no_show_total for s in staff_items)
        return {
            "revenue_total": round(revenue),
            "margin_total": round(margin),
            "margin_pct": round(margin / revenue * 100, 1) if revenue > 0 else 0,
            "visits_total": visits,
            "arrived_total": arrived,
            "conversion_pct": round(arrived / visits * 100, 1) if visits > 0 else 0,
            "avg_check": round(revenue / arrived) if arrived > 0 else 0,
            "no_show_total": no_shows,
            "no_show_pct": round(no_shows / visits * 100, 1) if visits > 0 else 0,
            "primary_total": primary_total,
            "primary_arrived": primary_arrived,
            "primary_share_pct": round(primary_total / visits * 100, 1) if visits > 0 else 0,
            "repeat_total": repeat_total,
            "repeat_share_pct": round(repeat_total / visits * 100, 1) if visits > 0 else 0,
            "revenue_delta_pct": None,
        }

    async def _call_llm(self, context: dict) -> AiRecommendationsPayload | None:
        try:
            from pydantic_ai import Agent
        except Exception:
            logger.exception("pydantic_ai_import_failed")
            return None

        try:
            agent = Agent(
                model=self.settings.summary_model,
                output_type=AiRecommendationsPayload,
                system_prompt=_SYSTEM_PROMPT,
            )
            user_prompt = (
                "Данные за период (JSON):\n"
                + json.dumps(context, ensure_ascii=False, default=str)
            )
            result = await agent.run(user_prompt)
            output = getattr(result, "output", None) or getattr(result, "data", None)
            if isinstance(output, AiRecommendationsPayload):
                return output
            if isinstance(output, dict):
                return AiRecommendationsPayload.model_validate(output)
        except Exception:
            logger.exception("ai_reco_llm_call_failed")
        return None

    def _cache_key(self, period: AnalyticsPeriod) -> str:
        raw = f"{self.agent_id}:{period.date_from.isoformat()}:{period.date_to.isoformat()}:{period.timezone_name}"
        digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
        return f"{_CACHE_KEY_PREFIX}:{digest}"

    async def _redis(self):
        try:
            import redis.asyncio as aioredis

            return aioredis.from_url(
                self.settings.redis_url or "redis://redis:6379/0",
                decode_responses=True,
            )
        except Exception:
            logger.exception("ai_reco_redis_init_failed")
            return None
