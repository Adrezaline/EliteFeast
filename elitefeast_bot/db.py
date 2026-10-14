from typing import AsyncIterator

from sqlalchemy import text
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
            if "delivery_date" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN delivery_date DATE")
            if "delivered_at" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN delivered_at DATETIME")
            if "review_requested_at" not in column_names:
                await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN review_requested_at DATETIME")
        elif conn.dialect.name == "postgresql":
            await conn.exec_driver_sql("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_date DATE")
            telegram_id_columns = (
                ("users", "telegram_id"),
                ("customer_language_preferences", "telegram_id"),
                ("shops", "owner_telegram_id"),
                ("orders", "client_telegram_id"),
                ("message_threads", "sender_telegram_id"),
                ("customer_care_agents", "telegram_id"),
                ("customer_care_messages", "sender_telegram_id"),
                ("customer_care_messages", "recipient_telegram_id"),
                ("customer_care_messages", "reviewed_by_telegram_id"),
                ("reviews", "client_telegram_id"),
            )
            for table_name, column_name in telegram_id_columns:
                column_type = await conn.scalar(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = :table_name AND column_name = :column_name"
                    ),
                    {"table_name": table_name, "column_name": column_name},
                )
                if column_type == "integer":
                    await conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE BIGINT"
                    )


async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
