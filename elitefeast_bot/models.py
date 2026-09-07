from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class StringEnum(str, PyEnum):
    pass


class OrderStatus(StringEnum):
    DRAFT = "draft"
    PENDING_RECEIPT_REVIEW = "pending_receipt_review"
    REJECTED = "rejected"
    PROCESSING = "processing"
    DELIVERED = "delivered"


class UserRole(StringEnum):
    CLIENT = "client"
    SHOP_OWNER = "shop_owner"
    ADMIN = "admin"


class DeliveryFor(StringEnum):
    SELF = "self"
    SOMEONE_ELSE = "someone_else"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.CLIENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    owner_telegram_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    live_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    orders_close_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_live_prompt_week: Mapped[Optional[str]] = mapped_column(String(32))
    delivery_note: Mapped[Optional[str]] = mapped_column(Text)
    products: Mapped[List["Product"]] = relationship(back_populates="shop")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    name: Mapped[str] = mapped_column(String(255))
    price_rub: Mapped[float] = mapped_column(Numeric(10, 2))
    description: Mapped[Optional[str]] = mapped_column(Text)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    restricted_cities_csv: Mapped[Optional[str]] = mapped_column(Text)
    allowed_cities_csv: Mapped[Optional[str]] = mapped_column(Text)
    shop: Mapped[Shop] = relationship(back_populates="products")

    def is_allowed_for_city(self, city: str) -> bool:
        if not self.allowed_cities_csv:
            return True
        allowed = {item.strip().casefold() for item in self.allowed_cities_csv.split(",") if item.strip()}
        return city.strip().casefold() in allowed


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.DRAFT)
    city: Mapped[Optional[str]] = mapped_column(String(255))
    delivery_address: Mapped[Optional[str]] = mapped_column(Text)
    delivery_for: Mapped[Optional[DeliveryFor]] = mapped_column(Enum(DeliveryFor))
    recipient_name: Mapped[Optional[str]] = mapped_column(String(255))
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(255))
    receipt_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    total_rub: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    shop: Mapped[Shop] = relationship()
    items: Mapped[List["OrderItem"]] = relationship(cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_rub: Mapped[float] = mapped_column(Numeric(10, 2))
    product_name: Mapped[str] = mapped_column(String(255))


class MessageThread(Base):
    __tablename__ = "message_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    sender_telegram_id: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    client_telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
