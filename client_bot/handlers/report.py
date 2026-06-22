from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    PhotoSize,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from client_bot.tasks import queue_admin_notification
from shared.database import get_session
from shared.models import Report

router = Router()


class ReportState(StatesGroup):
    text = State()
    media = State()


_main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📩 Murojaat yuborish")]],
    resize_keyboard=True,
)

_skip_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="O'tkazib yuborish →", callback_data="skip_media")]]
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Xush kelibsiz.\n\nUshbu bot korrupsiya faktlari bo'yicha murojaatlarni qabul qiladi. "
        "Barcha ma'lumotlar maxfiy saqlanadi.",
        reply_markup=_main_kb,
    )


@router.message(F.text == "📩 Murojaat yuborish")
async def start_report(message: Message, state: FSMContext) -> None:
    await state.set_state(ReportState.text)
    await message.answer(
        "Korrupsiya faktini batafsil tasvirlab bering.\n\nBekor qilish uchun /cancel yozing.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Murojaat bekor qilindi.", reply_markup=_main_kb)


@router.message(ReportState.text)
async def receive_text(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Iltimos, matnli tavsif yuboring.")
        return
    await state.update_data(text=message.text)
    await state.set_state(ReportState.media)
    await message.answer(
        "Dalil sifatida foto, video yoki hujjat biriktiring (ixtiyoriy).",
        reply_markup=_skip_kb,
    )


@router.message(ReportState.media, F.photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photo: PhotoSize = message.photo[-1]
    await _save_report(message, state, data["text"], media_url=photo.file_id, media_type="photo")


@router.message(ReportState.media, F.video)
async def receive_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.video is None:
        return
    await _save_report(message, state, data["text"], media_url=message.video.file_id, media_type="video")


@router.message(ReportState.media, F.document)
async def receive_document(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if message.document is None:
        return
    await _save_report(message, state, data["text"], media_url=message.document.file_id, media_type="document")


@router.callback_query(F.data == "skip_media")
async def skip_media(callback: object, state: FSMContext) -> None:
    from aiogram.types import CallbackQuery
    cb: CallbackQuery = callback  # type: ignore[assignment]
    data = await state.get_data()
    if cb.message:
        await _save_report(cb.message, state, data["text"], media_url=None, media_type=None)
    await cb.answer()


async def _save_report(
    message: Message,
    state: FSMContext,
    text: str,
    media_url: str | None,
    media_type: str | None,
) -> None:
    async with get_session() as session:
        report = Report(
            user_id=message.chat.id,
            username=message.chat.username,
            text=text,
            media_url=media_url,
            media_type=media_type,
            status="new",
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        report_id = report.id

    queue_admin_notification(report_id)

    await state.clear()
    await message.answer(
        f"✅ Murojaat #{report_id} qabul qilindi.\n\nRahmat. Administratorlar uni tez orada ko'rib chiqishadi.",
        reply_markup=_main_kb,
    )
