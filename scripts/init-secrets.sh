#!/bin/bash
# ============================================
# GPRBR CRM - Script de Inicialização
# ============================================
# Uso: ./scripts/init-secrets.sh

set -e

echo "🚀 Inicializando GPRBR CRM com Docker..."
echo "============================================"

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo "📝 Criando arquivo .env a partir do exemplo..."
    cp .env.example .env
    echo "✅ Arquivo .env criado"
else
    echo "✅ Arquivo .env já existe"
fi

# Gerar Django secret key se não estiver configurado
if grep -q "^DJANGO_SECRET_KEY=change-this-in-production" .env 2>/dev/null; then
    echo "🔐 Gerando Django SECRET_KEY..."
    SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || echo "django-insecure-$(openssl rand -hex 32)")
    sed -i "s/^DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$SECRET_KEY/" .env
    echo "✅ SECRET_KEY atualizada"
fi

# Pedir senha do banco se estiver padrão
if grep -q "^DB_PASSWORD=securepassword123" .env 2>/dev/null; then
    read -p "🔑 Definir senha do banco (padrão: securepassword123): " DB_PASS
    if [ -n "$DB_PASS" ]; then
        sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$DB_PASS/" .env
        sed -i "s/^DATABASE_URL=.*@db:.*/DATABASE_URL=postgresql:\/\/gprbr:$DB_PASS@db:5432\/gprbr/" .env
        echo "✅ Senha do banco atualizada"
    fi
fi

echo ""
echo "============================================"
echo "✅ Configuração concluída!"
echo ""
echo "Próximos passos:"
echo "  1. Editar .env se necessário"
echo "  2. Rodar: make build"
echo "  3. Rodar: make up"
echo "  4. Acessar: http://localhost:8000"
echo ""
