import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.auth import login
from app.main import root


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def first(self):
        return self._value


class _FakeExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return _FakeScalarResult(self._value)


class _FakeAsyncSession:
    def __init__(self, execute_results):
        self._execute_results = list(execute_results)

    async def execute(self, _query):
        return _FakeExecuteResult(self._execute_results.pop(0))


class _FakeOAuthForm:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class _FakeUser:
    def __init__(self, *, email="user@example.com", hashed_password="hashed", is_active=True):
        self.id = "user-1"
        self.email = email
        self.hashed_password = hashed_password
        self.full_name = "User"
        self.is_active = is_active
        self.is_superuser = False
        self.role = "member"


@pytest.mark.asyncio
async def test_login_invalid_credentials_message(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.auth.security.verify_password", lambda plain, hashed: False)

    db = _FakeAsyncSession([_FakeUser()])
    form = _FakeOAuthForm("user@example.com", "bad-password")

    with pytest.raises(HTTPException) as exc_info:
        await login(db=db, form_data=form)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "邮箱或密码错误"


@pytest.mark.asyncio
async def test_login_inactive_user_message(monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.auth.security.verify_password", lambda plain, hashed: True)

    db = _FakeAsyncSession([_FakeUser(is_active=False)])
    form = _FakeOAuthForm("user@example.com", "password")

    with pytest.raises(HTTPException) as exc_info:
        await login(db=db, form_data=form)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "账户已被禁用"


@pytest.mark.asyncio
async def test_root_does_not_expose_credentials():
    payload = await root()

    assert "demo_account" not in payload
    assert "password" not in str(payload).lower()
