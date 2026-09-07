"""Testes do fluxo de revisão da Súplica (oficialato).

Regras (a pedido do dono do produto):
- A súplica pode ser criada pelo Deputado ou pelo Prefeito.
- A aprovação da ficha é só de quem a fez; outro deputado/prefeito não pode
  aprovar, devolver nem encaminhar enquanto o candidato estiver com o criador.
- Depois de aprovada pelo criador, o candidato segue para o Prefeito da
  prefeitura → Tesoureiro → Chanceler → Grão Prior (1 nível por vez).
- Só o oficial da vez encaminha/devolve; todos com acesso podem VER.
- Aprovação definitiva: Grão Prior / Grande Chanceler / Admin.
"""

import pytest
from django.test import Client

from acesso.models import Usuario
from candidatos.models import Candidato
from teste.conftest import criar_usuario


@pytest.fixture
def deputado(tenant_aurora):
    return criar_usuario('Dep Criador', 'dep@aurora.com', 'deputado_mestre', tenant_aurora)


@pytest.fixture
def outro_deputado(tenant_aurora):
    return criar_usuario('Dep Outro', 'dep2@aurora.com', 'deputado_mestre', tenant_aurora)


@pytest.fixture
def prefeito(tenant_aurora):
    return criar_usuario('Prefeito Sul', 'pref@aurora.com', 'prefeito', tenant_aurora)


@pytest.fixture
def tesoureiro(tenant_aurora):
    return criar_usuario('Tesoureira', 'tes@aurora.com', 'grande_tesoureiro', tenant_aurora)


@pytest.fixture
def chanceler(tenant_aurora):
    return criar_usuario('Chanceler', 'chan@aurora.com', 'grande_chanceler', tenant_aurora)


@pytest.fixture
def prior(tenant_aurora):
    return criar_usuario('Grão Prior', 'prior@aurora.com', 'grande_prior', tenant_aurora)


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'id': usuario.id, 'nome': usuario.nome, 'email': usuario.email,
                    'role': usuario.role, 'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


_CPF_SEQ = 0


def _cpf_unico():
    global _CPF_SEQ
    _CPF_SEQ += 1
    return f'000000000{_CPF_SEQ:02d}'


def _criar_suplica(c, tenant, criador, nome='Novo Candidato'):
    """Cria via API (como faria o modal do kanban)."""
    r = c.post('/candidato/criar/', {
        'nome': nome,
        'prefeitura': 'prefeitura-sul',
        'loja': 'Loja Aurora',
        'cpf': _cpf_unico(),
    })
    assert r.status_code == 200, r.content.decode()
    cand = Candidato.objects.get(pk=r.json()['candidato_id'])
    assert cand.tenant_id == tenant.id
    assert cand.created_by_id == criador.id
    return cand


def _ficha_enviada(cand):
    """Simula o candidato preenchendo e enviando a ficha (status em revisão)."""
    cand.status = Candidato.Status.EM_REVISAO
    cand.save(update_fields=['status', 'updated_at'])


def _modal(c, cand):
    return c.get(f'/candidato/api/modal-detalhe/{cand.id}/')


def _flags(c, cand):
    r = _modal(c, cand)
    assert r.status_code == 200, r.content.decode()
    d = r.json()
    return {k: bool(d[k]) for k in
            ('pode_aprovar', 'pode_encaminhar', 'pode_devolver')}, d


# --- 1. Criador (Deputado) é quem aprova a ficha e envia ao Prefeito ---

