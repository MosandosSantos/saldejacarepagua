"""Criptografia simetrica de segredos (AES-256-GCM).

Uso: guardar valores sensiveis no banco (tokens de integracao, credenciais de API)
sem armazena-los em texto puro. A chave e derivada do `SECRET_KEY` do Django
(ou de `CRYPTO_KEY` no .env, quando definida) via SHA-256, resultando em uma
chave de 32 bytes para AES-256.

Formato do token: ``v1:<base64url(nonce[12] + ciphertext)>`` — o nonce e unico
por operacao, entao o mesmo segredo nunca gera o mesmo token duas vezes.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIXO = 'v1'
NONCE_BYTES = 12


def _chave() -> bytes:
    """Deriva a chave AES-256 a partir do segredo mestre (CRYPTO_KEY ou SECRET_KEY)."""
    from django.conf import settings

    segredo = getattr(settings, 'CRYPTO_KEY', '') or settings.SECRET_KEY
    return hashlib.sha256(segredo.encode('utf-8')).digest()


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
    except Exception:
        raise ValueError('segredo invalido: base64 corrompido')
    if len(dados) < NONCE_BYTES:
        raise ValueError('segredo invalido: payload curto demais')
    nonce, cifra = dados[:NONCE_BYTES], dados[NONCE_BYTES:]
    try:
        texto = AESGCM(_chave()).decrypt(nonce, cifra, None)
    except Exception:
        raise ValueError('segredo invalido: chave incorreta ou conteudo adulterado')
    return texto.decode('utf-8')
