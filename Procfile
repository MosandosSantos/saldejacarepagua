# Processos (VPS/Heroku-style). No Docker, o entrypoint roda `release` antes da `web`.
release: python manage.py migrate --noinput
web: uvicorn core.asgi:application --host 0.0.0.0 --port ${PORT:-8111} --workers 2
