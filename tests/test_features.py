"""Tests para las features de SEO rich snippets, reviews, tracking, factura
y carrito abandonado."""
import json


# ===== Schema.org Product + image-sitemap =====

def test_product_jsonld_present(client, db):
    row = db.execute(
        "SELECT slug FROM products WHERE active=1 AND slug<>'' LIMIT 1"
    ).fetchone()
    if not row:
        return
    r = client.get(f'/producto/{row["slug"]}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '"@type": "Product"' in html
    assert '"priceCurrency": "MXN"' in html
    assert '"@type": "Brand"' in html
    assert 'JD Peptides' in html


def test_image_sitemap_exists(client):
    r = client.get('/image-sitemap.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
    body = r.get_data(as_text=True)
    assert 'sitemap-image' in body
    assert '<image:loc>' in body


def test_robots_includes_image_sitemap(client):
    body = client.get('/robots.txt').get_data(as_text=True)
    assert '/image-sitemap.xml' in body


# ===== Tracking de guía =====

def test_carrier_tracking_url():
    from app import carrier_tracking_url
    assert 'dhl.com' in carrier_tracking_url('DHL', '123456')
    assert 'fedex.com' in carrier_tracking_url('FedEx', '987')
    assert 'estafeta.com' in carrier_tracking_url('Estafeta', 'EST123')
    assert carrier_tracking_url('UnknownCarrier', '1') is None
    assert carrier_tracking_url('', '1') is None
    assert carrier_tracking_url('DHL', '') is None


def test_admin_set_tracking_updates_order(admin_client, app):
    from app import get_db, execute_db
    # Crear orden de prueba
    with app.app_context():
        execute_db(
            "INSERT INTO orders (order_number, customer_name, customer_email, "
            "address, city, status, payment_status, payment_method, subtotal, "
            "shipping, total) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            ('JD-TEST-001', 'Test User', 'test@example.com', 'Calle 1',
             'CDMX', 'enviado', 'pagado', 'transferencia', 1000, 0, 1000)
        )
        oid = get_db().execute(
            "SELECT id FROM orders WHERE order_number='JD-TEST-001'"
        ).fetchone()['id']

    r = admin_client.post(f'/admin/ordenes/{oid}/tracking',
                          data={'tracking_carrier': 'DHL',
                                'tracking_number': '1234567890',
                                'notify_customer': '0',
                                '_csrf': admin_client.csrf},
                          follow_redirects=False)
    assert r.status_code in (200, 302)
    with app.app_context():
        row = get_db().execute(
            "SELECT tracking_carrier, tracking_number FROM orders WHERE id=?", (oid,)
        ).fetchone()
        assert row['tracking_carrier'] == 'DHL'
        assert row['tracking_number'] == '1234567890'


# ===== Reviews =====

def test_review_table_exists(db):
    cols = [r[1] for r in db.execute("PRAGMA table_info(reviews)").fetchall()]
    expected = {'product_id', 'order_id', 'customer_email', 'rating',
                'comment', 'status'}
    assert expected.issubset(set(cols))


def test_admin_reviews_route(admin_client):
    r = admin_client.get('/admin/reviews')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Reseñ' in body or 'eseñ' in body


def test_admin_reviews_filters(admin_client):
    for s in ('pending', 'approved', 'rejected', 'all'):
        r = admin_client.get(f'/admin/reviews?status={s}')
        assert r.status_code == 200


def test_submit_review_requires_delivered_order(client, app, sample_product):
    """Solo se puede reseñar pedidos en status='entregado'."""
    from app import get_db, execute_db
    with app.app_context():
        execute_db(
            "INSERT INTO orders (order_number, customer_name, customer_email, "
            "address, city, status, payment_status, payment_method, subtotal, "
            "shipping, total) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            ('JD-REV-NEW', 'X', 'x@x.com', 'A', 'B', 'nuevo', 'pagado',
             'transferencia', 100, 0, 100)
        )
        with client.session_transaction() as sess:
            sess['view_orders'] = ['JD-REV-NEW']
    r = client.post('/pedido/JD-REV-NEW/review',
                    data={'product_id': sample_product['id'],
                          'rating': 5, 'comment': 'great product really'},
                    follow_redirects=True)
    # No debe crear el review porque status != 'entregado'
    with app.app_context():
        n = get_db().execute(
            "SELECT COUNT(*) AS c FROM reviews WHERE order_id IN "
            "(SELECT id FROM orders WHERE order_number='JD-REV-NEW')"
        ).fetchone()['c']
        assert n == 0


