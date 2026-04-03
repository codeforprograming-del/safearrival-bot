from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from db import (
    add_user, add_contact, create_journey,
    deactivate_journey, get_active_journey,
    get_contacts, get_safe_word, set_safe_word,
    update_location, get_contacts_with_id,
    delete_contact, delete_all_contacts
)
from scheduler import schedule_journey_check, cancel_journey_job
from alerts import send_alert
import logging

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await add_user(user.id, user.first_name)
    await update.message.reply_text(
        f"🛡️ Welcome to *Safe Arrival*, {user.first_name}!\n\n"
        "I silently watch over your solo journeys.\n\n"
        "*Quick setup:*\n"
        "1️⃣ /addcontact — add a trusted contact\n"
        "2️⃣ /setsafeword — set your secret distress word\n"
        "3️⃣ /go — start a journey timer\n"
        "4️⃣ /safe — check in when you arrive\n"
        "5️⃣ /status — see your current journey\n"
        "6️⃣ /contacts — view and remove contacts\n\n"
        "Type /help for all commands.",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Safe Arrival — Commands*\n\n"
        "/go <destination> <minutes> — start journey timer\n"
        "/safe — confirm safe arrival\n"
        "/status — check active journey\n"
        "/addcontact <id> <name> — add trusted contact\n"
        "/contacts — view and remove contacts\n"
        "/setsafeword <word> — set secret distress word\n"
        "/help — show this message",
        parse_mode="Markdown"
    )

async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /go <destination> <minutes>\n"
            "Example: /go home 25"
        )
        return

    destination = context.args[0]
    try:
        minutes = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "⚠️ Minutes must be a number.\nExample: /go home 25"
        )
        return

    if minutes < 1 or minutes > 480:
        await update.message.reply_text(
            "⚠️ Minutes must be between 1 and 480."
        )
        return

    user = update.effective_user
    existing = await get_active_journey(user.id)
    if existing:
        await update.message.reply_text(
            "⚠️ You already have an active journey.\n"
            "Type /safe to end it first."
        )
        return

    deadline_dt = datetime.now() + timedelta(minutes=minutes)
    journey_id = await create_journey(
        user.id, destination, deadline_dt.timestamp()
    )

    await schedule_journey_check(
        context.bot, user.id, user.first_name,
        journey_id, destination, deadline_dt
    )

    await update.message.reply_text(
        f"🛡️ *Journey started!*\n\n"
        f"📍 Destination: *{destination}*\n"
        f"⏱️ Deadline: *{minutes} minutes*\n\n"
        f"👉 Share your *live location* now for real-time tracking.\n\n"
        f"Type /safe when you arrive safely.",
        parse_mode="Markdown"
    )

async def safe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    journey = await get_active_journey(user.id)

    if not journey:
        await update.message.reply_text(
            "No active journey found.\nStart one with /go."
        )
        return

    journey_id, destination, _ = journey
    await deactivate_journey(journey_id)
    cancel_journey_job(journey_id)

    # Reset location flags
    context.user_data["location_confirmed"] = False
    context.user_data["live_location_chat_id"] = None
    context.user_data["live_location_msg_id"] = None

    await update.message.reply_text(
        f"✅ *Safe arrival confirmed!*\n\n"
        f"Glad you made it to *{destination}* safely. Journey ended. 🎉",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    journey = await get_active_journey(user.id)
    contacts = await get_contacts(user.id)
    safe_word = await get_safe_word(user.id)

    if journey:
        j_id, dest, deadline_ts = journey
        remaining = max(0, int(
            (deadline_ts - datetime.now().timestamp()) / 60
        ))
        journey_text = (
            f"🟡 Active journey to *{dest}*\n"
            f"   ⏱️ *{remaining} min* remaining"
        )
    else:
        journey_text = "🟢 No active journey"

    contact_list = "\n".join(
        [f"  • {name}" for _, name in contacts]
    ) or "  None added yet. Use /addcontact"

    await update.message.reply_text(
        f"*Safe Arrival Status*\n\n"
        f"{journey_text}\n\n"
        f"👥 Trusted contacts:\n{contact_list}\n\n"
        f"🔐 Safe word: `{safe_word}`",
        parse_mode="Markdown"
    )

async def add_contact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addcontact <telegram_user_id> <name>\n"
            "Example: /addcontact 123456789 Priya\n\n"
            "To get someone's Telegram ID ask them to message @userinfobot"
        )
        return
    try:
        contact_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ User ID must be a number.")
        return

    name = " ".join(context.args[1:])
    await add_contact(update.effective_user.id, contact_id, name)
    await update.message.reply_text(
        f"✅ *{name}* added as a trusted contact.",
        parse_mode="Markdown"
    )