@pytest.mark.django_db
def test_deputado_criador_envia_ao_prefeito(tenant_aurora, deputado, outro_deputado, prefeito):
    c = _cliente_web(deputado)
    cand = _criar_suplica(c, tenant_aurora, deputado)
    assert cand.revisao_atual == Candidato.RevisaoAtual.DM  # nasce com o criador

    _ficha_enviada(cand)

    # O criador pode encaminhar (aprovou a ficha) — não devolve nem aprova final
    f, d = _flags(c, cand)
    assert f == {'pode_aprovar': False, 'pode_encaminhar': True, 'pode_devolver': False}

    r = c.post(f'/candidato/api/encaminhar/{cand.id}/', {'observacao': 'Ficha ok'})
    assert r.status_code == 200, r.content.decode()
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.PREFEITO

    # Criador não age mais (candidato agora é do Prefeito)
    f, _ = _flags(c, cand)
    assert f == {'pode_aprovar': False, 'pode_encaminhar': False, 'pode_devolver': False}

    # Outro deputado NUNCA pode agir num candidato que não criou
    c2 = _cliente_web(outro_deputado)
    f2, _ = _flags(c2, cand)
    assert f2 == {'pode_aprovar': False, 'pode_encaminhar': False, 'pode_devolver': False}
    r = c2.post(f'/candidato/api/encaminhar/{cand.id}/')
    assert r.status_code == 400

    # Prefeito recebe e pode encaminhar/devolver
    c3 = _cliente_web(prefeito)
    f3, _ = _flags(c3, cand)
    assert f3 == {'pode_aprovar': False, 'pode_encaminhar': True, 'pode_devolver': True}


@pytest.mark.django_db
def test_observacoes_do_deputado_nao_sao_apagadas(tenant_aurora, deputado, prefeito):
    """Prefeito pode acrescentar observações; as do criador permanecem."""
    from candidatos.models import CandidatoObservacao
    c = _cliente_web(deputado)
    cand = _criar_suplica(c, tenant_aurora, deputado)
    _ficha_enviada(cand)
    c.post(f'/candidato/api/encaminhar/{cand.id}/', {'observacao': 'Deputado: documentação completa'})

    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.PREFEITO
    cp = _cliente_web(prefeito)
    r = cp.post(f'/candidato/api/devolver/{cand.id}/', {'observacao': 'Prefeito: falta quitação'})
    assert r.status_code == 200, r.content.decode()

    textos = list(
        CandidatoObservacao.objects.filter(candidato=cand)
        .order_by('created_at').values_list('texto', flat=True),
    )
    assert any('documentação' in t for t in textos)   # a do deputado continua
    assert any('quitação' in t for t in textos)       # a do prefeito entrou


# --- 2. Cadeia completa: Prefeito → Tesoureiro → Chanceler → Grão Prior ---

