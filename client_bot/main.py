import asyncio
import logging

from aiogram import Bot, Dispatcher

from client_bot.handlers.report import router
from shared.config import settings
from shared.database import init_db
from shared.storage import build_storage

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    init_db(settings.postgres_dsn)
    bot = Bot(token=settings.bot_token_client)
    dp = Dispatcher(storage=build_storage("fsm:client"))
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
