from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from main import custom_logger


def init_scheduler(scheduled_job: callable, time_interval: int):
    scheduler = AsyncIOScheduler()

    custom_logger.info(
        f"Starting schefuler for task {scheduled_job.__name__} with interval {time_interval} seconds."
    )
    scheduler.start()
    custom_logger.debug("Scheduler started.")
    scheduler.add_job(scheduled_job, IntervalTrigger(seconds=time_interval))
    custom_logger.debug("Job added to scheduler.")

    return scheduler
