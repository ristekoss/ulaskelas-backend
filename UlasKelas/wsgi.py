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

# TODO: will use this later
# from courseUpdater import updater
# updater.start()

# For testing and populate courses data
# from courseUpdater import courseApi
# courseApi.update_courses()