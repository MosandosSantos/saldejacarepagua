"""Centraliza lógica de sessão do usuário.

Evita duplicação do padrão request.session['usuario'] = {...}
que aparecia em 4 pontos diferentes de acesso/views.py.
"""


def iniciar_sessao(request, usuario, nicho='saude', dispositivo=None):
    """Configura a sessão do usuário após login bem-sucedido.

    Args:
        request: HttpRequest
        usuario: Instância do model Usuario (ou dict com id, nome, email, role, tenant_id)
        nicho: Segmento do usuário (default: 'saude')
        dispositivo: Informações do dispositivo (opcional)
    """
    if isinstance(usuario, dict):
        dados_usuario = usuario
    else:
        dados_usuario = {
            'id': usuario.id,
            'nome': usuario.nome,
            'email': usuario.email,
            'role': usuario.role,
            'tenant_id': usuario.tenant_id,
        }

    request.session['usuario_id'] = dados_usuario.get('id')
    request.session['usuario'] = dados_usuario
    request.session['nicho'] = nicho

    if dispositivo:
        request.session['dispositivo'] = dispositivo


def encerrar_sessao(request):
    """Limpa todos os dados da sessão do usuário."""
    request.session.flush()


def obter_usuario_sessao(request):
    """Retorna os dados do usuário na sessão (ou None)."""
    return request.session.get('usuario')


def obter_tenant_id(request):
    """Retorna o tenant_id da sessão (ou None)."""
    usuario = request.session.get('usuario', {})
    return usuario.get('tenant_id') if isinstance(usuario, dict) else None
