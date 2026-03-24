import os
import sqlite3
import json
import uuid
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g)

app = Flask(__name__)
app.secret_key = 'jdp_secret_key_2024_ultra_secure'

DATABASE = os.path.join(os.path.dirname(__file__), 'database', 'jdp.db')

# ---------------------------------------------------------------------------
# Email configuration
# ---------------------------------------------------------------------------
# Para activar: pon tu cuenta Gmail remitente y una "Contraseña de aplicación"
# (Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicación)
EMAIL_SENDER   = 'jdpeptides@gmail.com'
EMAIL_PASSWORD = 'jnubbtghjzmqmxnp'
EMAIL_NOTIFY   = ['aamiga2006@gmail.com', 'jdpeptides@gmail.com']

def _build_items_rows(items):
    return ''.join(f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee">{i['product_name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{i['quantity']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{i['dose']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right">${i['unit_price']:.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:700">${i['subtotal']:.2f}</td>
        </tr>""" for i in items)

def _payment_label(method):
    return {'transferencia':'Transferencia Bancaria','efectivo':'Efectivo',
            'criptomonedas':'Criptomonedas','zelle':'Zelle','paypal':'PayPal'}.get(method, method)

def _admin_html(order, items):
    """Email interno para los administradores — muestra todos los datos."""
    pl = _payment_label(order['payment_method'])
    rows = _build_items_rows(items)
    notes_row = (f'<tr><td style="padding:5px 0;color:#666">Notas</td>'
                 f'<td style="padding:5px 0;color:#555;font-style:italic">{order["notes"]}</td></tr>'
                 if order['notes'] else '')
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;background:#fff">
      <div style="background:#0d0d0d;padding:28px 32px;text-align:center">
        <h1 style="margin:0;color:#c9a227;font-size:22px;letter-spacing:2px">JD PEPTIDES</h1>
        <p style="margin:6px 0 0;color:#999;font-size:12px;letter-spacing:1px">⚡ NUEVA ORDEN DE COMPRA</p>
      </div>
      <div style="background:#c9a227;padding:14px 32px">
        <span style="color:#fff;font-weight:700;font-size:16px">Orden # {order['order_number']}</span>
        &nbsp;&nbsp;<span style="color:#fff;font-size:13px">{order['created_at'][:16]}</span>
      </div>
      <div style="padding:28px 32px">
        <h3 style="margin:0 0 12px;color:#0d0d0d;font-size:13px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #c9a227;padding-bottom:8px">Datos del Cliente</h3>
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:24px">
          <tr><td style="padding:5px 0;color:#666;width:130px">Nombre</td><td style="padding:5px 0;font-weight:600;color:#111">{order['customer_name']}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Email</td><td style="padding:5px 0;color:#111">{order['customer_email']}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Teléfono</td><td style="padding:5px 0;color:#111">{order['customer_phone'] or '—'}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Dirección</td><td style="padding:5px 0;color:#111">{order['address']}, {order['city']}{', ' + order['state'] if order['state'] else ''} {order['zip_code'] or ''}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Método de pago</td><td style="padding:5px 0;font-weight:700;color:#c9a227">{pl}</td></tr>
          {notes_row}
        </table>
        <h3 style="margin:0 0 12px;color:#0d0d0d;font-size:13px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #c9a227;padding-bottom:8px">Productos</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
          <thead><tr style="background:#f5f5f5">
            <th style="padding:10px 12px;text-align:left;color:#333">Producto</th>
            <th style="padding:10px 12px;text-align:center;color:#333">Cant.</th>
            <th style="padding:10px 12px;text-align:center;color:#333">Dosis</th>
            <th style="padding:10px 12px;text-align:right;color:#333">P. Unit.</th>
            <th style="padding:10px 12px;text-align:right;color:#333">Subtotal</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <table style="width:220px;margin-left:auto;border-collapse:collapse;font-size:14px">
          <tr><td style="padding:5px 0;color:#666">Subtotal</td><td style="padding:5px 0;text-align:right">${order['subtotal']:.2f}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Envío</td><td style="padding:5px 0;text-align:right">{'Gratis' if order['shipping']==0 else f'${order["shipping"]:.2f}'}</td></tr>
          <tr style="border-top:2px solid #c9a227">
            <td style="padding:10px 0;font-weight:700;font-size:16px;color:#0d0d0d">TOTAL</td>
            <td style="padding:10px 0;text-align:right;font-weight:800;font-size:18px;color:#c9a227">${order['total']:.2f}</td>
          </tr>
        </table>
      </div>
      <div style="background:#f9f9f9;padding:14px 32px;text-align:center;border-top:1px solid #eee">
        <p style="margin:0;color:#999;font-size:11px">JD Peptides · Panel Admin · Correo automático</p>
      </div>
    </div>"""

def _customer_html(order, items):
    """Email de confirmación para el cliente — tono amigable y profesional."""
    pl = _payment_label(order['payment_method'])
    rows = _build_items_rows(items)
    payment_instructions = {
        'transferencia': '<p style="background:#fffbea;border-left:4px solid #c9a227;padding:12px 16px;margin:0;font-size:13px;color:#555">Realiza tu transferencia y envíanos el comprobante por WhatsApp o email para procesar tu pedido.</p>',
        'zelle':         '<p style="background:#fffbea;border-left:4px solid #c9a227;padding:12px 16px;margin:0;font-size:13px;color:#555">Envía el pago por Zelle y comparte el comprobante con nosotros para confirmar tu pedido.</p>',
        'paypal':        '<p style="background:#fffbea;border-left:4px solid #c9a227;padding:12px 16px;margin:0;font-size:13px;color:#555">Completa el pago por PayPal. Te contactaremos en breve para confirmar.</p>',
        'efectivo':      '<p style="background:#fffbea;border-left:4px solid #c9a227;padding:12px 16px;margin:0;font-size:13px;color:#555">Te contactaremos pronto para coordinar la entrega y el pago en efectivo.</p>',
        'criptomonedas': '<p style="background:#fffbea;border-left:4px solid #c9a227;padding:12px 16px;margin:0;font-size:13px;color:#555">Envíanos el hash de tu transacción para confirmar tu pedido.</p>',
    }.get(order['payment_method'], '')

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;background:#fff">
      <div style="background:#0d0d0d;padding:32px;text-align:center">
        <h1 style="margin:0;color:#c9a227;font-size:24px;letter-spacing:2px">JD PEPTIDES</h1>
        <p style="margin:8px 0 0;color:#ccc;font-size:13px">Péptidos de Investigación de Calidad Superior</p>
      </div>
      <div style="background:#c9a227;padding:16px 32px;text-align:center">
        <p style="margin:0;color:#fff;font-weight:700;font-size:18px">✓ ¡Pedido recibido!</p>
      </div>
      <div style="padding:32px">
        <p style="font-size:15px;color:#333;margin:0 0 8px">Hola <strong>{order['customer_name']}</strong>,</p>
        <p style="font-size:14px;color:#555;margin:0 0 24px">Hemos recibido tu pedido correctamente. A continuación encontrarás el resumen.</p>

        <div style="background:#f9f9f9;border-radius:8px;padding:16px 20px;margin-bottom:24px">
          <span style="font-size:13px;color:#888">Número de orden</span><br>
          <span style="font-size:20px;font-weight:700;color:#0d0d0d;letter-spacing:1px">{order['order_number']}</span>
          <span style="font-size:12px;color:#aaa;margin-left:12px">{order['created_at'][:16]}</span>
        </div>

        <h3 style="margin:0 0 12px;color:#0d0d0d;font-size:13px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #c9a227;padding-bottom:8px">Productos ordenados</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px">
          <thead><tr style="background:#f5f5f5">
            <th style="padding:10px 12px;text-align:left;color:#333">Producto</th>
            <th style="padding:10px 12px;text-align:center;color:#333">Cant.</th>
            <th style="padding:10px 12px;text-align:center;color:#333">Dosis</th>
            <th style="padding:10px 12px;text-align:right;color:#333">P. Unit.</th>
            <th style="padding:10px 12px;text-align:right;color:#333">Subtotal</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <table style="width:220px;margin-left:auto;border-collapse:collapse;font-size:14px;margin-bottom:24px">
          <tr><td style="padding:5px 0;color:#666">Subtotal</td><td style="padding:5px 0;text-align:right">${order['subtotal']:.2f}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Envío</td><td style="padding:5px 0;text-align:right">{'Gratis' if order['shipping']==0 else f'${order["shipping"]:.2f}'}</td></tr>
          <tr style="border-top:2px solid #c9a227">
            <td style="padding:10px 0;font-weight:700;font-size:15px;color:#0d0d0d">TOTAL</td>
            <td style="padding:10px 0;text-align:right;font-weight:800;font-size:17px;color:#c9a227">${order['total']:.2f}</td>
          </tr>
        </table>

        <h3 style="margin:0 0 12px;color:#0d0d0d;font-size:13px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #c9a227;padding-bottom:8px">Método de pago: {pl}</h3>
        {payment_instructions}

        <p style="margin:24px 0 0;font-size:13px;color:#777">¿Tienes alguna pregunta? Contáctanos en <a href="mailto:jdpeptides@gmail.com" style="color:#c9a227">jdpeptides@gmail.com</a></p>
      </div>
      <div style="background:#0d0d0d;padding:16px 32px;text-align:center">
        <p style="margin:0;color:#666;font-size:11px">JD Peptides · For Research Use Only · Los productos son exclusivamente para investigación científica.</p>
      </div>
    </div>"""

def _status_update_html(order, new_status, new_payment):
    """Email al cliente cuando cambia el estado de su orden."""
    status_config = {
        'procesando': {
            'icon': '⚙️',
            'color': '#3b82f6',
            'title': 'Tu pedido está siendo procesado',
            'message': 'Estamos verificando tu pago y preparando tu pedido. Te notificaremos en cuanto sea enviado.',
        },
        'enviado': {
            'icon': '🚚',
            'color': '#f59e0b',
            'title': '¡Tu pedido está en camino!',
            'message': 'Tu pedido ha sido despachado y está en camino hacia ti. Pronto lo recibirás.',
        },
        'entregado': {
            'icon': '✅',
            'color': '#10b981',
            'title': '¡Pedido entregado!',
            'message': 'Tu pedido ha sido entregado. Esperamos que disfrutes tus productos. ¡Gracias por confiar en JD Peptides!',
        },
        'cancelado': {
            'icon': '❌',
            'color': '#ef4444',
            'title': 'Tu pedido ha sido cancelado',
            'message': 'Lamentamos informarte que tu pedido ha sido cancelado. Si tienes alguna pregunta o crees que es un error, contáctanos de inmediato.',
        },
    }
    payment_config = {
        'reembolsado': {
            'icon': '💸',
            'color': '#8b5cf6',
            'title': 'Tu reembolso ha sido procesado',
            'message': 'Hemos procesado el reembolso de tu pedido. El monto será acreditado según el método de pago utilizado en un plazo de 3 a 5 días hábiles.',
        },
    }

    # Determinar qué evento mostrar (el pago tiene prioridad si es reembolso)
    if new_payment == 'reembolsado':
        cfg = payment_config['reembolsado']
    elif new_status in status_config:
        cfg = status_config[new_status]
    else:
        return None  # No hay nada relevante que notificar

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;background:#fff">
      <div style="background:#0d0d0d;padding:32px;text-align:center">
        <h1 style="margin:0;color:#c9a227;font-size:24px;letter-spacing:2px">JD PEPTIDES</h1>
        <p style="margin:8px 0 0;color:#ccc;font-size:13px">Péptidos de Investigación de Calidad Superior</p>
      </div>
      <div style="background:{cfg['color']};padding:16px 32px;text-align:center">
        <p style="margin:0;color:#fff;font-weight:700;font-size:18px">{cfg['icon']} {cfg['title']}</p>
      </div>
      <div style="padding:32px">
        <p style="font-size:15px;color:#333;margin:0 0 8px">Hola <strong>{order['customer_name']}</strong>,</p>
        <p style="font-size:14px;color:#555;margin:0 0 24px">{cfg['message']}</p>

        <div style="background:#f9f9f9;border-radius:8px;padding:16px 20px;margin-bottom:24px">
          <span style="font-size:13px;color:#888">Número de orden</span><br>
          <span style="font-size:20px;font-weight:700;color:#0d0d0d;letter-spacing:1px">{order['order_number']}</span>
        </div>

        <table style="width:220px;margin-left:auto;border-collapse:collapse;font-size:14px;margin-bottom:24px">
          <tr><td style="padding:5px 0;color:#666">Subtotal</td><td style="padding:5px 0;text-align:right">${order['subtotal']:.2f}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Envío</td><td style="padding:5px 0;text-align:right">{'Gratis' if order['shipping']==0 else f'${order["shipping"]:.2f}'}</td></tr>
          <tr style="border-top:2px solid #c9a227">
            <td style="padding:10px 0;font-weight:700;font-size:15px;color:#0d0d0d">TOTAL</td>
            <td style="padding:10px 0;text-align:right;font-weight:800;font-size:17px;color:#c9a227">${order['total']:.2f}</td>
          </tr>
        </table>

        <p style="margin:24px 0 0;font-size:13px;color:#777">¿Tienes alguna pregunta? Contáctanos en <a href="mailto:jdpeptides@gmail.com" style="color:#c9a227">jdpeptides@gmail.com</a></p>
      </div>
      <div style="background:#0d0d0d;padding:16px 32px;text-align:center">
        <p style="margin:0;color:#666;font-size:11px">JD Peptides · For Research Use Only · Los productos son exclusivamente para investigación científica.</p>
      </div>
    </div>"""


def send_status_email(order, new_status, new_payment):
    """Envía notificación al cliente cuando cambia el estado de su orden."""
    html = _status_update_html(order, new_status, new_payment)
    if not html:
        return

    subject_map = {
        'procesando': f'⚙️ Tu pedido está siendo procesado — {order["order_number"]}',
        'enviado':    f'🚚 ¡Tu pedido está en camino! — {order["order_number"]}',
        'entregado':  f'✅ Pedido entregado — {order["order_number"]}',
        'cancelado':  f'❌ Pedido cancelado — {order["order_number"]}',
    }
    if new_payment == 'reembolsado':
        subject = f'💸 Reembolso procesado — {order["order_number"]}'
    else:
        subject = subject_map.get(new_status, f'Actualización de tu pedido — {order["order_number"]}')

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = f'JD Peptides <{EMAIL_SENDER}>'
            msg['To']      = order['customer_email']
            msg.attach(MIMEText(html, 'html'))
            smtp.sendmail(EMAIL_SENDER, order['customer_email'], msg.as_string())
        print(f"[Email] Notificación de estado enviada a {order['customer_email']} ({new_status or new_payment})")
    except Exception as e:
        print(f"[Email] Error enviando notificación de estado: {e}")


def send_order_email(order, items):
    """Envía notificación a admins y confirmación al cliente."""
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)

            # 1) Email interno a los 2 admins
            admin_html = _admin_html(order, items)
            for recipient in EMAIL_NOTIFY:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f'⚡ Nueva Orden JD Peptides — {order["order_number"]}'
                msg['From']    = f'JD Peptides <{EMAIL_SENDER}>'
                msg['To']      = recipient
                msg.attach(MIMEText(admin_html, 'html'))
                smtp.sendmail(EMAIL_SENDER, recipient, msg.as_string())

            # 2) Email de confirmación al cliente
            customer_html = _customer_html(order, items)
            msg2 = MIMEMultipart('alternative')
            msg2['Subject'] = f'✓ Confirmación de tu pedido JD Peptides — {order["order_number"]}'
            msg2['From']    = f'JD Peptides <{EMAIL_SENDER}>'
            msg2['To']      = order['customer_email']
            msg2.attach(MIMEText(customer_html, 'html'))
            smtp.sendmail(EMAIL_SENDER, order['customer_email'], msg2.as_string())

        print(f"[Email] Enviado a admins {EMAIL_NOTIFY} y al cliente {order['customer_email']}")
    except Exception as e:
        print(f"[Email] Error: {e}")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Schema & seed
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    dose TEXT NOT NULL,
    price REAL NOT NULL,
    description TEXT,
    benefits TEXT,
    stock INTEGER DEFAULT 0,
    low_stock_alert INTEGER DEFAULT 5,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    payment_method TEXT,
    notes TEXT,
    subtotal REAL,
    shipping REAL DEFAULT 0,
    total REAL,
    status TEXT DEFAULT 'nuevo',
    payment_status TEXT DEFAULT 'pendiente',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    product_sku TEXT,
    dose TEXT,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT,
    reference TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    supplier TEXT NOT NULL,
    expected_date TEXT,
    notes TEXT,
    total REAL DEFAULT 0,
    status TEXT DEFAULT 'pendiente',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""

PRODUCTS_SEED = [
    {
        'sku': 'JDP-IGF1',
        'name': 'IGF-1 LR3',
        'category': 'Performance',
        'dose': '1 mg',
        'price': 89.99,
        'description': 'IGF-1 LR3 es una forma modificada del factor de crecimiento similar a la insulina tipo 1, diseñado para investigación en crecimiento muscular y recuperación.',
        'benefits': 'Potente efecto anabólico|Favorece el crecimiento muscular|Estimula la pérdida de grasa|Apoya la recuperación de lesiones',
        'stock': 25,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-KPV',
        'name': 'KPV',
        'category': 'Recuperación',
        'dose': '10 mg',
        'price': 59.99,
        'description': 'KPV es un tripéptido derivado del alfa-MSH, estudiado por sus propiedades antiinflamatorias y protectoras de tejidos.',
        'benefits': 'Reduce la inflamación|Protege y repara tejidos|Alivia el dolor y molestias|Favorece la barrera intestinal',
        'stock': 30,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-MOTSC',
        'name': 'MOTS-C',
        'category': 'Metabolismo',
        'dose': '10 mg',
        'price': 79.99,
        'description': 'MOTS-C es un péptido mitocondrial que regula el metabolismo energético y la homeostasis de la glucosa.',
        'benefits': 'Incrementa la sensibilidad a la insulina|Mejora el metabolismo celular|Favorece energía y vitalidad|Apoyo en pérdida de grasa',
        'stock': 20,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-BPC157',
        'name': 'BPC-157',
        'category': 'Recuperación',
        'dose': '10 mg',
        'price': 69.99,
        'description': 'BPC-157 es un pentadecapéptido estable derivado de la proteína de protección gástrica, investigado ampliamente por sus efectos regeneradores.',
        'benefits': 'Regenera tejidos intestinales y úlceras|Favorece tendones y ligamentos|Potente efecto reparador sistémico|Ayuda en condiciones inflamatorias',
        'stock': 35,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-TB500',
        'name': 'TB-500',
        'category': 'Recuperación',
        'dose': '10 mg',
        'price': 74.99,
        'description': 'TB-500 es una forma sintética de la Timosina Beta-4, estudiada por su papel en la regeneración de tejidos y recuperación de lesiones.',
        'benefits': 'Acelera la recuperación de lesiones|Reparación muscular y tendinosa|Favorece la cicatrización|Mejora la flexibilidad y movilidad|Útil en rehabilitación deportiva',
        'stock': 28,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-GHKCU',
        'name': 'GHK-Cu',
        'category': 'Anti-aging',
        'dose': '50 mg',
        'price': 54.99,
        'description': 'GHK-Cu es un tripéptido de cobre que ocurre naturalmente, reconocido por sus propiedades regenerativas en la piel y tejidos.',
        'benefits': 'Efecto anti-envejecimiento notable|Estimula el crecimiento capilar|Mejora la cicatrización de la piel|Reduce la inflamación en tejidos|Potencia la regeneración celular',
        'stock': 40,
        'low_stock_alert': 8,
    },
    {
        'sku': 'JDP-RETA',
        'name': 'Retatrutide',
        'category': 'Pérdida de Peso',
        'dose': '5 mg',
        'price': 149.99,
        'description': 'Retatrutide es un agonista triple de GIP/GLP-1/Glucagón investigado por su potente efecto en la regulación del peso corporal y el metabolismo.',
        'benefits': 'Ayuda en la Pérdida de Peso|Mejora el Control del Apetito|Reduce los Niveles de Azúcar en Sangre|Promueve Buena Salud Metabólica',
        'stock': 15,
        'low_stock_alert': 3,
    },
    {
        'sku': 'JDP-DSIP',
        'name': 'DSIP',
        'category': 'Bienestar',
        'dose': '5 mg',
        'price': 64.99,
        'description': 'DSIP (Delta Sleep-Inducing Peptide) es un neuropéptido investigado por su papel en la regulación del sueño y el ritmo circadiano.',
        'benefits': 'Mejora la calidad del sueño|Reduce el estrés oxidativo|Regulación del ritmo circadiano|Efectos neuroprotectores',
        'stock': 22,
        'low_stock_alert': 5,
    },
    {
        'sku': 'JDP-TA1',
        'name': 'Thymosin Alpha 1',
        'category': 'Inmune',
        'dose': '10 mg',
        'price': 84.99,
        'description': 'Thymosin Alpha 1 es un péptido inmunomodulador natural derivado del timo, estudiado por sus efectos en el sistema inmunológico.',
        'benefits': 'Fortalece el sistema inmune|Acción antiviral y antibacteriana|Apoyo en enfermedades autoinmunes|Estimula células T y NK',
        'stock': 18,
        'low_stock_alert': 4,
    },
    {
        'sku': 'JDP-IPA',
        'name': 'Ipamorelin',
        'category': 'Performance',
        'dose': '5 mg',
        'price': 69.99,
        'description': 'Ipamorelin es un secretagogo de la hormona de crecimiento selectivo, investigado por su capacidad de estimular la liberación de GH sin efectos secundarios significativos.',
        'benefits': 'Estimula la hormona de crecimiento|Mejora la composición corporal|Favorece la recuperación muscular|Mejora el sueño profundo',
        'stock': 32,
        'low_stock_alert': 6,
    },
    {
        'sku': 'JDP-TESA',
        'name': 'Tesamorelin',
        'category': 'Performance',
        'dose': '5 mg',
        'price': 89.99,
        'description': 'Tesamorelin es un análogo de la hormona liberadora de hormona de crecimiento (GHRH), estudiado por sus efectos en la reducción de grasa visceral.',
        'benefits': 'Estimula la hormona de crecimiento|Reduce grasa visceral|Mejora la composición corporal|Efectos neuroprotectores',
        'stock': 3,
        'low_stock_alert': 5,
    },
]


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    # Seed products if empty
    count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        for p in PRODUCTS_SEED:
            db.execute(
                """INSERT INTO products (sku, name, category, dose, price, description, benefits, stock, low_stock_alert)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p['sku'], p['name'], p['category'], p['dose'], p['price'],
                 p['description'], p['benefits'], p['stock'], p['low_stock_alert'])
            )
        db.commit()


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Cart helpers
# ---------------------------------------------------------------------------

def get_cart():
    return session.get('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def cart_count():
    cart = get_cart()
    return sum(item['quantity'] for item in cart.values())


def cart_total():
    cart = get_cart()
    return sum(item['quantity'] * item['price'] for item in cart.values())


app.jinja_env.globals['cart_count'] = cart_count


# ---------------------------------------------------------------------------
# Customer routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    with app.app_context():
        products = query_db("SELECT * FROM products WHERE active=1 LIMIT 6")
        categories = query_db("SELECT DISTINCT category FROM products WHERE active=1")
    return render_template('index.html', products=products, categories=categories)


@app.route('/catalogo')
def catalogo():
    category = request.args.get('categoria', '')
    search = request.args.get('q', '')
    if category and search:
        products = query_db(
            "SELECT * FROM products WHERE active=1 AND category=? AND (name LIKE ? OR description LIKE ?) ORDER BY name",
            (category, f'%{search}%', f'%{search}%')
        )
    elif category:
        products = query_db(
            "SELECT * FROM products WHERE active=1 AND category=? ORDER BY name",
            (category,)
        )
    elif search:
        products = query_db(
            "SELECT * FROM products WHERE active=1 AND (name LIKE ? OR description LIKE ?) ORDER BY name",
            (f'%{search}%', f'%{search}%')
        )
    else:
        products = query_db("SELECT * FROM products WHERE active=1 ORDER BY name")

    categories = query_db("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category")
    return render_template('catalogo.html', products=products, categories=categories,
                           current_category=category, search=search)


@app.route('/producto/<int:pid>')
def producto(pid):
    product = query_db("SELECT * FROM products WHERE id=? AND active=1", (pid,), one=True)
    if not product:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('catalogo'))
    related = query_db(
        "SELECT * FROM products WHERE active=1 AND category=? AND id!=? LIMIT 3",
        (product['category'], pid)
    )
    benefits = product['benefits'].split('|') if product['benefits'] else []
    return render_template('producto.html', product=product, related=related, benefits=benefits)


@app.route('/carrito/agregar', methods=['POST'])
def agregar_carrito():
    data = request.get_json() or request.form
    pid = str(data.get('product_id'))
    qty = int(data.get('quantity', 1))

    product = query_db("SELECT * FROM products WHERE id=? AND active=1", (pid,), one=True)
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'}), 404

    cart = get_cart()
    if pid in cart:
        cart[pid]['quantity'] += qty
    else:
        cart[pid] = {
            'id': product['id'],
            'name': product['name'],
            'dose': product['dose'],
            'price': product['price'],
            'sku': product['sku'],
            'quantity': qty,
        }
    save_cart(cart)

    return jsonify({
        'success': True,
        'message': f'{product["name"]} agregado al carrito',
        'cart_count': cart_count(),
        'cart_total': cart_total(),
    })


@app.route('/carrito')
def carrito():
    cart = get_cart()
    subtotal = cart_total()
    shipping = 0 if subtotal >= 200 else 15
    total = subtotal + shipping
    return render_template('carrito.html', cart=cart, subtotal=subtotal,
                           shipping=shipping, total=total)


@app.route('/carrito/actualizar', methods=['POST'])
def actualizar_carrito():
    cart = get_cart()
    for key, val in request.form.items():
        if key.startswith('qty_'):
            pid = key[4:]
            qty = int(val)
            if qty <= 0:
                cart.pop(pid, None)
            elif pid in cart:
                cart[pid]['quantity'] = qty
    save_cart(cart)
    flash('Carrito actualizado.', 'success')
    return redirect(url_for('carrito'))


@app.route('/carrito/eliminar/<pid>', methods=['POST'])
def eliminar_carrito(pid):
    cart = get_cart()
    cart.pop(str(pid), None)
    save_cart(cart)
    return jsonify({'success': True, 'cart_count': cart_count()})


@app.route('/checkout')
def checkout():
    cart = get_cart()
    if not cart:
        flash('Tu carrito está vacío.', 'error')
        return redirect(url_for('catalogo'))
    subtotal = cart_total()
    shipping = 0 if subtotal >= 200 else 15
    total = subtotal + shipping
    return render_template('checkout.html', cart=cart, subtotal=subtotal,
                           shipping=shipping, total=total)


@app.route('/checkout/procesar', methods=['POST'])
def procesar_checkout():
    cart = get_cart()
    if not cart:
        return redirect(url_for('catalogo'))

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    zip_code = request.form.get('zip_code', '').strip()
    payment_method = request.form.get('payment_method', '')
    notes = request.form.get('notes', '').strip()

    if not all([name, email, address, city, payment_method]):
        flash('Por favor completa todos los campos requeridos.', 'error')
        return redirect(url_for('checkout'))

    subtotal = cart_total()
    shipping = 0 if subtotal >= 200 else 15
    total = subtotal + shipping

    order_number = f'JDP-{datetime.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'

    order_id = execute_db(
        """INSERT INTO orders (order_number, customer_name, customer_email, customer_phone,
           address, city, state, zip_code, payment_method, notes, subtotal, shipping, total)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (order_number, name, email, phone, address, city, state, zip_code,
         payment_method, notes, subtotal, shipping, total)
    )

    for pid, item in cart.items():
        execute_db(
            """INSERT INTO order_items (order_id, product_id, product_name, product_sku, dose, quantity, unit_price, subtotal)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, item['id'], item['name'], item['sku'], item['dose'],
             item['quantity'], item['price'], item['quantity'] * item['price'])
        )
        # Decrease stock
        execute_db("UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?",
                   (item['quantity'], item['id']))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'salida', ?, 'Venta', ?)",
            (item['id'], item['quantity'], order_number)
        )

    session.pop('cart', None)
    order = query_db("SELECT * FROM orders WHERE id=?", (order_id,), one=True)
    items = query_db("SELECT * FROM order_items WHERE order_id=?", (order_id,))

    # Enviar notificación por email (en background para no bloquear la respuesta)
    import threading
    threading.Thread(target=send_order_email, args=(dict(order), [dict(i) for i in items]), daemon=True).start()

    return render_template('pedido_exitoso.html', order=order, items=items)


@app.route('/pedido/<order_number>')
def pedido(order_number):
    order = query_db("SELECT * FROM orders WHERE order_number=?", (order_number,), one=True)
    if not order:
        flash('Pedido no encontrado.', 'error')
        return redirect(url_for('index'))
    items = query_db("SELECT * FROM order_items WHERE order_id=?", (order['id'],))
    return render_template('pedido_exitoso.html', order=order, items=items)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == 'Aa52902763':
            session['admin_logged_in'] = True
            flash('Bienvenido al panel de administración.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Contraseña incorrecta.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    today = date.today().isoformat()

    total_sales = query_db(
        "SELECT COALESCE(SUM(total),0) as v FROM orders WHERE status != 'cancelado'",
        one=True
    )['v']

    orders_today = query_db(
        "SELECT COUNT(*) as c FROM orders WHERE date(created_at)=?", (today,), one=True
    )['c']

    active_products = query_db(
        "SELECT COUNT(*) as c FROM products WHERE active=1", one=True
    )['c']

    low_stock = query_db(
        "SELECT COUNT(*) as c FROM products WHERE active=1 AND stock <= low_stock_alert", one=True
    )['c']

    recent_orders = query_db(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10"
    )

    low_stock_products = query_db(
        "SELECT * FROM products WHERE active=1 AND stock <= low_stock_alert ORDER BY stock ASC LIMIT 10"
    )

    return render_template('admin/dashboard.html',
                           total_sales=total_sales,
                           orders_today=orders_today,
                           active_products=active_products,
                           low_stock=low_stock,
                           recent_orders=recent_orders,
                           low_stock_products=low_stock_products)


@app.route('/admin/productos')
@admin_required
def admin_productos():
    products = query_db("SELECT * FROM products ORDER BY name")
    return render_template('admin/productos.html', products=products)


@app.route('/admin/productos/nuevo', methods=['GET', 'POST'])
@admin_required
def admin_nuevo_producto():
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        dose = request.form.get('dose', '').strip()
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        low_stock_alert = int(request.form.get('low_stock_alert', 5))
        description = request.form.get('description', '').strip()
        benefits_raw = request.form.get('benefits', '').strip()
        benefits = '|'.join(line.strip() for line in benefits_raw.splitlines() if line.strip())
        active = 1 if request.form.get('active') else 0

        try:
            execute_db(
                """INSERT INTO products (sku, name, category, dose, price, stock, low_stock_alert, description, benefits, active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sku, name, category, dose, price, stock, low_stock_alert, description, benefits, active)
            )
            flash('Producto creado exitosamente.', 'success')
            return redirect(url_for('admin_productos'))
        except Exception as e:
            flash(f'Error al crear producto: {e}', 'error')

    categories = [r['category'] for r in query_db("SELECT DISTINCT category FROM products ORDER BY category")]
    return render_template('admin/producto_form.html', product=None, categories=categories, action='nuevo')


@app.route('/admin/productos/<int:pid>/editar', methods=['GET', 'POST'])
@admin_required
def admin_editar_producto(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not product:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('admin_productos'))

    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        dose = request.form.get('dose', '').strip()
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
        low_stock_alert = int(request.form.get('low_stock_alert', 5))
        description = request.form.get('description', '').strip()
        benefits_raw = request.form.get('benefits', '').strip()
        benefits = '|'.join(line.strip() for line in benefits_raw.splitlines() if line.strip())
        active = 1 if request.form.get('active') else 0

        try:
            execute_db(
                """UPDATE products SET sku=?, name=?, category=?, dose=?, price=?, stock=?,
                   low_stock_alert=?, description=?, benefits=?, active=? WHERE id=?""",
                (sku, name, category, dose, price, stock, low_stock_alert, description, benefits, active, pid)
            )
            flash('Producto actualizado.', 'success')
            return redirect(url_for('admin_productos'))
        except Exception as e:
            flash(f'Error al actualizar: {e}', 'error')

    benefits_text = (product['benefits'] or '').replace('|', '\n')
    categories = [r['category'] for r in query_db("SELECT DISTINCT category FROM products ORDER BY category")]
    return render_template('admin/producto_form.html', product=product,
                           benefits_text=benefits_text, categories=categories, action='editar')


@app.route('/admin/productos/<int:pid>/toggle', methods=['POST'])
@admin_required
def admin_toggle_producto(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if product:
        new_active = 0 if product['active'] else 1
        execute_db("UPDATE products SET active=? WHERE id=?", (new_active, pid))
        status = 'activado' if new_active else 'desactivado'
        flash(f'Producto {status}.', 'success')
    return redirect(url_for('admin_productos'))


@app.route('/admin/inventario')
@admin_required
def admin_inventario():
    products = query_db("SELECT * FROM products ORDER BY name")
    movements = query_db(
        """SELECT sm.*, p.name as product_name, p.sku
           FROM stock_movements sm
           JOIN products p ON sm.product_id = p.id
           ORDER BY sm.created_at DESC LIMIT 50"""
    )
    return render_template('admin/inventario.html', products=products, movements=movements)


@app.route('/admin/inventario/<int:pid>/ajuste', methods=['POST'])
@admin_required
def admin_ajuste_stock(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not product:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('admin_inventario'))

    mov_type = request.form.get('type', 'ajuste')
    quantity = int(request.form.get('quantity', 0))
    reason = request.form.get('reason', '').strip()

    if quantity <= 0:
        flash('La cantidad debe ser mayor a 0.', 'error')
        return redirect(url_for('admin_inventario'))

    if mov_type == 'entrada':
        execute_db("UPDATE products SET stock = stock + ? WHERE id=?", (quantity, pid))
    elif mov_type == 'salida':
        execute_db("UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?", (quantity, pid))
    else:  # ajuste
        execute_db("UPDATE products SET stock = ? WHERE id=?", (quantity, pid))

    execute_db(
        "INSERT INTO stock_movements (product_id, type, quantity, reason) VALUES (?, ?, ?, ?)",
        (pid, mov_type, quantity, reason)
    )
    flash('Ajuste de inventario realizado.', 'success')
    return redirect(url_for('admin_inventario'))


@app.route('/admin/ordenes')
@admin_required
def admin_ordenes():
    status_filter = request.args.get('status', '')
    if status_filter:
        orders = query_db(
            "SELECT * FROM orders WHERE status=? ORDER BY created_at DESC",
            (status_filter,)
        )
    else:
        orders = query_db("SELECT * FROM orders ORDER BY created_at DESC")
    return render_template('admin/ordenes.html', orders=orders, status_filter=status_filter)


@app.route('/admin/ordenes/<int:oid>')
@admin_required
def admin_orden_detalle(oid):
    order = query_db("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not order:
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('admin_ordenes'))
    items = query_db("SELECT * FROM order_items WHERE order_id=?", (oid,))
    return render_template('admin/orden_detalle.html', order=order, items=items)


@app.route('/admin/ordenes/<int:oid>/estado', methods=['POST'])
@admin_required
def admin_actualizar_estado(oid):
    new_status = request.form.get('status', '')
    new_payment = request.form.get('payment_status', '')
    valid_statuses = ['nuevo', 'procesando', 'enviado', 'entregado', 'cancelado']
    valid_payments = ['pendiente', 'pagado', 'reembolsado']

    order = query_db("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not order:
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('admin_ordenes'))

    old_status = order['status']
    old_payment = order['payment_status']

    status_changed = new_status in valid_statuses and new_status != old_status
    payment_changed = new_payment in valid_payments and new_payment != old_payment

    if status_changed:
        execute_db("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    if payment_changed:
        execute_db("UPDATE orders SET payment_status=? WHERE id=?", (new_payment, oid))

    # Notificar al cliente si hubo un cambio relevante
    notify_status = new_status if status_changed else ''
    notify_payment = new_payment if payment_changed else ''
    if notify_status or notify_payment:
        # Re-fetch para tener los datos actualizados
        updated_order = query_db("SELECT * FROM orders WHERE id=?", (oid,), one=True)
        send_status_email(updated_order, notify_status, notify_payment)

    flash('Estado actualizado.', 'success')
    return redirect(url_for('admin_orden_detalle', oid=oid))


@app.route('/admin/ordenes-compra')
@admin_required
def admin_ordenes_compra():
    pos = query_db(
        """SELECT po.*, COUNT(poi.id) as items_count
           FROM purchase_orders po
           LEFT JOIN purchase_order_items poi ON po.id = poi.po_id
           GROUP BY po.id
           ORDER BY po.created_at DESC"""
    )
    products = query_db("SELECT * FROM products WHERE active=1 ORDER BY name")
    return render_template('admin/ordenes_compra.html', pos=pos, products=products)


@app.route('/admin/ordenes-compra/nueva', methods=['POST'])
@admin_required
def admin_nueva_oc():
    supplier = request.form.get('supplier', '').strip()
    expected_date = request.form.get('expected_date', '').strip()
    notes = request.form.get('notes', '').strip()

    product_ids = request.form.getlist('product_id[]')
    quantities = request.form.getlist('quantity[]')
    unit_costs = request.form.getlist('unit_cost[]')

    if not supplier or not product_ids:
        flash('Proveedor y al menos un producto son requeridos.', 'error')
        return redirect(url_for('admin_ordenes_compra'))

    po_number = f'OC-{datetime.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'
    total = sum(int(q) * float(c) for q, c in zip(quantities, unit_costs) if q and c)

    po_id = execute_db(
        "INSERT INTO purchase_orders (po_number, supplier, expected_date, notes, total) VALUES (?, ?, ?, ?, ?)",
        (po_number, supplier, expected_date, notes, total)
    )

    for pid, qty, cost in zip(product_ids, quantities, unit_costs):
        if pid and qty and cost:
            qty_int = int(qty)
            cost_float = float(cost)
            execute_db(
                "INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_cost, subtotal) VALUES (?, ?, ?, ?, ?)",
                (po_id, int(pid), qty_int, cost_float, qty_int * cost_float)
            )

    flash(f'Orden de compra {po_number} creada.', 'success')
    return redirect(url_for('admin_ordenes_compra'))


@app.route('/admin/ordenes-compra/<int:po_id>')
@admin_required
def admin_oc_detalle(po_id):
    po = query_db("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po:
        flash('Orden de compra no encontrada.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    items = query_db(
        """SELECT poi.*, p.name as product_name, p.sku
           FROM purchase_order_items poi
           JOIN products p ON poi.product_id = p.id
           WHERE poi.po_id=?""",
        (po_id,)
    )
    return render_template('admin/ordenes_compra.html', po_detail=po, po_items=items,
                           pos=query_db("SELECT po.*, COUNT(poi.id) as items_count FROM purchase_orders po LEFT JOIN purchase_order_items poi ON po.id = poi.po_id GROUP BY po.id ORDER BY po.created_at DESC"),
                           products=query_db("SELECT * FROM products WHERE active=1 ORDER BY name"))


@app.route('/admin/ordenes-compra/<int:po_id>/recibir', methods=['POST'])
@admin_required
def admin_recibir_oc(po_id):
    po = query_db("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po or po['status'] == 'recibido':
        flash('Orden no válida o ya fue recibida.', 'error')
        return redirect(url_for('admin_ordenes_compra'))

    items = query_db(
        "SELECT * FROM purchase_order_items WHERE po_id=?", (po_id,)
    )
    for item in items:
        execute_db("UPDATE products SET stock = stock + ? WHERE id=?",
                   (item['quantity'], item['product_id']))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'entrada', ?, 'Orden de Compra', ?)",
            (item['product_id'], item['quantity'], po['po_number'])
        )

    execute_db("UPDATE purchase_orders SET status='recibido' WHERE id=?", (po_id,))
    flash(f'Orden {po["po_number"]} marcada como recibida. Inventario actualizado.', 'success')
    return redirect(url_for('admin_ordenes_compra'))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        init_db()
        print("=" * 50)
        print("  JD PEPTIDES - Tienda Digital")
        print("=" * 50)
        print(f"  URL: http://localhost:5000")
        print(f"  Admin: http://localhost:5000/admin")
        print(f"  Contraseña admin: Aa52902763")
        print("=" * 50)
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
