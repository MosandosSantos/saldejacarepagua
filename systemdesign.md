# System Design — GPRBRCRM (padrão replicável)

> Documento de arquitetura do projeto `gprbr` (Django + FastAPI + PostgreSQL).
> Serve de blueprint para replicar o mesmo padrão em outros projetos
> (ex.: gprbrCRM). Para um projeto novo, troque apenas os nomes de
> tema e o esquema de dados — a estrutura, as camadas e os testes são os mesmos.

---

## 1. Visão geral

Sistema CRM de clínica (GPRBRCRM) construído em duas camadas:

- **Django** = fonte de verdade dos dados (ORM, migrations, configuração central).
  Não expõe HTTP — serve apenas como ORM/configuração.
- **FastAPI** = camada REST (`/api/v1`), consumida pelo frontend (HTML/JS).

Banco de dados: **PostgreSQL** local (banco `gprbr`, já existente antes do
projeto — o Django adota as tabelas sem recriar dados).

---

## 2. Stack e versões

| Item | Versão | Observação |
|---|---|---|
| Python | 3.13.5 | venv em `.venv/` |
| Django | 5.2.x | LTS, usado só como ORM/config |
| FastAPI | 0.141.x | servidor: uvicorn |
| Pydantic | 2.13.x | schemas (DTOs) |
| psycopg | 3.3.x | driver PostgreSQL (`psycopg[binary]`) |
| pytest + pytest-django | 9.x / 4.12 | testes da API |
| httpx | 0.28.x | TestClient do FastAPI |

`requirements.txt`:

```
Django>=5.2,<5.3
fastapi>=0.115
uvicorn[standard]
pydantic>=2.7
psycopg[binary]>=3.2
python-dotenv>=1.0
pytest>=8
pytest-django>=4.8
httpx>=0.27
```

---

## 3. Estrutura de diretórios

```
projeto/
├── core/                  # Configuração central do Django
│   ├── settings.py        #   lê credenciais do .env (PGUSER, PGPASSWORD, ...)
│   ├── urls.py            #   vazio (as APIs ficam no FastAPI, não aqui)
│   ├── wsgi.py / asgi.py
│   └── __init__.py
├── <app1>/                # Módulo isolado por tema (ex.: contatos)
│   ├── models.py          #   espelha tabela existente (Meta.db_table)
│   ├── migrations/        #   criadas via makemigrations
│   ├── tests.py           #   testes unitários Django (TestCase)
│   └── apps.py
├── <app2>/                # Outro tema (ex.: tarefas)
│   └── ...
├── api/                   # FastAPI — camada HTTP
│   ├── main.py            #   create_app() + CORS + router; bootstrap do Django
│   └── v1/
│       ├── router.py      #   prefixo /api/v1, agrega sub-routers por tema
│       ├── schemas/       #   DTOs Pydantic (entrada/saída)
│       ├── repositories/  #   acesso a dados (Django ORM isolado aqui)
│       ├── services/      #   regras de negócio (recebem repository via DI)
│       └── routes/        #   endpoints HTTP finos (só request/response)
├── teste/                 # Suíte pytest da API (testpaths = teste)
│   ├── conftest.py        #   fixture `client` (TestClient + fechar conexões)
│   ├── test_<tema>_api.py
├── manage.py
├── pytest.ini
├── requirements.txt
└── .env                   # credenciais (não versionar)
```

### Regras da estrutura

1. **`core/`** = só configuração do Django (settings, urls). Sem models.
2. **Apps por tema**: cada domínio (contatos, tarefas, ...) é um app Django separado.
3. **`api/v1/`** = versão da API; a versão faz parte do prefixo da URL.
4. **Fluxo de uma requisição**: `route` (HTTP) → `service` (negócio) → `repository` (ORM) → banco.
   A route nunca consulta o ORM diretamente; o service nunca sabe de HTTP; o repository não tem regra de negócio.

---

## 4. Arquitetura em camadas (SOLID / Clean)

