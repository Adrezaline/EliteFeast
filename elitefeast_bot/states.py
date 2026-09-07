from aiogram.fsm.state import State, StatesGroup


class Checkout(StatesGroup):
    city = State()
    delivery_address = State()
    delivery_for = State()
    recipient_name = State()
    recipient_phone = State()
    receipt = State()


class Messaging(StatesGroup):
    waiting_for_message = State()


class AdminShopPhoto(StatesGroup):
    waiting_for_photo = State()


class AdminProduct(StatesGroup):
    name = State()
    price = State()
    description = State()
    available_cities = State()
    photo = State()


class AdminProductPhoto(StatesGroup):
    waiting_for_photo = State()


class OwnerLiveWindow(StatesGroup):
    live_from = State()
    orders_close_at = State()


class ReviewFlow(StatesGroup):
    rating = State()
    comment = State()
