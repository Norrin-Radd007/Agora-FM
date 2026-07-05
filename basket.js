/**
 * AGORA FM — Basket Nav Badge (basket.js)
 * Nav shows a basket icon + item-count badge only. Clicking it goes to
 * basket.html, which owns all viewing/editing/checkout logic.
 * Session 8/9 rework: replaces the old nav dropdown-panel version.
 */
(function () {

  // ── Build the nav basket button (icon + badge, links to basket.html) ───
  function buildBasketIcon() {
    if (document.getElementById('agora-basket-wrap')) return;
    var navCta = document.querySelector('.nav-cta');
    if (!navCta) return;

    var wrap = document.createElement('div');
    wrap.id = 'agora-basket-wrap';
    wrap.style.cssText = 'position:relative;display:inline-flex;align-items:center;';

    wrap.innerHTML = [
      '<a id="agora-basket-btn" href="basket.html" style="',
        'position:relative;display:inline-flex;align-items:center;gap:6px;',
        'padding:7px 14px;background:transparent;',
        'border:1px solid rgba(62,107,137,0.4);border-radius:2px;',
        'color:rgba(227,229,232,0.6);font-family:\'Barlow Condensed\',sans-serif;',
        'font-size:0.78rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;',
        'cursor:pointer;transition:all 0.2s;white-space:nowrap;text-decoration:none;',
      '">',
        '🛒 Basket',
        '<span id="agora-basket-badge" style="',
          'display:none;background:#F18F01;color:#0A1A2F;',
          'font-size:0.6rem;font-weight:700;padding:1px 5px;',
          'border-radius:8px;min-width:16px;text-align:center;',
          'font-family:\'Barlow Condensed\',sans-serif;',
        '">0</span>',
      '</a>'
    ].join('');

    navCta.insertBefore(wrap, navCta.firstChild);

    var btn = document.getElementById('agora-basket-btn');
    if (btn) {
      btn.addEventListener('mouseover', function(){ this.style.borderColor='#F18F01'; this.style.color='#F18F01'; });
      btn.addEventListener('mouseout',  function(){ this.style.borderColor='rgba(62,107,137,0.4)'; this.style.color='rgba(227,229,232,0.6)'; });
    }
  }

  // ── Keep the badge count in sync with the live basket ───────────────────
  async function updateBadge() {
    var badge = document.getElementById('agora-basket-badge');
    if (!badge) return;
    var b = await AgoraDB.basket.get();
    var count = (b.items || []).length;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'inline-block' : 'none';
  }

  // ── Small "added to basket" toast (no dropdown panel anymore) ──────────
  function showAddedToast(item) {
    var existing = document.getElementById('agora-basket-toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.id = 'agora-basket-toast';
    toast.style.cssText =
      'position:fixed;bottom:24px;right:24px;z-index:800;max-width:320px;' +
      'background:rgba(10,26,47,0.98);border:1px solid rgba(241,143,1,0.4);' +
      'border-radius:2px;padding:14px 16px;box-shadow:0 12px 32px rgba(0,0,0,0.5);' +
      'display:flex;align-items:center;gap:14px;animation:fadeUp 0.2s ease both;';
    toast.innerHTML =
      '<div style="flex:1;min-width:0;">' +
        '<div style="font-size:0.68rem;color:#5cb85c;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:3px;">✓ Added to Basket</div>' +
        '<div style="font-size:0.82rem;color:#E3E5E8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + ((item && item.name) || 'Service') + '</div>' +
      '</div>' +
      '<a href="basket.html" style="flex-shrink:0;padding:7px 12px;background:#F18F01;color:#0A1A2F;' +
      'font-family:\'Barlow Condensed\',sans-serif;font-size:0.68rem;font-weight:700;letter-spacing:1.5px;' +
      'text-transform:uppercase;text-decoration:none;border-radius:2px;">View</a>';
    document.body.appendChild(toast);
    setTimeout(function(){ if (toast.parentNode) toast.remove(); }, 4000);
  }

  // ── Public API (kept intentionally small) ───────────────────────────────
  window.AgoraBasket = {
    add: async function(item) {
      var s = await AgoraDB.auth.getSession();
      if (!s || !s.loggedIn) {
        if (confirm('Please sign in to add services to your basket. Go to sign in now?')) {
          window.location.href = 'index.html';
        }
        return;
      }
      var result = await AgoraDB.basket.addItem(item);
      await updateBadge();
      showAddedToast(item);
      return result;
    },
    refresh: function() { updateBadge(); }
  };

  document.addEventListener('DOMContentLoaded', function() {
    buildBasketIcon();
    updateBadge();
  });

})();
