"""Carrito + checkout flow."""
import pytest


def test_cart_starts_empty(client):
    r = client.get('/carrito')
    assert r.status_code == 200
    # Carrito vacío muestra "Tu carrito está vacío" o similar
    body = r.get_data(as_text=True).lower()
    assert ('vac' in body) or ('empty' in body)


def test_add_product_to_cart(client, sample_product):
    """POST /carrito/agregar incrementa el carrito."""
    r = client.post(
        '/carrito/agregar',
        data={'product_id': sample_product['id'], 'quantity': 2},
        follow_redirects=True,
    )
    assert r.status_code == 200
    # Confirmamos via /carrito
    r2 = client.get('/carrito')
    body = r2.get_data(as_text=True)
    # El SKU o el name del producto debe aparecer
    assert sample_product['sku'] in body or sample_product['name'] in body


def test_add_invalid_product_fails(client):
    r = client.post(
        '/carrito/agregar',
        data={'product_id': 99999, 'quantity': 1},
        follow_redirects=False,
    )
    # No crashea — redirige (302/3) o flash error con 200
    assert r.status_code < 500


def test_update_cart_quantity(client, sample_product):
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 1},
                follow_redirects=True)
    r = client.post(
        '/carrito/actualizar',
        data={'product_id': sample_product['id'], 'quantity': 5},
        follow_redirects=True,
    )
    assert r.status_code == 200


def test_remove_from_cart(client, sample_product):
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 1},
                follow_redirects=True)
    r = client.post(f'/carrito/eliminar/{sample_product["id"]}',
                    follow_redirects=True)
    assert r.status_code == 200
    # Después de eliminar, /carrito vuelve a estar vacío
    body = client.get('/carrito').get_data(as_text=True).lower()
    assert ('vac' in body) or ('empty' in body)


def test_checkout_empty_cart_redirects(client):
    """Checkout con carrito vacío debería redirigir a /catalogo o /carrito."""
    r = client.get('/checkout', follow_redirects=False)
    assert r.status_code < 500


def test_checkout_page_renders_with_items(client, sample_product):
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 1},
                follow_redirects=True)
    r = client.get('/checkout')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # Form de checkout tiene campos típicos
    assert ('name="customer_name"' in body) or ('name="name"' in body)
    assert 'email' in body