@pytest.mark.django_db
def test_cadeia_prefeito_tesoureiro_chanceler_e_devolucao(
        tenant_aurora, deputado, prefeito, tesoureiro, chanceler):
    c = _cliente_web(deputado)
    cand = _criar_suplica(c, tenant_aurora, deputado)
    _ficha_enviada(cand)
    c.post(f'/candidato/api/encaminhar/{cand.id}/')
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.PREFEITO

    # Prefeito devolve ao Deputado...
    cp = _cliente_web(prefeito)
    assert cp.post(f'/candidato/api/devolver/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.DM

    # ...e o Deputado (criador) reencaminha ao Prefeito
    assert c.post(f'/candidato/api/encaminhar/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.PREFEITO

    # Prefeito → Tesoureiro
    assert cp.post(f'/candidato/api/encaminhar/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.TESOUREIRO

    # Deputado/prefeito já não agem (vez do Tesoureiro)
    assert c.post(f'/candidato/api/encaminhar/{cand.id}/').status_code == 400
    assert cp.post(f'/candidato/api/devolver/{cand.id}/').status_code == 400

    # Tesoureiro → Chanceler
    ct = _cliente_web(tesoureiro)
    assert ct.post(f'/candidato/api/encaminhar/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.CHANCELER

    # Chanceler → Grão Prior
    cc = _cliente_web(chanceler)
    assert cc.post(f'/candidato/api/encaminhar/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.revisao_atual == Candidato.RevisaoAtual.PRIOR


# --- 3. Aprovação definitiva: só Grão Prior / Grande Chanceler / Admin ---

@pytest.mark.django_db
def test_aprovacao_final_restrita(tenant_aurora, deputado, prefeito, chanceler, prior, admin_saas):
    c = _cliente_web(deputado)

    # Candidato com o Grão Prior (fim da cadeia): deputado não aprova, prior aprova
    cand = _criar_suplica(c, tenant_aurora, deputado)
    cand.revisao_atual = Candidato.RevisaoAtual.PRIOR
    _ficha_enviada(cand)
    cand.save()

    f, _ = _flags(c, cand)
    assert f['pode_aprovar'] is False          # deputado nunca aprova em definitivo
    r = c.post(f'/candidato/api/aprovar/{cand.id}/')
    assert r.status_code == 403

    cp = _cliente_web(prefeito)
    f, _ = _flags(cp, cand)
    assert f['pode_aprovar'] is False          # prefeito não aprova em definitivo

    # No Grão Prior, o botão de aprovar vira o de aprovação final (sem encaminhar)
    cprior = _cliente_web(prior)
    f, _ = _flags(cprior, cand)
    assert f == {'pode_aprovar': True, 'pode_encaminhar': False, 'pode_devolver': True}
    assert cprior.post(f'/candidato/api/aprovar/{cand.id}/').status_code == 200
    cand.refresh_from_db()
    assert cand.status == Candidato.Status.APROVADO

    # Grande Chanceler também aprova quando o candidato está com ele
    cand2 = _criar_suplica(c, tenant_aurora, deputado, nome='Segundo Candidato')
    cand2.revisao_atual = Candidato.RevisaoAtual.CHANCELER
    _ficha_enviada(cand2)
    cand2.save()
    cch = _cliente_web(chanceler)
    f, _ = _flags(cch, cand2)
    assert f['pode_aprovar'] is True
    assert cch.post(f'/candidato/api/aprovar/{cand2.id}/').status_code == 200
    cand2.refresh_from_db()
    assert cand2.status == Candidato.Status.APROVADO

    # Admin tem bypass total (aprova em definitivo em qualquer nível)
    cand3 = _criar_suplica(c, tenant_aurora, deputado, nome='Terceiro Candidato')
    _ficha_enviada(cand3)
    cadmin = _cliente_web(admin_saas)
    f, _ = _flags(cadmin, cand3)
    assert f['pode_aprovar'] is True
    assert cadmin.post(f'/candidato/api/aprovar/{cand3.id}/').status_code == 200
    cand3.refresh_from_db()
    assert cand3.status == Candidato.Status.APROVADO


# --- 4. A ficha enviada fica com o criador (não pula para o Prefeito) ---

@pytest.mark.django_db
def test_ficha_enviada_fica_com_o_criador(tenant_aurora, deputado, prefeito):
    from datetime import timedelta

    from django.utils import timezone
    cand = Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Portal',
        cpf='11111111111',
        prefeitura='prefeitura-sul',
        loja='Loja Aurora',
        status=Candidato.Status.FICHA_ENVIADA,
        access_token='tokentesteabc123',
        token_expires_at=timezone.now() + timedelta(days=7),
        created_by=deputado,
        # revisao_atual None de propósito — simula candidato antigo
    )
    c = _cliente_web(prefeito)
    r = c.post('/candidato/%s/definir-senha/' % cand.access_token, {
        'senha': 'senha-forte-123', 'confirmar_senha': 'senha-forte-123',
    })
    assert r.status_code == 200, r.content.decode()
    cand.refresh_from_db()
    assert cand.status == Candidato.Status.EM_REVISAO
    # NÃO pula para o Prefeito: fica com o criador (Deputado → nível DM)
    assert cand.revisao_atual == Candidato.RevisaoAtual.DM


@pytest.mark.django_db
def test_suplica_criada_por_prefeito_nasce_com_ele(tenant_aurora, prefeito):
    c = _cliente_web(prefeito)
    cand = _criar_suplica(c, tenant_aurora, prefeito, nome='Súplica do Prefeito')
    assert cand.revisao_atual == Candidato.RevisaoAtual.PREFEITO
