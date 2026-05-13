"""SEO: robots.txt, sitemap.xml, favicon, meta tags Open Graph."""
import re


def test_robots_txt_has_user_agent(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200
    assert r.content_type.startswith('text/plain')
    body = r.get_data(as_text=True)
    assert 'User-agent: *' in body
    assert 'Disallow: /admin' in body
    assert 'Disallow: /carrito' in body
    assert 'Disallow: /checkout' in body


def test_robots_links_to_sitemap(client):
    r = client.get('/robots.txt')
    assert 'Sitemap:' in r.get_data(as_text=True)
    assert '/sitemap.xml' in r.get_data(as_text=True)


def test_sitemap_is_valid_xml(client):
    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
    body = r.get_data(as_text=True)
    assert body.lstrip().startswith('<?xml version="1.0"')
    assert '<urlset' in body
    assert '</urlset>' in body


def test_sitemap_contains_homepage_and_catalog(client):
    body = client.get('/sitemap.xml').get_data(as_text=True)
    assert re.search(r'<loc>https?://[^<]+/</loc>', body)
    assert '/catalogo' in body


def test_sitemap_contains_products(client):
    body = client.get('/sitemap.xml').get_data(as_text=True)
    n_urls = body.count('<url>')
    # Esperamos >= 6 estáticos + >= 1 categoría + >= 1 producto activo
    assert n_urls >= 10, f"sitemap solo tiene {n_urls} URLs"
    assert '/producto/' in body


def test_favicon_serves_ico(client):
    r = client.get('/favicon.ico')
    assert r.status_code == 200
    # Header puede ser image/vnd.microsoft.icon o image/x-icon
    assert 'icon' in r.content_type
    assert len(r.data) > 0


def test_og_image_referenced_in_head(client):
    r = client.get('/')
    html = r.get_data(as_text=True)
    assert 'og:image' in html
    assert 'og-image.png' in html
    assert 'og:image:width' in html


def test_favicon_links_in_head(client):
    html = client.get('/').get_data(as_text=True)
    assert 'favicon-32.png' in html
    assert 'apple-touch-icon' in html
    assert 'theme-color' in html


def test_organization_jsonld(client):
    """Schema.org Organization con sameAs Instagram."""
    html = client.get('/').get_data(as_text=True)
    assert 'application/ld+json' in html
    assert 'instagram.com/jdpeptidesmx' in html
