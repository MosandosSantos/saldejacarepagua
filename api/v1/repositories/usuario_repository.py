"""Acesso a dados de Usuario — unico ponto que toca o ORM do tema 'acesso'."""
from acesso.models import Usuario


class UsuarioRepository:
    def get_by_email(self, email: str):
        return Usuario.objects.filter(email__iexact=email).first()

    def get_by_id(self, usuario_id: int):
        return Usuario.objects.filter(id=usuario_id).first()

    def list_all(self):
        return list(Usuario.objects.select_related('tenant').all())

    def create(self, nome: str, email: str, senha_hash: str, role: str, tenant=None):
        return Usuario.objects.create(
            nome=nome, email=email, senha=senha_hash, role=role, tenant=tenant
        )
