from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from admin_bot.access import resolve_admin
from shared.database import get_session

DENIED = "Kirish taqiqlangan."


class AdminAuthMiddleware(BaseMiddleware):
    """Every update in the admin bot goes through here: no admin row — no handler."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return None

        async with get_session() as session:
            admin = await resolve_admin(session, user)

        if admin is None:
            await self._deny(event, user.id)
            return None

        data["admin"] = admin
        return await handler(event, data)

    async def _deny(self, event: TelegramObject, user_id: int) -> None:
        if isinstance(event, CallbackQuery):
            await event.answer(DENIED, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(
                f"{DENIED}\n\nSizning Telegram ID: <code>{user_id}</code>\n"
                "Kirish uchun administratorga murojaat qiling.",
                parse_mode="HTML",
            )
