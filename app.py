import os
import re
import csv
import io
import sqlite3
import json
import uuid
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, date
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g, send_from_directory,
                   Response, stream_with_context, make_response)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_compress import Compress

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jdp_secret_key_2024_ultra_secure')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30 days
Compress(app)

# ---------------------------------------------------------------------------
# Server-Sent Events bus — broadcasts real-time updates to connected clients
# ---------------------------------------------------------------------------

class SSEBus:
    """Thread-safe in-process SSE message broadcaster.
    Works correctly with a single gunicorn worker (--workers=1 --threads=N)."""
    def __init__(self):
        self._lock = threading.Lock()
        self._listeners = []

    def subscribe(self):
        q = []
        with self._lock:
            self._listeners.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)

    def publish(self, event_type, data):
        payload = f'event: {event_type}\ndata: {json.dumps(data)}\n\n'
        with self._lock:
            for q in self._listeners:
                q.append(payload)

sse_bus = SSEBus()


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

DATABASE = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'database', 'jdp.db'))

# Si DATABASE_PATH apunta a un volumen externo (ej. /data/tienda.db),
# guardamos las imágenes subidas en ese mismo volumen para que persistan.
_static_img = os.path.join(os.path.dirname(__file__), 'static', 'img')
_data_dir = os.path.dirname(DATABASE) if os.environ.get('DATABASE_PATH') else None
UPLOAD_FOLDER = os.path.join(_data_dir, 'img') if _data_dir else _static_img

