import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_initial_admin(db: AsyncSession) -> User | None:
    """Create or promote the explicitly configured initial administrator."""
    email = str(settings.INITIAL_ADMIN_EMAIL or "").strip()
    password = str(settings.INITIAL_ADMIN_PASSWORD or "")

    if not email and not password:
        return None
    if not email:
        raise RuntimeError("INITIAL_ADMIN_EMAIL is required when INITIAL_ADMIN_PASSWORD is set")

    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalars().first()
    if existing_user:
        changed = False
        if not existing_user.is_active:
            existing_user.is_active = True
            changed = True
        if not existing_user.is_superuser:
            existing_user.is_superuser = True
            changed = True
        if existing_user.role != "admin":
            existing_user.role = "admin"
            changed = True
        if changed:
            await db.flush()
            logger.info("Promoted configured initial administrator: %s", email)
        return existing_user

    if not password:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD is required to create the configured initial administrator")
    if len(password) < 12:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")

    admin_user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=str(settings.INITIAL_ADMIN_NAME or "Administrator").strip() or "Administrator",
        is_active=True,
        is_superuser=True,
        role="admin",
    )
    db.add(admin_user)
    await db.flush()
    logger.info("Created initial administrator: %s", email)
    return admin_user


async def init_db(db: AsyncSession) -> None:
    """Initialize database-backed application data and runtime assets."""
    logger.info("开始初始化数据库...")

    await create_initial_admin(db)
    await db.commit()

    from app.services.init_templates import init_templates_and_rules

    await init_templates_and_rules(db)

    from app.services.init_agent_assets import init_agent_assets

    await init_agent_assets(db)
    logger.info("数据库初始化完成")
