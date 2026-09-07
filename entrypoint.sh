#!/bin/bash
set -e

echo "🚀 Iniciando GPRBR CRM..."
echo "================================"

# Validar variáveis de ambiente críticas
if [ -z "$DJANGO_SECRET_KEY" ] || [ "$DJANGO_SECRET_KEY" = "change-this-in-production" ]; then
    echo "⚠️  AVISO: DJANGO_SECRET_KEY não está configurada. Use uma chave segura em produção."
fi

# Esperar banco de dados estar pronto
echo "⏳ Aguardando banco de dados..."
while ! nc -z db 5432; do
    sleep 1
done
echo "✅ Banco de dados conectado"

# Esperar Redis estar pronto
echo "⏳ Aguardando Redis..."
while ! nc -z redis 6379; do
    sleep 1
done
echo "✅ Redis conectado"

# Rodar migrations
echo "📦 Rodando migrations..."
python manage.py migrate --noinput
echo "✅ Migrations concluídas"

# Coletar static files (se não estiver usando servidor externo)
if [ "$STATIC_ROOT_COLLECT" = "True" ]; then
    echo "📦 Coletando static files..."
    python manage.py collectstatic --noinput
    echo "✅ Static files coletados"
fi

# Criar superusuário se não existir (opcional, via variável)
if [ -n "$CREATE_SUPERUSER" = "True" ] && [ -n "$SUPERUSER_EMAIL" ]; then
    echo "👤 Criando superusuário..."
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='${SUPERUSER_EMAIL}').exists():
    User.objects.create_superuser(
        email='${SUPERUSER_EMAIL}',
        password='${SUPERUSER_PASSWORD}',
        nome_completo='Admin',
        is_staff=True,
        is_superuser=True
    )
    print(f"✅ Superusuário criado: {SUPERUSER_EMAIL}")
else:
    print("✅ Superusuário já existe")
EOF
fi

# Limpar arquivos temporários
echo "🧹 Limpando arquivos temporários..."
find /tmp -type f -name "*.pyc" -delete 2>/dev/null || true

echo "================================"
echo "🚀 Iniciando aplicação..."

# Executar comando passado (padrão: runserver)
exec "$@"
