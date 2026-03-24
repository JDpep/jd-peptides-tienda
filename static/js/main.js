/* =========================================================
   JD PEPTIDES — Main JavaScript
   ========================================================= */

document.addEventListener('DOMContentLoaded', function () {

  // ---------------------------------------------------------
  // Flash messages auto-dismiss
  // ---------------------------------------------------------
  const flashContainer = document.querySelector('.flash-container');
  if (flashContainer) {
    const flashes = flashContainer.querySelectorAll('.flash');
    flashes.forEach((flash, i) => {
      flash.addEventListener('click', () => flash.remove());
      setTimeout(() => {
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(120%)';
        flash.style.transition = 'all 0.4s ease';
        setTimeout(() => flash.remove(), 400);
      }, 4000 + i * 500);
    });
  }

  // ---------------------------------------------------------
  // Mobile menu toggle
  // ---------------------------------------------------------
  const hamburger = document.getElementById('hamburger');
  const mobileNav = document.getElementById('mobileNav');
  if (hamburger && mobileNav) {
    hamburger.addEventListener('click', () => {
      const isOpen = mobileNav.classList.toggle('open');
      hamburger.setAttribute('aria-expanded', isOpen);
      hamburger.querySelectorAll('span').forEach((s, i) => {
        if (isOpen) {
          if (i === 0) s.style.transform = 'translateY(6px) rotate(45deg)';
          if (i === 1) s.style.opacity = '0';
          if (i === 2) s.style.transform = 'translateY(-6px) rotate(-45deg)';
        } else {
          s.style.transform = '';
          s.style.opacity = '';
        }
      });
    });
  }

  // ---------------------------------------------------------
  // Add to cart — AJAX
  // ---------------------------------------------------------
  document.querySelectorAll('.add-to-cart-btn').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const productId = this.dataset.productId;
      const qtyInput = document.getElementById('qty-' + productId) ||
                       document.getElementById('qty-detail');
      const quantity = qtyInput ? parseInt(qtyInput.value) : 1;

      const originalText = this.innerHTML;
      this.innerHTML = '<span style="display:inline-block;animation:spin 0.6s linear infinite">⟳</span> Agregando…';
      this.disabled = true;

      fetch('/carrito/agregar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, quantity: quantity })
      })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            updateCartBadges(data.cart_count);
            showToast(data.message, 'success');
            this.innerHTML = '✓ Agregado';
            setTimeout(() => {
              this.innerHTML = originalText;
              this.disabled = false;
            }, 1800);
          } else {
            showToast(data.message || 'Error al agregar', 'error');
            this.innerHTML = originalText;
            this.disabled = false;
          }
        })
        .catch(() => {
          showToast('Error de conexión', 'error');
          this.innerHTML = originalText;
          this.disabled = false;
        });
    });
  });

  // ---------------------------------------------------------
  // Remove from cart — AJAX
  // ---------------------------------------------------------
  document.querySelectorAll('.remove-from-cart').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      const pid = this.dataset.pid;
      const row = this.closest('tr');

      fetch('/carrito/eliminar/' + pid, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
          if (data.success) {
            if (row) {
              row.style.opacity = '0';
              row.style.transform = 'translateX(-20px)';
              row.style.transition = 'all 0.3s ease';
              setTimeout(() => { row.remove(); recalcCartTotals(); }, 300);
            }
            updateCartBadges(data.cart_count);
          }
        });
    });
  });

  // ---------------------------------------------------------
  // Cart quantity live update
  // ---------------------------------------------------------
  document.querySelectorAll('.cart-qty-input').forEach(input => {
    input.addEventListener('change', function () {
      let val = parseInt(this.value);
      if (isNaN(val) || val < 1) { this.value = 1; val = 1; }
      recalcCartTotals();
    });
  });

  function recalcCartTotals() {
    let subtotal = 0;
    document.querySelectorAll('.cart-table tbody tr').forEach(row => {
      const priceEl = row.querySelector('[data-price]');
      const qtyInput = row.querySelector('.cart-qty-input');
      if (priceEl && qtyInput) {
        const price = parseFloat(priceEl.dataset.price);
        const qty = parseInt(qtyInput.value) || 0;
        const lineTotal = price * qty;
        const subtotalEl = row.querySelector('.line-subtotal');
        if (subtotalEl) subtotalEl.textContent = '$' + lineTotal.toFixed(2);
        subtotal += lineTotal;
      }
    });
    const subtotalEl = document.getElementById('cart-subtotal');
    const shippingEl = document.getElementById('cart-shipping');
    const totalEl    = document.getElementById('cart-total');
    if (subtotalEl) subtotalEl.textContent = '$' + subtotal.toFixed(2);
    const shipping = subtotal >= 200 ? 0 : 15;
    if (shippingEl) shippingEl.textContent = shipping === 0 ? 'Gratis' : '$' + shipping.toFixed(2);
    if (totalEl)    totalEl.textContent = '$' + (subtotal + shipping).toFixed(2);
  }

  // ---------------------------------------------------------
  // Quantity selector (+/-)
  // ---------------------------------------------------------
  document.querySelectorAll('.qty-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const input = document.getElementById(this.dataset.target || 'qty-detail');
      if (!input) return;
      let val = parseInt(input.value) || 1;
      if (this.dataset.action === 'inc') val = Math.min(val + 1, 99);
      if (this.dataset.action === 'dec') val = Math.max(val - 1, 1);
      input.value = val;
    });
  });

  // ---------------------------------------------------------
  // Cart badge update
  // ---------------------------------------------------------
  function updateCartBadges(count) {
    document.querySelectorAll('.cart-count').forEach(el => {
      el.textContent = count;
      el.style.display = count > 0 ? 'inline-flex' : 'none';
    });
  }

  // ---------------------------------------------------------
  // Toast notification
  // ---------------------------------------------------------
  function showToast(message, type = 'success') {
    let container = document.querySelector('.flash-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'flash-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `flash flash-${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span> ${message}`;
    container.appendChild(toast);
    toast.addEventListener('click', () => toast.remove());
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(120%)';
      toast.style.transition = 'all 0.4s ease';
      setTimeout(() => toast.remove(), 400);
    }, 3500);
  }
  window.showToast = showToast;

  // ---------------------------------------------------------
  // Admin: confirm dialogs
  // ---------------------------------------------------------
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      if (!confirm(this.dataset.confirm)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  });

  // ---------------------------------------------------------
  // Admin: modal open/close
  // ---------------------------------------------------------
  document.querySelectorAll('[data-modal]').forEach(trigger => {
    trigger.addEventListener('click', function () {
      const modal = document.getElementById(this.dataset.modal);
      if (modal) modal.classList.add('open');
    });
  });
  document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
    el.addEventListener('click', function (e) {
      if (e.target === this) {
        const overlay = this.closest('.modal-overlay') || this;
        if (overlay) overlay.classList.remove('open');
      }
    });
  });
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => e.stopPropagation());
  });

  // ---------------------------------------------------------
  // Admin: PO line items (add/remove rows)
  // ---------------------------------------------------------
  const addLineBtn = document.getElementById('addPoLine');
  const poLines    = document.getElementById('poLines');
  const products   = window.JDP_PRODUCTS || [];

  if (addLineBtn && poLines) {
    let lineCount = poLines.querySelectorAll('.po-line').length;

    addLineBtn.addEventListener('click', () => {
      lineCount++;
      const line = document.createElement('div');
      line.className = 'po-line';
      line.innerHTML = `
        <div class="admin-form-group">
          <label class="admin-label">Producto</label>
          <select name="product_id[]" class="admin-input" required>
            <option value="">Seleccionar…</option>
            ${products.map(p => `<option value="${p.id}">${p.name} (${p.sku})</option>`).join('')}
          </select>
        </div>
        <div class="admin-form-group">
          <label class="admin-label">Cantidad</label>
          <input type="number" name="quantity[]" class="admin-input" min="1" value="1" required>
        </div>
        <div class="admin-form-group">
          <label class="admin-label">Costo Unit.</label>
          <input type="number" name="unit_cost[]" class="admin-input" min="0" step="0.01" value="0" required>
        </div>
        <div class="admin-form-group" style="padding-top:1.6rem">
          <button type="button" class="btn btn-danger btn-sm remove-po-line">✕</button>
        </div>`;
      poLines.appendChild(line);
      bindRemoveLine(line.querySelector('.remove-po-line'));
    });

    poLines.querySelectorAll('.remove-po-line').forEach(bindRemoveLine);
  }

  function bindRemoveLine(btn) {
    if (!btn) return;
    btn.addEventListener('click', function () {
      const line = this.closest('.po-line');
      if (line && document.querySelectorAll('.po-line').length > 1) {
        line.remove();
      } else {
        showToast('Debe haber al menos una línea.', 'error');
      }
    });
  }

  // ---------------------------------------------------------
  // Stock adjustment: show inline form
  // ---------------------------------------------------------
  document.querySelectorAll('.show-adjustment-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const form = document.getElementById('adjustment-form-' + this.dataset.pid);
      if (form) {
        const isHidden = form.style.display === 'none' || !form.style.display;
        form.style.display = isHidden ? 'table-row' : 'none';
      }
    });
  });

  // ---------------------------------------------------------
  // Category filter (catalog page)
  // ---------------------------------------------------------
  const searchInput = document.getElementById('catalogSearch');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const url = new URL(window.location.href);
        url.searchParams.set('q', this.value);
        url.searchParams.delete('page');
        window.location.href = url.toString();
      }, 600);
    });
  }

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', function (e) {
      const target = document.querySelector(this.hash);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // CSS spin animation
  const style = document.createElement('style');
  style.textContent = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }';
  document.head.appendChild(style);
});
