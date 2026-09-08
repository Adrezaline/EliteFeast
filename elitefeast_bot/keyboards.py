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
            [KeyboardButton(text="My Telegram ID")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Browse shops"), KeyboardButton(text="My orders")],
            [KeyboardButton(text="Admin shops"), KeyboardButton(text="Shop cards")],
            [KeyboardButton(text="Add shop"), KeyboardButton(text="Manage products")],
            [KeyboardButton(text="Customer care")],
            [KeyboardButton(text="My Telegram ID")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def customer_care_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Pending care messages")],
            [KeyboardButton(text="My Telegram ID")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def customer_care_message_keyboard(message_id: int, direction: str) -> InlineKeyboardMarkup:
    recipient = "shop owner" if direction == "client_to_owner" else "customer"
    reply_target = "customer" if direction == "client_to_owner" else "shop owner"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Approve to {recipient}", callback_data=f"care:approve:{message_id}")],
            [InlineKeyboardButton(text=f"Reply to {reply_target}", callback_data=f"care:reply:{message_id}")],
        ]
    )


def owner_reply_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Reply to customer", callback_data=f"message:client:{order_id}")],
        ]
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
    rows.append([InlineKeyboardButton(text="View cart", callback_data=f"cart:{shop_id}")])
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
            [InlineKeyboardButton(text="View cart", callback_data=f"cart:{shop_id}")],
            [InlineKeyboardButton(text="Checkout", callback_data=f"checkout:{shop_id}")],
        ]
    )


def cart_keyboard(order) -> InlineKeyboardMarkup:
    rows = []
    for item in order.items:
        rows.append(
            [
                InlineKeyboardButton(text="-", callback_data=f"cart:decrease:{order.id}:{item.id}"),
                InlineKeyboardButton(text=f"{item.product_name} x{item.quantity}", callback_data="cart:ignore"),
                InlineKeyboardButton(text="Remove", callback_data=f"cart:remove:{order.id}:{item.id}"),
            ]
        )
    if order.items:
        rows.append([InlineKeyboardButton(text="Clear cart", callback_data=f"cart:clear:{order.id}")])
        rows.append([InlineKeyboardButton(text="Checkout", callback_data=f"checkout:{order.shop_id}")])
    rows.append([InlineKeyboardButton(text="Back to catalog", callback_data=f"shop:{order.shop_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
