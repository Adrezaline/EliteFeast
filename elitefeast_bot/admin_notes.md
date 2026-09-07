# Admin Setup Notes

## Assigning Shop Owners

After a shop owner sends `/start` to the bot, add their Telegram ID to the relevant shop row in the database:

```sql
UPDATE shops
SET owner_telegram_id = 123456789
WHERE name = 'D Cake House';
```

For production, this should become an admin-only Telegram command such as:

```text
/assign_owner "D Cake House" 123456789
```

The implemented command uses the shop ID:

```text
/assign_owner 2 123456789
```

## Suggested Bot Commands

Register these with BotFather:

```text
start - Show available Elite Feast shops
shops - Browse live shops and products
orders - Check your order statuses
message_order - Message the shop owner about an order
owner - Shop owner availability panel
owner_orders - Shop owner approved order inbox
set_live_window - Owner/Admin: set when a shop goes live and closes orders
admin_shops - Admin: list shop IDs and owner assignments
admin_shop_cards - Admin: preview shops with pictures
add_shop - Admin: add a new shop by name
set_shop_photo - Admin: attach a Telegram photo to a shop
assign_owner - Admin: assign a Telegram user to a shop
admin_products - Admin: list products for a shop
add_product - Admin: add a product to a shop
set_product_photo - Admin: attach a Telegram photo to a product
remove_product - Admin: hide a product from the catalog
restore_product - Admin: make a hidden product available again
skip_photo - Admin: skip product photo while adding a product
```

## Product Management

Recommended flow:

```text
/admin_shops
/admin_products 2
/add_product 2
```

The bot will ask for product name, price, description, availability cities, and photo.

Products are removed by marking them unavailable:

```text
/remove_product 12
```

This preserves old order history. To bring it back:

```text
/restore_product 12
```

## Payment Flow

The bot does not process money directly. It expects the client to pay externally, upload a receipt screenshot, and wait for admin approval.

## Weekly Shop Availability

Every Monday after 09:00 Moscow time, the bot asks each assigned shop owner if their shop will go live that week.

Owners can answer from the buttons or use:

```text
/set_live_window 2
```

The bot asks for:

```text
2026-06-05 10:00
2026-06-06 18:00
```

The first time is when the shop goes live. The second time is when order acceptance closes. The bot automatically takes the shop offline after the close time.

## Reviews

Five hours after an order is marked delivered, the bot asks the customer for a 1-5 rating and optional comment.

## City Availability

Each product can be available to all cities in Russia or only selected cities.

When adding a product, send:

```text
-
```

for all cities in Russia, or send selected cities:

```text
Moscow,Saint Petersburg
```

Selected-city products are hidden when the client enters any city not on that list.
