# ============================================
# GPRBR CRM - Makefile de Docker
# ============================================

.PHONY: help build up down restart logs shell migrate createsuperuser test health

# Variáveis
COMPOSE_FILE := docker-compose.yml
ENV_FILE := .env

# ============================================
# Comandos principais
# ============================================

help:  ## ⚠️  Mostra este help
	@echo "🚀 GPRBR CRM - Comandos Docker"
	@echo ""
	@echo "Uso: make [comando]"
	@echo ""
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

build:  ## 🏗️  Constrói as imagens Docker
	docker-compose -f $(COMPOSE_FILE) build --no-cache

up:  ## 🚀  Inicia todos os serviços (DB + Redis + App)
	docker-compose -f $(COMPOSE_FILE) up -d

up-prod:  ## 🚀  Inicia em modo produção (com Nginx)
	docker-compose -f $(COMPOSE_FILE) --profile production up -d

down:  ## 🛑  Para todos os serviços
	docker-compose -f $(COMPOSE_FILE) down

down-volumes:  ## 🛑  Para serviços e remove volumes (⚠️ apaga dados!)
	docker-compose -f $(COMPOSE_FILE) down -v

restart:  ## 🔄  Reinicia todos os serviços
	docker-compose -f $(COMPOSE_FILE) restart

logs:  ## 📝  Mostra logs de todos os serviços
	docker-compose -f $(COMPOSE_FILE) logs -f

logs-app:  ## 📝  Mostra logs da aplicação
	docker-compose -f $(COMPOSE_FILE) logs -f app

logs-db:  ## 📝  Mostra logs do banco de dados
	docker-compose -f $(COMPOSE_FILE) logs -f db

logs-redis:  ## 📝  Mostra logs do Redis
	docker-compose -f $(COMPOSE_FILE) logs -f redis

# ============================================
# Comandos administrativos
# ============================================

shell:  ## 🐚  Abre shell na aplicação
	docker-compose -f $(COMPOSE_FILE) exec app bash

shell-root:  ## 🐚  Abre shell como root na aplicação
	docker-compose -f $(COMPOSE_FILE) exec -u root app bash

migrate:  ## 📦  Roda migrations do Django
	docker-compose -f $(COMPOSE_FILE) exec app python manage.py migrate

makemigrations:  ## 📦  Cria migrations do Django
	docker-compose -f $(COMPOSE_FILE) exec app python manage.py makemigrations

collectstatic:  ## 📦  Coleta static files
	docker-compose -f $(COMPOSE_FILE) exec app python manage.py collectstatic --noinput

createsuperuser:  ## 👤  Cria superusuário
	docker-compose -f $(COMPOSE_FILE) exec app python manage.py createsuperuser

dbshell:  ## 🗄️  Abre shell do PostgreSQL
	docker-compose -f $(COMPOSE_FILE) exec db psql -U gprbr -d gprbr

redis-cli:  ## 🔴  Abre CLI do Redis
	docker-compose -f $(COMPOSE_FILE) exec redis redis-cli

# ============================================
# Testes
# ============================================

test:  ## 🧪  Roda testes Django
	docker-compose -f $(COMPOSE_FILE) exec app python -m django test --settings=core.settings

lint:  ## 🔍  Roda linting (se configurado)
	docker-compose -f $(COMPOSE_FILE) exec app python -m flake8 .

# ============================================
# Health checks
# ============================================

health:  ## ❤️  Verifica saúde de todos os serviços
	@echo "Verificando serviços..."
	@echo ""
	@echo "📦 Aplicação:"
	docker-compose -f $(COMPOSE_FILE) exec app python -c "import urllib.request; print('  ✅ OK' if urllib.request.urlopen('http://localhost:8000/health/').status == 200 else '  ❌ Fail')"
	@echo "🗄️  PostgreSQL:"
	docker-compose -f $(COMPOSE_FILE) exec db pg_isready -U gprbr && echo "  ✅ OK" || echo "  ❌ Fail"
	@echo "🔴  Redis:"
	docker-compose -f $(COMPOSE_FILE) exec redis redis-cli ping | grep -q PONG && echo "  ✅ OK" || echo "  ❌ Fail"

# ============================================
# Utilitários
# ============================================

clean:  ## 🧹  Remove containers parados e imagens dangling
	docker system prune -f

clean-all:  ## 🧹  Remove tudo (containers, images, volumes, networks) ⚠️!
	docker system prune -a --volumes -f

backup-db:  ## 💾  Backup do banco de dados
	docker-compose -f $(COMPOSE_FILE) exec db pg_dump -U gprbr gprbr > backup_$$(date +%Y%m%d_%H%M%S).sql

restore-db:  ## 🔄  Restaura backup do banco de dados (usar: make restore-db FILE=backup.sql)
	docker-compose -f $(COMPOSE_FILE) exec -T db psql -U gprbr gprbr < $(FILE)

push:  ## 📤  Parte para produção (exemplo)
	@echo "📤 Preparando para produção..."
	@echo "  1. Build: make build"
	@echo "  2. Testar: make test"
	@echo "  3. Parar serviço atual"
	@echo "  4. docker-compose pull && docker-compose up -d"
	@echo "  5. Verificar logs: make logs-app"
