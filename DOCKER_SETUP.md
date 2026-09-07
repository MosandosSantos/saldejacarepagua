# 🐳 Docker Setup - GPRBR CRM

Guia completo para rodar a aplicação em Docker.

---

## 📋 Pré-requisitos

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM mínimo (8GB recomendado)
- 20GB disco livre

---

## 🚀 Instalação Rápida

### 1. Inicializar ambiente
```bash
# Clonar repositório (se ainda não fez)
git clone <repo-url> gprbr-crm
cd gprbr-crm

# Criar .env a partir do exemplo
cp .env.example .env

# Editar variáveis (opcional)
nano .env
```

### 2. Gerar secrets automaticamente
```bash
./scripts/init-secrets.sh
```

### 3. Construir e subir
```bash
# Construir imagens
make build

# Subir serviços
make up

# Verificar saúde
make health
```

### 4. Acessar aplicação
```
http://localhost:8000
```

---

## 📦 Estrutura de Serviços

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| **app** | 8000 | Django + FastAPI |
| **db** | 5432 | PostgreSQL 15 |
| **redis** | 6379 | Cache e sessões |
| **nginx** | 80/443 | Reverse Proxy (opcional) |

---

## 🔧 Comandos Principais

```bash
# Iniciar tudo
make up

# Parar tudo
make down

# Ver logs
make logs
make logs-app
make logs-db

# Rodar migrations
make migrate

# Criar superusuário
make createsuperuser

# Rodar testes
make test

# Abrir shell na app
make shell

# Backup do banco
make backup-db

# Ver saúde
make health
```

---

## 🔐 Variáveis de Ambiente

Edite o arquivo `.env` para configurar:

```bash
# Django
DJANGO_SECRET_KEY=sua-chave-segura-aqui
DJANGO_DEBUG=False

# Banco
DB_NAME=gprbr
DB_USER=gprbr
DB_PASSWORD=sua-senha-segura

# Redis
REDIS_URL=redis://redis:6379/0

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-app
```

---

## 🏗️ Dockerfile - O que está incluído

### Stage 1: Builder
- Python 3.13 slim
- Instala todas as dependências do `requirements.txt`
- Compila pacotes C si

### Stage 2: Runtime
- Python 3.13 slim (leve)
- Usuário não-root (`appuser`) para segurança
- Copia apenas o necessário
- Health check configurado

---

## 🌐 Nginx (opcional - modo produção)

Para usar Nginx como reverse proxy:

```bash
# Subir com Nginx
make up-prod

# Acessar
http://localhost (porta 80)
https://localhost (porta 443 - precisa de certificado)
```

### Configurar HTTPS

```bash
# Gerar certificado auto-assinado (para teste)
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/privkey.pem \
  -out certs/fullchain.pem \
  -subj "/CN=localhost"

# Reiniciar Nginx
docker-compose restart nginx
```

---

## 🗄️ PostgreSQL - Detalhes

- **Imagem:** postgres:15-alpine
- **Dados persistentes:** volume `postgres_data`
- **Health check:** pg_isready automático
- **Acesso:** `make dbshell`

### Conexão externa
```bash
# Conectar do host
psql -h localhost -U gprbr -d gprbr

# Com Docker
docker-compose exec db psql -U gprbr -d gprbr
```

---

## 🔴 Redis - Detalhes

- **Imagem:** redis:7-alpine
- **Dados persistentes:** volume `redis_data`
- **Memória máxima:** 256MB (LRU eviction)
- **Acesso:** `make redis-cli`

---

## 📊 Make Commands - Todos

| Comando | Descrição |
|---------|-----------|
| `make help` | Mostra todos os comandos |
| `make build` | Constrói imagens |
| `make up` | Sobe serviços |
| `make up-prod` | Sobe com Nginx |
| `make down` | Para serviços |
| `make restart` | Reinicia |
| `make logs` | Logs gerais |
| `make logs-app` | Logs da app |
| `make logs-db` | Logs do DB |
| `make shell` | Shell na app |
| `make migrate` | Roda migrations |
| `make createsuperuser` | Criar admin |
| `make test` | Rodar testes |
| `make health` | Verificar saúde |
| `make backup-db` | Backup do banco |
| `make clean` | Limpar caches |
| `make clean-all` | Limpar tudo ⚠️ |

---

## 🚨 Troubleshooting

### Container não sobe
```bash
# Ver logs
docker-compose logs app

# Ver health check
docker inspect gprbr-app | grep -A 10 Health

# Entrar no container
docker-compose exec app bash
```

### Banco não conecta
```bash
# Verificar se db está healthy
docker-compose ps

# Aguardar e tentar novamente
docker-compose restart app
```

### Redis não conecta
```bash
# Testar conexão
docker-compose exec redis redis-cli ping

# Ver logs
docker-compose logs redis
```

### Não tem espaço
```bash
# Limpar imagens dangling
docker system prune -f

# Limpar tudo (cuidado!)
docker system prune -a --volumes -f
```

---

## 🎯 Deploy em Produção

### 1. Preparar VPS
```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Configurar `.env` para produção
```bash
# Editar .env
nano .env

# Ajustar:
DJANGO_DEBUG=False
ALLOWED_HOSTS=seu-dominio.com.br
SECURE_SSL_REDIRECT=True
```

### 3. Subir
```bash
# Build
make build

# Subir em modo produção
make up-prod

# Criar superusuário
make createsuperuser
```

### 4. Configurar Nginx com HTTPS
```bash
# Instalar Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obter certificado
sudo certbot --nginx -d seu-dominio.com.br

# Configurar renovacao automatica
sudo crontab -e
# Adicionar:
# 0 0 1 * * certbot renew --quiet
```

---

## 📈 Monitoramento

### Logs em tempo real
```bash
# Todos
make logs

# Apenas app
make logs-app

# Apenas banco
make logs-db
```

### Métricas (opcional - Prometheus)
Adicionar serviço no docker-compose:
```yaml
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
```

---

## ✅ Checklist de Deploy

```bash
# Pré-deploy
[ ] .env configurado com chaves seguras
[ ] DJANGO_DEBUG=False
[ ] ALLOWED_HOSTS configurado
[ ] Senhas fortes nos bancos

# Deploy
[ ] make build
[ ] make up-prod
[ ] make migrate
[ ] make createsuperuser
[ ] make health (tudo OK)

# Pós-deploy
[ ] Acessar http://seu-dominio.com.br
[ ] Fazer login com superusuário
[ ] Verificar envio de emails
[ ] Configurar backup automático
[ ] Monitorar logs
```

---

**Relatório gerado:** Setembro 2026  
**Versão:** 1.0.0  
**Status:** ✅ Pronto para uso
