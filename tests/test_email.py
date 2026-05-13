"""Sistema de emails: _send_email + email_log + _log_email."""
import pytest


def test_send_email_without_key_returns_false_and_logs_skipped(app):
    """Sin RESEND_API_KEY → no envía y registra como 'skipped' en email_log."""
    import app as appmod
    from app import _send_email, get_db
    appmod.RESEND_API_KEY = ''
    ok = _send_email('test@example.com', 'Subject Test',
                     '<p>hi</p>', email_type='admin_test')
    assert ok is False
    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM email_log WHERE to_addr=? ORDER BY id DESC LIMIT 1",
            ('test@example.com',)
        ).fetchone()
        assert row is not None
        assert row['status'] == 'skipped'
        assert row['email_type'] == 'admin_test'
        assert 'RESEND_API_KEY' in (row['error_msg'] or '')


def test_send_email_with_fake_key_logs_failed(app):
    """Key inválida → HTTP error captured, status='failed'."""
    import app as appmod
    from app import _send_email, get_db
    appmod.RESEND_API_KEY = 're_FAKE_INVALID_KEY'
    ok = _send_email('user@example.com', 'Bad Key Test',
                     '<p>hi</p>', email_type='order_new_customer', order_id=999,
                     bcc='owner@example.com')
    assert ok is False
    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM email_log WHERE to_addr=? AND order_id=999 "
            "ORDER BY id DESC LIMIT 1",
            ('user@example.com',)
        ).fetchone()
        assert row is not None
        assert row['status'] == 'failed'
        assert row['order_id'] == 999
        assert row['bcc'] == 'owner@example.com'
        assert 'HTTP' in (row['error_msg'] or '')


def test_log_email_normalizes_list_recipients(app):
    """to_addr / bcc como lista se persisten como CSV."""
    from app import _log_email, get_db
    _log_email(['a@x.com', 'b@x.com'], 'List Test', 'ok',
               email_type='order_new_admin',
               bcc=['c@x.com', 'd@x.com'])
    with app.app_context():
        row = get_db().execute(
            "SELECT * FROM email_log WHERE subject='List Test' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row['to_addr'] == 'a@x.com,b@x.com'
        assert row['bcc'] == 'c@x.com,d@x.com'


def test_email_type_labels_translate(app):
    """Filter Jinja email_type_label devuelve label legible."""
    with app.test_request_context():
        from app import _email_type_label
        assert _email_type_label('order_new_customer') == 'Confirmación de orden (cliente)'
        assert _email_type_label('low_stock') == 'Alerta de stock bajo (admin)'
        # Tipo desconocido: devuelve el slug
        assert _email_type_label('xyz') == 'xyz'
        # Vacío: '—'
        assert _email_type_label('') == '—'


def test_valid_email_format():
    from app import valid_email
    assert valid_email('alice@example.com') is True
    assert valid_email('alice.bob+filter@sub.example.co.uk') is True
    assert valid_email('not-an-email') is False
    assert valid_email('alice@') is False
    assert valid_email('@example.com') is False
    assert valid_email('') is False


def test_admin_emails_route_shows_logs(admin_client, app):
    """Después de varios envíos, /admin/emails los lista."""
    import app as appmod
    from app import _send_email
    appmod.RESEND_API_KEY = ''
    _send_email('viewer@example.com', 'Visible in log',
                '<p>x</p>', email_type='admin_test')
    r = admin_client.get('/admin/emails')
    assert r.status_code == 200
    assert b'viewer@example.com' in r.data
    assert b'Visible in log' in r.data
