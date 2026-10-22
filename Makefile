# ============================================
# GPRBR CRM - Makefile de Docker
# ============================================

.PHONY: help build up down restart logs shell migrate createsuperuser test health test-local coverage quality-gate coverage-html

# Variáveis
COMPOSE := docker compose
COMPOSE_FILE := docker-compose.yml
ENV_FILE := .env
DB_NAME ?= saldabritanea
DB_USER ?= gprbr

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
	$(COMPOSE) -f $(COMPOSE_FILE) build --no-cache

up:  ## 🚀  Inicia todos os serviços (DB + Redis + App)
	$(COMPOSE) -f $(COMPOSE_FILE) up -d

up-prod:  ## 🚀  Inicia em modo produção (com Nginx)
	$(COMPOSE) -f $(COMPOSE_FILE) --profile production up -d

down:  ## 🛑  Para todos os serviços
	$(COMPOSE) -f $(COMPOSE_FILE) down

down-volumes:  ## 🛑  Para serviços e remove volumes (⚠️ apaga dados!)
	$(COMPOSE) -f $(COMPOSE_FILE) down -v

restart:  ## 🔄  Reinicia todos os serviços
	$(COMPOSE) -f $(COMPOSE_FILE) restart

logs:  ## 📝  Mostra logs de todos os serviços
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f

logs-app:  ## 📝  Mostra logs da aplicação
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f app

logs-db:  ## 📝  Mostra logs do banco de dados
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f db

logs-redis:  ## 📝  Mostra logs do Redis
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f redis

# ============================================
# Comandos administrativos
# ============================================

shell:  ## 🐚  Abre shell na aplicação
	$(COMPOSE) -f $(COMPOSE_FILE) exec app bash

shell-root:  ## 🐚  Abre shell como root na aplicação
	$(COMPOSE) -f $(COMPOSE_FILE) exec -u root app bash

migrate:  ## 📦  Roda migrations do Django
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python manage.py migrate

makemigrations:  ## 📦  Cria migrations do Django
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python manage.py makemigrations

collectstatic:  ## 📦  Coleta static files
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python manage.py collectstatic --noinput

createsuperuser:  ## 👤  Cria superusuário
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python manage.py createsuperuser

dbshell:  ## 🗄️  Abre shell do PostgreSQL
	$(COMPOSE) -f $(COMPOSE_FILE) exec db psql -U $(DB_USER) -d $(DB_NAME)

redis-cli:  ## 🔴  Abre CLI do Redis
	$(COMPOSE) -f $(COMPOSE_FILE) exec redis redis-cli

# ============================================
# Testes
# ============================================

test:  ## 🧪  Roda testes Django
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python -m django test --settings=core.settings

lint:  ## 🔍  Roda linting (se configurado)
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python -m flake8 .

# ============================================
# Qualidade (local, sem Docker)
# ============================================

PYTHON := .venv/Scripts/python.exe
REGRESSAO := teste/test_rbac_web.py teste/test_gprb_writes.py teste/test_potencia_web.py teste/test_gprb_transaction.py teste/test_loja_web.py teste/test_membro_web.py

test-local:  ## 🧪  Suíte de regressão do módulo GPRB (local, rápido)
	$(PYTHON) -m pytest $(REGRESSAO) -q

coverage:  ## 📊  Suíte completa com medição de cobertura (coverage run)
	$(PYTHON) -m coverage run -m pytest teste/ -q

quality-gate:  ## 🚦  Quality gate: falha se cobertura < fail_under do .coveragerc
	$(PYTHON) -m coverage report

coverage-html:  ## 📈  Gera relatório HTML (htmlcov/index.html)
	$(PYTHON) -m coverage html

# ============================================
# Health checks
# ============================================

health:  ## ❤️  Verifica saúde de todos os serviços
	@echo "Verificando serviços..."
	@echo ""
	@echo "📦 Aplicação:"
	$(COMPOSE) -f $(COMPOSE_FILE) exec app python -c "import urllib.request; print('  ✅ OK' if urllib.request.urlopen('http://localhost:8111/healthz/').status == 200 else '  ❌ Fail')"
	@echo "🗄️  PostgreSQL:"
	$(COMPOSE) -f $(COMPOSE_FILE) exec db pg_isready -U $(DB_USER) -d $(DB_NAME) && echo "  ✅ OK" || echo "  ❌ Fail"
	@echo "🔴  Redis:"
	$(COMPOSE) -f $(COMPOSE_FILE) exec redis redis-cli ping | grep -q PONG && echo "  ✅ OK" || echo "  ❌ Fail"

# ============================================
# Utilitários
# ============================================

clean:  ## 🧹  Remove containers parados e imagens dangling
	docker system prune -f

clean-all:  ## 🧹  Remove tudo (containers, images, volumes, networks) ⚠️!
	docker system prune -a --volumes -f

backup-db:  ## 💾  Backup do banco de dados
	$(COMPOSE) -f $(COMPOSE_FILE) exec db pg_dump -U $(DB_USER) $(DB_NAME) > backup_$$(date +%Y%m%d_%H%M%S).sql

restore-db:  ## 🔄  Restaura backup do banco de dados (usar: make restore-db FILE=backup.sql)
	$(COMPOSE) -f $(COMPOSE_FILE) exec -T db psql -U $(DB_USER) $(DB_NAME) < $(FILE)

push:  ## 📤  Parte para produção (exemplo)
	@echo "📤 Preparando para produção..."
	@echo "  1. Build: make build"
	@echo "  2. Testar: make test"
	@echo "  3. Parar serviço atual"
	@echo "  4. docker compose pull && docker compose up -d"
	@echo "  5. Verificar logs: make logs-app"
