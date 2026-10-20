#!/bin/bash
set -e

echo "Iniciando GPRBR CRM..."

echo "Aguardando banco de dados..."
while ! python -c "import socket; socket.create_connection(('db', 5432), timeout=1)" 2>/dev/null; do
    sleep 1
done
echo "Banco de dados conectado"

echo "Aguardando Redis..."
while ! python -c "import socket; socket.create_connection(('redis', 6379), timeout=1)" 2>/dev/null; do
    sleep 1
done
echo "Redis conectado"

echo "Rodando migrations..."
python manage.py migrate --noinput
echo "Migrations concluidas"

find /tmp -type f -name "*.pyc" -delete 2>/dev/null || true

echo "Iniciando aplicacao..."

exec "$@"
