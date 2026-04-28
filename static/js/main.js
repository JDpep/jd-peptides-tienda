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
  // Catalog: AJAX search (replaces page reload)
  // ---------------------------------------------------------
  const searchInput = document.getElementById('catalogSearch');
  const catalogGrid = document.getElementById('catalog-grid');
  const catalogCount = document.getElementById('catalog-count');

  if (searchInput && catalogGrid) {
    let debounceTimer;
    let currentCategory = new URL(window.location.href).searchParams.get('categoria') || '';

    // Category pills — update currentCategory on click
    document.querySelectorAll('.category-pill').forEach(pill => {
      pill.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelectorAll('.category-pill').forEach(p => p.classList.remove('active'));
        this.classList.add('active');
        currentCategory = this.dataset.category || '';
        runCatalogSearch(searchInput.value, currentCategory);
      });
    });

    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        runCatalogSearch(this.value, currentCategory);
      }, 400);
    });

    function runCatalogSearch(q, category) {
      // Show skeletons
      const skeletonCount = 4;
      catalogGrid.classList.add('catalog-loading');
      catalogGrid.innerHTML = Array(skeletonCount).fill(0).map(() => `
        <div class="skeleton-card">
          <div class="sk-visual"></div>
          <div class="sk-line"></div>
          <div class="sk-line short"></div>
        </div>`).join('');

      const params = new URLSearchParams();
      if (q) params.set('q', q);
      if (category) params.set('categoria', category);

      fetch('/api/productos?' + params.toString())
        .then(r => r.json())
        .then(data => {
          if (catalogCount) {
            catalogCount.textContent = data.count + ' producto' + (data.count !== 1 ? 's' : '');
          }
          if (data.products.length === 0) {
            catalogGrid.innerHTML = `
              <div style="grid-column:1/-1;text-align:center;padding:4rem 0;color:var(--text2)">
                <div style="font-size:3rem;margin-bottom:1rem">🔍</div>
                <p>No se encontraron productos para tu búsqueda.</p>
              </div>`;
          } else {
            catalogGrid.innerHTML = `<div class="products-grid animate-stagger">${data.products.map(p => renderProductCard(p)).join('')}</div>`;
            catalogGrid.querySelectorAll('.add-to-cart-btn').forEach(bindAddToCart);
            // Trigger entrance animations
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
          catalogGrid.innerHTML = '';
        });
    }

    function renderProductCard(p) {
      const inStock = p.stock > 0;
      const lowStock = p.stock > 0 && p.stock <= p.low_stock_alert;
      const isJpeg = p.image_url && /\.(jpeg|jpg)$/i.test(p.image_url);
      const imgTag = p.image_url
        ? `<img src="${p.image_url}" alt="${p.name}" class="product-card-img${isJpeg ? ' img-vial-right' : ''}" loading="lazy">`
        : `<div class="product-visual-name">${p.name}</div><div class="product-visual-dose">${p.dose}</div>`;

      const badge = !inStock
        ? `<span class="badge badge-red">Sin stock</span>`
        : lowStock
          ? `<span class="badge badge-orange">Stock bajo</span>`
          : `<span class="badge badge-green">Disponible</span>`;

      return `
        <div class="product-card" data-product-id="${p.id}">
          <div class="product-visual${p.image_url ? ' product-visual-has-img' : ''}">
            ${imgTag}
          </div>
          <div class="product-info" style="padding:1rem;display:flex;flex-direction:column;flex:1;gap:0.5rem">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem">
              <span class="product-category" style="font-size:0.72rem;color:var(--text2);text-transform:uppercase;letter-spacing:.06em">${p.category}</span>
              ${badge}
            </div>
            <h3 style="font-size:0.95rem;margin:0">${p.name}</h3>
            <span style="font-size:0.8rem;color:var(--text2)">${p.dose}</span>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-top:auto;padding-top:0.5rem">
              <span class="product-price" style="font-size:1.15rem;font-weight:800;color:var(--gold)">$${parseFloat(p.price).toFixed(2)}</span>
              ${inStock
                ? `<button class="btn btn-gold btn-sm add-to-cart-btn" data-product-id="${p.id}">+ Agregar</button>`
                : `<span style="font-size:0.78rem;color:var(--red)">Sin stock</span>`}
            </div>
          </div>
        </div>`;
    }
  } else if (searchInput) {
    // Fallback: old behavior if catalog-grid not present
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

    // Observe product cards and reveal-on-scroll sections
    document.querySelectorAll('.product-card, .reveal').forEach(el => {
      revealObserver.observe(el);
    });
  } else {
    // Fallback: show all immediately
    document.querySelectorAll('.product-card, .reveal').forEach(el => el.classList.add('visible'));
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
});

// SSE is only used in the admin panel (admin/base.html).
// Removed from the public store to avoid holding persistent connections
// that block gunicorn workers and cause worker timeouts.
