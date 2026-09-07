# Elite Feast Telegram Bot

Telegram bot for EliteFeast.ru marketplace orders, shop availability, receipt approval, owner notifications, and order status tracking.

## What It Does

- Shows only shops that are live for ordering.
- Lets shop owners switch their shop live/offline from Telegram.
- Shows each live shop catalog with city/product availability rules.
- Collects cart items, recipient type, delivery address, city, and receipt screenshot.
- Sends receipt/order approval requests to the marketplace admin.
- Notifies shop owners only after admin approval.
- Tracks order statuses: pending receipt review, processing, delivered, rejected.
- Relays client/shop-owner messages inside Telegram without exposing phone numbers.

## Tech Stack

- Python 3.11+
- aiogram 3
- SQLAlchemy
- SQLite by default, PostgreSQL-ready through `DATABASE_URL`

## Quick Start

1. Create a Telegram bot with BotFather and copy the token.
2. Copy `.env.example` to `.env`.
3. Fill in:
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_TELEGRAM_IDS`
4. Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

5. Seed sample Elite Feast shops/products:

```powershell
python -m elitefeast_bot.seed
```

6. Run the bot:

```powershell
python -m elitefeast_bot.main
```

## Recommended Production Setup

Use PostgreSQL for production:

```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/elitefeast_bot
```

Run the bot on a VPS with `systemd`, Docker, or another process manager. Keep `.env` private.

## Render Deployment

Do not upload or commit `.env`. In the Render service dashboard, add these values under **Environment**:

- `TELEGRAM_BOT_TOKEN`
- `ADMIN_TELEGRAM_IDS`
- `DATABASE_URL`
- `WOOCOMMERCE_BASE_URL` (optional)
- `WOOCOMMERCE_CONSUMER_KEY` (optional)
- `WOOCOMMERCE_CONSUMER_SECRET` (optional)

Render provides these to the app as environment variables, which the bot reads with `os.getenv(...)`. The local `.env` file is used only when developing on your computer, and it is excluded by `.gitignore`.

Use a Render PostgreSQL database for `DATABASE_URL`; the default SQLite file is not persistent across Render deployments or restarts. Change Render's PostgreSQL URL prefix from `postgresql://` to `postgresql+asyncpg://` before saving it.

## WooCommerce Integration

The bot currently uses its own database so shop owners can manage availability directly in Telegram. The `elitefeast_bot/integrations/woocommerce.py` file is a placeholder for syncing shops/products from EliteFeast.ru once WooCommerce API credentials are available.

You will need:

- WooCommerce consumer key
- WooCommerce consumer secret
- Product/vendor ownership mapping
