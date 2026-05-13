"""Verificación de la BD post-migraciones — seed + v1...v15."""
import pytest


def test_db_has_expected_tables(db):
    """Tablas core deben existir."""
    expected = {
        'products', 'orders', 'order_items', 'admin_users',
        'stock_movements', 'purchase_orders', 'purchase_order_items',
        'product_images', 'supplier_documents', 'email_log',
    }
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    tables = {r['name'] for r in rows}
    missing = expected - tables
    assert not missing, f"Tablas faltantes: {missing}"


def test_all_migrations_applied(db):
    """v1..v15 deben tener al menos un marker en stock_movements.
    (Algunas migraciones tempranas insertan un marker por SKU, así que
    usamos >= 1 en lugar de == 1.)"""
    expected_versions = list(range(1, 16))  # v1..v15
    # v6 fue saltada en el código (no existe)
    expected_versions.remove(6)
    for v in expected_versions:
        n = db.execute(
            "SELECT COUNT(*) AS c FROM stock_movements "
            "WHERE reason LIKE ?", (f'migration:v{v}:%',)
        ).fetchone()['c']
        assert n >= 1, f"Migración v{v} no aplicada (markers: {n})"


def test_prices_are_in_mxn_range(db):
    """Tras v15, todos los precios deben estar en rango MXN (cientos/miles),
    no en USD pequeños (decenas)."""
    rows = db.execute(
        "SELECT sku, name, price FROM products WHERE active=1"
    ).fetchall()
    for r in rows:
        price = r['price']
        # Mínimo razonable MXN: $50. USD precio típico ~$50-250 quedaría
        # SOLAPADO, así que verificamos que tengamos productos > $1000 MXN
        # como sanity check sobre el set completo.
        assert price > 0, f"Producto sin precio: {r['sku']}"
    # Al menos un producto > $1000 (imposible si seguimos en USD)
    high = db.execute(
        "SELECT COUNT(*) AS c FROM products WHERE active=1 AND price > 1000"
    ).fetchone()['c']
    assert high >= 10, f"Solo {high} productos > $1000 MXN — ¿siguen en USD?"


def test_pdf_products_present(db):
    """Productos del PDF Feb 2026 deben estar en catálogo."""
    expected_skus = [
        'JDP-RT5', 'JDP-RT10', 'JDP-TB500', 'JDP-BPC157', 'JDP-MOTSC',
        'JDP-DSIP', 'JDP-IGF1', 'JDP-KPV', 'JDP-GHKCU', 'JDP-CJC-NODAC',
        'JDP-IPA', 'JDP-AOD', 'JDP-TESA', 'JDP-TA1', 'JDP-CJC-DAC',
        'JDP-SLUPP', 'JDP-5AMINO',
    ]
    for sku in expected_skus:
        row = db.execute(
            "SELECT id, active FROM products WHERE sku=?", (sku,)
        ).fetchone()
        assert row is not None, f"SKU {sku} no existe en DB"
        assert row['active'] == 1, f"SKU {sku} está inactivo"


def test_no_duplicate_skus(db):
    rows = db.execute(
        "SELECT sku, COUNT(*) AS c FROM products GROUP BY sku HAVING c > 1"
    ).fetchall()
    assert not rows, f"SKUs duplicados: {[r['sku'] for r in rows]}"


def test_no_duplicate_slugs(db):
    rows = db.execute(
        "SELECT slug, COUNT(*) AS c FROM products "
        "WHERE slug IS NOT NULL AND slug<>'' "
        "GROUP BY slug HAVING c > 1"
    ).fetchall()
    assert not rows, f"Slugs duplicados: {[r['slug'] for r in rows]}"


def test_all_active_products_have_required_fields(db):
    """Cada producto activo debe tener name, dose, price > 0, category."""
    bad = db.execute(
        "SELECT sku FROM products WHERE active=1 AND "
        "(name IS NULL OR name='' OR dose IS NULL OR dose='' OR "
        " price <= 0 OR category IS NULL OR category='')"
    ).fetchall()
    assert not bad, f"Productos con campos faltantes: {[r['sku'] for r in bad]}"


def test_admin_user_bootstrapped(db):
    """ADMIN_USERNAME del env debe haber creado un usuario."""
    row = db.execute(
        "SELECT username, role FROM admin_users WHERE username='admin_test'"
    ).fetchone()
    assert row is not None
    assert row['role'] == 'superadmin'
