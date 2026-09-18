
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr | None = None
    is_active: bool | None = True
    is_superuser: bool = False
    full_name: str | None = None

    # Profile fields
    phone: str | None = None
    avatar_url: str | None = None
    role: str = "member"
    github_username: str | None = None
    gitlab_username: str | None = None

class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str

class UserUpdate(UserBase):
    password: str | None = Field(default=None, min_length=8)
    current_password: str | None = None

class UserInDBBase(UserBase):
    id: str
    created_at: object | None = None # Datetime
    updated_at: object | None = None

    model_config = ConfigDict(from_attributes=True)

class User(UserInDBBase):
    pass

class UserListResponse(BaseModel):
    users: list[User]
    total: int
    skip: int
    limit: int






