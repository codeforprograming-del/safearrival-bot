from telegram import Bot
from db import get_contacts, get_journey_location
import logging

logger = logging.getLogger(__name__)

async def send_alert(bot: Bot, user_id: int, user_name: str,
                     destination: str, journey_id: int = None):

    print(f"🔔 Alert triggered for {user_name} → {destination}")

    contacts = await get_contacts(user_id)
    print(f"📋 Found {len(contacts)} contact(s): {contacts}")

    if not contacts:
        print("❌ No contacts found in database!")
        await bot.send_message(
            chat_id=user_id,
            text="⚠️ Timer expired but you have no trusted contacts.\n"
                 "Add one with /addcontact."
        )
        return

    # Get last known coordinates from DB
    lat, lon = None, None
    if journey_id:
        location_str = await get_journey_location(journey_id)
        print(f"📍 Raw location from DB: {location_str}")
        if location_str:
            try:
                lat, lon = map(float, location_str.split(","))
                print(f"📍 Parsed location: {lat}, {lon}")
            except ValueError:
                print(f"⚠️ Could not parse location: {location_str}")
        else:
            print("⚠️ No location stored in DB for this journey")

    # Build alert message
    text_alert = (
        f"🚨 *Safe Arrival Alert*\n\n"
        f"*{user_name}* started a journey to *{destination}* "
        f"and hasn't checked in safely.\n\n"
        f"⏰ Their check-in timer has expired.\n\n"
        f"Please contact them immediately."
    )

    # Add Google Maps link if location available
    if lat and lon:
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        text_alert += (
            f"\n\n📍 *Last known location:*\n"
            f"[Open in Google Maps]({maps_link})"
        )

    # Send alert to every trusted contact
    for contact_id, contact_name in contacts:
        try:
            print(f"📤 Sending alert to {contact_name} "
                  f"(ID: {contact_id})...")

            # Step 1 — Send text alert with Google Maps link
            await bot.send_message(
                chat_id=contact_id,
                text=text_alert,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            print(f"✅ Text alert sent to {contact_name}!")

            # Step 2 — Send actual location pin on Telegram map
            if lat and lon:
                await bot.send_location(
                    chat_id=contact_id,
                    latitude=lat,
                    longitude=lon
                )
                print(f"📍 Location pin sent to {contact_name}!")
            else:
                await bot.send_message(
                    chat_id=contact_id,
                    text="📍 No location was shared during this journey.\n"
                         "Please try calling them directly."
                )
                print(f"⚠️ No location available for {contact_name}")

        except Exception as e:
            print(f"❌ FAILED to alert {contact_name}: {e}")
            logger.error(f"Failed to alert {contact_name}: {e}")

    # Notify the user themselves
    if lat and lon:
        user_msg = (
            "🚨 *Your journey timer expired!*\n\n"
            "✅ Your trusted contacts have been alerted.\n"
            "📍 Your last known location was shared with them."
        )
    else:
        user_msg = (
            "🚨 *Your journey timer expired!*\n\n"
            "✅ Your trusted contacts have been alerted.\n"
            "⚠️ No location was shared — next time share a "
            "live location for better safety."
        )

    await bot.send_message(
        chat_id=user_id,
        text=user_msg,
        parse_mode="Markdown"
    )
    print("✅ Alert process complete!")