import asyncio

from sqlalchemy import select

from elitefeast_bot.db import SessionLocal, init_db
from elitefeast_bot.models import Product, Shop


SHOPS = [
    {
        "name": "D Cake House",
        "is_live": True,
        "delivery_note": "Deliveries start after orders are taken.",
        "products": [
            ("Cake slice", 399.99, None),
            ("Parfait cup", 299.99, None),
        ],
    },
    {
        "name": "Asher's Cuisine",
        "is_live": True,
        "delivery_note": "Currently taking orders for Thursday.",
        "products": [
            ("Plate of Jollof rice and Turkey", 449.99, None),
            ("Sunday rice bowl", 499.99, None),
        ],
    },
    {
        "name": "African Bite",
        "is_live": False,
        "delivery_note": "Currently not taking orders.",
        "products": [
            ("Snack pack", 249.99, None),
        ],
    },
    {
        "name": "Elite Market",
        "is_live": False,
        "delivery_note": "Market groceries and pantry items.",
        "products": [
            ("MPAXY'S - Peak Milk 350g", 1299.99, None),
            ("MPAXY'S - Milo 400g", 999.99, None),
            ("Beans 1kg", 479.99, None),
            ("Palm oil 0.5 L", 749.99, "Moscow,Saint Petersburg"),
        ],
    },
]


async def seed() -> None:
    await init_db()
    async with SessionLocal() as session:
        for shop_data in SHOPS:
            result = await session.execute(select(Shop).where(Shop.name == shop_data["name"]))
            shop = result.scalar_one_or_none()
            if shop is None:
                shop = Shop(
                    name=shop_data["name"],
                    is_live=shop_data["is_live"],
                    delivery_note=shop_data["delivery_note"],
                )
                session.add(shop)
                await session.flush()

            for name, price, allowed_cities in shop_data["products"]:
                result = await session.execute(
                    select(Product).where(Product.shop_id == shop.id, Product.name == name)
                )
                if result.scalar_one_or_none() is None:
                    session.add(
                        Product(
                            shop_id=shop.id,
                            name=name,
                            price_rub=price,
                            allowed_cities_csv=allowed_cities,
                        )
                    )
        await session.commit()
    print("Seeded Elite Feast sample shops and products.")


if __name__ == "__main__":
    asyncio.run(seed())
