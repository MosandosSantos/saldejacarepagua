"""Middlewares de seguranca do projeto (Fase D)."""
from django.conf import settings
from django.shortcuts import redirect


def montar_csp() -> str:
    """Monta a string do header Content-Security-Policy a partir do settings."""
    diretivas = getattr(settings, 'CSP_DIRETIVAS', {})
    return '; '.join(f'{chave} {valor}' for chave, valor in diretivas.items())


# Headers extras aplicados em todas as respostas (defesa em profundidade).
# S8/B3 — nao bloqueiam ataques sozinhos, mas reduzem superficie de risco.
HEADERS_EXTRAS = {
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=(), payment=()',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin',
}


class SecurityHeadersMiddleware:
    """Aplica o header Content-Security-Policy e headers de defesa em todas as respostas web.

    Usa `setdefault` para nao sobrescrever um CSP que alguma view ja tenha definido.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault('Content-Security-Policy', montar_csp())
        for header, valor in HEADERS_EXTRAS.items():
            response.headers.setdefault(header, valor)
        return response


class ValidarSessaoMiddleware:
    """Valida o usuario da sessao contra o DB em cada request autenticada.

    S8/C3 — antes, `role`/`tenant_id` eram lidos do snapshot da sessao gravado
    no login. Mudancas no DB (demover admin, mudar tenant, deletar usuario)
    nao surtiam efeito ate a sessao expirar (2 semanas). Agora, a cada request:

    1. Se `usuario_id` nao esta na sessao -> prossegue (pagina publica).
    2. Se o usuario foi deletado -> flush + redirect para o login.
    3. Se `role`/`tenant_id` mudaram no DB -> atualiza o snapshot da sessao.
    4. Seta `request.usuario_logado` para views/decorators usarem quando quiserem.

    Custo: 1 SELECT por request autenticada (indexado por PK). Sem cache
    intencional — o objetivo e justamente reagir em tempo real a mudancas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        uid = request.session.get('usuario_id')
        if uid:
            from acesso.models import Usuario

            usuario = Usuario.objects.filter(pk=uid).only('id', 'nome', 'email', 'role', 'tenant_id').first()
            if usuario is None:
                # Usuario foi removido — invalida a sessao imediatamente.
                request.session.flush()
                return redirect('acesso:login')

            snap = request.session.get('usuario') or {}
            tenant = usuario.tenant
            atual = {
                'nome': usuario.nome,
                'email': usuario.email,
                'role': usuario.role,
                'tenant_id': usuario.tenant_id,
            }
            # Sincroniza apenas se algo mudou (evita gravar sessao a toa).
            if any(snap.get(k) != v for k, v in atual.items()):
                request.session['usuario'] = atual
                request.session['nicho'] = tenant.nicho if tenant else ''
                request.session.modified = True

            # Disponibiliza a instancia do DB p/ views que quiserem usar
            # (evita queries repetidas em apps que hoje releem o usuario).
            request.usuario_logado = usuario
        return self.get_response(request)
