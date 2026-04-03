from apscheduler.schedulers.asyncio import AsyncIOScheduler
from alerts import send_alert
from db import deactivate_journey, get_active_journey
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.start()

async def schedule_journey_check(bot, user_id, user_name,
                                  journey_id, destination, deadline_dt):
    job_id = f"journey_{journey_id}"

    async def fire_alert():
        journey = await get_active_journey(user_id)
        if journey and journey[0] == journey_id:
            logger.warning(f"Journey {journey_id} expired for user {user_id}")
            await deactivate_journey(journey_id)
            await send_alert(
                bot, user_id, user_name,
                destination, journey_id=journey_id
            )

    scheduler.add_job(
        fire_alert,
        trigger="date",
        run_date=deadline_dt,
        id=job_id,
        replace_existing=True
    )
    logger.info(f"Timer set for {deadline_dt} — user {user_id}")

def cancel_journey_job(journey_id):
    job_id = f"journey_{journey_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Cancelled job {job_id}")