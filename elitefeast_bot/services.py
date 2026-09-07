from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elitefeast_bot.models import Order, OrderItem, OrderStatus, Product, Shop, User, UserRole


async def upsert_user(session: AsyncSession, telegram_user, role: UserRole = UserRole.CLIENT) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_user.id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_user.id,
            full_name=telegram_user.full_name,
            username=telegram_user.username,
            role=role,
        )
        session.add(user)
    else:
        user.full_name = telegram_user.full_name
        user.username = telegram_user.username
    await session.commit()
    return user


async def live_shops(session: AsyncSession) -> List[Shop]:
    result = await session.execute(select(Shop).where(Shop.is_live.is_(True)).order_by(Shop.name))
    return list(result.scalars())


async def shop_products(session: AsyncSession, shop_id: int, city: Optional[str] = None) -> List[Product]:
    result = await session.execute(
        select(Product)
        .where(Product.shop_id == shop_id, Product.is_available.is_(True))
        .order_by(Product.name)
    )
    products = list(result.scalars())
    if city:
        return [product for product in products if product.is_allowed_for_city(city)]
    return products


async def get_or_create_draft_order(
    session: AsyncSession,
    client_telegram_id: int,
    shop_id: int,
) -> Order:
    result = await session.execute(
        select(Order).where(
            Order.client_telegram_id == client_telegram_id,
            Order.shop_id == shop_id,
            Order.status == OrderStatus.DRAFT,
        )
    )
    order = result.scalar_one_or_none()
    if order:
        return order
    order = Order(client_telegram_id=client_telegram_id, shop_id=shop_id)
    session.add(order)
    await session.commit()
    return order


async def add_product_to_order(
    session: AsyncSession,
    client_telegram_id: int,
    product_id: int,
) -> Order:
    product = await session.get(Product, product_id)
    if product is None:
        raise ValueError("Product not found")

    order = await get_or_create_draft_order(session, client_telegram_id, product.shop_id)
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price_rub=product.price_rub,
        product_name=product.name,
    )
    order.total_rub = float(order.total_rub or 0) + float(product.price_rub)
    session.add(item)
    await session.commit()
    return order


async def order_summary(session: AsyncSession, order: Order) -> str:
    await session.refresh(order, attribute_names=["items", "shop"])
    lines = [
        f"Order #{order.id}",
        f"Shop: {order.shop.name}",
        f"Status: {order.status.value}",
        "",
        "Items:",
    ]
    for item in order.items:
        lines.append(f"- {item.product_name} x{item.quantity}: {float(item.unit_price_rub):.2f} RUB")
    lines.extend(
        [
            "",
            f"Total: {float(order.total_rub or 0):.2f} RUB",
            f"City: {order.city or '-'}",
            f"Address: {order.delivery_address or '-'}",
        ]
    )
    return "\n".join(lines)
