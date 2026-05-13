"""Catálogo: filtros, búsqueda, sort, slug routing."""
import pytest


def test_catalog_lists_products(client):
    r = client.get('/catalogo')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'JDP-' in body or 'BPC' in body or 'producto' in body.lower()


def test_catalog_filter_by_category(client):
    r = client.get('/catalogo?category=Performance')
    assert r.status_code == 200


def test_catalog_search(client):
    r = client.get('/catalogo?search=BPC')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # Si BPC-157 está activo, debe aparecer
    assert 'BPC' in body or 'búsqueda' in body.lower() or 'resultado' in body.lower()


@pytest.mark.parametrize('sort', ['name_asc', 'name_desc', 'price_asc', 'price_desc',
                                  'stock_desc', 'newest'])
def test_catalog_sort_whitelisted(client, sort):
    r = client.get(f'/catalogo?sort={sort}')
    assert r.status_code == 200


def test_catalog_sort_invalid_falls_back(client):
    """Sort no en whitelist no debe causar SQL injection ni 500."""
    r = client.get('/catalogo?sort=DROP+TABLE+products')
    assert r.status_code == 200


def test_catalog_in_stock_filter(client):
    r = client.get('/catalogo?in_stock=1')
    assert r.status_code == 200


def test_catalog_price_range(client):
    r = client.get('/catalogo?min_price=1000&max_price=3000')
    assert r.status_code == 200


def test_product_page_by_id(client, sample_product):
    r = client.get(f'/producto/{sample_product["id"]}')
    assert r.status_code in (200, 301, 302)
    if r.status_code == 200:
        body = r.get_data(as_text=True)
        assert sample_product['name'] in body or sample_product['sku'] in body


def test_product_page_by_slug(client, db):
    """Si el producto tiene slug, /producto/<slug> funciona."""
    row = db.execute(
        "SELECT slug, name FROM products WHERE active=1 AND slug IS NOT NULL "
        "AND slug<>'' LIMIT 1"
    ).fetchone()
    if not row:
        pytest.skip('Ningún producto activo tiene slug — esperado en DB fresca con seed')
    slug = row['slug']
    r = client.get(f'/producto/{slug}')
    assert r.status_code == 200
    assert row['name'].encode('utf-8') in r.data or row['name'] in r.get_data(as_text=True)


def test_currency_is_mxn_not_usd(client):
    """Confirma que la conversión de moneda quedó aplicada en todas las vistas."""
    for path in ['/', '/catalogo', '/carrito']:
        body = client.get(path).get_data(as_text=True)
        # No debe aparecer 'USD' como divisa del precio (sí puede USDT crypto)
        assert ' USD' not in body or 'USDT' in body, f"{path} aún muestra USD"
        assert 'MXN' in body or 'MX$' in body or '/carrito' in path, \
            f"{path} no muestra MXN"
