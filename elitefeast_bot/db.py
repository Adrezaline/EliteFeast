from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from elitefeast_bot.config import get_settings
from elitefeast_bot.models import Base


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            columns = await conn.exec_driver_sql("PRAGMA table_info(shops)")
            column_names = {row[1] for row in columns}
            if "photo_file_id" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE shops ADD COLUMN photo_file_id VARCHAR(255)")
            if "live_from" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE shops ADD COLUMN live_from DATETIME")
            if "orders_close_at" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE shops ADD COLUMN orders_close_at DATETIME")
            if "last_live_prompt_week" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE shops ADD COLUMN last_live_prompt_week VARCHAR(32)")
            columns = await conn.exec_driver_sql("PRAGMA table_info(products)")
            column_names = {row[1] for row in columns}
            if "photo_file_id" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE products ADD COLUMN photo_file_id VARCHAR(255)")
            if "allowed_cities_csv" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE products ADD COLUMN allowed_cities_csv TEXT")
            columns = await conn.exec_driver_sql("PRAGMA table_info(orders)")
            column_names = {row[1] for row in columns}
            if "delivered_at" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN delivered_at DATETIME")
            if "review_requested_at" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN review_requested_at DATETIME")


async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
