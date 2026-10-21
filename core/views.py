"""Views auxiliares do core (páginas estáticas, SEO, upgrade, etc.)."""
import json

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone


def versao_educativa(request, recurso=''):
    """Exibe mensagem de que a funcionalidade é exclusiva da versão Professional."""
    context = {
        'recurso': recurso,
        'titulo': recurso.replace('_', ' ').title() if recurso else 'Funcionalidade',
    }
    return render(request, 'core/versao_educativa.html', context)


def _site_base(request):
    """Domínio canônico configurado ou, no fallback, o host da requisição."""
    return (settings.SEO_SITE_URL or request.build_absolute_uri('/')).rstrip('/')


def robots_txt(request):
    """robots.txt público: indexa só a home/login e bloqueia a área interna."""
    sitemap_url = f'{_site_base(request)}/sitemap.xml'
    linhas = [
        'User-agent: *',
        'Allow: /$',
        'Allow: /login/',
        'Allow: /static/',
        'Disallow: /dashboard/',
        'Disallow: /membros/',
        'Disallow: /contatos/',
        'Disallow: /vales/',
        'Disallow: /lojas/',
        'Disallow: /agendas/',
        'Disallow: /agenda/',
        'Disallow: /tarefas/',
        'Disallow: /gestao/',
        'Disallow: /iniciacao/',
        'Disallow: /recepcao/',
        'Disallow: /candidato/',
        'Disallow: /equipe/',
        'Disallow: /config/',
        'Disallow: /automacoes/',
        'Disallow: /comunicacao/',
        'Disallow: /emails/',
        'Disallow: /premium/',
        'Disallow: /captura/',
        'Disallow: /login/logout/',
        'Disallow: /healthz/',
        'Disallow: /api/',
        'Disallow: /admin/',
        'Disallow: /media/',
        'Disallow: /staticfiles/',
        '',
        f'Sitemap: {sitemap_url}',
    ]
    return HttpResponse(
        '\n'.join(linhas) + '\n',
        content_type='text/plain; charset=utf-8',
    )


def sitemap_xml(request):
    """Sitemap com a página pública (home de login)."""
    home_url = f'{_site_base(request)}/'
    hoje = timezone.localdate().isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{home_url}</loc>
    <lastmod>{hoje}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')


def manifest_webmanifest(request):
    """Manifesto PWA: nome, cores e ícones da águia bicéfala."""
    dados = {
        'name': settings.SEO_SITE_NAME,
        'short_name': settings.SEO_SITE_SHORT_NAME,
        'description': settings.SEO_SITE_DESCRIPTION,
        'lang': 'pt-BR',
        'dir': 'ltr',
        'id': '/',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'portrait-primary',
        'background_color': '#730A40',
        'theme_color': settings.SEO_THEME_COLOR,
        'categories': ['business', 'productivity'],
        'icons': [
            {
                'src': static('img/icon-192.png'),
                'sizes': '192x192',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': static('img/icon-512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'any',
            },
            {
                'src': static('img/icon-maskable-512.png'),
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'maskable',
            },
        ],
    }
    return HttpResponse(
        json.dumps(dados, ensure_ascii=False, indent=2),
        content_type='application/manifest+json; charset=utf-8',
    )
