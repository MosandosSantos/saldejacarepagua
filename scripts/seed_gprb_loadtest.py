"""Seed de carga no banco GPRB (PostgreSQL externo, saldabritanea).

Cria 5 potências de teste (IDs lt_pot_*), 5 tenants lt_ com 2 lojas cada
(10 lojas lt_) e 100 membros ATIVOS distribuídos entre as potências, com a
MAIORIA vinculada a múltiplas lojas (N:N via member_loja). Os tenant
reais (GOB, COMAB, ...), as 4 potências reais, a prefeitura real e a loja
real existentes NÃO são alterados.

Isolamento/idempotência: todos os artefatos de teste usam o prefixo 'lt_'.
Cada execução apaga o seed anterior (vinculos, membros, lojas, prefeituras,
tenants lt_ e potencias lt_) e reinsere tudo, numa única transação.

Uso (dentro do container do app, que já recebe as envs GPRB_DB_*):
    python scripts/seed_gprb_loadtest.py
"""
import datetime as dt
import os
import random
import string
import sys

import psycopg

TENANT_GPRB_ID = 'tenant_gprb_0001'


def _limpar(cur):
    """Remove artefatos de execuções anteriores (prefixo lt_)."""
    cur.execute("DELETE FROM member_loja WHERE \"memberId\" LIKE 'lt_%'")
    cur.execute("DELETE FROM member WHERE id LIKE 'lt_%'")
    cur.execute("DELETE FROM loja WHERE id LIKE 'lt_%'")
    cur.execute("DELETE FROM prefeitura WHERE id LIKE 'lt_%'")
    cur.execute("DELETE FROM tenant WHERE code LIKE 'lt_%'")
    cur.execute("DELETE FROM potencia WHERE id LIKE 'lt_%'")


def _criar_potencias(cur):
    """5 potências lt_ (as 4 reais — GOB, COMAB, CSMB, GLMMMRJ — ficam intactas)."""
    nomes = ['LT Alfa', 'LT Bravo', 'LT Charlie', 'LT Delta', 'LT Echo']
    for i, nome in enumerate(nomes, 1):
        cur.execute(
            'INSERT INTO potencia (id, nome) VALUES (%s, %s)',
            (f'lt_pot_{i:04d}', nome),
        )


def _criar_lojas(cur):
    """5 tenants lt_ × 2 lojas = 10 lojas; cada loja ancorada numa potência lt_."""
    hoje = dt.datetime.now()
    siglas = ['LTALFA', 'LTBRAVO', 'LTCHARLIE', 'LTDELTA', 'LTECHO']
    lojas = []  # [(loja_id, potencia_id)]
    for i in range(1, 6):
        tenant_id = f'lt_ten_{i:04d}'
        cur.execute(
            'INSERT INTO tenant (id, name, code, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, %s, %s)',
            (tenant_id, f'Tenant Load Test {i}', f'lt_ten{i:04d}', hoje, hoje),
        )
        cur.execute(
            'INSERT INTO prefeitura (id, "tenantId", nome, sigla, status, '
            '"createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (
                f'lt_pref_{i:04d}', TENANT_GPRB_ID,
                f'Prefeitura Load Test {i}', f'{siglas[i - 1]}P', 'ATIVA',
                hoje, hoje,
            ),
        )
        for j in (1, 2):
            loja_id = f'lt_loja_{(i - 1) * 2 + j:04d}'
            cur.execute(
                'INSERT INTO loja (id, "tenantId", "lojaMX", numero, situacao, '
                '"prefeituraId", "createdAt", "updatedAt") '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (
                    loja_id, tenant_id, f'Loja LT {i}-{j}', i * 1000 + j,
                    'ATIVA', f'lt_pref_{i:04d}', hoje, hoje,
                ),
            )
            lojas.append((loja_id, f'lt_pot_{i:04d}'))
    return lojas


def _criar_membros(cur, lojas):
    """100 membros ATIVOS; 85% (a maioria) em 2..5 lojas via member_loja."""
    hoje = dt.date.today()
    agora = dt.datetime.now()
    loja_ids = [l[0] for l in lojas]
    potencia_por_loja = dict(lojas)
    rng = random.SystemRandom()

    membros = []
    for i in range(1, 101):
        nasc = dt.date(rng.randint(1970, 2004), rng.randint(1, 12), rng.randint(1, 28))
        adm = hoje.replace(year=hoje.year - rng.randint(1, 15))
        membros.append(dict(
            id=f'lt_mem_{i:04d}',
            tenant=TENANT_GPRB_ID,
            loja=rng.choice(loja_ids),
            rito='REAA',
            nasc=nasc,
            nome=f'Membro Load Test {i:03d}',
            cpf=''.join(rng.choices(string.digits, k=11)),
            email=f'lt_membro{i:03d}@exemplo.teste',
            celular='+5511' + ''.join(rng.choices(string.digits, k=9)),
            situacao='ATIVO',
            rua='Rua Load Test 100',
            cep='09720-000',
            cidade='São Bernardo',
            uf='SP',
            adm=adm,
            hoje=agora,
        ))

    cur.executemany(
        '''
        INSERT INTO member (id, "tenantId", "lojaId", rito, "dataNascimento",
            "nomeCompleto", cpf, email, celular, situacao,
            "enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf",
            "dataAdmissao", "createdAt", "updatedAt")
        VALUES (%(id)s, %(tenant)s, %(loja)s, %(rito)s, %(nasc)s,
            %(nome)s, %(cpf)s, %(email)s, %(celular)s, %(situacao)s,
            %(rua)s, %(cep)s, %(cidade)s, %(uf)s,
            %(adm)s, %(hoje)s, %(hoje)s)
        ''',
        membros,
    )

    # N:N — a maioria: membros 1..85 ficam em 2..5 lojas; 86..100 em 1 loja.
    for i, m in enumerate(membros, 1):
        loja_principal = potencia_por_loja.get(m['id']) or m['loja']
        if i <= 85:
            extras = rng.sample(loja_ids, rng.choice([2, 2, 3, 3, 4]))
            escolhidas = set(extras) | {loja_principal}
        else:
            escolhidas = {loja_principal}
        # potencia_simbolismo = potência da loja principal
        pot = potencia_por_loja.get(next(
            (lid for lid, pid in lojas if lid in escolhidas),
            m['loja'],
        ))
        cur.execute(
            'UPDATE member SET "potencia_simbolismo" = %s WHERE id = %s',
            (pot, m['id']),
        )
        for loja_id in escolhidas:
            cur.execute(
                'INSERT INTO member_loja ("memberId", "lojaId") '
                'VALUES (%s, %s) ON CONFLICT DO NOTHING',
                (m['id'], loja_id),
            )
    return len(membros)


def main():
    dsn = (
        f"host={os.environ.get('GPRB_DB_HOST', '127.0.0.1')} "
        f"port={os.environ.get('GPRB_DB_PORT', '5432')} "
        f"dbname={os.environ.get('GPRB_DB_NAME', 'saldabritanea')} "
        f"user={os.environ.get('GPRB_DB_USER', 'postgres')} "
        f"password={os.environ.get('GPRB_DB_PASSWORD', '')}"
    )
    if '--clean' in sys.argv:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                _limpar(cur)
            print('SEED REMOVIDO (todos os artefatos lt_)')
        return
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            _limpar(cur)
            _criar_potencias(cur)
            lojas = _criar_lojas(cur)
            n_membros = _criar_membros(cur, lojas)
        conn.commit()
        print(f'SEED OK: 5 potencias lt_, 10 lojas lt_, {n_membros} membros lt_')


if __name__ == '__main__':
    main()
