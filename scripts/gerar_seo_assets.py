"""Gera os ativos de SEO/identidade a partir de ``static/img/logo.png``.

Uso:
    python scripts/gerar_seo_assets.py

Produz:
    static/img/favicon.ico            (16, 32, 48 e 64 px)
    static/img/favicon-32x32.png
    static/img/favicon-48x48.png
    static/img/favicon-192x192.png
    static/img/apple-touch-icon.png   (180x180)
    static/img/icon-192.png           (PWA)
    static/img/icon-512.png           (PWA)
    static/img/icon-maskable-512.png  (PWA maskable)
    static/img/og-image.png           (1200x630, Open Graph/Twitter)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
IMG_DIR = BASE_DIR / 'static' / 'img'
LOGO = IMG_DIR / 'logo.png'

IVORY = (246, 241, 231, 255)
WINE = (74, 10, 42)
WINE_LIGHT = (107, 15, 61)
GOLD = (232, 200, 106)
CREAM = (244, 238, 241)
FONT_SERIF_BOLD = Path('C:/Windows/Fonts/georgiab.ttf')
FONT_SANS = Path('C:/Windows/Fonts/segoeui.ttf')
FONT_SANS_BOLD = Path('C:/Windows/Fonts/segoeuib.ttf')


def _eagle_trimmed() -> Image.Image:
    logo = Image.open(LOGO).convert('RGBA')
    bbox = logo.getbbox()
    return logo.crop(bbox) if bbox else logo


def _fit(img: Image.Image, lado: int) -> Image.Image:
    """Redimensiona mantendo proporção para caber em um quadrado de ``lado``."""
    escala = min(lado / img.width, lado / img.height)
    novo = (max(1, round(img.width * escala)), max(1, round(img.height * escala)))
    return img.resize(novo, Image.LANCZOS)


def _colar_centro(base: Image.Image, img: Image.Image) -> None:
    x = (base.width - img.width) // 2
    y = (base.height - img.height) // 2
    base.alpha_composite(img, (x, y))


def _gradiente_vertical(tamanho, topo, base):
    img = Image.new('RGB', tamanho)
    draw = ImageDraw.Draw(img)
    for y in range(tamanho[1]):
        t = y / max(1, tamanho[1] - 1)
        cor = tuple(round(topo[i] + (base[i] - topo[i]) * t) for i in range(3))
        draw.line([(0, y), (tamanho[0], y)], fill=cor)
    return img


def gerar_favicons(eagle: Image.Image) -> None:
    # Fundo marfim: a águia roxa continua legível em abas claras e escuras.
    base = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([0, 0, 255, 255], radius=52, fill=IVORY)
    _colar_centro(base, _fit(eagle, 208))

    base.save(
        IMG_DIR / 'favicon.ico',
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    for lado in (32, 48, 192):
        base.resize((lado, lado), Image.LANCZOS).save(
            IMG_DIR / f'favicon-{lado}x{lado}.png', optimize=True
        )

    # Ícone de atalho iOS: sem transparência, fundo vinho e águia central.
    apple = _gradiente_vertical((180, 180), WINE_LIGHT, WINE).convert('RGBA')
    _colar_centro(apple, _fit(eagle, 148))
    apple.save(IMG_DIR / 'apple-touch-icon.png', optimize=True)


def gerar_pwa(eagle: Image.Image) -> None:
    for lado, ocupacao, nome in (
        (192, 0.80, 'icon-192.png'),
        (512, 0.80, 'icon-512.png'),
        (512, 0.62, 'icon-maskable-512.png'),
    ):
        canvas = _gradiente_vertical((lado, lado), WINE_LIGHT, WINE).convert('RGBA')
        draw = ImageDraw.Draw(canvas)
        margem = round(lado * 0.055)
        draw.rounded_rectangle(
            [margem, margem, lado - margem - 1, lado - margem - 1],
            radius=round(lado * 0.09),
            outline=GOLD + (170,),
            width=max(1, round(lado * 0.008)),
        )
        _colar_centro(canvas, _fit(eagle, round(lado * ocupacao)))
        canvas.save(IMG_DIR / nome, optimize=True)


def gerar_og_image(eagle: Image.Image) -> None:
    largura, altura = 1200, 630
    canvas = _gradiente_vertical((largura, altura), (59, 6, 32), (107, 15, 61)).convert('RGBA')

    # Brilho suave atrás da águia.
    glow = Image.new('RGBA', (largura, altura), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for raio in range(330, 0, -10):
        alpha = round(16 * (1 - raio / 330))
        gdraw.ellipse(
            [320 - raio, 315 - raio, 320 + raio, 315 + raio],
            fill=(244, 114, 182, alpha),
        )
    canvas.alpha_composite(glow)

    # Águia bicéfala à esquerda.
    aguia = _fit(eagle, 420)
    canvas.alpha_composite(aguia, (120, (altura - aguia.height) // 2))

    draw = ImageDraw.Draw(canvas)
    # Moldura dourada discreta.
    draw.rounded_rectangle(
        [26, 26, largura - 27, altura - 27],
        radius=22,
        outline=(232, 200, 106, 120),
        width=2,
    )

    fonte_olho = ImageFont.truetype(str(FONT_SANS_BOLD), 22)
    fonte_titulo = ImageFont.truetype(str(FONT_SERIF_BOLD), 56)
    fonte_sub = ImageFont.truetype(str(FONT_SANS), 22)
    fonte_pe = ImageFont.truetype(str(FONT_SANS_BOLD), 19)

    x_texto = 600
    draw.text((x_texto, 150), 'VALE DE JACAREPAGUÁ · REAA GRAU 33º', font=fonte_olho, fill=GOLD)
    draw.line([(x_texto, 192), (x_texto + 150, 192)], fill=GOLD, width=3)

    linhas = ('Sistema de', 'Administração de', 'Lojas Maçônicas')
    y = 222
    for linha in linhas:
        draw.text((x_texto, y), linha, font=fonte_titulo, fill=CREAM)
        y += 70

    draw.text(
        (x_texto, 452),
        'Gestão de membros, lojas, sessões e comunicações.',
        font=fonte_sub,
        fill=(244, 238, 241, 215),
    )
    draw.text(
        (x_texto, 512),
        'Acesso restrito · Segurança e conformidade LGPD',
        font=fonte_pe,
        fill=(232, 200, 106),
    )

    canvas.convert('RGB').save(IMG_DIR / 'og-image.png', optimize=True)


def gerar_webp() -> None:
    """Versões WebP das imagens da home (LCP menor, mesma qualidade visual)."""
    for nome, qualidade in (
        ('brasao_3d.png', 90),
        ('medalhas_grau33.png', 82),
        ('templo_maconico.png', 82),
    ):
        origem = IMG_DIR / nome
        if not origem.exists():
            continue
        destino = origem.with_suffix('.webp')
        with Image.open(origem) as img:
            img.convert('RGBA').save(
                destino, 'WEBP', quality=qualidade, method=6
            )


def main() -> None:
    if not LOGO.exists():
        raise SystemExit(f'Logo não encontrada: {LOGO}')
    eagle = _eagle_trimmed()
    gerar_favicons(eagle)
    gerar_pwa(eagle)
    gerar_og_image(eagle)
    gerar_webp()
    print('Ativos de SEO gerados em', IMG_DIR)


if __name__ == '__main__':
    main()