async def set_safe_word_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /setsafeword <word>\n"
            "Example: /setsafeword mango\n\n"
            "Typing this word anytime instantly alerts your contacts."
        )
        return
    word = context.args[0].lower()
    await set_safe_word(update.effective_user.id, word)
    await update.message.reply_text(
        f"🔐 Safe word set to: *{word}*\n\n"
        "Type it anytime to silently alert your contacts.",
        parse_mode="Markdown"
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    location = update.message.location
    if not location:
        return

    journey = await get_active_journey(user.id)
    if not journey:
        await update.message.reply_text(
            "📍 Location received but no active journey.\n"
            "Start one with /go <destination> <minutes>."
        )
        return

    # Save coordinates IMMEDIATELY to database
    await update_location(user.id, location.latitude, location.longitude)
    print(f"📍 Initial location saved: "
          f"{location.latitude}, {location.longitude}")

    is_live = location.live_period is not None

    if is_live:
        # Store live location message details
        context.user_data["live_location_chat_id"] = update.message.chat_id
        context.user_data["live_location_msg_id"] = update.message.message_id

        if not context.user_data.get("location_confirmed"):
            context.user_data["location_confirmed"] = True
            await update.message.reply_text(
                "📡 *Live location linked!*\n\n"
                "✅ Your real-time coordinates are being tracked.\n"
                f"📌 Current position saved:\n"
                f"`{location.latitude}, {location.longitude}`\n\n"
                "Trusted contacts will receive your exact location "
                "if your timer expires without /safe check-in.",
                parse_mode="Markdown"
            )
    else:
        # Static location saved but warn user
        await update.message.reply_text(
            "📍 *Static location saved!*\n\n"
            f"📌 Position saved:\n"
            f"`{location.latitude}, {location.longitude}`\n\n"
            "⚠️ For better safety share a *Live Location* — "
            "it updates your position in real time.",
            parse_mode="Markdown"
        )

async def handle_edited_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires on every live location coordinate update from Telegram."""
    user = update.effective_user
    location = update.edited_message.location
    if not location:
        return

    # Silently update coordinates in DB
    await update_location(user.id, location.latitude, location.longitude)
    print(f"📍 Live location updated for {user.first_name}: "
          f"{location.latitude}, {location.longitude}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    user = update.effective_user
    safe_word = await get_safe_word(user.id)

    if text == safe_word:
        journey = await get_active_journey(user.id)
        destination = journey[1] if journey else "unknown location"
        journey_id = journey[0] if journey else None
        await send_alert(
            context.bot, user.id, user.first_name,
            destination, journey_id=journey_id
        )
        await update.message.reply_text(
            "🚨 *Distress signal sent* to your trusted contacts!\n\n"
            "Help is on the way. Stay safe.",
            parse_mode="Markdown"
        )

async def list_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contacts = await get_contacts_with_id(user.id)

    if not contacts:
        await update.message.reply_text(
            "👥 *Your Trusted Contacts*\n\n"
            "No contacts added yet.\n\n"
            "Add one with:\n`/addcontact <telegram_id> <name>`",
            parse_mode="Markdown"
        )
        return

    text = "👥 *Your Trusted Contacts*\n\n"
    for idx, (row_id, contact_id, name) in enumerate(contacts, 1):
        text += f"{idx}. *{name}*\n"
        text += f"   🆔 Telegram ID: `{contact_id}`\n\n"
    text += "Tap a button below to remove a contact:"

    keyboard = []
    for row_id, contact_id, name in contacts:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 Remove {name}",
                callback_data=f"remove_{row_id}_{name}"
            )
        ])

    if len(contacts) > 1:
        keyboard.append([
            InlineKeyboardButton(
                "❌ Remove ALL contacts",
                callback_data="remove_all"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("✅ Done", callback_data="cancel_remove")
    ])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_remove_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data

    if data == "cancel_remove":
        await query.edit_message_text("✅ No changes made.")
        return

    if data == "remove_all":
        await delete_all_contacts(user.id)
        await query.edit_message_text(
            "✅ *All contacts removed successfully!*\n\n"
            "Add new ones with `/addcontact <telegram_id> <name>`",
            parse_mode="Markdown"
        )
        return

    if data.startswith("remove_"):
        parts = data.split("_", 2)
        row_id = int(parts[1])
        name = parts[2]
        await delete_contact(row_id)

        contacts = await get_contacts_with_id(user.id)

        if not contacts:
            await query.edit_message_text(
                f"🗑 *{name}* removed successfully!\n\n"
                "No more trusted contacts.\n"
                "Add one with `/addcontact <telegram_id> <name>`",
                parse_mode="Markdown"
            )
            return

        text = f"🗑 *{name}* removed successfully!\n\n"
        text += "👥 *Remaining Contacts:*\n\n"
        for idx, (r_id, contact_id, c_name) in enumerate(contacts, 1):
            text += f"{idx}. *{c_name}*\n"
            text += f"   🆔 Telegram ID: `{contact_id}`\n\n"
        text += "Tap to remove more:"

        keyboard = []
        for r_id, contact_id, c_name in contacts:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 Remove {c_name}",
                    callback_data=f"remove_{r_id}_{c_name}"
                )
            ])

        if len(contacts) > 1:
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Remove ALL contacts",
                    callback_data="remove_all"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("✅ Done", callback_data="cancel_remove")
        ])

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )