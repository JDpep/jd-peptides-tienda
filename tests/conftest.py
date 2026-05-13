"""Fixtures comunes para todos los tests.

Cada test arranca con una DB SQLite fresca temporal (PRODUCTS_SEED + tablas
creadas por init_db). No tocamos Postgres; los tests son hermeticos.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Asegurar que el proyecto root esté en sys.path antes de importar app
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ----- Helpers para configurar el entorno del proceso de prueba ---------------

def _seed_env():
    """Setea env vars antes de importar app.py.
    Usa una DB temporal y secret_key fija para que las sesiones sean estables."""
    tmpfd, tmpdb = tempfile.mkstemp(suffix='_jdp_test.db', prefix='jdp_test_')
    os.close(tmpfd)
    os.environ['DATABASE_PATH'] = tmpdb
    os.environ['DATABASE_URL']  = ''
    os.environ['SECRET_KEY']    = 'pytest_secret_key_at_least_32_chars_long'
    # Bootstrap admin desde env (init_db lo crea si la tabla está vacía)
    os.environ.setdefault('ADMIN_USERNAME', 'admin_test')
    os.environ.setdefault('ADMIN_PASSWORD', 'TestPassword123!')
    # Aseguramos que Sentry/GA estén apagados
    os.environ['SENTRY_DSN'] = ''
    os.environ['GA_MEASUREMENT_ID'] = ''
    # Resend sin key para que email no salga, pero sí registre en email_log
    os.environ['RESEND_API_KEY'] = ''
    return tmpdb


_DB_PATH = _seed_env()


# Importar la app DESPUÉS de setear env (los defaults se leen al import time)
from app import app as flask_app  # noqa: E402


@pytest.fixture(scope='session', autouse=True)
def _cleanup_db():
    """Borra la DB temporal al finalizar la sesión de tests."""
    yield
    try:
        os.unlink(_DB_PATH)
    except OSError:
        pass


@pytest.fixture
def app():
    """Flask app configurada para testing."""
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,  # los CSRF custom siguen ahí, pero acepta sin token en testing
    )
    return flask_app


@pytest.fixture
def client(app):
    """Test client estándar (sin login)."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def admin_client(app):
    """Test client con sesión admin pre-establecida (saltea login)."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['admin_logged_in'] = True
            sess['admin_user']      = 'admin_test'
            sess['admin_role']      = 'superadmin'
        yield c


@pytest.fixture
def csrf_token(client):
    """Obtiene un CSRF token válido desde el login page."""
    r = client.get('/admin/login')
    html = r.get_data(as_text=True)
    import re
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else None


@pytest.fixture
def db():
    """Acceso directo a la DB para setup/teardown de fixtures."""
    from app import get_db
    with flask_app.app_context():
        yield get_db()


@pytest.fixture
def sample_product(db):
    """Garantiza al menos un producto activo y devuelve su ID."""
    row = db.execute(
        "SELECT id, sku, name, price FROM products WHERE active=1 LIMIT 1"
    ).fetchone()
    assert row, "PRODUCTS_SEED no se cargó — init_db falló"
    return dict(row) if hasattr(row, '__getitem__') else row
