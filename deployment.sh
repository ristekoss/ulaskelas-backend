#!/usr/bin/env bash

# Export env variables
export $(grep -v '^#' .env)

python manage.py collectstatic --no-input && python manage.py migrate && gunicorn --bind 0.0.0.0:${PORT} --workers 2 UlasKelas.wsgi
