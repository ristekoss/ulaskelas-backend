from datetime import datetime
from django.db import transaction
from django.db.models import Count, Sum
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from main.models import Profile, Review

def update_leaderboard():
    users = Profile.objects.all()

    for user in users:
        likes_count = Review.objects.filter(user=user).filter(is_active=True).annotate(likes_count=Count('reviewlike')).aggregate(Sum('likes_count'))['likes_count__sum']
        user.likes_count = likes_count

    with transaction.atomic():
        for user in users:
            user.save()

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        update_leaderboard,
        trigger=IntervalTrigger(minutes=5),  # Every 5 minutes
        id="update_courses",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()