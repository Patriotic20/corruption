from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from shared.config import settings
from shared.database import get_session
from shared.models import Admin, Reply, Report

router = Router()

STATUS_UZ = {
    "new": "🆕 Yangi",
    "in_progress": "🔄 Ko'rib chiqilmoqda",
    "done": "✔️ Yakunlandi",
}

_filter_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🆕 Yangi", callback_data="filter_list:new"),
            InlineKeyboardButton(text="🔄 Jarayonda", callback_data="filter_list:in_progress"),
            InlineKeyboardButton(text="✔️ Yakunlandi", callback_data="filter_list:done"),
            InlineKeyboardButton(text="📋 Barchasi", callback_data="filter_list:all"),
        ]
    ]
)


class AdminReplyState(StatesGroup):
    waiting_for_text = State()


async def _notify_user(user_id: int, report_id: int, new_status: str) -> None:
    status_label = STATUS_UZ.get(new_status, new_status)
    client_bot = Bot(token=settings.bot_token_client)
    try:
        await client_bot.send_message(
            user_id,
            f"📋 Sizning <b>#{report_id}</b> murojaatingiz holati yangilandi:\n{status_label}",
            parse_mode="HTML",
        )
    except Exception:
        pass
    finally:
        await client_bot.session.close()


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, admin: Admin) -> None:
    lines = [f"Salom, {admin.name}!", "", "/list — murojaatlar ro'yxati"]
    if admin.role == "super":
        lines += [
            "/admins — administratorlar ro'yxati",
            "/add_admin — yangi administrator qo'shish",
            "/remove_admin — administratorni o'chirish",
        ]
    await message.answer("\n".join(lines))


# ─── /list ───────────────────────────────────────────────────────────────────

async def _send_list(target: Message | CallbackQuery, status_filter: str | None) -> None:
    msg = target if isinstance(target, Message) else target.message
    if msg is None:
        return

    async with get_session() as session:
        query = select(Report).order_by(Report.created_at.desc()).limit(10)
        if status_filter:
            query = query.where(Report.status == status_filter)
        reports = list((await session.execute(query)).scalars())

    if not reports:
        text = "Hozircha murojaatlar yo'q."
    else:
        label = f"<b>{STATUS_UZ.get(status_filter, 'Oxirgi murojaatlar')}:</b>\n" if status_filter else "<b>Oxirgi murojaatlar:</b>\n"
        lines = [label]
        for r in reports:
            preview = r.text[:60] + ("…" if len(r.text) > 60 else "")
            lines.append(f"#{r.id} [{r.status}] — {preview}")
        text = "\n".join(lines)

    if isinstance(target, CallbackQuery):
        await msg.edit_text(text, parse_mode="HTML", reply_markup=_filter_kb)
        await target.answer()
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=_filter_kb)


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await _send_list(message, status_filter=None)


@router.callback_query(F.data.startswith("filter_list:"))
async def handle_filter_list(callback: CallbackQuery) -> None:
    raw = callback.data.split(":", 1)[1]
    status_filter = None if raw == "all" else raw
    await _send_list(callback, status_filter=status_filter)


# ─── Reply to citizen ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reply_to:"))
async def handle_reply_button(callback: CallbackQuery, state: FSMContext) -> None:
    report_id = int(callback.data.split(":", 1)[1])
    await state.set_state(AdminReplyState.waiting_for_text)
    await state.update_data(report_id=report_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"#{report_id} murojaat egasiga javob yozing:\n(Bekor qilish uchun /cancel)"
        )


@router.message(AdminReplyState.waiting_for_text, Command("cancel"))
async def cmd_cancel_reply(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(AdminReplyState.waiting_for_text)
async def handle_reply_text(message: Message, state: FSMContext, admin: Admin) -> None:
    if not message.text:
        return

    data = await state.get_data()
    report_id: int = data["report_id"]

    async with get_session() as session:
        report = await session.get(Report, report_id)
        if not report:
            await message.answer("Murojaat topilmadi.")
            await state.clear()
            return

        session.add(Reply(report_id=report_id, admin_id=admin.id, text=message.text))
        await session.commit()

        user_id = report.user_id

    client_bot = Bot(token=settings.bot_token_client)
    try:
        await client_bot.send_message(
            user_id,
            f"📩 <b>#{report_id} murojaatingizga javob:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
    except Exception:
        await message.answer("⚠️ Foydalanuvchiga xabar yuborib bo'lmadi.")
        await state.clear()
        return
    finally:
        await client_bot.session.close()

    await state.clear()
    await message.answer(f"✅ Javob #{report_id} murojaat egasiga yuborildi.")
