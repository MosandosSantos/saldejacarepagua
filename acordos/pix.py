"""Geração de PIX — BR Code estático (payload EMV copia-e-cola + QR Code SVG).

Implementa o padrão BR Code (Banco Central) em Python puro: o payload é montado
em campos TLV (ID + tamanho + valor), finalizado com CRC16-CCITT (0xFFFF). O QR
Code é renderizado em SVG via lib `qrcode` — sem provedor externo (decisão do
cliente no S6). Requer apenas a chave PIX e os dados do recebedor da empresa.
"""

from decimal import Decimal, ROUND_HALF_UP
import io

import qrcode
from qrcode.image.svg import SvgPathImage

DOIS = Decimal('0.01')

def _limpar(texto, max_len):
    """Mantém apenas ASCII imprimível do campo EMV (o padrão BR Code é ASCII).

    Acentos/ç/ñ são substituídos pelo caractere base (a maioria dos PSPs aceita);
    caracteres fora da tabela ASCII são descartados e o texto é truncado.
    """
    _acentos = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'Á': 'a', 'À': 'a', 'Â': 'a', 'Ã': 'a', 'Ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'É': 'e', 'È': 'e', 'Ê': 'e', 'Ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i', 'Í': 'i', 'Ì': 'i', 'Î': 'i', 'Ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'Ó': 'o', 'Ò': 'o', 'Ô': 'o', 'Õ': 'o', 'Ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u', 'Ú': 'u', 'Ù': 'u', 'Û': 'u', 'Ü': 'u',
        'ç': 'c', 'Ç': 'c', 'ñ': 'n',
    }
    saida = []
    for ch in (texto or ''):
        ch = _acentos.get(ch, ch)
        if ord(ch) > 127:
            continue
        saida.append(ch)
    return ''.join(saida)[:max_len]


def _tlv(tag, valor):
    """Campo EMV: tag + tamanho (2 dígitos) + valor."""
    return f'{tag}{len(valor):02d}{valor}'


def _crc16(payload):
    """CRC16-CCITT (polinômio 0x1021, init 0xFFFF) — checksum do BR Code."""
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f'{crc:04X}'


def montar_payload_pix(chave, nome_recebedor, cidade, valor, txid='***'):
    """Monta o payload EMV/BR Code (copia-e-cola) para pagamento estático.

    - `txid='***'` é o padrão para QR estático (PIX não dinâmico).
    - Retorna a string completa com CRC16, pronta para o QR Code / copia-e-cola.
    """
    chave = (chave or '').strip()
    nome = _limpar(nome_recebedor, 25)
    cidade = _limpar(cidade, 15)
    txid = _limpar(txid, 25) or '***'

    gui = _tlv('00', 'BR.GOV.BCB.PIX')
    mai = _tlv('26', gui + _tlv('01', chave))

    payload = '000201'          # Payload Format Indicator
    payload += mai               # Merchant Account Information
    payload += '52040000'        # Merchant Category Code
    payload += '5303986'         # Transaction Currency (BRL)
    if valor is not None and Decimal(valor) > 0:
        valor_str = f'{Decimal(valor).quantize(DOIS, rounding=ROUND_HALF_UP):.2f}'
        payload += _tlv('54', valor_str)
    payload += '5802BR'          # Country Code
    payload += _tlv('59', nome)  # Merchant Name
    payload += _tlv('60', cidade)  # Merchant City
    payload += _tlv('62', _tlv('05', txid))  # Additional Data Field (txid)
    payload += '6304'            # CRC tag
    payload += _crc16(payload)
    return payload


def qrcode_svg(payload):
    """Renderiza o payload do BR Code como QR Code em SVG (string)."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(image_factory=SvgPathImage).save(buffer)
    return buffer.getvalue().decode('utf-8')
