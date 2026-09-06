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


# ---------------------------------------------------------------------------
# Checkout: campos obligatorios y POST/Redirect/GET
# ---------------------------------------------------------------------------

def _checkout_form(**over):
    """Formulario de checkout válido; se sobreescribe lo que interese romper."""
    data = {
        'name': 'Beto Prueba',
        'email': 'beto@ejemplo.mx',
        'phone': '5512345678',
        'address': 'Av. Reforma 100',
        'address_ext': '100',
        'city': 'CDMX',
        'state': 'CDMX',
        'zip_code': '06000',
        'payment_method': 'paypal',
        'ruo_ack': '1',
    }
    data.update(over)
    return data


def _with_item(client, sample_product):
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 1})


def test_checkout_redirects_to_order_page(client, sample_product):
    """POST/Redirect/GET: recargar la confirmación no debe reenviar el form."""
    _with_item(client, sample_product)
    r = client.post('/checkout/procesar', data=_checkout_form())
    assert r.status_code == 302, r.status_code
    assert '/pedido/' in r.headers['Location']
    # Y el GET entra sin pedir correo: _finalize_order dejó el número en sesión.
    r2 = client.get(r.headers['Location'])
    assert r2.status_code == 200
    assert 'Beto Prueba' in r2.get_data(as_text=True)


@pytest.mark.parametrize('missing', ['state', 'zip_code', 'ruo_ack'])
def test_checkout_rejects_missing_required_field(client, sample_product, missing):
    """Sin estado, sin CP o sin aceptación RUO no se crea pedido.

    El `required` del HTML se salta posteando directo, así que la regla
    tiene que vivir en el servidor.
    """
    _with_item(client, sample_product)
    r = client.post('/checkout/procesar', data=_checkout_form(**{missing: ''}))
    assert r.status_code == 302
    assert '/checkout' in r.headers['Location']
    assert '/pedido/' not in r.headers['Location']


def test_checkout_rejects_malformed_zip(client, sample_product):
    """CP mexicano: exactamente 5 dígitos."""
    _with_item(client, sample_product)
    for bad in ('123', '060000', 'abcde'):
        r = client.post('/checkout/procesar', data=_checkout_form(zip_code=bad))
        assert '/pedido/' not in r.headers.get('Location', ''), bad
