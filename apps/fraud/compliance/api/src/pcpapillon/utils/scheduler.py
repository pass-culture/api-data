from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from main import custom_logger
from pcpapillon.utils.env_vars import (
    isAPI_LOCAL,
)


def init_scheduler(scheduled_job: callable, time_interval: int):
    scheduler = AsyncIOScheduler()
    if isAPI_LOCAL:
        custom_logger.info("Disabling scheduler for local API")
        return scheduler

    scheduler.start()
    scheduler.add_job(scheduled_job, IntervalTrigger(seconds=time_interval))

    return scheduler
