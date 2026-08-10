# Railway — processos. A linha `release` roda ANTES de subir a `web` em cada deploy.
release: python manage.py migrate --noinput
web: uvicorn core.asgi:application --host 0.0.0.0 --port $PORT --workers 2
