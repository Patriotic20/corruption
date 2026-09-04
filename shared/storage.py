from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

from shared.config import settings


def build_storage(prefix: str) -> RedisStorage:
    """FSM state in Redis, so a half-filled form survives a restart.

    Each bot gets its own key prefix; Celery uses the same database but
    unrelated key names.
    """
    return RedisStorage.from_url(
        settings.redis_url,
        key_builder=DefaultKeyBuilder(prefix=prefix),
    )
