"""Criptografia simetrica de segredos (AES-256-GCM).

Uso: guardar valores sensiveis no banco (tokens de integracao, credenciais de API)
sem armazena-los em texto puro. A chave e derivada do `SECRET_KEY` do Django
(ou de `CRYPTO_KEY` no .env, quando definida) via **HKDF-SHA256** — KDF padrão
com salt e info dedicados (S8/C4), em vez de SHA-256 cru.

Formato do token: ``v1:<base64url(nonce[12] + ciphertext)>`` — o nonce e unico
por operacao, entao o mesmo segredo nunca gera o mesmo token duas vezes.
"""
import base64
import os
from binascii import Error as BinasciiError

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings

PREFIXO = 'v1'
NONCE_BYTES = 12
# Salt e info fixos determinam uma chave AES unica para este uso (aead).
# Mudar estes valores invalida todos os tokens v1 existentes — versione o
# PREFIXO se precisar rotacionar.
_HKDF_SALT = b'recrm-aes-v1'
_HKDF_INFO = b'aead'


def _chave() -> bytes:
    """Deriva a chave AES-256 a partir do segredo mestre (CRYPTO_KEY ou SECRET_KEY).

    Usa HKDF-SHA256 em vez de SHA-256 direto (S8/C4): KDF padrao, com salt/info
    dedicados que isolam esta chave de outros usos do SECRET_KEY (sessao, JWT).
    Em producao, defina CRYPTO_KEY no .env para separar totalmente.
    """
    base = getattr(settings, 'CRYPTO_KEY', '') or settings.SECRET_KEY
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(base.encode('utf-8'))


def encriptar(texto: str) -> str:
    """Cifra um texto e devolve um token seguro (`v1:<base64>`)."""
    if not isinstance(texto, str):
        raise TypeError('encriptar espera uma string')
    nonce = os.urandom(NONCE_BYTES)
    cifra = AESGCM(_chave()).encrypt(nonce, texto.encode('utf-8'), None)
    payload = base64.urlsafe_b64encode(nonce + cifra).decode('ascii')
    return f'{PREFIXO}:{payload}'


def desencriptar(token: str) -> str:
    """Decifra um token gerado por `encriptar`. Erro se invalido ou adulterado."""
    if not isinstance(token, str) or not token.startswith(f'{PREFIXO}:'):
        raise ValueError('segredo invalido: prefixo ausente ou formato incorreto')
    try:
        dados = base64.urlsafe_b64decode(token[len(PREFIXO) + 1:].encode('ascii'))
    except (ValueError, BinasciiError):
        raise ValueError('segredo invalido: base64 corrompido')
    if len(dados) < NONCE_BYTES:
        raise ValueError('segredo invalido: payload curto demais')
    nonce, cifra = dados[:NONCE_BYTES], dados[NONCE_BYTES:]
    try:
        texto = AESGCM(_chave()).decrypt(nonce, cifra, None)
    except (InvalidTag, ValueError):
        raise ValueError('segredo invalido: chave incorreta ou conteudo adulterado')
    return texto.decode('utf-8')
