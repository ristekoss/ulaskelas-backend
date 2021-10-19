from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from courseUpdater import courseApi

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        courseApi.update_courses,
        trigger=IntervalTrigger(days=14),  # Every 2 weeks
        id="update_courses",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()