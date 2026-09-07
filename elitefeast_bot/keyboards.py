from typing import List

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def customer_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Browse shops"), KeyboardButton(text="My orders")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def client_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Message shop owner", callback_data=f"message:owner:{order_id}")],
        ]
    )


def shops_keyboard(shops: List) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=shop.name, callback_data=f"shop:{shop.id}")]
            for shop in shops
        ]
    )


def single_shop_keyboard(shop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open catalog", callback_data=f"shop:{shop_id}")],
        ]
    )


def product_keyboard(products: List, shop_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Add {product.name} - {float(product.price_rub):.2f} RUB",
                callback_data=f"add:{product.id}",
            )
        ]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="Checkout", callback_data=f"checkout:{shop_id}")])
    rows.append([InlineKeyboardButton(text="Back to shops", callback_data="shops")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_for_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="For myself", callback_data="delivery_for:self")],
            [InlineKeyboardButton(text="For someone else", callback_data="delivery_for:someone_else")],
        ]
    )


def single_product_keyboard(product_id: int, shop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Add to order", callback_data=f"add:{product_id}")],
            [InlineKeyboardButton(text="Checkout", callback_data=f"checkout:{shop_id}")],
        ]
    )


def admin_receipt_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Approve", callback_data=f"admin:approve:{order_id}"),
                InlineKeyboardButton(text="Reject", callback_data=f"admin:reject:{order_id}"),
            ]
        ]
    )


def owner_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mark processing", callback_data=f"owner:processing:{order_id}")],
            [InlineKeyboardButton(text="Mark delivered", callback_data=f"owner:delivered:{order_id}")],
            [InlineKeyboardButton(text="Message client", callback_data=f"message:client:{order_id}")],
            [InlineKeyboardButton(text="Message admin", callback_data=f"message:admin:{order_id}")],
        ]
    )


def owner_live_keyboard(shop_id: int, is_live: bool) -> InlineKeyboardMarkup:
    label = "Go offline" if is_live else "Go live"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"owner:toggle_live:{shop_id}")],
            [InlineKeyboardButton(text="Set live window", callback_data=f"owner:week_live:{shop_id}")],
        ]
    )


def owner_weekly_prompt_keyboard(shop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Set live window", callback_data=f"owner:week_live:{shop_id}")],
            [InlineKeyboardButton(text="Stay offline", callback_data=f"owner:week_off:{shop_id}")],
        ]
    )


def review_rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"review:rating:{order_id}:1"),
                InlineKeyboardButton(text="2", callback_data=f"review:rating:{order_id}:2"),
                InlineKeyboardButton(text="3", callback_data=f"review:rating:{order_id}:3"),
                InlineKeyboardButton(text="4", callback_data=f"review:rating:{order_id}:4"),
                InlineKeyboardButton(text="5", callback_data=f"review:rating:{order_id}:5"),
            ],
            [InlineKeyboardButton(text="Skip review", callback_data=f"review:skip:{order_id}")],
        ]
    )
