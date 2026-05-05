import asyncio
import logging

from devteam.bot import dp, main_bot
from devteam.config import config


async def main() -> None:
    if not config.telegram_bot_token:
        raise RuntimeError("DEVTEAM_TELEGRAM_BOT_TOKEN не задан")
    if not config.anthropic_api_key:
        raise RuntimeError("DEVTEAM_ANTHROPIC_API_KEY не задан")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logging.getLogger(__name__).info("DevTeam bot запущен")
    await dp.start_polling(main_bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
