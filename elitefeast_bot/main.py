import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, Message
from sqlalchemy import select

from elitefeast_bot.config import get_settings, require_bot_token
from elitefeast_bot.db import SessionLocal, init_db
from elitefeast_bot.keyboards import (
    admin_menu_keyboard,
    admin_receipt_keyboard,
    cart_keyboard,
    client_order_keyboard,
    customer_care_menu_keyboard,
    customer_care_message_keyboard,
    customer_menu_keyboard,
    delivery_for_keyboard,
    owner_live_keyboard,
    owner_order_keyboard,
    owner_reply_keyboard,
    owner_weekly_prompt_keyboard,
    product_keyboard,
    review_rating_keyboard,
    shops_keyboard,
    single_product_keyboard,
    single_shop_keyboard,
)
from elitefeast_bot.models import (
    CareMessageDirection,
    CareMessageStatus,
    CustomerCareAgent,
    CustomerCareMessage,
    DeliveryFor,
    MessageThread,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Review,
    Shop,
)
from elitefeast_bot.services import (
    add_product_to_order,
    clear_draft_order,
    draft_order,
    draft_order_summary,
    remove_draft_item,
    live_shops,
    order_summary,
    shop_products,
    update_draft_item_quantity,
    upsert_user,
)
from elitefeast_bot.states import (
    AdminMenu,
    AdminProduct,
    AdminProductPhoto,
    AdminShopPhoto,
    Checkout,
    CustomerCare,
    Messaging,
    OwnerLiveWindow,
    ReviewFlow,
)


settings = get_settings()
bot = Bot(token=require_bot_token(settings))
dp = Dispatcher()


def moscow_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=3)


def current_prompt_week() -> str:
    year, week, _ = moscow_now().isocalendar()
    return f"{year}-{week:02d}"


def parse_moscow_datetime(value: str):
    value = value.strip()
    for pattern in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    return None


def format_datetime(value) -> str:
    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


async def request_payment_receipt(message: Message, state: FSMContext) -> None:
    if not settings.payment_card_number:
        await state.clear()
        await message.answer(
            "Sorry, payment details are not available at the moment. Please contact Elite Feast before making payment."
        )
        return
    await state.set_state(Checkout.receipt)
    await message.answer(
        "Please make your payment to this bank card:\n"
        f"{settings.payment_card_number}\n\n"
        "After making payment, please upload a screenshot or photo of the payment receipt. Thank you."
    )


async def active_customer_care_ids(session) -> List[int]:
    result = await session.execute(
        select(CustomerCareAgent.telegram_id).where(CustomerCareAgent.is_active.is_(True))
    )
    return list(result.scalars())


async def is_customer_care_agent(session, telegram_id: int) -> bool:
    result = await session.execute(
        select(CustomerCareAgent.id).where(
            CustomerCareAgent.telegram_id == telegram_id,
            CustomerCareAgent.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


def customer_care_message_text(care_message: CustomerCareMessage) -> str:
    sender = "Customer" if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER else "Shop owner"
    recipient = "shop owner" if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER else "customer"
    return (
        f"Customer-care approval needed\n"
        f"Order #{care_message.order_id}\n"
        f"From: {sender}\n"
        f"Send to: {recipient}\n\n"
        f"{care_message.message}"
    )


async def notify_customer_care_agents(care_message: CustomerCareMessage, agent_ids) -> None:
    for agent_id in agent_ids:
        try:
            await bot.send_message(
                agent_id,
                customer_care_message_text(care_message),
                reply_markup=customer_care_message_keyboard(care_message.id, care_message.direction.value),
            )
        except Exception:
            logging.exception("Could not notify customer-care agent %s", agent_id)


async def send_shop_cards(message: Message, shops) -> None:
    await message.answer("Please choose an available shop:")
    for shop in shops:
        caption = shop.name
        if shop.delivery_note:
            caption = f"{shop.name}\n{shop.delivery_note}"
        if shop.photo_file_id:
            await message.answer_photo(
                shop.photo_file_id,
                caption=caption,
                reply_markup=single_shop_keyboard(shop.id),
            )
        else:
            await message.answer(caption, reply_markup=single_shop_keyboard(shop.id))


async def send_product_cards(message: Message, shop: Shop, products) -> None:
    await message.answer(f"{shop.name}\nPlease select the products you would like to add to your order:")
    for product in products:
        caption = f"{product.name}\n{float(product.price_rub):.2f} RUB"
        if product.description:
            caption = f"{caption}\n{product.description}"
        availability = product.allowed_cities_csv or "all cities in Russia"
        caption = f"{caption}\nAvailable: {availability}"
        if product.photo_file_id:
            await message.answer_photo(
                product.photo_file_id,
                caption=caption,
                reply_markup=single_product_keyboard(product.id, shop.id),
            )
        else:
            await message.answer(caption, reply_markup=single_product_keyboard(product.id, shop.id))


async def send_cart(message: Message, order: Order) -> None:
    await message.answer(draft_order_summary(order), reply_markup=cart_keyboard(order))


@dp.message(Command("start"))
async def start(message: Message) -> None:
    async with SessionLocal() as session:
        await upsert_user(session, message.from_user)
        shops = await live_shops(session)
        is_care_agent = await is_customer_care_agent(session, message.from_user.id)

    if message.from_user.id in settings.admin_ids:
        menu = admin_menu_keyboard()
    elif is_care_agent:
        menu = customer_care_menu_keyboard()
    else:
        menu = customer_menu_keyboard()
    if not shops:
        await message.answer(
            "No Elite Feast shops are live right now. Please check again soon.",
            reply_markup=menu,
        )
        return

    if any(shop.photo_file_id for shop in shops):
        await send_shop_cards(message, shops)
    else:
        await message.answer("Please choose an available shop:", reply_markup=shops_keyboard(shops))
    await message.answer("Thank you. Please use the buttons below whenever you need them.", reply_markup=menu)


@dp.message(Command("shops"))
async def show_shops(message: Message) -> None:
    await start(message)


@dp.message(F.text == "Browse shops")
async def browse_shops_button(message: Message) -> None:
    await start(message)


@dp.message(Command("orders"))
async def show_orders(message: Message) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Order)
            .where(Order.client_telegram_id == message.from_user.id)
            .order_by(Order.created_at.desc())
        )
        orders = list(result.scalars())

    if not orders:
        await message.answer("You do not have any orders yet. Thank you for visiting Elite Feast.")
        return

    lines = ["Thank you. Here are your orders:"]
    for order in orders[:10]:
        lines.append(f"#{order.id}: {order.status.value} - {float(order.total_rub or 0):.2f} RUB")
    async with SessionLocal() as session:
        is_care_agent = await is_customer_care_agent(session, message.from_user.id)
    if message.from_user.id in settings.admin_ids:
        menu = admin_menu_keyboard()
    elif is_care_agent:
        menu = customer_care_menu_keyboard()
    else:
        menu = customer_menu_keyboard()
    await message.answer("\n".join(lines), reply_markup=menu)
    for order in orders[:10]:
        await message.answer(
            f"Order #{order.id}",
            reply_markup=client_order_keyboard(order.id),
        )