### 4.1 Schemas (DTOs) — `api/v1/schemas/<tema>.py`

- Entrada e saída separadas (`ContatoPayload` vs `ContatoOut`).
- Validação na entrada: `nome: str = Field(min_length=1)`, `valor: float = Field(ge=0)`.
- Saída com `model_config = {'from_attributes': True}` para serializar models direto.

```python
class ContatoPayload(BaseModel):
    nome: str = Field(min_length=1)
    empresa: str = ''
    ...
    valor: float = Field(default=0, ge=0)

class ContatoOut(BaseModel):
    id: int
    nome: str
    ...
    updated_at: datetime
    model_config = {'from_attributes': True}
```

### 4.2 Repositories — `api/v1/repositories/<tema>_repository.py`

- Único lugar que conhece o Django ORM.
- Métodos por operação: `list_all()`, `get(id)`, `create(dict)`, `update(obj, dict)`, `delete(id) -> bool`.

```python
class ContatoRepository:
    def list_all(self) -> list[Contato]:
        return list(Contato.objects.all())

    def get(self, contato_id: int) -> Contato | None:
        return Contato.objects.filter(pk=contato_id).first()
    ...
```

### 4.3 Services — `api/v1/services/<tema>_service.py`

- Regras de negócio (ex.: campo vazio vira `'—'`, dia útil na agenda).
- Recebem o repository no `__init__` (injeção de dependência → fácil de trocar em teste).
- Exceção de domínio própria (ex.: `ContatoNaoEncontrado`) para a route traduzir em HTTP.

### 4.4 Routes — `api/v1/routes/<tema>.py`

- Fino: valida o payload, chama o service, traduz exceção de domínio em HTTPException.

```python
def get_service() -> ContatoService:
    return ContatoService(ContatoRepository())

@router.get('/{contato_id}', response_model=ContatoOut)
def obter_contato(contato_id: int, service: ContatoService = Depends(get_service)):
    try:
        return service.obter(contato_id)
    except ContatoNaoEncontrado:
        raise HTTPException(status_code=404, detail='nao encontrado')
```

### 4.5 Bootstrap do Django no FastAPI — `api/main.py`

```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
```

### 4.6 Settings — `core/settings.py`

- Lê `.env` com `python-dotenv` (`load_dotenv(BASE_DIR / '.env')`).
- `INSTALLED_APPS` só com os apps do projeto (sem contribs desnecessários).
- `DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'` (caso as tabelas usem `SERIAL`).

---

## 5. Models ↔ banco existente

Para adotar tabelas **já existentes** (sem tocar nos dados):

```python
# <app>/models.py
class Contato(models.Model):
    nome = models.TextField()
    ...
    class Meta:
        db_table = 'contatos'   # nome exato da tabela no Postgres
        ordering = ['id']
```

Passos:

```
python manage.py makemigrations
python manage.py migrate --fake-initial   # marca as migrations como aplicadas sem alterar o banco
```

`--fake-initial` é a chave: o Django adota as tabelas existentes como se as
migrations já tivessem rodado. Validação: `manage.py shell` + `Model.objects.count()`.

---

## 6. Contratos da API (`/api/v1`)

### contatos

| Método | Rota | Status | Descrição |
|---|---|---|---|
| GET | `/api/v1/contatos` | 200 | Lista todos (ordem por id) |
| POST | `/api/v1/contatos` | 201 | Cria contato |
| GET | `/api/v1/contatos/{id}` | 200 / 404 | Busca por id |
| PUT | `/api/v1/contatos/{id}` | 200 / 404 | Atualiza (payload completo) |
| PATCH | `/api/v1/contatos/{id}/stage` | 200 / 404 | Move de etapa (`{"stage": "..."}`) |
| DELETE | `/api/v1/contatos/{id}` | 204 / 404 | Exclui |

Regras de negócio: nome obrigatório; `valor >= 0`; campos vazios viram `'—'`;
`updated_at` atualizado automaticamente a cada escrita.

