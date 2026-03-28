#!/bin/sh
set -e

# Keep startup fast for Railway healthcheck.
# Build already runs collectstatic.
# Run migrations only when explicitly enabled.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60
