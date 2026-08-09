"""Camada de integração com o softphone (PRD 5.2 — Softphone).

O sistema inicia a chamada com uma única ação abrindo uma URI de protocolo:

- `sip:+55<numero>@<dominio>` — abre o MicroSIP (ou outro softphone SIP) já
  registrado como manipulador do esquema `sip:` no navegador;
- `tel:+55<numero>` — fallback que abre o discador padrão do sistema operacional.

A configuração (esquema e domínio SIP) é por empresa (Tenant), editável em
Configurações → Discador, com fallback para as variáveis de ambiente
`SOFTPHONE_SCHEMA` / `SOFTPHONE_DOMINIO`.
"""

from django.conf import settings


def config_softphone(tenant=None):
    """Configuração do softphone: esquema ('sip'|'tel') e domínio SIP.

    Prioridade: configuração do tenant (empresa) > variáveis de ambiente.
    """
    if tenant is not None and getattr(tenant, 'softphone_schema', ''):
        schema = tenant.softphone_schema
        dominio = (tenant.softphone_dominio or '').strip()
    else:
        schema = getattr(settings, 'SOFTPHONE_SCHEMA', 'sip')
        dominio = (getattr(settings, 'SOFTPHONE_DOMINIO', '') or '').strip()
    return schema, dominio


def uri_chamada(contato, tenant=None):
    """URI de chamada para um contato — base do clique único no softphone.

    Retorna string vazia quando o contato não tem telefone válido.
    """
    numero = contato.tel_normalizado or ''
    if not numero:
        return ''
    schema, dominio = config_softphone(tenant)
    if schema == 'sip' and dominio:
        return f'sip:+{numero}@{dominio}'
    return f'tel:+{numero}'
