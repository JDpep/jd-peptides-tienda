"""Admin routes — requieren sesión admin pre-establecida."""
import pytest


def test_admin_dashboard_loads(admin_client):
    r = admin_client.get('/admin/dashboard')
    # Puede no existir endpoint con ese nombre exacto — probar variantes
    if r.status_code == 404:
        r = admin_client.get('/admin')
    assert r.status_code in (200, 302)


def test_admin_productos_list(admin_client):
    r = admin_client.get('/admin/productos')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    # Algún SKU del seed debería aparecer
    assert 'JDP-' in body


def test_admin_ordenes_list(admin_client):
    r = admin_client.get('/admin/ordenes')
    assert r.status_code == 200


def test_admin_reportes_renders(admin_client):
    r = admin_client.get('/admin/reportes')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Ingresos' in body
    assert 'Ticket promedio' in body
    assert 'Ventas diarias' in body


@pytest.mark.parametrize('days', [7, 30, 90, 180, 365])
def test_admin_reportes_window_param(admin_client, days):
    r = admin_client.get(f'/admin/reportes?days={days}')
    assert r.status_code == 200


def test_admin_reportes_invalid_days_falls_back(admin_client):
    """Valores inválidos no crashean (clamped al rango válido)."""
    r = admin_client.get('/admin/reportes?days=999999')
    assert r.status_code == 200
    r = admin_client.get('/admin/reportes?days=abc')
    assert r.status_code == 200
    r = admin_client.get('/admin/reportes?days=-5')
    assert r.status_code == 200


def test_admin_emails_renders(admin_client):
    r = admin_client.get('/admin/emails')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Auditor' in body
    assert 'Resend API' in body


def test_admin_emails_filters(admin_client):
    for status in ('ok', 'failed', 'skipped'):
        r = admin_client.get(f'/admin/emails?status={status}')
        assert r.status_code == 200


def test_admin_nav_includes_reportes_and_emails(admin_client):
    r = admin_client.get('/admin/productos')
    body = r.get_data(as_text=True)
    assert '/admin/reportes' in body
    assert '/admin/emails' in body


def test_admin_without_session_blocked(client):
    """Sin login, /admin/productos redirige a /admin/login."""
    r = client.get('/admin/productos', follow_redirects=False)
    assert r.status_code in (302, 401, 403)
