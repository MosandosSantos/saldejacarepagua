#!/bin/bash
# ============================================
# GPRBR CRM - Inicialização de secrets (VPS/Docker)
# ============================================
# Uso: ./scripts/init-secrets.sh
# - Cria .env a partir de .env.production.example se ainda não existir.
# - Gera DJANGO_SECRET_KEY, JWT_SECRET e CRYPTO_KEY quando estiverem
#   com placeholder/vazios.
# - Pede a senha do Postgres quando ainda for a padrão.
# - Nunca sobrescreve valores já configurados.

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

if [ ! -f .env ]; then
    cp .env.production.example .env
    echo "✅ .env criado a partir de .env.production.example"
fi

set_env() {
    "$PYTHON" - "$1" "$2" <<'PY'
import pathlib
import sys

key, value = sys.argv[1], sys.argv[2]
path = pathlib.Path('.env')
lines = path.read_text(encoding='utf-8').splitlines()
out, found = [], False
for line in lines:
    if line.startswith(key + '='):
        out.append(f'{key}={value}')
        found = True
    else:
        out.append(line)
if not found:
    out.append(f'{key}={value}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
PY
}

get_env() {
    grep -E "^$1=" .env | head -n1 | cut -d= -f2- || true
}

generate_if_placeholder() {
    key="$1"
    length="$2"
    current="$(get_env "$key")"
    case "$current" in
        TROQUE*|change-this*|"")
            set_env "$key" "$("$PYTHON" -c "import secrets; print(secrets.token_urlsafe($length))")"
            echo "✅ $key gerado"
            ;;
        *)
            echo "ℹ️  $key já configurado (mantido)"
            ;;
    esac
}

generate_if_placeholder DJANGO_SECRET_KEY 64
generate_if_placeholder JWT_SECRET 48
generate_if_placeholder CRYPTO_KEY 48

DB_PASS="$(get_env DB_PASSWORD)"
case "$DB_PASS" in
    TROQUE*|securepassword123|"")
        read -rsp "Senha do Postgres (16+ caracteres, apenas letras/números): " NOVA_SENHA
        echo
        NOVA_SENHA="${NOVA_SENHA%$'\r'}"
        if ! [[ "$NOVA_SENHA" =~ ^[A-Za-z0-9]{16,}$ ]]; then
            echo "❌ Senha inválida. Use 16+ caracteres, apenas letras e números."
            exit 1
        fi
        set_env DB_PASSWORD "$NOVA_SENHA"
        echo "✅ DB_PASSWORD definida"
        ;;
    *)
        echo "ℹ️  DB_PASSWORD já configurada (mantida)"
        ;;
esac

echo ""
echo "✅ Secrets prontos."
echo "Agora edite no .env:"
echo "  - CLOUDFLARE_TURNSTILE_SITE_KEY e CLOUDFLARE_TURNSTILE_SECRET_KEY"
echo "  - EMAIL_* (se for usar convites/lembretes)"
echo "  - GPRB_TENANT_ID / GPRB_TENANT_NAME (se aplicável)"
echo ""
echo "Depois rode: docker compose up -d --build"
