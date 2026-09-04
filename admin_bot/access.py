import re
from datetime import datetime

from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.models import Admin, AdminInvite

USERNAME_RE = r"^@?[A-Za-z0-9_]{5,32}$"


def normalize_username(raw: str) -> str | None:
    """'@Shaxboz_Jumayev' -> 'shaxboz_jumayev'. None if it is not a valid username."""
    candidate = raw.strip()
    if not re.match(USERNAME_RE, candidate):
        return None
    return candidate.lstrip("@").lower()


def is_super_id(user_id: int) -> bool:
    return user_id in settings.admin_id_list


async def resolve_admin(session: AsyncSession, user: User) -> Admin | None:
    """Return the active Admin row for this Telegram user, or None if access is denied.

    Authorization is always bound to the immutable telegram_id. A username is only
    used once, to claim a pending invite; afterwards it is display data.
    """
    username = user.username.lower() if user.username else None
    admin = await session.scalar(select(Admin).where(Admin.telegram_id == user.id))

    if is_super_id(user.id):
        if admin is None:
            admin = Admin(telegram_id=user.id, name=user.full_name, role="super")
            session.add(admin)
        admin.name = user.full_name
        admin.username = username
        admin.role = "super"
        admin.is_active = True
        await session.commit()
        await session.refresh(admin)
        return admin

    if admin is not None:
        if not admin.is_active:
            return None
        if admin.name != user.full_name or admin.username != username:
            admin.name = user.full_name
            admin.username = username
            await session.commit()
        return admin

    if username is None:
        return None

    invite = await session.scalar(
        select(AdminInvite).where(
            AdminInvite.username == username,
            AdminInvite.used_at.is_(None),
        )
    )
    if invite is None:
        return None

    admin = Admin(
        telegram_id=user.id,
        name=user.full_name,
        username=username,
        role="admin",
        is_active=True,
    )
    session.add(admin)
    invite.used_at = datetime.now()
    await session.commit()
    await session.refresh(admin)
    return admin
