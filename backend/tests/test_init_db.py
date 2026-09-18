from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.db.init_db import create_initial_admin


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _ExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return _ScalarResult(self._value)


@pytest.mark.asyncio
async def test_create_initial_admin_from_explicit_settings(monkeypatch):
    monkeypatch.setattr(settings, "INITIAL_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", "strong-password-123")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_NAME", "Admin")

    db = MagicMock()
    db.execute = AsyncMock(return_value=_ExecuteResult(None))
    db.flush = AsyncMock()

    user = await create_initial_admin(db)

    assert user is not None
    assert user.email == "admin@example.com"
    assert user.is_superuser is True
    assert user.role == "admin"
    db.add.assert_called_once_with(user)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_initial_admin_rejects_partial_configuration(monkeypatch):
    monkeypatch.setattr(settings, "INITIAL_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(settings, "INITIAL_ADMIN_PASSWORD", None)

    db = MagicMock()

    with pytest.raises(RuntimeError, match="must be configured together"):
        await create_initial_admin(db)
