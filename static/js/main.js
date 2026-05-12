/* =========================================================
   JD PEPTIDES — Main JavaScript
   ========================================================= */

document.addEventListener('DOMContentLoaded', function () {

  // ---------------------------------------------------------
  // Flash messages auto-dismiss (with slide-out animation)
  // ---------------------------------------------------------
  const flashContainer = document.querySelector('.flash-container');
  if (flashContainer) {
    const flashes = flashContainer.querySelectorAll('.flash');
    flashes.forEach((flash, i) => {
      flash.addEventListener('click', () => dismissFlash(flash));
      setTimeout(() => dismissFlash(flash), 4000 + i * 500);
    });
  }

  function dismissFlash(flash) {
    if (flash._dismissed) return;
    flash._dismissed = true;
    flash.classList.add('dismissing');
    setTimeout(() => flash.remove(), 380);
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
  // Add to cart — AJAX with animations
  // ---------------------------------------------------------
  function bindAddToCart(btn) {
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
            this.classList.add('added');
            setTimeout(() => {
              this.innerHTML = originalText;
              this.classList.remove('added');
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
  }
  document.querySelectorAll('.add-to-cart-btn').forEach(bindAddToCart);

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
  // Cart quantity live update — AJAX
  // ---------------------------------------------------------
  document.querySelectorAll('.cart-qty-input').forEach(input => {
    input.addEventListener('change', function () {
      let val = parseInt(this.value);
      if (isNaN(val) || val < 1) { this.value = 1; val = 1; }
      const row = this.closest('tr');
      const pid = row ? row.dataset.pid : null;
      // Optimistic local update
      recalcCartTotals();
      // Sync to server
      if (pid) {
        fetch('/api/carrito/actualizar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product_id: pid, quantity: val })
        }).then(r => r.json()).then(data => {
          if (data.success) {
            updateCartBadges(data.cart_count);
          }
        }).catch(() => {});
      }
    });
  });

  function recalcCartTotals() {
    let subtotal = 0;
    document.querySelectorAll('.cart-table tbody tr[data-pid]').forEach(row => {
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
  // Cart badge update with bounce animation
  // ---------------------------------------------------------
  function updateCartBadges(count) {
    document.querySelectorAll('.cart-count').forEach(el => {
      el.textContent = count;
      el.style.display = count > 0 ? 'inline-flex' : 'none';
      el.classList.remove('bump');
      void el.offsetWidth; // reflow to restart animation
      el.classList.add('bump');
      setTimeout(() => el.classList.remove('bump'), 450);
    });
  }

  // ---------------------------------------------------------
  // Toast notification
  // ---------------------------------------------------------
  function showToast(message, type = 'success', persistent = false) {
    let container = document.querySelector('.flash-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'flash-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `flash flash-${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : type === 'info' ? 'ℹ' : '✕'}</span> ${message}`;
    container.appendChild(toast);
    toast.addEventListener('click', () => dismissFlash(toast));
    if (!persistent) {
      setTimeout(() => dismissFlash(toast), 3500);
    }
    return toast;
  }
  window.showToast = showToast;

  // ---------------------------------------------------------
  // Product image gallery crossfade
  // ---------------------------------------------------------
  document.querySelectorAll('.gallery-thumb').forEach(thumb => {
    thumb.addEventListener('click', function () {
      const mainImg = document.getElementById('gallery-main-img');
      if (!mainImg) return;
      const newSrc = this.dataset.src || this.src;
      if (mainImg.src === newSrc) return;
      mainImg.classList.add('fading');
      setTimeout(() => {
        mainImg.src = newSrc;
        mainImg.classList.remove('fading');
      }, 220);
      document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
      this.classList.add('active');
    });
  });

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
    poLines.querySelectorAll('.remove-po-line').forEach(bindRemoveLine);

    addLineBtn.addEventListener('click', () => {
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
  // Catalog: sidebar filters + AJAX + drawer mobile + quickview
  // ---------------------------------------------------------
  const searchInput   = document.getElementById('catalogSearch');
  const catalogGrid   = document.getElementById('catalog-grid');
  const catalogCount  = document.getElementById('catalog-count');
  const filtersForm   = document.getElementById('catalogFiltersForm');
  const sortSelect    = document.getElementById('catalogSort');
  const sidebar       = document.getElementById('catalogSidebar');
  const sidebarOpen   = document.getElementById('catalogSidebarOpen');
  const sidebarClose  = document.getElementById('catalogSidebarClose');
  const backdrop      = document.getElementById('catalogSidebarBackdrop');
  const filtersCount  = document.getElementById('catalogFiltersCount');
  const activeChips   = document.getElementById('catalogActiveChips');
  const clearAllBtn   = document.getElementById('catalogClearAll');
  const emptyClearBtn = document.getElementById('catalogEmptyClear');

  if (filtersForm && catalogGrid) {
    const TAG_LABELS = window.TAG_LABELS || {};
    let debounceTimer;

    // Helpers ---------------------------------------------------
    function escHtml(s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function buildParams() {
      const fd = new FormData(filtersForm);
      const params = new URLSearchParams();
      const set = (k, v) => { if (v != null && v !== '') params.set(k, v); };
      set('q',         (fd.get('q') || '').toString().trim());
      set('categoria', fd.get('categoria') || '');
      set('tag',       fd.get('tag') || '');
      set('min_price', fd.get('min_price') || '');
      set('max_price', fd.get('max_price') || '');
      if (fd.get('in_stock')) params.set('in_stock', '1');
      if (sortSelect && sortSelect.value && sortSelect.value !== 'name_asc') {
        params.set('sort', sortSelect.value);
      }
      return params;
    }

    function activeFiltersCount() {
      const p = buildParams();
      let n = 0;
      for (const k of ['q', 'categoria', 'tag', 'min_price', 'max_price', 'in_stock']) {
        if (p.get(k)) n++;
      }
      return n;
    }

    function syncURL(params) {
      const url = new URL(window.location.href);
      url.search = params.toString();
      window.history.replaceState({}, '', url);
    }

    // Active chips bar -----------------------------------------
    function renderActiveChips() {
      if (!activeChips) return;
      const p = buildParams();
      const labels = [];
      if (p.get('q'))         labels.push({ key:'q',         label: `“${p.get('q')}”`,                        title:'Búsqueda' });
      if (p.get('categoria')) labels.push({ key:'categoria', label: p.get('categoria'),                       title:'Categoría' });
      if (p.get('tag'))       labels.push({ key:'tag',       label: TAG_LABELS[p.get('tag')] || p.get('tag'), title:'Cross-ref' });
      if (p.get('min_price')) labels.push({ key:'min_price', label: `≥ $${p.get('min_price')}`,               title:'Precio mín' });
      if (p.get('max_price')) labels.push({ key:'max_price', label: `≤ $${p.get('max_price')}`,               title:'Precio máx' });
      if (p.get('in_stock'))  labels.push({ key:'in_stock',  label: 'En stock',                               title:'Stock' });

      if (!labels.length) { activeChips.hidden = true; activeChips.innerHTML = ''; return; }
      activeChips.hidden = false;
      activeChips.innerHTML =
        '<span class="cac-label">Filtros activos</span>' +
        labels.map(l =>
          `<button type="button" class="cac-chip" data-clear="${l.key}" title="Quitar ${escHtml(l.title)}">
             <span>${escHtml(l.label)}</span>
             <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="3" x2="9" y2="9"/><line x1="9" y1="3" x2="3" y2="9"/></svg>
           </button>`
        ).join('') +
        `<button type="button" class="cac-clear-all" id="cacClearAll">Limpiar todo</button>`;
      activeChips.querySelectorAll('.cac-chip').forEach(btn => {
        btn.addEventListener('click', () => clearSingle(btn.dataset.clear));
      });
      const ca = activeChips.querySelector('#cacClearAll');
      if (ca) ca.addEventListener('click', clearAll);
    }

    function updateFiltersCount() {
      if (!filtersCount) return;
      const n = activeFiltersCount();
      if (n > 0) { filtersCount.hidden = false; filtersCount.textContent = n; }
      else       { filtersCount.hidden = true; }
    }

    function clearSingle(key) {
      if (key === 'q')         { searchInput.value = ''; }
      if (key === 'categoria') { const el = filtersForm.querySelector('input[name="categoria"][value=""]'); if (el) el.checked = true; }
      if (key === 'tag')       { const el = filtersForm.querySelector('input[name="tag"][value=""]');       if (el) el.checked = true; }
      if (key === 'min_price') { const el = filtersForm.querySelector('input[name="min_price"]'); if (el) el.value = ''; }
      if (key === 'max_price') { const el = filtersForm.querySelector('input[name="max_price"]'); if (el) el.value = ''; }
      if (key === 'in_stock')  { const el = filtersForm.querySelector('input[name="in_stock"]');  if (el) el.checked = false; }
      apply();
    }

    function clearAll() {
      filtersForm.reset();
      if (sortSelect) sortSelect.value = 'name_asc';
      apply();
    }

    // Apply (AJAX) ---------------------------------------------
    function showSkeletons() {
      const skeletons = Array(6).fill(0).map(() => `
        <div class="skeleton-card">
          <div class="sk-visual"></div>
          <div class="sk-line"></div>
          <div class="sk-line short"></div>
        </div>`).join('');
      catalogGrid.classList.add('catalog-loading');
      catalogGrid.innerHTML = `<div class="products-grid">${skeletons}</div>`;
    }

    function apply() {
      const params = buildParams();
      syncURL(params);
      renderActiveChips();
      updateFiltersCount();
      showSkeletons();
      fetch('/api/productos?' + params.toString())
        .then(r => r.json())
        .then(data => {
          if (catalogCount) {
            catalogCount.textContent = data.count + ' producto' + (data.count !== 1 ? 's' : '');
          }
          if (data.products.length === 0) {
            catalogGrid.innerHTML = `
              <div class="catalog-empty">
                <div class="catalog-empty-illustration">
                  <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" width="96" height="96" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="52" cy="52" r="32" opacity="0.5"/>
                    <line x1="76" y1="76" x2="104" y2="104" stroke-linecap="round"/>
                    <line x1="40" y1="52" x2="64" y2="52" opacity="0.6"/>
                    <line x1="52" y1="40" x2="52" y2="64" opacity="0.6"/>
                  </svg>
                </div>
                <h3>No encontramos péptidos con esos filtros</h3>
                <p>Prueba quitando algún filtro o buscando con otro término.</p>
                <button type="button" id="catalogEmptyClear" class="btn btn-gold btn-sm">Limpiar filtros</button>
              </div>`;
            const ec = document.getElementById('catalogEmptyClear');
            if (ec) ec.addEventListener('click', clearAll);
          } else {
            catalogGrid.innerHTML =
              `<div class="products-grid animate-stagger">${data.products.map(p => renderProductCard(p)).join('')}</div>`;
            catalogGrid.querySelectorAll('.add-to-cart-btn').forEach(bindAddToCart);
            requestAnimationFrame(() => {
              catalogGrid.querySelectorAll('.product-card').forEach((card, i) => {
                card.style.setProperty('--delay', i * 0.05 + 's');
                card.classList.add('animate-in');
              });
            });
          }
          catalogGrid.classList.remove('catalog-loading');
        })
        .catch(() => {
          catalogGrid.classList.remove('catalog-loading');
          catalogGrid.innerHTML = '<p style="text-align:center;padding:3rem;color:var(--text3)">Error al cargar productos.</p>';
        });
    }

    function renderProductCard(p) {
      const inStock  = p.stock > 0;
      const lowAlert = (p.low_stock_alert == null ? 5 : p.low_stock_alert);
      const isJpeg   = p.image_url && (/\.(jpeg|jpg)$/i.test(p.image_url) || /_frasco_/i.test(p.image_url));
      const detailUrl = '/producto/' + encodeURIComponent(p.slug || p.id);
      const altText   = `Frasco ${p.name} ${p.dose} — For Research Use Only`;

      const imgTag = p.image_url
        ? `<img src="${escHtml(p.image_url)}" alt="${escHtml(altText)}" class="product-card-img${isJpeg ? ' img-vial-right' : ''}" loading="lazy" decoding="async" width="320" height="533">`
        : `<div class="product-visual-name">${escHtml(p.name)}</div><div class="product-visual-dose">${escHtml(p.dose)}</div>`;

      let stockBadge;
      if (!inStock)                 stockBadge = `<span class="stock-badge out">Agotado</span>`;
      else if (p.stock <= lowAlert) stockBadge = `<span class="stock-badge low">Pocas unidades (${p.stock})</span>`;
      else                          stockBadge = `<span class="stock-badge ok">En stock</span>`;

      const tagsHtml = (p.tags || '').split('|').filter(Boolean).slice(0, 3).map(t => {
        const label = TAG_LABELS[t] || t.replace(/-/g, ' ');
        return `<a href="/catalogo?tag=${encodeURIComponent(t)}" class="tag-chip" onclick="event.stopPropagation()">${escHtml(label)}</a>`;
      }).join('');
      const tagsBlock = tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : '';

      return `
        <div class="product-card" data-product-id="${p.id}">
          <button type="button" class="product-quickview-btn" data-product-id="${p.id}" title="Vista rápida" aria-label="Vista rápida">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
          <a href="${detailUrl}" style="text-decoration:none;display:contents">
            <div class="product-visual${p.image_url ? ' product-visual-has-img' : ''}">
              <div class="product-visual-cat">
                <span class="badge badge-gold">${escHtml(p.category)}</span>
              </div>
              ${imgTag}
            </div>
          </a>
          <div class="product-body">
            <h3 class="product-name">${escHtml(p.name)}</h3>
            <p class="product-dose">${escHtml(p.sku || '')} · ${escHtml(p.dose)}</p>
            ${tagsBlock}
            <div class="product-price" style="color:var(--gold)">$${parseFloat(p.price).toFixed(2)} <span class="price-currency">USD</span></div>
            <div style="margin-top:0.5rem">${stockBadge}</div>
          </div>
          <div class="product-footer">
            <a href="${detailUrl}" class="btn btn-ghost btn-sm">Ver detalle</a>
            ${inStock
              ? `<button class="btn btn-gold btn-sm add-to-cart-btn" data-product-id="${p.id}">+ Agregar</button>`
              : `<span style="font-size:0.78rem;color:var(--red);font-weight:600">Sin stock</span>`}
          </div>
        </div>`;
    }

    // Event wiring ---------------------------------------------
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(apply, 350);
      });
    }
    filtersForm.querySelectorAll('input[type="radio"], input[type="checkbox"]').forEach(el => {
      el.addEventListener('change', apply);
    });
    filtersForm.querySelectorAll('input[type="number"]').forEach(el => {
      el.addEventListener('change', apply);
      el.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(apply, 500);
      });
    });
    if (sortSelect) sortSelect.addEventListener('change', apply);
    if (clearAllBtn) clearAllBtn.addEventListener('click', clearAll);
    if (emptyClearBtn) emptyClearBtn.addEventListener('click', clearAll);

    // Mobile drawer ---------------------------------------------
    function openDrawer() {
      sidebar.classList.add('open');
      backdrop.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function closeDrawer() {
      sidebar.classList.remove('open');
      backdrop.classList.remove('open');
      document.body.style.overflow = '';
    }
    if (sidebarOpen) sidebarOpen.addEventListener('click', openDrawer);
    if (sidebarClose) sidebarClose.addEventListener('click', closeDrawer);
    if (backdrop) backdrop.addEventListener('click', closeDrawer);

    // Initial state on load -------------------------------------
    renderActiveChips();
    updateFiltersCount();

    // Bind quickview on initial server-rendered cards
    bindQuickViewButtons();
    // Re-bind after every AJAX render via mutation observer:
    const obs = new MutationObserver(bindQuickViewButtons);
    obs.observe(catalogGrid, { childList: true, subtree: true });
  }

  // ---------------------------------------------------------
  // Quick-view modal (catalog cards)
  // ---------------------------------------------------------
  const qvOverlay = document.getElementById('quickViewOverlay');
  const qvContent = document.getElementById('quickViewContent');
  const qvLoading = document.getElementById('quickViewLoading');
  const qvClose   = document.getElementById('quickViewClose');
  const TAG_LABELS_QV = window.TAG_LABELS || {};

  function escHtmlQV(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function openQuickView(productId) {
    if (!qvOverlay) return;
    qvOverlay.hidden = false;
    qvContent.innerHTML = '';
    qvLoading.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Hit /api/productos and find the matching product
    fetch('/api/productos').then(r => r.json()).then(data => {
      const p = (data.products || []).find(x => String(x.id) === String(productId));
      qvLoading.style.display = 'none';
      if (!p) { qvContent.innerHTML = '<p style="padding:2rem;text-align:center">Producto no encontrado.</p>'; return; }
      const inStock = p.stock > 0;
      const tagsHtml = (p.tags || '').split('|').filter(Boolean).map(t =>
        `<span class="tag-chip">${escHtmlQV(TAG_LABELS_QV[t] || t)}</span>`
      ).join('');
      const benefits = (p.benefits || '').split('|').filter(Boolean).slice(0, 4);
      const benefitsList = benefits.length
        ? `<ul style="margin:0.85rem 0 0;padding-left:1.1rem;color:var(--text2);font-size:0.85rem;line-height:1.65">${benefits.map(b => `<li>${escHtmlQV(b)}</li>`).join('')}</ul>`
        : '';
      const detailUrl = '/producto/' + encodeURIComponent(p.slug || p.id);
      qvContent.innerHTML = `
        <div class="qv-img-wrap">
          ${p.image_url ? `<img src="${escHtmlQV(p.image_url)}" alt="${escHtmlQV(p.name)}">` : ''}
        </div>
        <div class="qv-info">
          <h2 id="qvTitle">${escHtmlQV(p.name)}</h2>
          <div class="qv-meta">${escHtmlQV(p.sku || '')} · ${escHtmlQV(p.dose)} · ${escHtmlQV(p.category)}</div>
          ${tagsHtml ? `<div class="card-tags">${tagsHtml}</div>` : ''}
          <div class="qv-price">$${parseFloat(p.price).toFixed(2)} <span class="price-currency">USD</span></div>
          ${p.description ? `<p class="qv-desc">${escHtmlQV(p.description)}</p>` : ''}
          ${benefitsList}
          <div class="qv-actions">
            <a href="${detailUrl}" class="btn btn-ghost btn-sm">Ver detalle completo →</a>
            ${inStock
              ? `<button class="btn btn-gold btn-sm add-to-cart-btn" data-product-id="${p.id}">+ Agregar al carrito</button>`
              : `<span style="font-size:0.85rem;color:var(--red);font-weight:600;padding:0.5rem 0">Sin stock</span>`}
          </div>
        </div>`;
      qvContent.querySelectorAll('.add-to-cart-btn').forEach(bindAddToCart);
    }).catch(() => {
      qvLoading.style.display = 'none';
      qvContent.innerHTML = '<p style="padding:2rem;text-align:center">Error al cargar.</p>';
    });
  }
  function closeQuickView() {
    if (!qvOverlay) return;
    qvOverlay.hidden = true;
    qvContent.innerHTML = '';
    document.body.style.overflow = '';
  }
  function bindQuickViewButtons() {
    document.querySelectorAll('.product-quickview-btn').forEach(btn => {
      if (btn._qvBound) return;
      btn._qvBound = true;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        openQuickView(btn.dataset.productId);
      });
    });
  }
  if (qvClose) qvClose.addEventListener('click', closeQuickView);
  if (qvOverlay) qvOverlay.addEventListener('click', (e) => { if (e.target === qvOverlay) closeQuickView(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && qvOverlay && !qvOverlay.hidden) closeQuickView(); });
  // Initial bind on server-rendered cards
  bindQuickViewButtons();

  // ---------------------------------------------------------
  // Smooth scroll for anchor links
  // ---------------------------------------------------------
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

  // ---------------------------------------------------------
  // Scroll reveal — fade-in cards and sections as they enter viewport
  // ---------------------------------------------------------
  if ('IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.product-card, .reveal, .reveal-left, .reveal-right').forEach(el => {
      revealObserver.observe(el);
    });

    // Count-up for stat numbers when they enter view
    const countUpObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const raw = el.dataset.target;
        if (!raw) return;
        countUpObserver.unobserve(el);
        const end = parseFloat(raw);
        const isInt = Number.isInteger(end);
        const suffix = el.dataset.suffix || '';
        const prefix = el.dataset.prefix || '';
        const dur = 1200;
        const start = performance.now();
        function tick(now) {
          const pct = Math.min((now - start) / dur, 1);
          const eased = 1 - Math.pow(1 - pct, 3);
          const val = end * eased;
          el.textContent = prefix + (isInt ? Math.round(val) : val.toFixed(1)) + suffix;
          if (pct < 1) requestAnimationFrame(tick);
          else { el.textContent = prefix + (isInt ? end : end.toFixed(1)) + suffix; el.classList.add('counted'); }
        }
        requestAnimationFrame(tick);
      });
    }, { threshold: 0.3 });

    document.querySelectorAll('.cq-stat-num[data-target]').forEach(el => {
      countUpObserver.observe(el);
    });

  } else {
    document.querySelectorAll('.product-card, .reveal, .reveal-left, .reveal-right').forEach(el => el.classList.add('visible'));
  }

  // ---------------------------------------------------------
  // Navbar: add scrolled shadow class on scroll
  // ---------------------------------------------------------
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    const onScroll = () => navbar.classList.toggle('scrolled', window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // ---------------------------------------------------------
  // Button press feedback (subtle scale)
  // ---------------------------------------------------------
  document.addEventListener('pointerdown', (e) => {
    const btn = e.target.closest('.btn');
    if (btn && !btn.disabled) {
      btn.classList.add('btn-pressing');
      const up = () => { btn.classList.remove('btn-pressing'); document.removeEventListener('pointerup', up); };
      document.addEventListener('pointerup', up);
    }
  });

  // Stagger index product cards on page load
  const indexGrid = document.querySelector('.products-grid:not(#catalog-grid .products-grid)');
  if (indexGrid) {
    indexGrid.querySelectorAll('.product-card').forEach((card, i) => {
      card.style.setProperty('--delay', i * 0.06 + 's');
    });
  }

  // ---------------------------------------------------------
  // Mobile tab bar — auto-hide on scroll down, show on scroll up
  // ---------------------------------------------------------
  const tabbar = document.getElementById('mobileTabbar');
  if (tabbar) {
    let lastY = window.scrollY;
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        const goingDown = y > lastY && y > 80;
        tabbar.classList.toggle('hidden', goingDown);
        lastY = y;
        ticking = false;
      });
    }, { passive: true });
  }

  // ---------------------------------------------------------
  // Premium polish — cursor-tracked gold glow + vial tilt
  // Skipped automatically if user prefers reduced motion.
  // ---------------------------------------------------------
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && window.matchMedia('(pointer: fine)').matches) {
    document.querySelectorAll('.product-card').forEach(card => {
      const visual = card.querySelector('.product-visual-has-img');
      const img    = card.querySelector('.product-card-img');
      card.addEventListener('pointermove', (e) => {
        const r = card.getBoundingClientRect();
        const mx = ((e.clientX - r.left) / r.width)  * 100;
        const my = ((e.clientY - r.top ) / r.height) * 100;
        card.style.setProperty('--mx', mx + '%');
        card.style.setProperty('--my', my + '%');
        if (visual && img) {
          // very subtle 3D tilt (max ~3deg) — gives a "weight" feel without being gimmicky
          const tx = (mx - 50) / 50; // -1 .. 1
          const ty = (my - 50) / 50;
          img.style.transform = `scale(1.07) translateY(-2px) rotateY(${tx * 2.2}deg) rotateX(${-ty * 1.6}deg)`;
        }
      }, { passive: true });
      card.addEventListener('pointerleave', () => {
        card.style.removeProperty('--mx');
        card.style.removeProperty('--my');
        if (img) img.style.transform = '';
      });
    });
  }
});

// SSE is only used in the admin panel (admin/base.html).
// Removed from the public store to avoid holding persistent connections
// that block gunicorn workers and cause worker timeouts.