# ===== Carrito abandonado =====

def test_abandoned_cart_table_exists(db):
    cols = [r[1] for r in db.execute("PRAGMA table_info(abandoned_carts)").fetchall()]
    expected = {'customer_email', 'items_json', 'total',
                'reminded_at', 'recovered_order_id'}
    assert expected.issubset(set(cols))


def test_abandoned_snapshot_requires_cart(client):
    """Sin items en carrito, snapshot retorna 400."""
    r = client.post('/api/cart/abandon-snapshot',
                    json={'email': 'test@example.com'})
    assert r.status_code == 400
    data = r.get_json()
    assert data['error'] == 'empty_cart'


def test_abandoned_snapshot_requires_valid_email(client, sample_product):
    """Sin email válido → 400 con error invalid_email."""
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 1})
    r = client.post('/api/cart/abandon-snapshot',
                    json={'email': 'not-an-email'})
    assert r.status_code == 400


def test_abandoned_snapshot_persists(client, app, sample_product):
    """Snapshot válido se guarda en abandoned_carts."""
    from app import get_db
    client.post('/carrito/agregar',
                data={'product_id': sample_product['id'], 'quantity': 2})
    r = client.post('/api/cart/abandon-snapshot',
                    json={'email': 'abandon@example.com', 'name': 'Test'})
    assert r.status_code == 200
    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM abandoned_carts WHERE customer_email='abandon@example.com'"
            " ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row['customer_name'] == 'Test'
        items = json.loads(row['items_json'])
        assert len(items) > 0


def test_cron_endpoint_rejects_unauthorized(client):
    """Sin CRON_SECRET en env, endpoint retorna 403."""
    r = client.get('/cron/send-abandoned-reminders')
    assert r.status_code == 403


def test_cron_endpoint_accepts_authorized(client, monkeypatch):
    """Con CRON_SECRET y Authorization Bearer correcto, retorna 200."""
    import app as appmod
    monkeypatch.setenv('CRON_SECRET', 'test-secret-123')
    # El módulo lee la env directamente en cada request, así que no hay que reimportar
    r = client.get('/cron/send-abandoned-reminders',
                   headers={'Authorization': 'Bearer test-secret-123'})
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert 'sent' in data


# ===== Factura =====

def test_factura_requires_session_whitelist(client):
    """Sin haberlo whitelisteado, /pedido/<n>/factura redirige."""
    r = client.get('/pedido/UNAUTH-123/factura', follow_redirects=False)
    assert r.status_code in (301, 302)


def test_factura_renders_for_whitelisted_order(client, app):
    from app import get_db, execute_db
    with app.app_context():
        execute_db(
            "INSERT INTO orders (order_number, customer_name, customer_email, "
            "address, city, status, payment_status, payment_method, subtotal, "
            "shipping, total) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            ('JD-FACT-001', 'F User', 'f@x.com', 'Calle X', 'CDMX', 'pagado',
             'pagado', 'transferencia', 500, 0, 500)
        )
    with client.session_transaction() as sess:
        sess['view_orders'] = ['JD-FACT-001']
    r = client.get('/pedido/JD-FACT-001/factura')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'JD-FACT-001' in body
    assert 'COMPROBANTE' in body or 'comprobante' in body.lower()
    assert 'MXN' in body