@dp.message(F.text == "My orders")
async def my_orders_button(message: Message) -> None:
    await show_orders(message)


@dp.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer(
            f"Admin access is not enabled for this account. Your Telegram ID is {message.from_user.id}."
        )
        return
    await message.answer("Elite Feast admin panel", reply_markup=admin_menu_keyboard())


@dp.message(Command("whoami"))
@dp.message(F.text == "My Telegram ID")
async def show_telegram_id(message: Message) -> None:
    is_admin = message.from_user.id in settings.admin_ids
    async with SessionLocal() as session:
        is_care_agent = await is_customer_care_agent(session, message.from_user.id)
    status = "Yes" if is_admin else "No"
    if is_admin:
        menu = admin_menu_keyboard()
    elif is_care_agent:
        menu = customer_care_menu_keyboard()
    else:
        menu = customer_menu_keyboard()
    await message.answer(
        f"Your Telegram ID: {message.from_user.id}\nAdministrator: {status}",
        reply_markup=menu,
    )


@dp.message(F.text == "Admin shops")
async def admin_shops_button(message: Message) -> None:
    await admin_shops(message)


@dp.message(F.text == "Shop cards")
async def admin_shop_cards_button(message: Message) -> None:
    await admin_shop_cards(message)


@dp.message(F.text == "Add shop")
async def add_shop_button(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return
    await state.set_state(AdminMenu.shop_name)
    await message.answer("Send the new shop name.")


@dp.message(AdminMenu.shop_name)
async def add_shop_from_menu(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await state.clear()
        await message.answer("Admin only.")
        return
    await create_shop(message, message.text.strip())
    await state.clear()


@dp.message(F.text == "Manage products")
async def manage_products_button(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return
    await state.set_state(AdminMenu.product_shop_id)
    await message.answer("Send the shop ID. Tap Admin shops to see all shop IDs.")


@dp.message(AdminMenu.product_shop_id)
async def manage_products_for_shop(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await state.clear()
        await message.answer("Admin only.")
        return
    if not (message.text or "").strip().isdigit():
        await message.answer("Please send a shop ID number, for example 2.")
        return
    await state.clear()
    await send_admin_products(message, int(message.text.strip()))


@dp.message(F.text == "Customer care")
async def customer_care_management(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return
    await state.set_state(AdminMenu.customer_care_telegram_id)
    await message.answer("Please send the Telegram ID of the customer-care agent.")


@dp.message(AdminMenu.customer_care_telegram_id)
async def assign_customer_care_from_menu(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await state.clear()
        await message.answer("Admin only.")
        return
    if not (message.text or "").strip().isdigit():
        await message.answer("Please send a Telegram ID number, for example 123456789.")
        return
    await assign_customer_care_agent(message, int(message.text.strip()))
    await state.clear()


@dp.message(Command("assign_care"))
async def assign_customer_care_command(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Please send it like this: /assign_care 123456789")
        return
    await assign_customer_care_agent(message, int(parts[1]))


async def assign_customer_care_agent(message: Message, telegram_id: int) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(CustomerCareAgent).where(CustomerCareAgent.telegram_id == telegram_id)
        )
        agent = result.scalar_one_or_none()
        if agent:
            agent.is_active = True
        else:
            agent = CustomerCareAgent(telegram_id=telegram_id)
            session.add(agent)
        await session.commit()

    await message.answer(f"Customer care is now assigned to Telegram ID {telegram_id}.")
    try:
        await bot.send_message(
            telegram_id,
            "You have been assigned as an Elite Feast customer-care agent. Please use the buttons below to review messages.",
            reply_markup=customer_care_menu_keyboard(),
        )
    except Exception:
        await message.answer("Please ask the customer-care agent to open this bot with /start, then they can use /care.")


@dp.message(Command("care"))
async def customer_care_panel(message: Message) -> None:
    async with SessionLocal() as session:
        is_care_agent = await is_customer_care_agent(session, message.from_user.id)
    if not is_care_agent:
        await message.answer("Customer-care access is not enabled for this account.")
        return
    await message.answer("Elite Feast customer-care panel", reply_markup=customer_care_menu_keyboard())


@dp.message(F.text == "Pending care messages")
async def pending_customer_care_messages(message: Message) -> None:
    async with SessionLocal() as session:
        is_care_agent = await is_customer_care_agent(session, message.from_user.id)
        if not is_care_agent:
            await message.answer("Customer-care access is not enabled for this account.")
            return
        result = await session.execute(
            select(CustomerCareMessage)
            .where(CustomerCareMessage.status == CareMessageStatus.PENDING)
            .order_by(CustomerCareMessage.created_at)
        )
        messages = list(result.scalars())

    if not messages:
        await message.answer("There are no messages waiting for review.")
        return
    for care_message in messages:
        await message.answer(
            customer_care_message_text(care_message),
            reply_markup=customer_care_message_keyboard(care_message.id, care_message.direction.value),
        )


@dp.callback_query(F.data.startswith("care:approve:"))
async def approve_customer_care_message(callback: CallbackQuery) -> None:
    care_message_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        if not await is_customer_care_agent(session, callback.from_user.id):
            await callback.answer("Customer-care access only.", show_alert=True)
            return
        care_message = await session.get(CustomerCareMessage, care_message_id)
        if not care_message or care_message.status != CareMessageStatus.PENDING:
            await callback.answer("This message has already been reviewed.", show_alert=True)
            return
        care_message.status = CareMessageStatus.FORWARDED
        care_message.reviewed_by_telegram_id = callback.from_user.id
        care_message.reviewed_at = datetime.utcnow()
        await session.commit()

    if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER:
        text = f"Customer message about order #{care_message.order_id}:\n\n{care_message.message}"
        reply_markup = owner_reply_keyboard(care_message.order_id)
    else:
        text = f"Shop owner response about order #{care_message.order_id}:\n\n{care_message.message}"
        reply_markup = None
    await bot.send_message(care_message.recipient_telegram_id, text, reply_markup=reply_markup)
    await callback.message.answer(f"Message for order #{care_message.order_id} approved and sent.")
    await callback.answer("Approved")


@dp.callback_query(F.data.startswith("care:reply:"))
async def reply_to_customer_care_message(callback: CallbackQuery, state: FSMContext) -> None:
    care_message_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        if not await is_customer_care_agent(session, callback.from_user.id):
            await callback.answer("Customer-care access only.", show_alert=True)
            return
        care_message = await session.get(CustomerCareMessage, care_message_id)
        if not care_message or care_message.status != CareMessageStatus.PENDING:
            await callback.answer("This message has already been reviewed.", show_alert=True)
            return

    await state.update_data(care_message_id=care_message_id)
    await state.set_state(CustomerCare.reply)
    recipient = "customer" if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER else "shop owner"
    await callback.message.answer(f"Please send the reply you would like to send to the {recipient}.")
    await callback.answer()


@dp.message(CustomerCare.reply, F.text)
async def send_customer_care_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    async with SessionLocal() as session:
        if not await is_customer_care_agent(session, message.from_user.id):
            await state.clear()
            await message.answer("Customer-care access only.")
            return
        care_message = await session.get(CustomerCareMessage, data["care_message_id"])
        if not care_message or care_message.status != CareMessageStatus.PENDING:
            await state.clear()
            await message.answer("This message has already been reviewed.")
            return
        care_message.status = CareMessageStatus.CARE_REPLIED
        care_message.reviewed_by_telegram_id = message.from_user.id
        care_message.reviewed_at = datetime.utcnow()
        session.add(
            MessageThread(
                order_id=care_message.order_id,
                sender_telegram_id=message.from_user.id,
                message=message.text,
            )
        )
        await session.commit()

    recipient = "customer" if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER else "shop owner"
    await bot.send_message(
        care_message.sender_telegram_id,
        f"Customer care message about order #{care_message.order_id}:\n\n{message.text}",
    )
    await state.clear()
    await message.answer(f"Your reply has been sent to the {recipient}.")


@dp.callback_query(F.data.startswith("review:rating:"))
async def review_rating(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, order_id_raw, rating_raw = callback.data.split(":")
    order_id = int(order_id_raw)
    rating = int(rating_raw)
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if not order or order.client_telegram_id != callback.from_user.id:
            await callback.answer("Sorry, this is not your order.", show_alert=True)
            return

    await state.update_data(order_id=order_id, rating=rating)
    await state.set_state(ReviewFlow.comment)
    await callback.message.answer("Thank you. Please send a short comment about the product, or send - to skip.")
    await callback.answer()


@dp.callback_query(F.data.startswith("review:skip:"))
async def review_skip(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if not order or order.client_telegram_id != callback.from_user.id:
            await callback.answer("Sorry, this is not your order.", show_alert=True)
            return
        session.add(Review(order_id=order.id, client_telegram_id=callback.from_user.id))
        await session.commit()
    await callback.message.answer("No problem. Thank you for ordering from Elite Feast.")
    await callback.answer()


@dp.message(ReviewFlow.comment)
async def review_comment(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    comment = message.text.strip()
    async with SessionLocal() as session:
        review = Review(
            order_id=data["order_id"],
            client_telegram_id=message.from_user.id,
            rating=data["rating"],
            comment=None if comment == "-" else comment,
        )
        session.add(review)
        await session.commit()
    await state.clear()
    await message.answer("Thank you for the review.")
    for admin_id in settings.admin_ids:
        await bot.send_message(
            admin_id,
            f"New review for order #{data['order_id']}: {data['rating']}/5\n{None if comment == '-' else comment}",
        )


@dp.message(Command("message_order"))
async def message_order(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Please send the order number like this: /message_order 15")
        return

    order_id = int(parts[1])
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if not order or order.client_telegram_id != message.from_user.id:
            await message.answer("Sorry, I could not find that order for your Telegram account. Please check the order number and try again.")
            return
        await session.refresh(order, attribute_names=["shop"])
        if not order.shop.owner_telegram_id:
            await message.answer("Sorry, this shop owner is not connected to Telegram yet. Please try again a little later.")
            return

    await state.update_data(order_id=order_id, target="owner")
    await state.set_state(Messaging.waiting_for_message)
    await message.answer("Please send the message you would like us to relay to the shop owner.")


@dp.callback_query(F.data.startswith("message:owner:"))
async def message_owner(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if not order or order.client_telegram_id != callback.from_user.id:
            await callback.answer("Sorry, this is not your order.", show_alert=True)
            return
        await session.refresh(order, attribute_names=["shop"])
        if not order.shop.owner_telegram_id:
            await callback.answer("This shop owner is not connected to Telegram yet.", show_alert=True)
            return

    await state.update_data(order_id=order_id, target="owner")
    await state.set_state(Messaging.waiting_for_message)
    await callback.message.answer("Please send the message you would like us to relay to the shop owner.")
    await callback.answer()


@dp.message(Command("assign_owner"))
async def assign_owner(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Send it like this: /assign_owner 2 123456789")
        return

    shop_id = int(parts[1])
    owner_telegram_id = int(parts[2])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            return
        shop.owner_telegram_id = owner_telegram_id
        await session.commit()

    await message.answer(f"{shop.name} is now assigned to Telegram ID {owner_telegram_id}.")
    await bot.send_message(
        owner_telegram_id,
        f"You have been assigned as the shop owner for {shop.name}. Use /owner and /owner_orders.",
    )


@dp.message(Command("add_shop"))
async def add_shop(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    text = message.text or ""
    name = text[len("/add_shop") :].strip()
    await create_shop(message, name)


async def create_shop(message: Message, name: str) -> None:
    if not name:
        await message.answer("Please send a shop name.")
        return

    async with SessionLocal() as session:
        result = await session.execute(select(Shop).where(Shop.name == name))
        shop = result.scalar_one_or_none()
        if shop:
            await message.answer(f"{shop.name} already exists as shop #{shop.id}.")
            return

        shop = Shop(name=name, is_live=False)
        session.add(shop)
        await session.commit()

    await message.answer(
        f"Added {shop.name} as shop #{shop.id}. It is offline by default.\n"
        f"To add a picture, send /set_shop_photo {shop.id} and then upload the image."
    )


@dp.message(Command("set_shop_photo"))
async def set_shop_photo(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Send it like this: /set_shop_photo 2")
        return

    shop_id = int(parts[1])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            return

    await state.update_data(shop_id=shop_id)
    await state.set_state(AdminShopPhoto.waiting_for_photo)
    await message.answer(f"Upload the picture for shop #{shop_id}.")


@dp.message(AdminShopPhoto.waiting_for_photo, F.photo)
async def save_shop_photo(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        await state.clear()
        return

    data = await state.get_data()
    shop_id = data["shop_id"]
    photo_file_id = message.photo[-1].file_id
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            await state.clear()
            return
        shop.photo_file_id = photo_file_id
        await session.commit()

    await state.clear()
    await message.answer(f"Picture saved for {shop.name}.")


@dp.message(Command("admin_products"))
async def admin_products(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Send it like this: /admin_products 2")
        return

    await send_admin_products(message, int(parts[1]))


async def send_admin_products(message: Message, shop_id: int) -> None:
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            return
        result = await session.execute(
            select(Product).where(Product.shop_id == shop_id).order_by(Product.name)
        )
        products = list(result.scalars())

    if not products:
        await message.answer(f"{shop.name} does not have products yet.")
        return

    lines = [f"Products for {shop.name}:"]
    for product in products:
        state = "available" if product.is_available else "removed"
        photo = "photo" if product.photo_file_id else "no photo"
        cities = product.allowed_cities_csv or "all Russia"
        lines.append(
            f"#{product.id}: {product.name} - {float(product.price_rub):.2f} RUB - {state} - {cities} - {photo}"
        )
    lines.append("")
    lines.append("Use /add_product SHOP_ID, /remove_product PRODUCT_ID, /restore_product PRODUCT_ID, or /set_product_photo PRODUCT_ID.")
    await message.answer("\n".join(lines))


@dp.message(Command("add_product"))
async def add_product_admin(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Send it like this: /add_product 2")
        return

    shop_id = int(parts[1])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            return

    await state.update_data(shop_id=shop_id)
    await state.set_state(AdminProduct.name)
    await message.answer("Send the product name.")


@dp.message(AdminProduct.name)
async def add_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminProduct.price)
    await message.answer("Send the product price in RUB, for example 449.99")


@dp.message(AdminProduct.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Please send a number, for example 449.99")
        return
    if price <= 0:
        await message.answer("The price must be greater than 0.")
        return

    await state.update_data(price=price)
    await state.set_state(AdminProduct.description)
    await message.answer("Send a short description, or send - to skip.")


@dp.message(AdminProduct.description)
async def add_product_description(message: Message, state: FSMContext) -> None:
    description = message.text.strip()
    await state.update_data(description=None if description == "-" else description)
    await state.set_state(AdminProduct.available_cities)
    await message.answer(
        "Where is this product available?\n"
        "Send - for all cities in Russia, or send selected cities separated by commas."
    )


@dp.message(AdminProduct.available_cities)
async def add_product_available_cities(message: Message, state: FSMContext) -> None:
    available_cities = message.text.strip()
    await state.update_data(allowed_cities_csv=None if available_cities == "-" else available_cities)
    await state.set_state(AdminProduct.photo)
    await message.answer("Upload a product photo, or send /skip_photo.")


@dp.message(Command("skip_photo"), AdminProduct.photo)
async def add_product_skip_photo(message: Message, state: FSMContext) -> None:
    await create_product_from_state(message, state, None)


@dp.message(AdminProduct.photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    await create_product_from_state(message, state, message.photo[-1].file_id)


async def create_product_from_state(message: Message, state: FSMContext, photo_file_id) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        await state.clear()
        return

    data = await state.get_data()
    async with SessionLocal() as session:
        product = Product(
            shop_id=data["shop_id"],
            name=data["name"],
            price_rub=data["price"],
            description=data.get("description"),
            allowed_cities_csv=data.get("allowed_cities_csv"),
            photo_file_id=photo_file_id,
            is_available=True,
        )
        session.add(product)
        await session.commit()

    await state.clear()
    await message.answer(f"Added product #{product.id}: {product.name}.")


@dp.message(Command("set_product_photo"))
async def set_product_photo(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Send it like this: /set_product_photo 12")
        return

    product_id = int(parts[1])
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            await message.answer("I could not find that product ID.")
            return

    await state.update_data(product_id=product_id)
    await state.set_state(AdminProductPhoto.waiting_for_photo)
    await message.answer(f"Upload the picture for product #{product_id}.")


@dp.message(AdminProductPhoto.waiting_for_photo, F.photo)
async def save_product_photo(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        await state.clear()
        return

    data = await state.get_data()
    product_id = data["product_id"]
    photo_file_id = message.photo[-1].file_id
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            await message.answer("I could not find that product ID.")
            await state.clear()
            return
        product.photo_file_id = photo_file_id
        await session.commit()

    await state.clear()
    await message.answer(f"Picture saved for {product.name}.")


@dp.message(Command("remove_product"))
async def remove_product(message: Message) -> None:
    await set_product_availability(message, False)


@dp.message(Command("restore_product"))
async def restore_product(message: Message) -> None:
    await set_product_availability(message, True)


async def set_product_availability(message: Message, is_available: bool) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    command = "/restore_product" if is_available else "/remove_product"
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(f"Send it like this: {command} 12")
        return

    product_id = int(parts[1])
    async with SessionLocal() as session:
        product = await session.get(Product, product_id)
        if not product:
            await message.answer("I could not find that product ID.")
            return
        product.is_available = is_available
        await session.commit()

    state_text = "available" if is_available else "removed from the catalog"
    await message.answer(f"{product.name} is now {state_text}.")


@dp.message(Command("admin_shops"))
async def admin_shops(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    async with SessionLocal() as session:
        result = await session.execute(select(Shop).order_by(Shop.name))
        shops = list(result.scalars())

    if not shops:
        await message.answer("No shops found.")
        return

    live_shops_list = [shop for shop in shops if shop.is_live]
    offline_shops = [shop for shop in shops if not shop.is_live]

    lines = ["Live shops:"]
    if live_shops_list:
        for shop in live_shops_list:
            owner = shop.owner_telegram_id or "not assigned"
            photo = "photo" if shop.photo_file_id else "no photo"
            lines.append(
                f"#{shop.id}: {shop.name} - owner: {owner} - {photo} - closes: {format_datetime(shop.orders_close_at)}"
            )
    else:
        lines.append("None")

    lines.append("")
    lines.append("Offline shops:")
    if offline_shops:
        for shop in offline_shops:
            owner = shop.owner_telegram_id or "not assigned"
            photo = "photo" if shop.photo_file_id else "no photo"
            lines.append(
                f"#{shop.id}: {shop.name} - owner: {owner} - {photo} - next live: {format_datetime(shop.live_from)}"
            )
    else:
        lines.append("None")

    lines.append("")
    lines.append("Use /add_shop Name, /set_shop_photo SHOP_ID, /set_live_window SHOP_ID, or /assign_owner SHOP_ID TELEGRAM_ID.")
    await message.answer("\n".join(lines))


@dp.message(Command("admin_shop_cards"))
async def admin_shop_cards(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        await message.answer("Admin only.")
        return

    async with SessionLocal() as session:
        result = await session.execute(select(Shop).order_by(Shop.name))
        shops = list(result.scalars())

    if not shops:
        await message.answer("No shops found.")
        return

    for shop in shops:
        owner = shop.owner_telegram_id or "not assigned"
        live_state = "live" if shop.is_live else "offline"
        caption = f"#{shop.id}: {shop.name}\nStatus: {live_state}\nOwner: {owner}"
        if shop.photo_file_id:
            await message.answer_photo(shop.photo_file_id, caption=caption)
        else:
            await message.answer(caption)


@dp.callback_query(F.data == "shops")
async def shops_callback(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        shops = await live_shops(session)
    await callback.message.edit_text("Please choose an available shop:", reply_markup=shops_keyboard(shops))
    await callback.answer()


@dp.callback_query(F.data.startswith("shop:"))
async def show_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    shop_id = int(callback.data.split(":")[1])
    await state.update_data(shop_id=shop_id)
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        products = await shop_products(session, shop_id)

    if not products:
        await callback.message.edit_text(f"Sorry, {shop.name} has no available products right now. Please check again soon.")
        await callback.answer()
        return

    if any(product.photo_file_id for product in products):
        await callback.message.answer("Thank you. Please have a look through the catalog.")
        await send_product_cards(callback.message, shop, products)
    else:
        await callback.message.edit_text(
            f"{shop.name}\n\nPlease select the products you would like to add to your order:",
            reply_markup=product_keyboard(products, shop_id),
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("add:"))
async def add_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        order = await add_product_to_order(session, callback.from_user.id, product_id)
        order = await draft_order(session, callback.from_user.id, order.shop_id)
    await callback.answer(f"Thank you. Added to order #{order.id}.")
    await send_cart(callback.message, order)


@dp.callback_query(F.data.startswith("cart:decrease:"))
async def decrease_cart_item(callback: CallbackQuery) -> None:
    _, _, order_id_raw, item_id_raw = callback.data.split(":")
    async with SessionLocal() as session:
        order = await update_draft_item_quantity(
            session,
            callback.from_user.id,
            int(order_id_raw),
            int(item_id_raw),
            -1,
        )
    if not order:
        await callback.answer("This cart is no longer available.", show_alert=True)
        return
    await callback.message.edit_text(draft_order_summary(order), reply_markup=cart_keyboard(order))
    await callback.answer("Cart updated")


@dp.callback_query(F.data.startswith("cart:remove:"))
async def remove_cart_item(callback: CallbackQuery) -> None:
    _, _, order_id_raw, item_id_raw = callback.data.split(":")
    async with SessionLocal() as session:
        order = await remove_draft_item(
            session,
            callback.from_user.id,
            int(order_id_raw),
            int(item_id_raw),
        )
    if not order:
        await callback.answer("This cart is no longer available.", show_alert=True)
        return
    await callback.message.edit_text(draft_order_summary(order), reply_markup=cart_keyboard(order))
    await callback.answer("Item removed")


@dp.callback_query(F.data.startswith("cart:clear:"))
async def clear_cart(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        order = await clear_draft_order(session, callback.from_user.id, order_id)
    if not order:
        await callback.answer("This cart is no longer available.", show_alert=True)
        return
    await callback.message.edit_text(draft_order_summary(order), reply_markup=cart_keyboard(order))
    await callback.answer("Cart cleared")


@dp.callback_query(F.data == "cart:ignore")
async def cart_item_label(callback: CallbackQuery) -> None:
    await callback.answer()


@dp.callback_query(F.data.startswith("cart:"))
async def view_cart(callback: CallbackQuery) -> None:
    shop_id = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        order = await draft_order(session, callback.from_user.id, shop_id)
    if not order:
        await callback.message.answer("Your cart is empty. Please add a product before checking out.")
        await callback.answer()
        return
    await callback.message.answer(draft_order_summary(order), reply_markup=cart_keyboard(order))
    await callback.answer()


@dp.callback_query(F.data.startswith("checkout:"))
async def checkout(callback: CallbackQuery, state: FSMContext) -> None:
    shop_id = int(callback.data.split(":")[1])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        now = moscow_now()
        if not shop or not shop.is_live or (shop.orders_close_at and shop.orders_close_at <= now):
            await callback.message.answer("Sorry, this shop is no longer accepting orders right now. Please choose another available shop.")
            await callback.answer()
            return
        order = await draft_order(session, callback.from_user.id, shop_id)
        if not order or not order.items:
            await callback.message.answer("Your cart is empty. Please add a product before checking out.")
            await callback.answer()
            return

    await state.update_data(shop_id=shop_id)
    await state.set_state(Checkout.city)
    await callback.message.answer("Please tell us which city this order is for.")
    await callback.answer()


@dp.message(Checkout.city)
async def checkout_city(message: Message, state: FSMContext) -> None:
    city = message.text.strip()
    data = await state.get_data()
    shop_id = data["shop_id"]
    async with SessionLocal() as session:
        result = await session.execute(
            select(Product.name)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.client_telegram_id == message.from_user.id,
                Order.shop_id == shop_id,
                Order.status == OrderStatus.DRAFT,
            )
        )
        product_names = list(result.scalars())
        products = await shop_products(session, shop_id, city)
        allowed_names = {product.name for product in products}

    unavailable_names = [name for name in product_names if name not in allowed_names]
    if unavailable_names:
        await state.clear()
        await message.answer(
            "Sorry, some items in your cart are not available for that city:\n"
            + "\n".join(f"- {name}" for name in unavailable_names)
            + "\n\nPlease start a new order with /shops. Thank you for your understanding."
        )
        return

    await state.update_data(city=city)
    await state.set_state(Checkout.delivery_address)
    await message.answer("Please send the delivery address.")


@dp.message(Checkout.delivery_address)
async def checkout_address(message: Message, state: FSMContext) -> None:
    await state.update_data(delivery_address=message.text.strip())
    await state.set_state(Checkout.delivery_for)
    await message.answer("Please let us know who this delivery is for.", reply_markup=delivery_for_keyboard())


@dp.callback_query(Checkout.delivery_for, F.data.startswith("delivery_for:"))
async def checkout_delivery_for(callback: CallbackQuery, state: FSMContext) -> None:
    delivery_for = callback.data.split(":")[1]
    await state.update_data(delivery_for=delivery_for)
    if delivery_for == DeliveryFor.SOMEONE_ELSE.value:
        await state.set_state(Checkout.recipient_name)
        await callback.message.answer("Please send the recipient's name.")
    else:
        await request_payment_receipt(callback.message, state)
    await callback.answer()


@dp.message(Checkout.recipient_name)
async def checkout_recipient_name(message: Message, state: FSMContext) -> None:
    await state.update_data(recipient_name=message.text.strip())
    await state.set_state(Checkout.recipient_phone)
    await message.answer("Please send the recipient's phone number.")


@dp.message(Checkout.recipient_phone)
async def checkout_recipient_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(recipient_phone=message.text.strip())
    await request_payment_receipt(message, state)


@dp.message(Checkout.receipt, F.photo)
async def checkout_receipt(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    receipt_file_id = message.photo[-1].file_id
    shop_id = data["shop_id"]

    async with SessionLocal() as session:
        result = await session.execute(
            select(Order).where(
                Order.client_telegram_id == message.from_user.id,
                Order.shop_id == shop_id,
                Order.status == OrderStatus.DRAFT,
            )
        )
        order = result.scalar_one()
        order.city = data["city"]
        order.delivery_address = data["delivery_address"]
        order.delivery_for = DeliveryFor(data["delivery_for"])
        order.recipient_name = data.get("recipient_name")
        order.recipient_phone = data.get("recipient_phone")
        order.receipt_file_id = receipt_file_id
        order.status = OrderStatus.PENDING_RECEIPT_REVIEW
        await session.commit()
        summary = await order_summary(session, order)

    await message.answer("Thank you. We have received your receipt, and your order is now awaiting confirmation.")
    for admin_id in settings.admin_ids:
        await bot.send_photo(
            admin_id,
            receipt_file_id,
            caption=f"Receipt approval needed\n\n{summary}",
            reply_markup=admin_receipt_keyboard(order.id),
        )
    await state.clear()


@dp.callback_query(F.data.startswith("admin:"))
async def admin_action(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer("Admin only", show_alert=True)
        return

    _, action, order_id_raw = callback.data.split(":")
    order_id = int(order_id_raw)
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        await session.refresh(order, attribute_names=["shop"])
        if action == "approve":
            order.status = OrderStatus.PROCESSING
            await session.commit()
            summary = await order_summary(session, order)
            await bot.send_message(order.client_telegram_id, f"Thank you. Your payment for order #{order.id} has been confirmed, and the order is now being processed.")
            if order.shop.owner_telegram_id:
                await bot.send_message(
                    order.shop.owner_telegram_id,
                    f"New approved order\n\n{summary}",
                    reply_markup=owner_order_keyboard(order.id),
                )
            await callback.message.answer(f"Order #{order.id} approved.")
        elif action == "reject":
            order.status = OrderStatus.REJECTED
            await session.commit()
            await bot.send_message(order.client_telegram_id, f"Sorry, we could not confirm the receipt for order #{order.id}. Please contact us if you need any assistance.")
            await callback.message.answer(f"Order #{order.id} rejected.")
    await callback.answer()


@dp.message(Command("owner"))
async def owner_panel(message: Message) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Shop).where(Shop.owner_telegram_id == message.from_user.id))
        shops = list(result.scalars())

    if not shops:
        await message.answer("No shop is assigned to your Telegram account yet.")
        return

    for shop in shops:
        state = "live" if shop.is_live else "offline"
        details = f"{shop.name} is currently {state}."
        if shop.live_from or shop.orders_close_at:
            details += f"\nLive from: {format_datetime(shop.live_from)}\nOrders close: {format_datetime(shop.orders_close_at)}"
        await message.answer(
            details,
            reply_markup=owner_live_keyboard(shop.id, shop.is_live),
        )


@dp.message(Command("set_live_window"))
async def set_live_window(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Send it like this: /set_live_window 2")
        return

    shop_id = int(parts[1])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await message.answer("I could not find that shop ID.")
            return
        if shop.owner_telegram_id != message.from_user.id and message.from_user.id not in settings.admin_ids:
            await message.answer("This is not your shop.")
            return

    await state.update_data(shop_id=shop_id)
    await state.set_state(OwnerLiveWindow.live_from)
    await message.answer("When will this shop go live? Send date/time like 2026-06-05 10:00")


@dp.message(OwnerLiveWindow.live_from)
async def owner_live_from(message: Message, state: FSMContext) -> None:
    live_from = parse_moscow_datetime(message.text)
    if not live_from:
        await message.answer("Please send the date/time like 2026-06-05 10:00")
        return
    await state.update_data(live_from=live_from.isoformat())
    await state.set_state(OwnerLiveWindow.orders_close_at)
    await message.answer("When should order acceptance close? Send date/time like 2026-06-06 18:00")


@dp.message(OwnerLiveWindow.orders_close_at)
async def owner_orders_close_at(message: Message, state: FSMContext) -> None:
    orders_close_at = parse_moscow_datetime(message.text)
    if not orders_close_at:
        await message.answer("Please send the date/time like 2026-06-06 18:00")
        return

    data = await state.get_data()
    live_from = datetime.fromisoformat(data["live_from"])
    if orders_close_at <= live_from:
        await message.answer("The closing time must be after the live time.")
        return

    async with SessionLocal() as session:
        shop = await session.get(Shop, data["shop_id"])
        shop.live_from = live_from
        shop.orders_close_at = orders_close_at
        shop.is_live = live_from <= moscow_now() < orders_close_at
        shop.last_live_prompt_week = current_prompt_week()
        await session.commit()

    await state.clear()
    await message.answer(
        f"{shop.name} schedule saved.\n"
        f"Live from: {format_datetime(shop.live_from)}\n"
        f"Orders close: {format_datetime(shop.orders_close_at)}"
    )


@dp.message(Command("owner_orders"))
async def owner_orders(message: Message) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Order)
            .join(Shop, Shop.id == Order.shop_id)
            .where(
                Shop.owner_telegram_id == message.from_user.id,
                Order.status.in_([OrderStatus.PROCESSING, OrderStatus.DELIVERED]),
            )
            .order_by(Order.created_at.desc())
        )
        orders = list(result.scalars())

        if not orders:
            await message.answer("You do not have any approved orders yet.")
            return

        for order in orders[:10]:
            summary = await order_summary(session, order)
            await message.answer(summary, reply_markup=owner_order_keyboard(order.id))


@dp.callback_query(F.data.startswith("owner:toggle_live:"))
async def owner_toggle_live(callback: CallbackQuery) -> None:
    shop_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your shop.", show_alert=True)
            return
        shop.is_live = not shop.is_live
        if not shop.is_live:
            shop.orders_close_at = None
        await session.commit()
    await callback.message.edit_text(
        f"{shop.name} is now {'live' if shop.is_live else 'offline'}.",
        reply_markup=owner_live_keyboard(shop.id, shop.is_live),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("owner:week_live:"))
async def owner_week_live(callback: CallbackQuery, state: FSMContext) -> None:
    shop_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your shop.", show_alert=True)
            return
    await state.update_data(shop_id=shop_id)
    await state.set_state(OwnerLiveWindow.live_from)
    await callback.message.answer("When will this shop go live this week? Send date/time like 2026-06-05 10:00")
    await callback.answer()


@dp.callback_query(F.data.startswith("owner:week_off:"))
async def owner_week_off(callback: CallbackQuery) -> None:
    shop_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        shop = await session.get(Shop, shop_id)
        if shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your shop.", show_alert=True)
            return
        shop.is_live = False
        shop.live_from = None
        shop.orders_close_at = None
        shop.last_live_prompt_week = current_prompt_week()
        await session.commit()
    await callback.message.answer(f"{shop.name} will stay offline this week.")
    await callback.answer()


@dp.callback_query(F.data.startswith("owner:"))
async def owner_order_action(callback: CallbackQuery) -> None:
    _, action, order_id_raw = callback.data.split(":")
    order_id = int(order_id_raw)
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        await session.refresh(order, attribute_names=["shop"])
        if order.shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your order.", show_alert=True)
            return
        if action == "processing":
            order.status = OrderStatus.PROCESSING
        elif action == "delivered":
            order.status = OrderStatus.DELIVERED
            order.delivered_at = datetime.utcnow()
        await session.commit()
    await bot.send_message(order.client_telegram_id, f"Thank you. The status of order #{order.id} is now: {order.status.value}.")
    for admin_id in settings.admin_ids:
        await bot.send_message(
            admin_id,
            f"Shop owner updated order #{order.id} ({order.shop.name}) to {order.status.value}.",
        )
    await callback.answer("Status updated")


@dp.callback_query(F.data.startswith("message:client:"))
async def message_client(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        await session.refresh(order, attribute_names=["shop"])
        if order.shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your order.", show_alert=True)
            return

    await state.update_data(order_id=order_id, target="client")
    await state.set_state(Messaging.waiting_for_message)
    await callback.message.answer("Send the message to relay.")
    await callback.answer()


@dp.callback_query(F.data.startswith("message:admin:"))
async def message_admin(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = int(callback.data.split(":")[2])
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        await session.refresh(order, attribute_names=["shop"])
        if order.shop.owner_telegram_id != callback.from_user.id:
            await callback.answer("This is not your order.", show_alert=True)
            return

    await state.update_data(order_id=order_id, target="admin")
    await state.set_state(Messaging.waiting_for_message)
    await callback.message.answer("Send the message to relay to the admin.")
    await callback.answer()


@dp.message(Messaging.waiting_for_message)
async def relay_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = data["order_id"]
    requested_target = data.get("target")
    target_ids = []
    care_message = None
    care_agent_ids = []
    async with SessionLocal() as session:
        order = await session.get(Order, order_id)
        if not order:
            await state.clear()
            await message.answer("Sorry, this order is no longer available.")
            return
        await session.refresh(order, attribute_names=["shop"])
        thread_message = MessageThread(
            order_id=order.id,
            sender_telegram_id=message.from_user.id,
            message=message.text,
        )
        session.add(thread_message)

        if requested_target == "admin":
            target_ids = list(settings.admin_ids)
        elif requested_target == "client" and message.from_user.id == order.shop.owner_telegram_id:
            care_message = CustomerCareMessage(
                order_id=order.id,
                sender_telegram_id=message.from_user.id,
                recipient_telegram_id=order.client_telegram_id,
                direction=CareMessageDirection.OWNER_TO_CLIENT,
                message=message.text,
            )
            session.add(care_message)
            care_agent_ids = await active_customer_care_ids(session)
        elif message.from_user.id == order.client_telegram_id and order.shop.owner_telegram_id:
            care_message = CustomerCareMessage(
                order_id=order.id,
                sender_telegram_id=message.from_user.id,
                recipient_telegram_id=order.shop.owner_telegram_id,
                direction=CareMessageDirection.CLIENT_TO_OWNER,
                message=message.text,
            )
            session.add(care_message)
            care_agent_ids = await active_customer_care_ids(session)
        elif requested_target == "client":
            target_ids = [order.client_telegram_id]

        await session.commit()

    if care_message:
        await notify_customer_care_agents(care_message, care_agent_ids)
        if care_message.direction == CareMessageDirection.CLIENT_TO_OWNER:
            await message.answer("Thank you. Your message is now with customer care for review before it is shared with the shop owner.")
        else:
            await message.answer("Your message is now with customer care for review before it is shared with the customer.")
    elif target_ids:
        for target_id in target_ids:
            await bot.send_message(target_id, f"Message about order #{order.id}:\n\n{message.text}")
        await message.answer("Thank you. Your message has been sent.")
    else:
        await message.answer("Sorry, no recipient is assigned yet. Please try again a little later.")
    await state.clear()


async def schedule_loop() -> None:
    while True:
        try:
            now = moscow_now()
            week = current_prompt_week()
            async with SessionLocal() as session:
                result = await session.execute(
                    select(Shop).where(Shop.owner_telegram_id.is_not(None)).order_by(Shop.name)
                )
                shops = list(result.scalars())
                for shop in shops:
                    if shop.live_from and shop.orders_close_at:
                        if not shop.is_live and shop.live_from <= now < shop.orders_close_at:
                            shop.is_live = True
                            await bot.send_message(
                                shop.owner_telegram_id,
                                f"{shop.name} is now live and accepting orders until {format_datetime(shop.orders_close_at)}.",
                            )
                        elif shop.is_live and shop.orders_close_at <= now:
                            shop.is_live = False
                            await bot.send_message(
                                shop.owner_telegram_id,
                                f"{shop.name} is now offline because order acceptance closed at {format_datetime(shop.orders_close_at)}.",
                            )

                    if now.weekday() == 0 and now.hour >= 9 and shop.last_live_prompt_week != week:
                        await bot.send_message(
                            shop.owner_telegram_id,
                            f"Will {shop.name} go live this week?",
                            reply_markup=owner_weekly_prompt_keyboard(shop.id),
                        )
                        shop.last_live_prompt_week = week
                await session.commit()
        except Exception:
            logging.exception("Schedule loop failed")
        await asyncio.sleep(15 * 60)


async def review_request_loop() -> None:
    while True:
        try:
            cutoff = datetime.utcnow() - timedelta(hours=5)
            async with SessionLocal() as session:
                result = await session.execute(
                    select(Order).where(
                        Order.status == OrderStatus.DELIVERED,
                        Order.delivered_at.is_not(None),
                        Order.delivered_at <= cutoff,
                        Order.review_requested_at.is_(None),
                    )
                )
                orders = list(result.scalars())
                for order in orders:
                    await bot.send_message(
                        order.client_telegram_id,
                        f"Thank you for your order. How was order #{order.id}? Please rate the product when you have a moment.",
                        reply_markup=review_rating_keyboard(order.id),
                    )
                    order.review_requested_at = datetime.utcnow()
                await session.commit()
        except Exception:
            logging.exception("Review request loop failed")
        await asyncio.sleep(10 * 60)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Open Elite Feast"),
            BotCommand(command="shops", description="Browse available shops"),
            BotCommand(command="orders", description="View my orders"),
            BotCommand(command="admin", description="Open administrator panel"),
            BotCommand(command="care", description="Open customer-care panel"),
            BotCommand(command="whoami", description="Show my Telegram ID"),
        ]
    )
    asyncio.create_task(schedule_loop())
    asyncio.create_task(review_request_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
