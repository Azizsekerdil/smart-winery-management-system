"""Test altyapisi.

ONEMLI: Ortam degiskenleri `app` paketinden HERHANGI bir ithal yapilmadan ONCE
ayarlanir; `app.core.config.settings` modul duzeyinde tek ornek (singleton)
oldugu icin sonradan degistirmek etkisiz kalir.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# --------------------------------------------------------------- ortam kurulumu
_TMP_DIR = Path(tempfile.mkdtemp(prefix="saraphane-test-"))
_DB_PATH = _TMP_DIR / "test.db"

os.environ.update(
    {
        "APP_ENV": "development",
        "DEBUG": "true",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}",
        "SECRET_KEY": "test-only-secret-key-do-not-use-in-production-0123456789",
        "SECRETS_ENCRYPTION_KEY": "test-only-encryption-key-0123456789abcdef",
        "RATE_LIMIT_ENABLED": "false",
        "SEED_DEMO_DATA": "false",
        "LOG_LEVEL": "WARNING",
        "LOG_FILE": str(_TMP_DIR / "test.log"),
        "AGENT_WORKSPACE": str(Path(__file__).resolve().parents[1]),
        # Testlerde dis servislere gercek istek atilmaz
        "ANTHROPIC_API_KEY": "",
        "NVIDIA_API_KEY": "",
    }
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import *
from app.models.user import User
from app.services.ai.registry import ensure_default_configs

TEST_PASSWORD = "TestParola123!"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="function", autouse=True)
async def _fresh_database() -> AsyncIterator[None]:
    """Her test icin temiz sema + varsayilan AI saglayici kayitlari.

    Uygulama bu kayitlari acilista (lifespan) olusturur; testlerde sema her
    testte sifirlandigi icin burada yeniden kurulur.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        await ensure_default_configs(s)
    yield


@pytest_asyncio.fixture
async def session() -> AsyncIterator:
    async with SessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_user(roles: list[str], username: str = "testuser") -> User:
    async with SessionLocal() as s:
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name=f"Test {username}",
            password_hash=hash_password(TEST_PASSWORD),
            roles=roles,
            is_active=True,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


@pytest_asyncio.fixture
async def make_user():
    """Belirli rollerle kullanici uretir."""

    async def _factory(roles: list[str], username: str = "testuser") -> User:
        return await _create_user(roles, username)

    return _factory


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, make_user):
    """Verilen rollerle giris yapip Authorization basligi dondurur."""

    async def _factory(roles: list[str], username: str = "testuser") -> dict[str, str]:
        await make_user(roles, username)
        response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _factory


@pytest_asyncio.fixture
async def admin_headers(auth_headers) -> dict[str, str]:
    return await auth_headers(["sistem_yoneticisi"], "admin_test")


@pytest.fixture(scope="session", autouse=True)
def _cleanup() -> Iterator[None]:
    yield
    # Gecici dosyalari birak (Windows'ta SQLite kilidi nedeniyle silme zorlanmaz)

