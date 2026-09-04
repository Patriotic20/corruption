from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, MessageOriginUser
from sqlalchemy import select

from admin_bot.access import is_super_id, normalize_username
from shared.database import get_session
from shared.models import Admin, AdminInvite

router = Router()

ONLY_SUPER = "Bu buyruq faqat bosh administrator uchun."
ASK_TARGET = (
    "Yangi administratorni qo'shish uchun quyidagilardan birini yuboring:\n\n"
    "• uning xabarini bu yerga <b>forward</b> qiling;\n"
    "• uning <b>kontaktini</b> yuboring;\n"
    "• yoki <b>@username</b> ni yozing.\n\n"
    "Bekor qilish uchun /cancel"
)


class AddAdminState(StatesGroup):
    waiting_for_target = State()


def _is_super(admin: Admin) -> bool:
    return admin.role == "super"


# ─── /admins ─────────────────────────────────────────────────────────────────

@router.message(Command("admins"))
async def cmd_admins(message: Message, admin: Admin) -> None:
    if not _is_super(admin):
        await message.answer(ONLY_SUPER)
        return

    async with get_session() as session:
        admins = list(
            (await session.execute(select(Admin).order_by(Admin.id))).scalars()
        )
        invites = list(
            (
                await session.execute(
                    select(AdminInvite)
                    .where(AdminInvite.used_at.is_(None))
                    .order_by(AdminInvite.id)
                )
            ).scalars()
        )

    lines = ["<b>Administratorlar:</b>"]
    for a in admins:
        role = "👑 bosh" if a.role == "super" else "👤 admin"
        status = "✅ aktiv" if a.is_active else "⛔️ o'chirilgan"
        username = f"@{a.username}" if a.username else "—"
        lines.append(f"#{a.id} {a.name} ({username}) — {role}, {status}")

    if invites:
        lines.append("\n<b>Kutilayotgan takliflar:</b>")
        for inv in invites:
            lines.append(f"@{inv.username}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── /add_admin ──────────────────────────────────────────────────────────────

async def _grant_by_username(session, username: str, invited_by: int) -> str:
    existing = await session.scalar(select(Admin).where(Admin.username == username))
    if existing:
        if existing.is_active:
            return f"@{username} allaqachon administrator."
        existing.is_active = True
        await session.commit()
        return f"✅ @{username} qayta faollashtirildi."

    invite = await session.scalar(
        select(AdminInvite).where(AdminInvite.username == username)
    )
    if invite is None:
        invite = AdminInvite(username=username)
        session.add(invite)
    invite.invited_by = invited_by
    invite.used_at = None
    await session.commit()

    return (
        f"✅ @{username} uchun taklif yaratildi.\n\n"
        "Unga botga /start yuborishni ayting — shundan keyin u administrator bo'ladi."
    )


async def _grant_by_user_id(
    session, telegram_id: int, name: str, username: str | None, invited_by: int
) -> str:
    label = f"@{username}" if username else name

    existing = await session.scalar(
        select(Admin).where(Admin.telegram_id == telegram_id)
    )
    if existing:
        if existing.is_active:
            return f"{label} allaqachon administrator."
        existing.is_active = True
        existing.name = name
        existing.username = username
        await session.commit()
        return f"✅ {label} qayta faollashtirildi."

    session.add(
        Admin(
            telegram_id=telegram_id,
            name=name,
            username=username,
            role="admin",
            is_active=True,
        )
    )
    # pending invite for the same person is no longer needed
    if username:
        invite = await session.scalar(
            select(AdminInvite).where(AdminInvite.username == username)
        )
        if invite:
            await session.delete(invite)
    await session.commit()
    return f"✅ {label} administrator sifatida qo'shildi."


@router.message(Command("add_admin"))
async def cmd_add_admin(
    message: Message, command: CommandObject, admin: Admin, state: FSMContext
) -> None:
    if not _is_super(admin):
        await message.answer(ONLY_SUPER)
        return

    if not command.args:
        await state.set_state(AddAdminState.waiting_for_target)
        await message.answer(ASK_TARGET, parse_mode="HTML")
        return

    username = normalize_username(command.args)
    if username is None:
        await message.answer("Username noto'g'ri. Namuna: /add_admin @username")
        return

    async with get_session() as session:
        text = await _grant_by_username(session, username, admin.id)
    await message.answer(text)


@router.message(AddAdminState.waiting_for_target, Command("cancel"))
async def cmd_cancel_add(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(AddAdminState.waiting_for_target, F.contact)
async def add_admin_by_contact(message: Message, state: FSMContext, admin: Admin) -> None:
    contact = message.contact
    if contact.user_id is None:
        await message.answer(
            "Bu kontakt Telegram foydalanuvchisi emas. @username yuboring yoki /cancel."
        )
        return

    name = " ".join(filter(None, [contact.first_name, contact.last_name]))
    async with get_session() as session:
        text = await _grant_by_user_id(session, contact.user_id, name, None, admin.id)
    await state.clear()
    await message.answer(text)


@router.message(AddAdminState.waiting_for_target, F.forward_origin)
async def add_admin_by_forward(message: Message, state: FSMContext, admin: Admin) -> None:
    origin = message.forward_origin
    if not isinstance(origin, MessageOriginUser):
        await message.answer(
            "Bu foydalanuvchi forward'da o'z profilini yashirgan. "
            "@username yuboring yoki kontaktini ulashing. Bekor qilish — /cancel"
        )
        return

    user = origin.sender_user
    async with get_session() as session:
        text = await _grant_by_user_id(
            session,
            user.id,
            user.full_name,
            user.username.lower() if user.username else None,
            admin.id,
        )
    await state.clear()
    await message.answer(text)


@router.message(AddAdminState.waiting_for_target)
async def add_admin_by_username(message: Message, state: FSMContext, admin: Admin) -> None:
    username = normalize_username(message.text or "")
    if username is None:
        await message.answer(
            "Tushunmadim. Xabarni forward qiling, kontakt yuboring yoki @username yozing.\n"
            "Bekor qilish — /cancel"
        )
        return

    async with get_session() as session:
        text = await _grant_by_username(session, username, admin.id)
    await state.clear()
    await message.answer(text)


# ─── /remove_admin ───────────────────────────────────────────────────────────

@router.message(Command("remove_admin"))
async def cmd_remove_admin(message: Message, command: CommandObject, admin: Admin) -> None:
    if not _is_super(admin):
        await message.answer(ONLY_SUPER)
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Namuna: /remove_admin @username yoki /remove_admin 123456789")
        return

    telegram_id = int(raw) if raw.isdigit() else None
    username = normalize_username(raw) if telegram_id is None else None
    if telegram_id is None and username is None:
        await message.answer("Username noto'g'ri. Namuna: /remove_admin @username")
        return

    async with get_session() as session:
        if telegram_id is not None:
            target = await session.scalar(
                select(Admin).where(Admin.telegram_id == telegram_id)
            )
        else:
            target = await session.scalar(select(Admin).where(Admin.username == username))

        if target is not None:
            if is_super_id(target.telegram_id):
                await message.answer(
                    "Bosh administratorni o'chirib bo'lmaydi — uni .env dagi "
                    "ADMIN_IDS dan olib tashlang."
                )
                return
            if target.id == admin.id:
                await message.answer("O'zingizni o'chira olmaysiz.")
                return
            target.is_active = False
            username = target.username

        removed_invite = False
        if username:
            invite = await session.scalar(
                select(AdminInvite).where(AdminInvite.username == username)
            )
            if invite is not None:
                await session.delete(invite)
                removed_invite = True

        await session.commit()

    if target is not None:
        await message.answer(f"⛔️ {target.name} administratorlar ro'yxatidan o'chirildi.")
    elif removed_invite:
        await message.answer(f"⛔️ @{username} uchun taklif bekor qilindi.")
    else:
        await message.answer("Bunday administrator topilmadi.")
