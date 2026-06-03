import json
import app as A

def _enable_paypal(monkeypatch):
    monkeypatch.setattr(A, 'PAYPAL_CLIENT_ID', 'test_client', raising=False)
    monkeypatch.setattr(A, 'PAYPAL_SECRET', 'test_secret', raising=False)

def test_create_order_flow(client, sample_product, monkeypatch):
    _enable_paypal(monkeypatch)
    calls = {}
    def fake_req(method, path, body=None):
        calls['create'] = (method, path, body)
        return 201, {'id': 'PP-ORDER-123', 'status': 'CREATED'}
    monkeypatch.setattr(A, '_paypal_request', fake_req)
    client.post('/carrito/agregar', data={'product_id': sample_product['id'], 'quantity': 1})
    r = client.post('/checkout/paypal/create-order', json={
        'name':'Ana Probadora','email':'ana@x.com','address':'Av Siempre Viva',
        'address_ext':'742','city':'CDMX','zip_code':'06000','phone':'5512345678'})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()['id'] == 'PP-ORDER-123'
    # PayPal recibió MXN con 2 decimales
    body = calls['create'][2]
    assert body['purchase_units'][0]['amount']['currency_code'] == 'MXN'
    assert '.' in body['purchase_units'][0]['amount']['value']

def test_create_order_rejects_bad_form(client, sample_product, monkeypatch):
    _enable_paypal(monkeypatch)
    monkeypatch.setattr(A, '_paypal_request', lambda *a, **k: (201, {'id':'X'}))
    client.post('/carrito/agregar', data={'product_id': sample_product['id'], 'quantity': 1})
    r = client.post('/checkout/paypal/create-order', json={'name':'','email':'bad'})
    assert r.status_code == 400
    assert 'error' in r.get_json()

def test_capture_creates_paid_order(client, sample_product, db, monkeypatch):
    _enable_paypal(monkeypatch)
    # stock inicial
    row = db.execute("SELECT id, stock FROM products WHERE id=?", (sample_product['id'],)).fetchone()
    stock0 = row['stock'] if hasattr(row,'__getitem__') else row[1]

    def fake_req(method, path, body=None):
        if path.endswith('/capture'):
            return 201, {'status':'COMPLETED','purchase_units':[{'payments':{'captures':[{'id':'CAP-999'}]}}]}
        return 201, {'id':'PP-ORDER-ABC','status':'CREATED'}
    monkeypatch.setattr(A, '_paypal_request', fake_req)

    client.post('/carrito/agregar', data={'product_id': sample_product['id'], 'quantity': 2})
    r1 = client.post('/checkout/paypal/create-order', json={
        'name':'Beto','email':'beto@x.com','address':'Calle 1','address_ext':'10','city':'GDL'})
    ppid = r1.get_json()['id']
    assert ppid == 'PP-ORDER-ABC'

    r2 = client.post('/checkout/paypal/capture-order', json={'orderID': ppid})
    assert r2.status_code == 200, r2.get_data(as_text=True)
    red = r2.get_json()['redirect']
    assert '/pedido/' in red

    # Orden creada, pagada, con referencia, stock descontado
    o = db.execute("SELECT * FROM orders WHERE payment_reference LIKE ?", ('%CAP-999%',)).fetchone()
    assert o is not None
    od = dict(o) if hasattr(o,'keys') else o
    assert od['payment_status'] == 'pagado'
    assert od['payment_method'] == 'paypal'
    row2 = db.execute("SELECT stock FROM products WHERE id=?", (sample_product['id'],)).fetchone()
    stock1 = row2['stock'] if hasattr(row2,'__getitem__') else row2[0]
    assert stock1 == stock0 - 2

    # Idempotencia: recapturar redirige a la misma orden, sin duplicar
    r3 = client.post('/checkout/paypal/capture-order', json={'orderID': ppid})
    assert r3.status_code == 200
    cnt = db.execute("SELECT COUNT(*) AS n FROM orders WHERE payment_reference LIKE ?", ('%CAP-999%',)).fetchone()
    n = cnt['n'] if hasattr(cnt,'__getitem__') else cnt[0]
    assert n == 1

def test_capture_not_completed_no_order(client, sample_product, db, monkeypatch):
    _enable_paypal(monkeypatch)
    def fake_req(method, path, body=None):
        if path.endswith('/capture'):
            return 201, {'status':'DECLINED'}
        return 201, {'id':'PP-DECLINE','status':'CREATED'}
    monkeypatch.setattr(A, '_paypal_request', fake_req)
    client.post('/carrito/agregar', data={'product_id': sample_product['id'], 'quantity': 1})
    ppid = client.post('/checkout/paypal/create-order', json={
        'name':'C','email':'c@x.com','address':'X','address_ext':'1','city':'CDMX'}).get_json()['id']
    r = client.post('/checkout/paypal/capture-order', json={'orderID': ppid})
    assert r.status_code == 402
    o = db.execute("SELECT COUNT(*) AS n FROM orders WHERE payment_reference LIKE ?", ('%'+ppid+'%',)).fetchone()
    n = o['n'] if hasattr(o,'__getitem__') else o[0]
    assert n == 0

def test_checkout_page_has_paypal_sdk(client, sample_product, monkeypatch):
    _enable_paypal(monkeypatch)
    client.post('/carrito/agregar', data={'product_id': sample_product['id'], 'quantity': 1})
    h = client.get('/checkout').get_data(as_text=True)
    assert 'paypal.com/sdk/js' in h
    assert 'paypal-button-container' in h
