"""
WSGI config for UlasKelas project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'UlasKelas.settings')

application = get_wsgi_application()

# Scheduler update course
from courseUpdater import updater as course_updater
from leaderboard_updater import updater as leaderboard_updater
course_updater.start()
leaderboard_updater.start()
 