DOCS_FOLDER = os.path.join(_data_dir or os.path.dirname(DATABASE), 'docs')
os.makedirs(DOCS_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_DOC_EXTENSIONS = {'xlsx', 'xls', 'csv', 'pdf'}

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Al arrancar: si el volumen está vacío, copiar las imágenes del repo al volumen
# para que /media/ siempre las encuentre aunque sea el primer deploy.
if UPLOAD_FOLDER != _static_img and os.path.isdir(_static_img):
    import shutil as _shutil
    for _fname in os.listdir(_static_img):
        _src = os.path.join(_static_img, _fname)
        _dst = os.path.join(UPLOAD_FOLDER, _fname)
        if os.path.isfile(_src) and not os.path.exists(_dst):
            _shutil.copy2(_src, _dst)

# ---------------------------------------------------------------------------
# Email configuration — Resend API (works on Railway, no SMTP needed)
# Docs: https://resend.com/docs  |  Free tier: 3,000 emails/month
# ---------------------------------------------------------------------------
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM     = os.environ.get('EMAIL_FROM', 'JD Peptides <noreply@jdpeptides.com>')
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
    """Envía notificación al cliente cuando cambia el estado de su orden (background)."""
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
    _send_email_bg(order['customer_email'], subject, html)
    print(f"[Email] Estado encolado (bg) a {order['customer_email']} ({new_status or new_payment})")


def _send_email(to, subject, html):
    """Envía un email via Resend API (HTTP — funciona en Railway)."""
    if not RESEND_API_KEY:
        print("[Email] RESEND_API_KEY no configurada — email omitido")
        return False
    payload = json.dumps({
        "from": EMAIL_FROM,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[Email] Enviado a {to} — {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[Email] Resend HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"[Email] Error: {e}")
    return False


def _send_email_bg(to, subject, html):
    """Envía email en background — no bloquea la respuesta HTTP."""
    t = threading.Thread(target=_send_email, args=(to, subject, html), daemon=True)
    t.start()


def _do_send_emails(order, items):
    admin_html = _admin_html(order, items)
    subject_admin = f'⚡ Nueva Orden JD Peptides — {order["order_number"]}'
    for recipient in EMAIL_NOTIFY:
        _send_email_bg(recipient, subject_admin, admin_html)
    customer_html = _customer_html(order, items)
    _send_email_bg(order['customer_email'],
                   f'✅ Confirmación de tu pedido — {order["order_number"]}',
                   customer_html)
    print(f"[Email] Encolado (bg) — admins {EMAIL_NOTIFY} + cliente {order['customer_email']}")


_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def valid_email(email):
    return bool(_EMAIL_RE.match(email))


VALID_PAYMENT_METHODS = {'transferencia', 'efectivo', 'criptomonedas', 'zelle', 'paypal'}


def send_low_stock_alert(product):
    """Envía alerta de stock bajo a los admins (máximo 1 por producto cada 24 horas)."""
    alerted_at = product.get('low_stock_alerted_at')
    if alerted_at:
        try:
            last = datetime.fromisoformat(alerted_at)
            if (datetime.now() - last).total_seconds() < 86400:
                return  # Ya se envió alerta en las últimas 24 horas
        except Exception:
            pass
    # Registrar timestamp de la alerta antes de enviar
    execute_db(
        "UPDATE products SET low_stock_alerted_at=? WHERE id=?",
        (datetime.now().isoformat(), product['id'])
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff">
      <div style="background:#0d0d0d;padding:24px 32px;text-align:center">
        <h1 style="margin:0;color:#c9a227;font-size:20px;letter-spacing:2px">JD PEPTIDES</h1>
        <p style="margin:6px 0 0;color:#999;font-size:12px">Alerta de Inventario</p>
      </div>
      <div style="background:#f97316;padding:14px 32px;text-align:center">
        <span style="color:#fff;font-weight:700;font-size:16px">⚠️ Stock Bajo Detectado</span>
      </div>
      <div style="padding:28px 32px">
        <p style="font-size:15px;color:#333;margin:0 0 20px">
          El siguiente producto ha alcanzado el umbral mínimo de stock:
        </p>
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:20px;margin-bottom:24px">
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <tr><td style="padding:6px 0;color:#666;width:160px">Producto</td>
                <td style="padding:6px 0;font-weight:700;color:#111">{product['name']}</td></tr>
            <tr><td style="padding:6px 0;color:#666">SKU</td>
                <td style="padding:6px 0;color:#555;font-family:monospace">{product['sku']}</td></tr>
            <tr><td style="padding:6px 0;color:#666">Stock actual</td>
                <td style="padding:6px 0;font-weight:700;color:#ef4444;font-size:18px">{product['stock']} unidades</td></tr>
            <tr><td style="padding:6px 0;color:#666">Umbral alerta</td>
                <td style="padding:6px 0;color:#f97316">{product['low_stock_alert']} unidades</td></tr>
            <tr><td style="padding:6px 0;color:#666">Categoría</td>
                <td style="padding:6px 0;color:#555">{product.get('category', '')}</td></tr>
          </table>
        </div>
        <p style="font-size:13px;color:#777;margin:0">
          Considera crear una nueva orden de compra para reponer este producto.
        </p>
      </div>
      <div style="background:#f9f9f9;padding:14px 32px;text-align:center;border-top:1px solid #eee">
        <p style="margin:0;color:#999;font-size:11px">JD Peptides · Panel Admin · Alerta automática de inventario</p>
      </div>
    </div>"""

    subject = f'⚠️ Stock bajo: {product["name"]} ({product["stock"]} uds) — JD Peptides'
    for recipient in EMAIL_NOTIFY:
        _send_email_bg(recipient, subject, html)
    print(f"[Email] Alerta stock bajo encolada (bg): {product['name']}")


def send_po_received_email(po, items):
    """Envía confirmación de OC recibida a los admins."""
    rows = ''.join(f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee">{i.get('product_name', '')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center">{i.get('quantity', 0)}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right">${i.get('unit_cost', 0):.2f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;font-weight:700">${i.get('subtotal', 0):.2f}</td>
        </tr>""" for i in items)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff">
      <div style="background:#0d0d0d;padding:24px 32px;text-align:center">
        <h1 style="margin:0;color:#c9a227;font-size:20px;letter-spacing:2px">JD PEPTIDES</h1>
        <p style="margin:6px 0 0;color:#999;font-size:12px">Gestión de Inventario</p>
      </div>
      <div style="background:#10b981;padding:14px 32px;text-align:center">
        <span style="color:#fff;font-weight:700;font-size:16px">✅ Orden de Compra Recibida</span>
      </div>
      <div style="padding:28px 32px">
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:20px">
          <tr><td style="padding:5px 0;color:#666;width:140px">OC Número</td>
              <td style="padding:5px 0;font-weight:700;color:#111;font-family:monospace">{po['po_number']}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Proveedor</td>
              <td style="padding:5px 0;color:#111">{po['supplier']}</td></tr>
          <tr><td style="padding:5px 0;color:#666">Total</td>
              <td style="padding:5px 0;font-weight:700;color:#c9a227">${po['total']:.2f}</td></tr>
        </table>
        <h3 style="margin:0 0 12px;color:#0d0d0d;font-size:13px;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #c9a227;padding-bottom:8px">Productos Recibidos</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <thead><tr style="background:#f5f5f5">
            <th style="padding:10px 12px;text-align:left">Producto</th>
            <th style="padding:10px 12px;text-align:center">Cant.</th>
            <th style="padding:10px 12px;text-align:right">Costo Unit.</th>
            <th style="padding:10px 12px;text-align:right">Subtotal</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <div style="background:#f9f9f9;padding:14px 32px;text-align:center;border-top:1px solid #eee">
        <p style="margin:0;color:#999;font-size:11px">JD Peptides · Panel Admin · Notificación automática</p>
      </div>
    </div>"""

    subject = f'✅ OC Recibida: {po["po_number"]} — {po["supplier"]}'
    for recipient in EMAIL_NOTIFY:
        _send_email_bg(recipient, subject, html)
    print(f"[Email] Notificación OC encolada (bg): {po['po_number']}")


def send_order_email(order, items):
    """Envía notificación a admins y confirmación al cliente via Resend API."""
    _do_send_emails(order, items)


# ---------------------------------------------------------------------------
# Supplier document parsing helpers
# ---------------------------------------------------------------------------

def extract_text_from_file(filepath, filename):
    """Extrae texto de Excel, CSV o PDF. Retorna (text, error)."""
    ext = filename.rsplit('.', 1)[-1].lower()

    if ext in ('xlsx', 'xls'):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                lines.append(f'=== Hoja: {sheet.title} ===')
                for row in sheet.iter_rows(values_only=True):
                    if any(c is not None for c in row):
                        lines.append('\t'.join(str(c) if c is not None else '' for c in row))
            return '\n'.join(lines), None
        except ImportError:
            return None, 'openpyxl no instalado'
        except Exception as e:
            return None, f'Error leyendo Excel: {e}'

    elif ext == 'csv':
        try:
            with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
                return f.read(), None
        except Exception as e:
            return None, f'Error leyendo CSV: {e}'

    elif ext == 'pdf':
        try:
            import pdfplumber
            lines = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        lines.append(text)
                    for table in (page.extract_tables() or []):
                        for row in table:
                            if any(c for c in row if c):
                                lines.append('\t'.join(str(c or '') for c in row))
            return '\n'.join(lines) or 'PDF sin texto extraíble', None
        except ImportError:
            return None, 'pdfplumber no instalado. Agrega pdfplumber a requirements.txt'
        except Exception as e:
            return None, f'Error leyendo PDF: {e}'

    return None, f'Formato no soportado: .{ext}'


def parse_doc_with_claude(doc_text, existing_products):
    """Usa Claude claude-haiku-4-5 para extraer datos estructurados del documento."""
    if not ANTHROPIC_API_KEY:
        return None, 'ANTHROPIC_API_KEY no configurada en las variables de entorno.'

    products_hint = '\n'.join(
        f'- {p["name"]} (SKU: {p["sku"]}, ID: {p["id"]})'
        for p in (existing_products or [])[:30]
    )

    prompt = f"""Eres un asistente experto en analizar documentos de proveedores de péptidos y productos de investigación científica.

Analiza el siguiente texto extraído de un documento de proveedor (puede ser una factura, lista de precios, cotización u orden de compra) y devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:

{{
  "supplier": "nombre del proveedor o Desconocido",
  "document_date": "YYYY-MM-DD o null",
  "currency": "USD",
  "products": [
    {{
      "name": "nombre del producto",
      "matched_product_id": null,
      "sku": "código SKU o null",
      "dose": "dosis/concentración/presentación o null",
      "quantity": 0,
      "unit_cost": 0.0,
      "description": "descripción adicional o null"
    }}
  ],
  "notes": "notas generales del documento"
}}

Productos existentes en el sistema para matching:
{products_hint}

Para cada producto del documento, intenta hacer matching con los productos existentes. Si encuentras una coincidencia, pon el ID correspondiente en "matched_product_id". Si no hay match, deja null.

Texto del documento:
{doc_text[:8000]}

Devuelve ÚNICAMENTE el JSON válido, sin markdown, sin explicaciones adicionales."""

    payload = json.dumps({
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 2048,
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode()

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={
            'x-api-key': ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            result = json.loads(resp.read().decode())
            content = result['content'][0]['text'].strip()
            # Remove possible markdown fences
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            return json.loads(content.strip()), None
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300]
        return None, f'Claude API {e.code}: {err}'
    except json.JSONDecodeError as e:
        return None, f'Respuesta de Claude no es JSON válido: {e}'
    except Exception as e:
        return None, f'Error: {e}'

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")   # lecturas concurrentes sin lock
        db.execute("PRAGMA synchronous = NORMAL")  # más rápido, sigue siendo seguro
        db.execute("PRAGMA cache_size = -8000")    # 8 MB cache en memoria
        db.execute("PRAGMA temp_store = MEMORY")
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
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

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
    image_path TEXT DEFAULT '',
    low_stock_alerted_at TEXT DEFAULT NULL,
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

CREATE TABLE IF NOT EXISTS product_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS supplier_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    supplier TEXT,
    status TEXT DEFAULT 'pendiente',
    extracted_json TEXT,
    po_id INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    processed_at TEXT
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
        'image_path': 'vial_igf1_lr3.jpeg',
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
        'image_path': 'vial_kpv.png',
    },
    {
        'sku': 'JDP-MOTSC',
        'name': 'MOTS-C',
        'category': 'Performance',
        'dose': '10 mg',
        'price': 79.99,
        'description': 'MOTS-C es un péptido mitocondrial que regula el metabolismo energético y la homeostasis de la glucosa.',
        'benefits': 'Incrementa la sensibilidad a la insulina|Mejora el metabolismo celular|Favorece energía y vitalidad|Apoyo en pérdida de grasa',
        'stock': 20,
        'low_stock_alert': 5,
        'image_path': 'vial_mots_c.png',
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
        'image_path': 'vial_bpc157.png',
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
        'image_path': 'vial_tb500.png',
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
        'image_path': 'vial_ghk_cu.png',
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
        'image_path': 'vial_retatrutide.jpeg',
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
        'image_path': 'vial_dsip.png',
    },
    {
        'sku': 'JDP-TA1',
        'name': 'Thymosin Alpha 1',
        'category': 'Anti-aging',
        'dose': '10 mg',
        'price': 84.99,
        'description': 'Thymosin Alpha 1 es un péptido inmunomodulador natural derivado del timo, estudiado por sus efectos en el sistema inmunológico.',
        'benefits': 'Fortalece el sistema inmune|Acción antiviral y antibacteriana|Apoyo en enfermedades autoinmunes|Estimula células T y NK',
        'stock': 18,
        'low_stock_alert': 4,
        'image_path': 'vial_thymosin_alpha1.png',
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
        'image_path': 'vial_ipamorelin.png',
    },
    {
        'sku': 'JDP-TESA',
        'name': 'Tesamorelin',
        'category': 'Pérdida de Peso',
        'dose': '5 mg',
        'price': 89.99,
        'description': 'Tesamorelin es un análogo de la hormona liberadora de hormona de crecimiento (GHRH), estudiado por sus efectos en la reducción de grasa visceral.',
        'benefits': 'Estimula la hormona de crecimiento|Reduce grasa visceral|Mejora la composición corporal|Efectos neuroprotectores',
        'stock': 3,
        'low_stock_alert': 5,
        'image_path': 'vial_tesamorelin.png',
    },
]


INDICES = """
CREATE INDEX IF NOT EXISTS idx_products_active    ON products(active);
CREATE INDEX IF NOT EXISTS idx_products_category  ON products(category);
CREATE INDEX IF NOT EXISTS idx_orders_status      ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created     ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order  ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_prod   ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_mov_product  ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_mov_created  ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_po_status          ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_items_po        ON purchase_order_items(po_id);
"""

def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.executescript(INDICES)
    db.commit()
    # Agregar columna image_path si no existe (migration para DBs antiguas)
    cols = [row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()]
    if 'image_path' not in cols:
        db.execute("ALTER TABLE products ADD COLUMN image_path TEXT DEFAULT ''")
        db.commit()
    if 'low_stock_alerted_at' not in cols:
        db.execute("ALTER TABLE products ADD COLUMN low_stock_alerted_at TEXT DEFAULT NULL")
        db.commit()
    # Migrate supplier_documents table
    try:
        db.execute("SELECT id FROM supplier_documents LIMIT 1")
    except Exception:
        db.execute("""CREATE TABLE IF NOT EXISTS supplier_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL, original_name TEXT NOT NULL,
            file_type TEXT NOT NULL, supplier TEXT, status TEXT DEFAULT 'pendiente',
            extracted_json TEXT, po_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')), processed_at TEXT
        )""")
        db.commit()
    # Seed / migrate admin users
    user_count = db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
    if user_count == 0:
        # Primera instalación: crear ambos usuarios
        db.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                   ('Alb.peptide10', generate_password_hash('Aa52902763', method='pbkdf2:sha256'), 'superadmin'))
        db.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                   ('JacoM.JDP', generate_password_hash('Peptideed398', method='pbkdf2:sha256'), 'admin'))
        db.commit()
    else:
        # Migración: renombrar 'alberto' → 'Alb.peptide10' si existe
        old = db.execute("SELECT id FROM admin_users WHERE username='alberto'").fetchone()
        if old:
            db.execute("UPDATE admin_users SET username=?, password_hash=? WHERE username='alberto'",
                       ('Alb.peptide10', generate_password_hash('Aa52902763', method='pbkdf2:sha256')))
            db.commit()
        # Agregar JacoM.JDP si no existe
        jaco = db.execute("SELECT id FROM admin_users WHERE username='JacoM.JDP'").fetchone()
        if not jaco:
            db.execute("INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
                       ('JacoM.JDP', generate_password_hash('Peptideed398', method='pbkdf2:sha256'), 'admin'))
            db.commit()
    # Seed products if empty
    count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        for p in PRODUCTS_SEED:
            db.execute(
                """INSERT INTO products (sku, name, category, dose, price, description, benefits, stock, low_stock_alert, image_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p['sku'], p['name'], p['category'], p['dose'], p['price'],
                 p['description'], p['benefits'], p['stock'], p['low_stock_alert'],
                 p.get('image_path', ''))
            )
        db.commit()
    else:
        # Migration: always restore image_path from seed (ensures images show after deploys)
        for p in PRODUCTS_SEED:
            if p.get('image_path'):
                db.execute(
                    "UPDATE products SET image_path=? WHERE sku=?",
                    (p['image_path'], p['sku'])
                )
            if p.get('category'):
                db.execute(
                    "UPDATE products SET category=? WHERE sku=?",
                    (p['category'], p['sku'])
                )
            if p.get('description'):
                db.execute(
                    "UPDATE products SET description=? WHERE sku=? AND (description IS NULL OR description='')",
                    (p['description'], p['sku'])
                )
            if p.get('benefits'):
                db.execute(
                    "UPDATE products SET benefits=? WHERE sku=? AND (benefits IS NULL OR benefits='')",
                    (p['benefits'], p['sku'])
                )
        # Category migrations for products not in seed (added via admin)
        _cat_fixes = [
            ('JDP-NAD',  'Anti-aging'),
            ('JDP-RT20', 'Pérdida de Peso'),
            ('JDP-RT10', 'Pérdida de Peso'),
            ('JDP-RETA', 'Pérdida de Peso'),
        ]
        for _sku, _cat in _cat_fixes:
            db.execute("UPDATE products SET category=? WHERE sku=?", (_cat, _sku))
        db.commit()
    # Migration: remove old non-vial product_images for standard SKUs so detail pages use static vials
    STANDARD_SKUS = ['JDP-IGF1','JDP-KPV','JDP-MOTSC','JDP-BPC157','JDP-TB500',
                     'JDP-GHKCU','JDP-RETA','JDP-DSIP','JDP-TA1','JDP-IPA','JDP-TESA']
    for sku in STANDARD_SKUS:
        db.execute("""
            DELETE FROM product_images WHERE product_id IN (
                SELECT id FROM products WHERE sku=?
            ) AND filename NOT LIKE 'vial_%'
        """, (sku,))
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


OWNER_USER = 'Alb.peptide10'

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        if session.get('admin_user') != OWNER_USER:
            flash('Acceso restringido al propietario del sistema.', 'error')
            return redirect(url_for('admin_dashboard'))
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
# Admin polling endpoint — lightweight replacement for SSE
# ---------------------------------------------------------------------------

@app.route('/admin/api/poll')
@admin_required
def admin_poll():
    since = request.args.get('since', '')
    new_orders = []
    if since:
        rows = query_db(
            "SELECT order_number, customer_name, total FROM orders WHERE created_at > ? ORDER BY created_at DESC LIMIT 10",
            (since,)
        )
        new_orders = [dict(r) for r in rows]
    return jsonify({
        'new_orders': new_orders,
        'server_time': datetime.now().isoformat(),
    })


# ---------------------------------------------------------------------------
# Media serving — uploaded images (persistent volume or static/img fallback)
# ---------------------------------------------------------------------------

@app.route('/media/<path:filename>')
def media_file(filename):
    """Serve uploaded product images from the persistent volume.
    Falls back to static/img for images bundled with the app."""
    upload_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(upload_path):
        return send_from_directory(UPLOAD_FOLDER, filename)
    return send_from_directory(_static_img, filename)


# ---------------------------------------------------------------------------
# Customer routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
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


@app.route('/api/productos')
def api_productos():
    """AJAX endpoint — returns filtered products as JSON for catalog search."""
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

    SKU_IMAGE_MAP = {
        'JDP-IGF1': 'vial_igf1_lr3.jpeg', 'JDP-KPV': 'vial_kpv.jpeg',
        'JDP-MOTSC': 'vial_mots_c.jpeg', 'JDP-BPC157': 'vial_bpc157.jpeg',
        'JDP-TB500': 'vial_tb500.jpeg', 'JDP-GHKCU': 'vial_ghk_cu.jpeg',
        'JDP-RETA': 'vial_retatrutide.jpeg', 'JDP-DSIP': 'vial_dsip.png',
        'JDP-TA1': 'vial_thymosin_alpha1.png', 'JDP-IPA': 'vial_ipamorelin.png',
        'JDP-TESA': 'vial_tesamorelin.png',
    }
    result = []
    for p in products:
        d = dict(p)
        img = SKU_IMAGE_MAP.get(d.get('sku', ''), '') or d.get('image_path') or ''
        d['image_url'] = f'/media/{img}' if img else ''
        result.append(d)
    return jsonify({'products': result, 'count': len(result)})


@app.route('/api/carrito/actualizar', methods=['POST'])
def api_actualizar_carrito():
    """AJAX cart update — update single item quantity without page reload."""
    data = request.get_json() or {}
    pid = str(data.get('product_id', ''))
    qty = safe_int(data.get('quantity', 1), 1)
    cart = get_cart()
    if qty <= 0:
        cart.pop(pid, None)
    elif pid in cart:
        cart[pid]['quantity'] = qty
    save_cart(cart)
    subtotal = cart_total()
    shipping = 0 if subtotal >= 200 else 15
    return jsonify({
        'success': True,
        'cart_count': cart_count(),
        'subtotal': subtotal,
        'shipping': shipping,
        'total': subtotal + shipping,
    })


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
    images_raw = query_db("SELECT * FROM product_images WHERE product_id=? ORDER BY sort_order, id", (pid,))
    # Solo pasar imágenes cuyos archivos existen (evita entradas huérfanas de uploads borrados)
    images = [img for img in images_raw if
              os.path.exists(os.path.join(UPLOAD_FOLDER, img['filename'])) or
              os.path.exists(os.path.join(_static_img, img['filename']))]
    return render_template('producto.html', product=product, related=related, benefits=benefits, images=images)


@app.route('/carrito/agregar', methods=['POST'])
def agregar_carrito():
    data = request.get_json() or request.form
    pid = str(data.get('product_id', ''))
    qty = safe_int(data.get('quantity', 1), 1)
    if qty < 1:
        qty = 1

    product = query_db("SELECT * FROM products WHERE id=? AND active=1", (pid,), one=True)
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'}), 404
    if product['stock'] <= 0:
        return jsonify({'success': False, 'message': 'Producto sin stock disponible'}), 400

    cart = get_cart()
    current_in_cart = cart[pid]['quantity'] if pid in cart else 0
    total_requested = current_in_cart + qty
    if total_requested > product['stock']:
        available = product['stock'] - current_in_cart
        if available <= 0:
            return jsonify({'success': False, 'message': f'Ya tienes el máximo disponible de "{product["name"]}" en tu carrito ({product["stock"]} uds)'}), 400
        qty = available  # Ajustar al máximo disponible

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
            qty = safe_int(val, 0)
            if qty <= 0:
                cart.pop(pid, None)
            elif pid in cart:
                # Cap at real available stock
                prod = query_db("SELECT stock FROM products WHERE id=? AND active=1",
                                (cart[pid]['id'],), one=True)
                if not prod or prod['stock'] == 0:
                    cart.pop(pid, None)
                else:
                    cart[pid]['quantity'] = min(qty, prod['stock'])
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

    if not valid_email(email):
        flash('El email ingresado no es válido.', 'error')
        return redirect(url_for('checkout'))

    if payment_method not in VALID_PAYMENT_METHODS:
        flash('Método de pago no válido.', 'error')
        return redirect(url_for('checkout'))

    subtotal = cart_total()
    shipping = 0 if subtotal >= 200 else 15
    total = subtotal + shipping

    db = get_db()
    order_id = None
    order_number = None
    alert_product_ids = []

    try:
        # BEGIN EXCLUSIVE: una sola escritura activa a la vez — evita oversell concurrente
        db.execute("BEGIN EXCLUSIVE")

        # Re-validar stock DENTRO del lock (el SELECT previo ya no es confiable)
        for pid, item in cart.items():
            row = db.execute(
                "SELECT stock, name FROM products WHERE id=? AND active=1", (item['id'],)
            ).fetchone()
            if not row:
                db.execute("ROLLBACK")
                flash(f'"{item["name"]}" ya no está disponible.', 'error')
                return redirect(url_for('checkout'))
            if row['stock'] < item['quantity']:
                db.execute("ROLLBACK")
                flash(
                    f'"{row["name"]}" está agotado. Actualiza tu carrito.' if row['stock'] == 0
                    else f'Solo quedan {row["stock"]} unidad(es) de "{row["name"]}". Actualiza tu carrito.',
                    'error'
                )
                return redirect(url_for('checkout'))

        # Insertar orden
        cur = db.execute(
            """INSERT INTO orders (order_number, customer_name, customer_email, customer_phone,
               address, city, state, zip_code, payment_method, notes, subtotal, shipping, total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ('TEMP', name, email, phone, address, city, state, zip_code,
             payment_method, notes, subtotal, shipping, total)
        )
        order_id = cur.lastrowid
        order_number = f'JD-{datetime.now().strftime("%d/%m/%y")}-{419 + order_id}'
        db.execute("UPDATE orders SET order_number=? WHERE id=?", (order_number, order_id))

        # Insertar ítems y descontar stock — todo dentro de la misma transacción
        for pid, item in cart.items():
            db.execute(
                """INSERT INTO order_items
                   (order_id, product_id, product_name, product_sku, dose, quantity, unit_price, subtotal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (order_id, item['id'], item['name'], item['sku'], item['dose'],
                 item['quantity'], item['price'], item['quantity'] * item['price'])
            )
            db.execute(
                "UPDATE products SET stock = stock - ? WHERE id=?",
                (item['quantity'], item['id'])
            )
            db.execute(
                "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'salida', ?, 'Venta', ?)",
                (item['id'], item['quantity'], order_number)
            )
            alert_product_ids.append(item['id'])

        db.commit()  # Un solo commit — atómico

    except Exception as e:
        try:
            db.execute("ROLLBACK")
        except Exception:
            pass
        print(f"[Checkout] Error en transacción: {e}")
        flash('Error al procesar el pedido. Por favor intenta de nuevo.', 'error')
        return redirect(url_for('checkout'))

    # Post-commit: SSE y alertas de stock bajo (fuera de la transacción, no crítico)
    for product_id in alert_product_ids:
        updated_prod = query_db("SELECT * FROM products WHERE id=?", (product_id,), one=True)
        if updated_prod:
            sse_bus.publish('stock_updated', {'id': product_id, 'stock': updated_prod['stock']})
            if updated_prod['stock'] <= updated_prod['low_stock_alert']:
                try:
                    send_low_stock_alert(dict(updated_prod))
                except Exception as e:
                    print(f"[Email] Alerta stock bajo falló: {e}")

    sse_bus.publish('new_order', {
        'order_number': order_number,
        'customer_name': name,
        'total': total,
        'time': datetime.now().strftime('%H:%M'),
    })

    session.pop('cart', None)
    order = query_db("SELECT * FROM orders WHERE id=?", (order_id,), one=True)
    items = query_db("SELECT * FROM order_items WHERE order_id=?", (order_id,))

    try:
        send_order_email(dict(order), [dict(i) for i in items])
    except Exception as e:
        print(f"[Email] Error al enviar: {e}")

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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = query_db("SELECT * FROM admin_users WHERE username=? AND active=1", (username,), one=True)
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_user'] = user['username']
            session['admin_role'] = user['role']
            flash(f'Bienvenido, {user["username"]}.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('admin/login.html')



@app.route('/admin/test-email')
@admin_required
def admin_test_email():
    """Prueba SMTP sincrónico y muestra el error exacto."""
    if not RESEND_API_KEY:
        flash('❌ RESEND_API_KEY no configurada en las variables de entorno de Railway.', 'error')
        return redirect(url_for('admin_dashboard'))
    ok = _send_email(EMAIL_NOTIFY[0], '✅ Test email JD Peptides',
                     '<p style="font-family:Arial">Email de prueba desde JD Peptides funcionando ✅</p>')
    if ok:
        flash(f'✅ Email enviado a {EMAIL_NOTIFY[0]} — revisa tu bandeja (y spam).', 'success')
    else:
        flash('❌ Error enviando — revisa que RESEND_API_KEY y EMAIL_FROM sean correctos en Railway.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_user', None)
    session.pop('admin_role', None)
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('admin_login'))


# ---------------------------------------------------------------------------
# Gestión de usuarios admin
# ---------------------------------------------------------------------------

@app.route('/admin/usuarios')
@superadmin_required
def admin_usuarios():
    users = query_db("SELECT * FROM admin_users ORDER BY created_at DESC")
    return render_template('admin/usuarios.html', users=users)


@app.route('/admin/usuarios/nuevo', methods=['POST'])
@superadmin_required
def admin_nuevo_usuario():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'admin')
    if not username or not password:
        flash('Usuario y contraseña son requeridos.', 'error')
        return redirect(url_for('admin_usuarios'))
    existing = query_db("SELECT id FROM admin_users WHERE username=?", (username,), one=True)
    if existing:
        flash('Ese nombre de usuario ya existe.', 'error')
        return redirect(url_for('admin_usuarios'))
    execute_db(
        "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password, method='pbkdf2:sha256'), role)
    )
    flash(f'Usuario "{username}" creado correctamente.', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/usuarios/<int:uid>/password', methods=['POST'])
@superadmin_required
def admin_cambiar_password(uid):
    new_password = request.form.get('password', '').strip()
    if not new_password:
        flash('La nueva contraseña no puede estar vacía.', 'error')
        return redirect(url_for('admin_usuarios'))
    execute_db("UPDATE admin_users SET password_hash=? WHERE id=?",
               (generate_password_hash(new_password, method='pbkdf2:sha256'), uid))
    flash('Contraseña actualizada.', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/usuarios/<int:uid>/toggle', methods=['POST'])
@superadmin_required
def admin_toggle_usuario(uid):
    user = query_db("SELECT * FROM admin_users WHERE id=?", (uid,), one=True)
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuarios'))
    if user['username'] == session.get('admin_user'):
        flash('No puedes desactivar tu propia cuenta.', 'error')
        return redirect(url_for('admin_usuarios'))
    new_status = 0 if user['active'] else 1
    execute_db("UPDATE admin_users SET active=? WHERE id=?", (new_status, uid))
    estado = 'activado' if new_status else 'desactivado'
    flash(f'Usuario "{user["username"]}" {estado}.', 'success')
    return redirect(url_for('admin_usuarios'))


@app.route('/admin/usuarios/<int:uid>/eliminar', methods=['POST'])
@superadmin_required
def admin_eliminar_usuario(uid):
    user = query_db("SELECT * FROM admin_users WHERE id=?", (uid,), one=True)
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('admin_usuarios'))
    if user['username'] == session.get('admin_user'):
        flash('No puedes eliminar tu propia cuenta.', 'error')
        return redirect(url_for('admin_usuarios'))
    execute_db("DELETE FROM admin_users WHERE id=?", (uid,))
    flash(f'Usuario "{user["username"]}" eliminado.', 'success')
    return redirect(url_for('admin_usuarios'))


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

    # ── Comparativo mes actual: costos (OC) vs ventas ──────────────────────
    mes_actual = date.today().strftime('%Y-%m')

    costos_mes = query_db("""
        SELECT p.name AS product_name, p.sku,
               COALESCE(SUM(poi.quantity),0) AS qty_compra,
               COALESCE(SUM(poi.subtotal),0) AS costo_total
        FROM purchase_order_items poi
        JOIN purchase_orders po ON poi.po_id = po.id
        JOIN products p ON poi.product_id = p.id
        WHERE strftime('%Y-%m', po.created_at) = ?
          AND po.status != 'cancelado'
        GROUP BY p.id
    """, (mes_actual,))

    ventas_mes = query_db("""
        SELECT p.name AS product_name, p.sku,
               COALESCE(SUM(oi.quantity),0) AS qty_venta,
               COALESCE(SUM(oi.subtotal),0) AS venta_total
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE strftime('%Y-%m', o.created_at) = ?
          AND o.status != 'cancelado'
        GROUP BY p.id
    """, (mes_actual,))

    # Merge por sku
    costos_dict  = {r['sku']: dict(r) for r in costos_mes}
    ventas_dict  = {r['sku']: dict(r) for r in ventas_mes}
    all_skus = sorted(set(list(costos_dict.keys()) + list(ventas_dict.keys())))
    comparativo = []
    for sku in all_skus:
        c = costos_dict.get(sku, {})
        v = ventas_dict.get(sku, {})
        name = c.get('product_name') or v.get('product_name', sku)
        costo = c.get('costo_total', 0)
        venta = v.get('venta_total', 0)
        comparativo.append({
            'sku': sku,
            'name': name,
            'qty_compra': c.get('qty_compra', 0),
            'costo_total': costo,
            'qty_venta': v.get('qty_venta', 0),
            'venta_total': venta,
            'margen': venta - costo,
        })

    # ── Ventas últimos 7 días ──────────────────────────────────────────────
    sales_7d_raw = query_db("""
        SELECT date(created_at) as day,
               COUNT(*) as order_count,
               COALESCE(SUM(total), 0) as day_total
        FROM orders
        WHERE date(created_at) >= date('now', '-6 days')
          AND status != 'cancelado'
        GROUP BY date(created_at)
        ORDER BY day ASC
    """)
    # Ensure all 7 days are present (fill gaps with 0)
    from datetime import timedelta
    sales_7d = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        found = next((r for r in sales_7d_raw if r['day'] == d), None)
        sales_7d.append({
            'day': d,
            'order_count': found['order_count'] if found else 0,
            'day_total': round(found['day_total'], 2) if found else 0,
        })

    # ── Pipeline de estados ───────────────────────────────────────────────
    status_rows = query_db("""
        SELECT status, COUNT(*) as count FROM orders
        WHERE status != 'cancelado'
        GROUP BY status
    """)
    status_counts = {r['status']: r['count'] for r in status_rows}

    return render_template('admin/dashboard.html',
                           total_sales=total_sales,
                           orders_today=orders_today,
                           active_products=active_products,
                           low_stock=low_stock,
                           recent_orders=recent_orders,
                           low_stock_products=low_stock_products,
                           comparativo=comparativo,
                           mes_actual=mes_actual,
                           sales_7d=sales_7d,
                           status_counts=status_counts)


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
        price = safe_float(request.form.get('price', 0))
        stock = safe_int(request.form.get('stock', 0))
        low_stock_alert = safe_int(request.form.get('low_stock_alert', 5), 5)
        description = request.form.get('description', '').strip()
        benefits_raw = request.form.get('benefits', '').strip()
        benefits = '|'.join(line.strip() for line in benefits_raw.splitlines() if line.strip())
        active = 1 if request.form.get('active') else 0

        try:
            pid = execute_db(
                """INSERT INTO products (sku, name, category, dose, price, stock, low_stock_alert, description, benefits, active, image_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')""",
                (sku, name, category, dose, price, stock, low_stock_alert, description, benefits, active)
            )
            files = request.files.getlist('images')
            first_uploaded = None
            for i, file in enumerate(files):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    execute_db("INSERT INTO product_images (product_id, filename, sort_order) VALUES (?, ?, ?)", (pid, filename, i))
                    if first_uploaded is None:
                        first_uploaded = filename
            if first_uploaded:
                execute_db("UPDATE products SET image_path=? WHERE id=?", (first_uploaded, pid))
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
        price = safe_float(request.form.get('price', 0))
        stock = safe_int(request.form.get('stock', 0))
        low_stock_alert = safe_int(request.form.get('low_stock_alert', 5), 5)
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
            files = request.files.getlist('images')
            existing_count = query_db("SELECT COUNT(*) as c FROM product_images WHERE product_id=?", (pid,), one=True)['c']
            first_uploaded = None
            for i, file in enumerate(files):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    execute_db("INSERT INTO product_images (product_id, filename, sort_order) VALUES (?, ?, ?)", (pid, filename, existing_count + i))
                    if first_uploaded is None:
                        first_uploaded = filename
            # Siempre actualizar image_path con la primera imagen subida
            if first_uploaded:
                execute_db("UPDATE products SET image_path=? WHERE id=?", (first_uploaded, pid))
            # Notificar en tiempo real a la tienda
            sse_bus.publish('product_updated', {
                'id': pid, 'name': name, 'price': price,
                'stock': stock, 'active': active
            })
            flash('Producto actualizado.', 'success')
            return redirect(url_for('admin_productos'))
        except Exception as e:
            flash(f'Error al actualizar: {e}', 'error')

    benefits_text = (product['benefits'] or '').replace('|', '\n')
    categories = [r['category'] for r in query_db("SELECT DISTINCT category FROM products ORDER BY category")]
    product_images = query_db("SELECT * FROM product_images WHERE product_id=? ORDER BY sort_order, id", (pid,))
    return render_template('admin/producto_form.html', product=product,
                           benefits_text=benefits_text, categories=categories,
                           action='editar', product_images=product_images)


@app.route('/admin/productos/imagen/<int:img_id>/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_imagen(img_id):
    img = query_db("SELECT * FROM product_images WHERE id=?", (img_id,), one=True)
    if img:
        pid = img['product_id']
        execute_db("DELETE FROM product_images WHERE id=?", (img_id,))
        flash('Imagen eliminada.', 'success')
        return redirect(url_for('admin_editar_producto', pid=pid))
    flash('Imagen no encontrada.', 'error')
    return redirect(url_for('admin_productos'))


@app.route('/admin/ordenes/<int:oid>/invoice')
@admin_required
def admin_orden_invoice(oid):
    order = query_db("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not order:
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('admin_ordenes'))
    items = query_db("SELECT * FROM order_items WHERE order_id=?", (oid,))
    return render_template('admin/invoice_venta.html', order=order, items=items)


@app.route('/admin/productos/<int:pid>/toggle', methods=['POST'])
@admin_required
def admin_toggle_producto(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if product:
        new_active = 0 if product['active'] else 1
        execute_db("UPDATE products SET active=? WHERE id=?", (new_active, pid))
        status = 'activado' if new_active else 'desactivado'
        flash(f'Producto {status}.', 'success')
        sse_bus.publish('product_updated', {'id': pid, 'active': new_active})
    return redirect(url_for('admin_productos'))


@app.route('/admin/productos/<int:pid>/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_producto(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not product:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('admin_productos'))
    # Check if product has any orders
    order_count = query_db("SELECT COUNT(*) as c FROM order_items WHERE product_id=?", (pid,), one=True)['c']
    if order_count > 0:
        # Soft delete — preserve order history
        execute_db("UPDATE products SET active=0 WHERE id=?", (pid,))
        flash(f'"{product["name"]}" tiene {order_count} pedido(s) vinculados. Se desactivó en lugar de eliminar.', 'warning')
    else:
        execute_db("DELETE FROM product_images WHERE product_id=?", (pid,))
        execute_db("DELETE FROM stock_movements WHERE product_id=?", (pid,))
        execute_db("DELETE FROM products WHERE id=?", (pid,))
        flash(f'"{product["name"]}" eliminado permanentemente.', 'success')
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


@app.route('/admin/ordenes/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_ordenes():
    ids = request.form.getlist('order_ids')
    if not ids:
        flash('No se seleccionaron órdenes.', 'error')
        return redirect(url_for('admin_ordenes'))
    placeholders = ','.join('?' * len(ids))
    execute_db(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", ids)
    execute_db(f"DELETE FROM orders WHERE id IN ({placeholders})", ids)
    flash(f'{len(ids)} orden(es) eliminada(s).', 'success')
    return redirect(request.referrer or url_for('admin_ordenes'))


@app.route('/admin/ordenes-compra/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_ocs():
    ids = request.form.getlist('oc_ids')
    if not ids:
        flash('No se seleccionaron órdenes de compra.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    placeholders = ','.join('?' * len(ids))
    execute_db(f"DELETE FROM purchase_order_items WHERE po_id IN ({placeholders})", ids)
    execute_db(f"DELETE FROM purchase_orders WHERE id IN ({placeholders})", ids)
    flash(f'{len(ids)} orden(es) de compra eliminada(s).', 'success')
    return redirect(url_for('admin_ordenes_compra'))


@app.route('/admin/movimientos/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_movimientos():
    ids = request.form.getlist('movement_ids')
    if not ids:
        flash('No se seleccionaron movimientos.', 'error')
        return redirect(url_for('admin_inventario'))
    placeholders = ','.join('?' * len(ids))
    execute_db(f"DELETE FROM stock_movements WHERE id IN ({placeholders})", ids)
    flash(f'{len(ids)} movimiento(s) eliminado(s).', 'success')
    return redirect(url_for('admin_inventario'))


@app.route('/admin/inventario/<int:pid>/ajuste', methods=['POST'])
@admin_required
def admin_ajuste_stock(pid):
    product = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not product:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('admin_inventario'))

    mov_type = request.form.get('type', 'ajuste')
    quantity = safe_int(request.form.get('quantity', 0))
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
    # Notificar stock actualizado
    updated = query_db("SELECT stock FROM products WHERE id=?", (pid,), one=True)
    if updated:
        sse_bus.publish('stock_updated', {'id': pid, 'stock': updated['stock']})
        # Enviar alerta si stock bajo
        if mov_type in ('salida', 'ajuste'):
            prod_info = query_db("SELECT * FROM products WHERE id=?", (pid,), one=True)
            if prod_info and prod_info['stock'] <= prod_info['low_stock_alert']:
                try:
                    send_low_stock_alert(dict(prod_info))
                except Exception as e:
                    print(f"[Email] Alerta stock bajo falló: {e}")
    flash('Ajuste de inventario realizado.', 'success')
    return redirect(url_for('admin_inventario'))


@app.route('/admin/inventario/exportar-csv')
@admin_required
def admin_exportar_inventario_csv():
    """Export full inventory as CSV download."""
    products = query_db("SELECT * FROM products ORDER BY name")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Nombre', 'Categoría', 'Dosis', 'Precio', 'Stock',
                     'Alerta Bajo Stock', 'Activo', 'Creado'])
    for p in products:
        writer.writerow([
            p['sku'], p['name'], p['category'], p['dose'],
            f"{p['price']:.2f}", p['stock'], p['low_stock_alert'],
            'Sí' if p['active'] else 'No',
            (p['created_at'] or '')[:10]
        ])
    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = (
        f'attachment; filename=inventario_{date.today().isoformat()}.csv'
    )
    return resp


@app.route('/admin/inventario/ajuste-bulk', methods=['POST'])
@admin_required
def admin_ajuste_bulk():
    """Apply the same stock adjustment to multiple products at once."""
    product_ids = request.form.getlist('product_ids')
    mov_type = request.form.get('type', 'ajuste')
    quantity = safe_int(request.form.get('quantity', 0))
    reason = request.form.get('reason', '').strip() or 'Ajuste bulk'

    if not product_ids or quantity <= 0:
        flash('Selecciona al menos un producto y una cantidad válida.', 'error')
        return redirect(url_for('admin_inventario'))

    for pid in product_ids:
        pid_int = safe_int(pid)
        if not pid_int:
            continue
        if mov_type == 'entrada':
            execute_db("UPDATE products SET stock = stock + ? WHERE id=?", (quantity, pid_int))
        elif mov_type == 'salida':
            execute_db("UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?", (quantity, pid_int))
        else:
            execute_db("UPDATE products SET stock = ? WHERE id=?", (quantity, pid_int))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason) VALUES (?, ?, ?, ?)",
            (pid_int, mov_type, quantity, reason)
        )
        updated = query_db("SELECT stock FROM products WHERE id=?", (pid_int,), one=True)
        if updated:
            sse_bus.publish('stock_updated', {'id': pid_int, 'stock': updated['stock']})

    flash(f'Ajuste bulk aplicado a {len(product_ids)} producto(s).', 'success')
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

    # Estado efectivo antes y después del cambio
    eff_status  = new_status  if status_changed  else old_status
    eff_payment = new_payment if payment_changed else old_payment

    # Stock debe estar "libre" (devuelto) cuando la orden es cancelada O reembolsada
    def stock_libre(status, payment):
        return status == 'cancelado' or payment == 'reembolsado'

    era_libre  = stock_libre(old_status, old_payment)
    sera_libre = stock_libre(eff_status, eff_payment)

    if status_changed:
        execute_db("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    if payment_changed:
        execute_db("UPDATE orders SET payment_status=? WHERE id=?", (new_payment, oid))

    # Mover inventario solo si cambia el estado de "libre"
    if era_libre != sera_libre:
        items = query_db("SELECT * FROM order_items WHERE order_id=?", (oid,))
        if sera_libre:
            # Orden pasa a cancelada/reembolsada → devolver stock
            reason = 'Cancelación de orden' if eff_status == 'cancelado' else 'Reembolso de orden'
            for item in items:
                execute_db("UPDATE products SET stock = stock + ? WHERE id=?",
                           (item['quantity'], item['product_id']))
                execute_db(
                    "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'entrada', ?, ?, ?)",
                    (item['product_id'], item['quantity'], reason, order['order_number'])
                )
        else:
            # Orden reactivada → volver a descontar stock
            for item in items:
                execute_db("UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?",
                           (item['quantity'], item['product_id']))
                execute_db(
                    "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'salida', ?, 'Reactivación de orden', ?)",
                    (item['product_id'], item['quantity'], order['order_number'])
                )

    # Notificar al cliente si hubo un cambio relevante
    notify_status = new_status if status_changed else ''
    notify_payment = new_payment if payment_changed else ''
    if notify_status or notify_payment:
        # Re-fetch para tener los datos actualizados
        updated_order = query_db("SELECT * FROM orders WHERE id=?", (oid,), one=True)
        send_status_email(updated_order, notify_status, notify_payment)
        sse_bus.publish('order_updated', {
            'id': oid,
            'status': eff_status,
            'payment_status': eff_payment,
        })

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

    # Construir ítems válidos antes de tocar la BD
    line_items = []
    for pid, qty, cost in zip(product_ids, quantities, unit_costs):
        if not pid or not qty or not cost:
            continue
        qty_int = safe_int(qty, 0)
        cost_float = safe_float(cost, 0.0)
        pid_int = safe_int(pid, 0)
        if qty_int <= 0 or cost_float <= 0 or pid_int <= 0:
            continue
        prod = query_db("SELECT id FROM products WHERE id=?", (pid_int,), one=True)
        if not prod:
            flash(f'Producto ID {pid_int} no encontrado.', 'error')
            return redirect(url_for('admin_ordenes_compra'))
        line_items.append((pid_int, qty_int, cost_float))

    if not line_items:
        flash('Debes agregar al menos un producto con cantidad y costo válidos.', 'error')
        return redirect(url_for('admin_ordenes_compra'))

    po_number = f'OC-{datetime.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'
    total = sum(qty * cost for _, qty, cost in line_items)

    po_id = execute_db(
        "INSERT INTO purchase_orders (po_number, supplier, expected_date, notes, total) VALUES (?, ?, ?, ?, ?)",
        (po_number, supplier, expected_date, notes, total)
    )

    for pid_int, qty_int, cost_float in line_items:
        execute_db(
            "INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_cost, subtotal) VALUES (?, ?, ?, ?, ?)",
            (po_id, pid_int, qty_int, cost_float, qty_int * cost_float)
        )
        execute_db("UPDATE products SET stock = stock + ? WHERE id=?", (qty_int, pid_int))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'entrada', ?, 'Orden de Compra', ?)",
            (pid_int, qty_int, po_number)
        )

    flash(f'Orden de compra {po_number} creada. Inventario actualizado.', 'success')
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


@app.route('/admin/ordenes-compra/<int:po_id>/invoice')
@admin_required
def admin_oc_invoice(po_id):
    po = query_db("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po:
        flash('Orden de compra no encontrada.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    items = query_db(
        """SELECT poi.*, p.name as product_name, p.sku, p.dose
           FROM purchase_order_items poi
           JOIN products p ON poi.product_id = p.id
           WHERE poi.po_id=?""",
        (po_id,)
    )
    return render_template('admin/invoice_oc.html', po=po, items=items)


@app.route('/admin/ordenes-compra/<int:po_id>/recibir', methods=['POST'])
@admin_required
def admin_recibir_oc(po_id):
    po = query_db("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po or po['status'] == 'recibido':
        flash('Orden no válida o ya fue recibida.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    # Stock ya fue sumado al crear la OC — solo actualizar status
    execute_db("UPDATE purchase_orders SET status='recibido' WHERE id=?", (po_id,))
    # Enviar notificación de OC recibida
    try:
        po_items = query_db(
            """SELECT poi.*, p.name as product_name, p.sku
               FROM purchase_order_items poi
               JOIN products p ON poi.product_id = p.id
               WHERE poi.po_id=?""",
            (po_id,)
        )
        send_po_received_email(dict(po), [dict(i) for i in po_items])
    except Exception as e:
        print(f"[Email] Notificación OC falló: {e}")
    flash(f'Orden {po["po_number"]} marcada como recibida.', 'success')
    return redirect(url_for('admin_ordenes_compra'))


@app.route('/admin/ordenes-compra/<int:po_id>/cancelar', methods=['POST'])
@admin_required
def admin_cancelar_oc(po_id):
    po = query_db("SELECT * FROM purchase_orders WHERE id=?", (po_id,), one=True)
    if not po:
        flash('Orden no encontrada.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    if po['status'] == 'cancelado':
        flash('Esta orden ya está cancelada.', 'error')
        return redirect(url_for('admin_ordenes_compra'))
    # Revertir el stock que se sumó al crear (tanto pendiente como recibido)
    items = query_db("SELECT * FROM purchase_order_items WHERE po_id=?", (po_id,))
    for item in items:
        execute_db("UPDATE products SET stock = MAX(0, stock - ?) WHERE id=?",
                   (item['quantity'], item['product_id']))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?, 'salida', ?, 'Cancelación OC', ?)",
            (item['product_id'], item['quantity'], po['po_number'])
        )
    execute_db("UPDATE purchase_orders SET status='cancelado' WHERE id=?", (po_id,))
    flash(f'Orden {po["po_number"]} cancelada. Inventario revertido.', 'success')
    return redirect(url_for('admin_ordenes_compra'))


# ---------------------------------------------------------------------------
# Supplier documents — upload, parse with AI, import to inventory
# ---------------------------------------------------------------------------

@app.route('/admin/proveedor-docs')
@admin_required
def admin_proveedor_docs():
    docs = query_db("SELECT * FROM supplier_documents ORDER BY created_at DESC LIMIT 30")
    return render_template('admin/proveedor_docs.html', docs=docs)


@app.route('/admin/proveedor-docs/subir', methods=['POST'])
@admin_required
def admin_subir_doc():
    file = request.files.get('document')
    if not file or not file.filename:
        flash('Debes seleccionar un archivo.', 'error')
        return redirect(url_for('admin_proveedor_docs'))

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_DOC_EXTENSIONS:
        flash(f'Formato no soportado. Usa: {", ".join(ALLOWED_DOC_EXTENSIONS)}', 'error')
        return redirect(url_for('admin_proveedor_docs'))

    safe_name = f'{uuid.uuid4().hex[:12]}_{secure_filename(file.filename)}'
    filepath = os.path.join(DOCS_FOLDER, safe_name)
    file.save(filepath)

    # Extract text
    doc_text, err = extract_text_from_file(filepath, file.filename)
    if err:
        flash(f'Error al leer el archivo: {err}', 'error')
        return redirect(url_for('admin_proveedor_docs'))

    # Parse with Claude
    existing_products = query_db("SELECT id, name, sku, dose, price FROM products WHERE active=1 ORDER BY name")
    parsed, err = parse_doc_with_claude(doc_text, [dict(p) for p in existing_products])
    if err:
        # Save doc with error status so admin can retry
        execute_db(
            "INSERT INTO supplier_documents (filename, original_name, file_type, status, extracted_json) VALUES (?,?,?,?,?)",
            (safe_name, file.filename, ext, 'error', json.dumps({'error': err, 'raw_text': doc_text[:2000]}))
        )
        flash(f'El archivo se subió pero el análisis IA falló: {err}', 'error')
        return redirect(url_for('admin_proveedor_docs'))

    doc_id = execute_db(
        "INSERT INTO supplier_documents (filename, original_name, file_type, supplier, status, extracted_json) VALUES (?,?,?,?,?,?)",
        (safe_name, file.filename, ext, parsed.get('supplier', ''), 'analizado', json.dumps(parsed))
    )
    flash(f'Documento analizado: {parsed.get("supplier","")}, {len(parsed.get("products",[]))} producto(s) detectado(s).', 'success')
    return redirect(url_for('admin_doc_preview', doc_id=doc_id))


@app.route('/admin/proveedor-docs/<int:doc_id>')
@admin_required
def admin_doc_preview(doc_id):
    doc = query_db("SELECT * FROM supplier_documents WHERE id=?", (doc_id,), one=True)
    if not doc:
        flash('Documento no encontrado.', 'error')
        return redirect(url_for('admin_proveedor_docs'))
    parsed = json.loads(doc['extracted_json']) if doc['extracted_json'] else {}
    products = query_db("SELECT id, name, sku, dose, price, stock FROM products ORDER BY name")
    docs = query_db("SELECT * FROM supplier_documents ORDER BY created_at DESC LIMIT 30")
    return render_template('admin/proveedor_docs.html',
                           doc=doc, parsed=parsed,
                           all_products=products,
                           docs=docs)


@app.route('/admin/proveedor-docs/<int:doc_id>/importar', methods=['POST'])
@admin_required
def admin_importar_doc(doc_id):
    doc = query_db("SELECT * FROM supplier_documents WHERE id=?", (doc_id,), one=True)
    if not doc:
        flash('Documento no encontrado.', 'error')
        return redirect(url_for('admin_proveedor_docs'))
    if doc['status'] == 'importado':
        flash('Este documento ya fue importado.', 'error')
        return redirect(url_for('admin_doc_preview', doc_id=doc_id))

    supplier = request.form.get('supplier', '').strip() or doc['supplier'] or 'Proveedor'
    expected_date = request.form.get('expected_date', '').strip()
    notes = request.form.get('notes', '').strip()
    create_products = request.form.get('create_products') == '1'

    # Collect line items from form
    product_ids_form = request.form.getlist('product_id[]')
    quantities_form  = request.form.getlist('quantity[]')
    unit_costs_form  = request.form.getlist('unit_cost[]')
    names_form       = request.form.getlist('product_name[]')
    doses_form       = request.form.getlist('product_dose[]')
    skus_form        = request.form.getlist('product_sku[]')

    line_items = []
    new_product_ids = []

    for i, pid_str in enumerate(product_ids_form):
        qty = safe_int(quantities_form[i] if i < len(quantities_form) else '0', 0)
        cost = safe_float(unit_costs_form[i] if i < len(unit_costs_form) else '0', 0.0)
        if qty <= 0 or cost < 0:
            continue

        pid = safe_int(pid_str, 0)

        if pid == 0 and create_products:
            # Create new product
            pname = (names_form[i] if i < len(names_form) else '').strip() or f'Producto {i+1}'
            pdose = (doses_form[i] if i < len(doses_form) else '').strip() or '—'
            psku  = (skus_form[i]  if i < len(skus_form)  else '').strip()
            if not psku:
                psku = f'JDP-{uuid.uuid4().hex[:6].upper()}'
            existing = query_db("SELECT id FROM products WHERE sku=?", (psku,), one=True)
            if existing:
                pid = existing['id']
            else:
                pid = execute_db(
                    "INSERT INTO products (sku, name, category, dose, price, stock, low_stock_alert, active) VALUES (?,?,?,?,?,0,5,1)",
                    (psku, pname, 'General', pdose, cost)
                )
                new_product_ids.append(pid)

        if pid > 0:
            line_items.append((pid, qty, cost))

    if not line_items:
        flash('No hay ítems válidos para importar.', 'error')
        return redirect(url_for('admin_doc_preview', doc_id=doc_id))

    # Create purchase order
    po_number = f'OC-{datetime.now().strftime("%Y%m%d")}-{str(uuid.uuid4())[:6].upper()}'
    total = sum(qty * cost for _, qty, cost in line_items)
    po_id = execute_db(
        "INSERT INTO purchase_orders (po_number, supplier, expected_date, notes, total, status) VALUES (?,?,?,?,?,'recibido')",
        (po_number, supplier, expected_date, f'Importado desde doc #{doc_id}. {notes}', total)
    )

    for pid, qty, cost in line_items:
        execute_db(
            "INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_cost, subtotal) VALUES (?,?,?,?,?)",
            (po_id, pid, qty, cost, qty * cost)
        )
        execute_db("UPDATE products SET stock = stock + ? WHERE id=?", (qty, pid))
        execute_db(
            "INSERT INTO stock_movements (product_id, type, quantity, reason, reference) VALUES (?,'entrada',?,?,?)",
            (pid, qty, f'Importación doc proveedor #{doc_id}', po_number)
        )

    execute_db(
        "UPDATE supplier_documents SET status='importado', po_id=?, processed_at=? WHERE id=?",
        (po_id, datetime.now().isoformat(), doc_id)
    )

    sse_bus.publish('stock_updated', {'reload': True})
    msg = f'OC {po_number} creada con {len(line_items)} ítem(s).'
    if new_product_ids:
        msg += f' {len(new_product_ids)} producto(s) nuevo(s) creado(s).'
    flash(msg, 'success')
    return redirect(url_for('admin_oc_detalle', po_id=po_id))


@app.route('/admin/proveedor-docs/<int:doc_id>/eliminar', methods=['POST'])
@admin_required
def admin_eliminar_doc(doc_id):
    doc = query_db("SELECT * FROM supplier_documents WHERE id=?", (doc_id,), one=True)
    if doc:
        filepath = os.path.join(DOCS_FOLDER, doc['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        execute_db("DELETE FROM supplier_documents WHERE id=?", (doc_id,))
        flash('Documento eliminado.', 'success')
    return redirect(url_for('admin_proveedor_docs'))


# ---------------------------------------------------------------------------
# Páginas informativas
# ---------------------------------------------------------------------------

@app.route('/sobre-nosotros')
def sobre_nosotros():
    return render_template('sobre_nosotros.html')


@app.route('/info')
def info():
    return render_template('info.html')


@app.route('/privacidad')
def privacidad():
    return render_template('privacidad.html')


@app.route('/terminos')
def terminos():
    return render_template('terminos.html')


@app.route('/faq')
def faq():
    return render_template('faq.html')


_nav_cats_cache = {'data': [], 'ts': 0}
_NAV_CATS_TTL = 60  # segundos

@app.context_processor
def inject_globals():
    cats = []
    try:
        now_ts = time.time()
        if now_ts - _nav_cats_cache['ts'] > _NAV_CATS_TTL:
            _nav_cats_cache['data'] = [r['category'] for r in query_db(
                "SELECT DISTINCT category FROM products WHERE active=1 AND category IS NOT NULL ORDER BY category"
            )]
            _nav_cats_cache['ts'] = now_ts
        cats = _nav_cats_cache['data']
    except Exception:
        pass
    return {'now': datetime.now(), 'nav_categories': cats}


# ---------------------------------------------------------------------------
# Inicializar BD al arrancar (funciona con gunicorn y python app.py)
# ---------------------------------------------------------------------------

with app.app_context():
    init_db()

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