### health

- `GET /` → `{"api": "GPRBRCRM", "version": "1.0.0", "docs": "/docs"}`
- `/docs` → Swagger (gerado pelo FastAPI).

---

## 7. Padrão de testes (TDD)

Dois níveis:

### 7.1 Unitários (Django) — `<app>/tests.py`

`manage.py test` — valida models, defaults e relacionamentos:

```python
class ContatoModelTest(TestCase):
    def test_cria_contato_com_defaults(self):
        c = Contato.objects.create(nome='Maria', seg='estetica', stage='interessado')
        self.assertEqual(c.empresa, '—')
```

### 7.2 Integração (API) — `teste/` (pytest)

`pytest` — cobre todos os endpoints via `TestClient` (resposta 200/201/204/404/422).

`pytest.ini` (importante):

```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings
python_files = test_*.py
testpaths = teste
pythonpath = .
addopts = --reuse-db
```

**Armadilha conhecida (não pule):** o `TestClient` do FastAPI roda o app numa
thread própria; o ORM do teste roda em outra. Dados criados por fixture com o
marcador padrão do pytest-django NÃO aparecem nas chamadas HTTP. Solução usada:

- marcar os testes com `@pytest.mark.django_db(transaction=True)` (escreve
  imediatamente, visível à thread do app);
- `--reuse-db` no pytest.ini (evita o drop do banco de teste — o teardown
  falha silenciosamente por causa da sessão do TestClient; com `--reuse-db` o
  banco persiste e os testes rodam mais rápido; o flush do pytest-django
  mantém o isolamento entre testes);
- fixture `client` em `teste/conftest.py` fecha as conexões do ORM ao final
  (`connections.close_all()`) para não vazar sessões.

```python
# teste/conftest.py
@pytest.fixture
def client():
    from api.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client
    from django.db import connections
    connections.close_all()
```

`pytest` + `manage.py test` usam o mesmo banco de teste (`test_gprbr`):
se um deixar o banco para trás, o outro pede para dropar — resolver com:
`DROP DATABASE IF EXISTS test_gprbr;` (após matar as sessões).

---

## 8. Passo a passo para replicar (projeto novo)

1. Clonar/abrir o repositório do projeto novo (ex.: gprbrCRM).
2. Criar venv e instalar deps:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
3. Copiar a estrutura de pastas acima (core/, api/, teste/, manage.py, pytest.ini, .gitignore, .env).
4. `core/settings.py`: ajustar `PGDATABASE`/credenciais do `.env` do projeto novo.
5. Criar os apps por tema (um por domínio do projeto novo):
   ```
   .venv\Scripts\python manage.py startapp <tema1>
   ```
6. Definir os models espelhando as tabelas existentes (`Meta.db_table`).
7. `python manage.py makemigrations` + `python manage.py migrate --fake-initial`.
8. Escrever os testes dos endpoints **antes** do código (TDD): schemas → repository → service → route.
9. Rodar: `.venv\Scripts\python -m pytest` e `.venv\Scripts\python manage.py test`.
10. Subir: `.venv\Scripts\python -m uvicorn api.main:app --port 8000`.

---

## 9. Convenções

- Código e mensagens em **português** (nomes de campos/rotas em inglês onde fizer sentido).
- Exceções de domínio (ex.: `ContatoNaoEncontrado`) → routes traduzem em HTTP 404/400.
- Nomes de arquivo: `<tema>_repository.py`, `<tema>_service.py`, `test_<tema>_api.py`.
- Defaults de dados vazios: `'—'` (travessão), valor monetário `0`.
- IDs e datas: tabelas usam `SERIAL` + `TIMESTAMPTZ`; models usam `AutoField` + `DateTimeField(auto_now=True)`.
- Nada de SQL cru nas routes/services: sempre pelo repository.
- CORS liberado (`*`) apenas para desenvolvimento local.
