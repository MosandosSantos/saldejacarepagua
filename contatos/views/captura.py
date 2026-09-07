"""Captura pública de lead (Fase H) — pagina sem login com token por tenant."""

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render

from acesso.models import Tenant
from automacoes.engine import disparar
from contatos.models import Contato, criar_negocio, so_digitos
from contatos.scoring import atualizar_score
from core.dominio import SEGS
from recepcao.models import etapas_do_tenant

LIMITE_ENVIOS_POR_IP = 5


def captura_lead(request, token):
    """Página pública (sem login) — o lead preenche e vira contato + negócio.

    Proteções: token único por tenant (URL secreta), honeypot anti-robô e limite
    de envios por IP (janela de 1h, cache locmem). O lead entra na primeira etapa
    do pipeline do tenant com a origem configurada (Site/Instagram/WhatsApp).
    """
    tenant = get_object_or_404(Tenant.objects.all(), token_captura=token)
    erros = []
    sucesso = False
    desativado = not tenant.captura_ativa
    if request.method == 'POST' and tenant.captura_ativa:
        # Honeypot: robô preenche o campo invisível → responde sucesso sem gravar
        if request.POST.get('website'):
            sucesso = True
        else:
            nome = (request.POST.get('nome') or '').strip()
            tel = (request.POST.get('tel') or '').strip()
            email = (request.POST.get('email') or '').strip().lower()
            if not nome:
                erros.append('Informe seu nome.')
            if not tel and not email:
                erros.append('Informe pelo menos um telefone ou e-mail para contato.')
            if not erros:
                # Rate limit: só conta envios válidos (5/hora por IP) — erros de
                # digitação não bloqueiam o lead legítimo.
                # '0.0.0.0' é fallback seguro quando REMOTE_ADDR ausente (não é bind de interface).
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')  # nosec B104
                chave = f'captura:{ip}'
                enviados = int(cache.get(chave, 0) or 0)
                if enviados >= LIMITE_ENVIOS_POR_IP:
                    erros.append('Muitos envios deste aparelho. Tente novamente mais tarde.')
                else:
                    cache.set(chave, enviados + 1, 3600)
                    seg = request.POST.get('seg', '')
                    if seg not in SEGS:
                        seg = ''
                    procedimento = (request.POST.get('procedimento') or '').strip() or '—'
                    origem = tenant.origem_captura or 'Site'
                    # Deduplicação: mesmo telefone normalizado (mesmo tenant) →
                    # atualiza o contato existente e registra um novo negócio,
                    # em vez de criar contato duplicado.
                    tel_digitos = so_digitos(tel)
                    contato = (
                        Contato.objects.filter(tenant_id=tenant.id, tel_normalizado=tel_digitos).first()
                        if tel_digitos else None
                    )
                    novo_contato = contato is None
                    if novo_contato:
                        contato = Contato.objects.create(
                            tenant=tenant,
                            nome=nome,
                            tel=tel or '—',
                            email=email or '—',
                            seg=seg,
                            procedimento=procedimento,
                            origem=origem,
                        )
                    else:
                        contato.nome = nome
                        if tel:
                            contato.tel = tel
                        if email:
                            contato.email = email
                        if seg:
                            contato.seg = seg
                        contato.procedimento = procedimento
                        contato.origem = origem
                        contato.save()
                    etapas = etapas_do_tenant(tenant.id, tenant.nicho)
                    stage = etapas[0]['key'] if etapas else 'interessado'
                    negocio = criar_negocio(contato, stage=stage, valor=0, tenant_id=tenant.id)
                    if novo_contato:
                        # só contatos realmente novos disparam o gatilho "Contato novo" —
                        # quem já existia (dedup por telefone) apenas ganha um negócio.
                        disparar('contato_criado', tenant_id=tenant.id, contato=contato, negocio=negocio)
                    disparar('negocio_criado', tenant_id=tenant.id, contato=contato, negocio=negocio)
                    atualizar_score(contato)
                    sucesso = True
    return render(request, 'contatos/captura.html', {
        'tenant': tenant,
        'erros': erros,
        'sucesso': sucesso,
        'desativado': desativado,
        'segs': SEGS,
    })
