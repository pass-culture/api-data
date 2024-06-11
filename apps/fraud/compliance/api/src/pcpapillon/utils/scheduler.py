from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


def init_scheduler(scheduled_job: callable, time_interval: int):
    scheduler = AsyncIOScheduler()
    scheduler.start()
    scheduler.add_job(scheduled_job, IntervalTrigger(seconds=time_interval))

    return scheduler
