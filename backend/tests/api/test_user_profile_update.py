from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.users import update_user_me
from app.core.security import get_password_hash, verify_password
from app.schemas.user import UserUpdate


class _CurrentUser:
    def __init__(self):
        self.id = "user-1"
        self.email = "demo@example.com"
        self.hashed_password = get_password_hash("current-password")
        self.full_name = "Demo"
        self.phone = None
        self.avatar_url = None
        self.role = "admin"
        self.github_username = None
        self.gitlab_username = None
        self.is_active = True
        self.is_superuser = True


@pytest.mark.asyncio
async def test_update_user_me_requires_current_password_for_password_change():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = _CurrentUser()

    with pytest.raises(HTTPException) as exc_info:
        await update_user_me(
            db=db,
            user_in=UserUpdate(
                current_password="wrong-password",
                password="new-password",
            ),
            current_user=user,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "当前密码错误"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_me_changes_password_with_current_password():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = _CurrentUser()

    await update_user_me(
        db=db,
        user_in=UserUpdate(
            current_password="current-password",
            password="new-password",
        ),
        current_user=user,
    )

    assert verify_password("new-password", user.hashed_password) is True
    assert verify_password("current-password", user.hashed_password) is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_me_changes_email_without_changing_user_identity():
    db = MagicMock()
    db.execute = AsyncMock()
    db.execute.return_value.scalars.return_value.first.return_value = None
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    user = _CurrentUser()

    result = await update_user_me(
        db=db,
        user_in=UserUpdate(email="owner@example.com"),
        current_user=user,
    )

    assert result is user
    assert user.id == "user-1"
    assert user.email == "owner@example.com"
    db.commit.assert_awaited_once()
