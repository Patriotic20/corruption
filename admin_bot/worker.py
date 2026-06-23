import asyncio
import logging
import os

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from shared.celery_app import celery_app
from shared.config import settings
from shared.database import get_session, init_db
from shared.models import Admin, Report

logger = logging.getLogger(__name__)


def _build_status_keyboard(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_to:{report_id}"),
            ],
        ]
    )


@celery_app.task(name="admin_bot.worker.notify_admins")
def notify_admins(report_id: int) -> None:
    asyncio.run(_send_notification(report_id))


async def _download_media(client_bot: Bot, file_id: str, fallback_name: str) -> BufferedInputFile | None:
    try:
        file = await client_bot.get_file(file_id)
        # preserve original filename with extension from Telegram file path
        filename = os.path.basename(file.file_path) if file.file_path else fallback_name
        downloaded = await client_bot.download_file(file.file_path)
        return BufferedInputFile(downloaded.read(), filename=filename)
    except Exception as e:
        logger.error("Failed to download media: %s", e)
        return None


async def _send_notification(report_id: int) -> None:
    init_db(settings.postgres_dsn)
    admin_bot = Bot(token=settings.bot_token_admin)
    client_bot = Bot(token=settings.bot_token_client)

    try:
        async with get_session() as session:
            report = await session.get(Report, report_id)
            admins = list(
                (
                    await session.execute(select(Admin).where(Admin.is_active == True))
                ).scalars()
            )

        if not report:
            logger.warning("Report #%s not found", report_id)
            return

        text = (
            f"📨 <b>Yangi murojaat #{report.id}</b>\n\n"
            f"📋 Holat: <b>{report.status}</b>\n\n"
            f"{report.text}"
        )
        keyboard = _build_status_keyboard(report.id)

        media_file: BufferedInputFile | None = None
        if report.media_url and report.media_type:
            ext = {"photo": "photo.jpg", "video": "video.mp4", "document": "document"}.get(report.media_type, "file")
            media_file = await _download_media(client_bot, report.media_url, ext)

        for admin in admins:
            try:
                if media_file and report.media_type == "photo":
                    await admin_bot.send_photo(
                        admin.telegram_id, photo=media_file,
                        caption=text, parse_mode="HTML", reply_markup=keyboard,
                    )
                elif media_file and report.media_type == "video":
                    await admin_bot.send_video(
                        admin.telegram_id, video=media_file,
                        caption=text, parse_mode="HTML", reply_markup=keyboard,
                    )
                elif media_file and report.media_type == "document":
                    await admin_bot.send_document(
                        admin.telegram_id, document=media_file,
                        caption=text, parse_mode="HTML", reply_markup=keyboard,
                    )
                else:
                    await admin_bot.send_message(
                        admin.telegram_id, text,
                        parse_mode="HTML", reply_markup=keyboard,
                    )
            except Exception as e:
                logger.error("Failed to notify admin %s: %s", admin.telegram_id, e)
    finally:
        await admin_bot.session.close()
        await client_bot.session.close()
