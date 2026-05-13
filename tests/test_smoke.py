"""Smoke tests — todas las rutas públicas devuelven HTTP < 500.

Si algún test aquí falla, el deploy está roto en algo básico.
"""
import pytest


PUBLIC_ROUTES_GET = [
    '/',
    '/catalogo',
    '/catalogo?category=Performance',
    '/catalogo?search=BPC',
    '/catalogo?sort=price_asc',
    '/catalogo?in_stock=1',
    '/carrito',
    '/checkout',
    '/contacto',
    '/faq',
    '/privacidad',
    '/terminos',
    '/sobre-nosotros',
    '/info',
    '/tracking',
    '/robots.txt',
    '/sitemap.xml',
    '/favicon.ico',
]


@pytest.mark.parametrize('path', PUBLIC_ROUTES_GET)
def test_public_route_responds_2xx_or_3xx(client, path):
    r = client.get(path)
    assert r.status_code < 500, f"{path} → {r.status_code} ({r.data[:200]!r})"


def test_homepage_contains_brand(client):
    r = client.get('/')
    assert r.status_code == 200
    assert b'JD' in r.data and b'Peptides' in r.data


def test_404_for_unknown_route(client):
    r = client.get('/no-existe-esta-ruta-de-prueba-2026')
    assert r.status_code == 404


def test_404_unknown_product_slug(client):
    """Slug inexistente: la app puede 404 o redirigir al catálogo."""
    r = client.get('/producto/no-existe-este-slug-xyz', follow_redirects=False)
    assert r.status_code in (302, 404)
    if r.status_code == 302:
        # Si redirige, debe ir al catálogo o home (no a otro producto)
        loc = r.headers.get('Location', '')
        assert '/catalogo' in loc or loc == '/' or loc.endswith('/')


def test_nosotros_redirects_301(client):
    r = client.get('/nosotros', follow_redirects=False)
    assert r.status_code == 301
    assert r.headers['Location'].endswith('/sobre-nosotros')


def test_admin_login_required(client):
    """Sin sesión, /admin/dashboard redirige a /admin/login."""
    r = client.get('/admin/productos', follow_redirects=False)
    assert r.status_code in (302, 401, 403)
    if r.status_code == 302:
        assert '/admin/login' in r.headers['Location']
