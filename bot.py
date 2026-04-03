import asyncio
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    filters
)
from dotenv import load_dotenv
import os

from db import init_db
from scheduler import start_scheduler
from handlers import (
    start, help_cmd, go, safe, status,
    add_contact_cmd, set_safe_word_cmd,
    handle_location, handle_edited_location,
    handle_message, list_contacts,
    handle_remove_contact
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/safearrival.log"),
        logging.StreamHandler()
    ]
)

async def main():
    await init_db()
    start_scheduler()

    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         help_cmd))
    app.add_handler(CommandHandler("go",           go))
    app.add_handler(CommandHandler("safe",         safe))
    app.add_handler(CommandHandler("status",       status))
    app.add_handler(CommandHandler("addcontact",   add_contact_cmd))
    app.add_handler(CommandHandler("contacts",     list_contacts))
    app.add_handler(CommandHandler("removecontact",list_contacts))
    app.add_handler(CommandHandler("setsafeword",  set_safe_word_cmd))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(
        MessageHandler(
            filters.UpdateType.EDITED_MESSAGE & filters.LOCATION,
            handle_edited_location
        )
    )
    app.add_handler(CallbackQueryHandler(handle_remove_contact))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("✅ Safe Arrival bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())