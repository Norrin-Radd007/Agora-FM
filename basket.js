/**
 * AGORA FM — Basket Nav Dropdown (basket.js)
 * Basket icon sits in the nav bar. Clicking it opens a compact
 * dropdown panel anchored below the nav. Does not cover page content.
 */
(function () {
  var fmt = function(n){ return '£' + (parseFloat(n)||0).toFixed(2); };
  var isOpen = false;

  // ── Build the nav basket button + dropdown ──────────────────────────────
  function buildBasket() {
    if (document.getElementById('agora-basket-wrap')) return;

    // Wrapper injected into .nav-cta
    var navCta = document.querySelector('.nav-cta');
    if (!navCta) return;

    var wrap = document.createElement('div');
    wrap.id = 'agora-basket-wrap';
    wrap.style.cssText = 'position:relative;display:inline-flex;align-items:center;';

    // Nav button
    wrap.innerHTML = [
      '<button id="agora-basket-btn" onclick="AgoraBasket.toggle()" style="',
        'position:relative;display:inline-flex;align-items:center;gap:6px;',
        'padding:7px 14px;background:transparent;',
        'border:1px solid rgba(62,107,137,0.4);border-radius:2px;',
        'color:rgba(227,229,232,0.6);font-family:\'Barlow Condensed\',sans-serif;',
        'font-size:0.78rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;',
        'cursor:pointer;transition:all 0.2s;white-space:nowrap;',
      '">',
        '🛒 Basket',
        '<span id="agora-basket-badge" style="',
          'display:none;background:#F18F01;color:#0A1A2F;',
          'font-size:0.6rem;font-weight:700;padding:1px 5px;',
          'border-radius:8px;min-width:16px;text-align:center;',
          'font-family:\'Barlow Condensed\',sans-serif;',
        '">0</span>',
      '</button>',

      // Dropdown panel
      '<div id="agora-basket-panel" style="',
        'display:none;position:absolute;top:calc(100% + 10px);right:0;',
        'width:360px;background:rgba(10,26,47,0.99);',
        'border:1px solid rgba(62,107,137,0.35);border-radius:2px;',
        'box-shadow:0 16px 48px rgba(0,0,0,0.6);z-index:600;',
        'backdrop-filter:blur(16px);',
        'animation:fadeDown 0.18s ease both;',
      '">',

        // Arrow pointer
        '<div style="position:absolute;top:-6px;right:20px;width:12px;height:12px;',
          'background:rgba(10,26,47,0.99);border-left:1px solid rgba(62,107,137,0.35);',
          'border-top:1px solid rgba(62,107,137,0.35);transform:rotate(45deg);"></div>',

        // Header
        '<div style="padding:14px 18px;border-bottom:1px solid rgba(62,107,137,0.2);',
          'display:flex;align-items:center;justify-content:space-between;">',
          '<div>',
            '<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.1rem;',
              'letter-spacing:2px;color:#E3E5E8;">Service Basket</div>',
            '<div id="agora-basket-count-lbl" style="font-size:0.65rem;',
              'color:rgba(227,229,232,0.4);letter-spacing:1.5px;text-transform:uppercase;',
              'margin-top:2px;">0 services</div>',
          '</div>',
          '<button onclick="AgoraBasket.close()" style="background:none;border:none;',
            'color:rgba(227,229,232,0.3);font-size:1rem;cursor:pointer;padding:4px 6px;',
            'transition:color 0.15s;" ',
            'onmouseover="this.style.color=\'#F18F01\'" ',
            'onmouseout="this.style.color=\'rgba(227,229,232,0.3)\'">✕</button>',
        '</div>',

        // Items
        '<div id="agora-basket-items" style="max-height:240px;overflow-y:auto;padding:6px 0;">',
          '<div id="agora-basket-empty" style="padding:28px 18px;text-align:center;',
            'color:rgba(227,229,232,0.3);font-size:0.78rem;">',
            '<div style="font-size:1.6rem;margin-bottom:8px;">🛒</div>',
            'No services added yet<br>',
            '<span style="font-size:0.7rem;font-weight:300;">Browse services and click Commission to add them</span>',
          '</div>',
        '</div>',

        // Footer
        '<div id="agora-basket-footer" style="display:none;border-top:1px solid rgba(62,107,137,0.2);padding:14px 18px;">',
          '<div style="margin-bottom:12px;">',
            '<div style="display:flex;justify-content:space-between;font-size:0.75rem;',
              'color:rgba(227,229,232,0.5);margin-bottom:5px;">',
              '<span>Subtotal</span><span id="bkt-sub">£0.00</span>',
            '</div>',
            '<div style="display:flex;justify-content:space-between;font-size:0.75rem;',
              'color:rgba(227,229,232,0.5);margin-bottom:5px;">',
              '<span>VAT (20%)</span><span id="bkt-vat">£0.00</span>',
            '</div>',
            '<div style="display:flex;justify-content:space-between;font-size:0.7rem;',
              'color:rgba(241,143,1,0.6);margin-bottom:10px;">',
              '<span>Commission (5%)</span><span id="bkt-comm">£0.00</span>',
            '</div>',
            '<div style="display:flex;justify-content:space-between;',
              'font-family:\'Bebas Neue\',sans-serif;font-size:1.3rem;letter-spacing:1px;',
              'border-top:1px solid rgba(62,107,137,0.2);padding-top:10px;">',
              '<span style="color:#E3E5E8;">Total inc. VAT</span>',
              '<span id="bkt-total" style="color:#F18F01;">£0.00</span>',
            '</div>',
          '</div>',
          '<button onclick="AgoraBasket.checkout()" style="width:100%;padding:12px;',
            'background:#F18F01;border:none;border-radius:2px;color:#0A1A2F;',
            'font-family:\'Barlow Condensed\',sans-serif;font-size:0.85rem;font-weight:700;',
            'letter-spacing:3px;text-transform:uppercase;cursor:pointer;transition:all 0.2s;" ',
            'onmouseover="this.style.background=\'#FF9F0A\'" ',
            'onmouseout="this.style.background=\'#F18F01\'">',
            'Proceed to Payment →',
          '</button>',
          '<button onclick="AgoraBasket.clearAll()" style="width:100%;padding:8px;',
            'background:transparent;border:1px solid rgba(62,107,137,0.25);border-radius:2px;',
            'color:rgba(227,229,232,0.35);font-family:\'Barlow Condensed\',sans-serif;',
            'font-size:0.68rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;',
            'cursor:pointer;margin-top:6px;transition:all 0.2s;" ',
            'onmouseover="this.style.borderColor=\'rgba(231,76,60,0.4)\';this.style.color=\'#e74c3c\'" ',
            'onmouseout="this.style.borderColor=\'rgba(62,107,137,0.25)\';this.style.color=\'rgba(227,229,232,0.35)\'">',
            'Clear Basket',
          '</button>',
        '</div>',

      '</div>' // end panel
    ].join('');

    // Insert before the first child of nav-cta
    navCta.insertBefore(wrap, navCta.firstChild);

    // Add fadeDown keyframe if not already present
    if (!document.getElementById('basket-keyframes')) {
      var style = document.createElement('style');
      style.id = 'basket-keyframes';
      style.textContent = '@keyframes fadeDown{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}';
      document.head.appendChild(style);
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
      var wrap = document.getElementById('agora-basket-wrap');
      if (wrap && !wrap.contains(e.target)) {
        AgoraBasket.close();
      }
    });

    // Hover styles on nav button
    var btn = document.getElementById('agora-basket-btn');
    if (btn) {
      btn.addEventListener('mouseover', function(){ this.style.borderColor='#F18F01'; this.style.color='#F18F01'; });
      btn.addEventListener('mouseout',  function(){
        if (!isOpen) { this.style.borderColor='rgba(62,107,137,0.4)'; this.style.color='rgba(227,229,232,0.6)'; }
      });
    }
  }

  // ── Render basket contents ──────────────────────────────────────────────
  async function render() {
    var b       = await AgoraDB.basket.get();
    var items   = b.items || [];
    var container = document.getElementById('agora-basket-items');
    var footer    = document.getElementById('agora-basket-footer');
    var empty     = document.getElementById('agora-basket-empty');
    var countLbl  = document.getElementById('agora-basket-count-lbl');
    var badge     = document.getElementById('agora-basket-badge');
    if (!container) return;

    var count = items.length;
    if (countLbl) countLbl.textContent = count + (count === 1 ? ' service' : ' services');
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'inline-block' : 'none';
    }

    if (count === 0) {
      if (empty)  empty.style.display  = 'block';
      if (footer) footer.style.display = 'none';
      container.querySelectorAll('.bkt-item').forEach(function(r){ r.remove(); });
      return;
    }

    if (empty)  empty.style.display  = 'none';
    if (footer) footer.style.display = 'block';
    container.querySelectorAll('.bkt-item').forEach(function(r){ r.remove(); });

    items.forEach(function(item) {
      var lineTotal = parseFloat(item.price) * (item.qty || 1);
      var row = document.createElement('div');
      row.className = 'bkt-item';
      row.style.cssText = 'padding:9px 18px;border-bottom:1px solid rgba(62,107,137,0.08);display:flex;align-items:center;gap:8px;';
      row.innerHTML = [
        '<div style="flex:1;min-width:0;">',
          '<div style="font-size:0.78rem;font-weight:500;color:#E3E5E8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + item.name + '</div>',
          '<div style="font-size:0.67rem;color:#5589A8;margin-top:1px;">' + (item.supplierName||'') + '</div>',
        '</div>',
        '<div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">',
          '<input type="number" min="1" max="99" value="' + (item.qty||1) + '" ',
            'onchange="AgoraBasket.updateQty(\'' + item.id + '\',this.value)" ',
            'style="width:40px;padding:3px 5px;background:rgba(10,26,47,0.8);border:1px solid rgba(62,107,137,0.3);',
            'border-radius:2px;color:#E3E5E8;font-size:0.72rem;text-align:center;">',
          '<div style="font-family:\'Barlow Condensed\',sans-serif;font-size:0.85rem;font-weight:700;color:#F18F01;min-width:52px;text-align:right;">' + fmt(lineTotal) + '</div>',
          '<button onclick="AgoraBasket.remove(\'' + item.id + '\')" ',
            'style="background:none;border:none;color:rgba(227,229,232,0.2);cursor:pointer;font-size:0.8rem;padding:2px 4px;transition:color 0.15s;" ',
            'onmouseover="this.style.color=\'#e74c3c\'" onmouseout="this.style.color=\'rgba(227,229,232,0.2)\'">✕</button>',
        '</div>'
      ].join('');
      container.appendChild(row);
    });

    if (document.getElementById('bkt-sub'))   document.getElementById('bkt-sub').textContent   = fmt(b.subtotal);
    if (document.getElementById('bkt-vat'))   document.getElementById('bkt-vat').textContent   = fmt(b.vat);
    if (document.getElementById('bkt-comm'))  document.getElementById('bkt-comm').textContent  = fmt(b.commission);
    if (document.getElementById('bkt-total')) document.getElementById('bkt-total').textContent = fmt(b.total);
  }

  // ── Public API ──────────────────────────────────────────────────────────
  window.AgoraBasket = {
    open: function() {
      var panel = document.getElementById('agora-basket-panel');
      var btn   = document.getElementById('agora-basket-btn');
      if (!panel) return;
      panel.style.display = 'block';
      if (btn) { btn.style.borderColor='#F18F01'; btn.style.color='#F18F01'; }
      isOpen = true;
      render();
    },
    close: function() {
      var panel = document.getElementById('agora-basket-panel');
      var btn   = document.getElementById('agora-basket-btn');
      if (panel) panel.style.display = 'none';
      if (btn) { btn.style.borderColor='rgba(62,107,137,0.4)'; btn.style.color='rgba(227,229,232,0.6)'; }
      isOpen = false;
    },
    toggle: function() {
      if (isOpen) { AgoraBasket.close(); } else { AgoraBasket.open(); }
    },
    add: async function(item) {
      var s = await AgoraDB.auth.getSession();
      if (!s || !s.loggedIn) {
        if (confirm('Please sign in to add services to your basket. Go to sign in now?')) {
          window.location.href = 'index.html';
        }
        return;
      }
      var result = await AgoraDB.basket.addItem(item);
      await render();
      AgoraBasket.open();
      if (result && result.added === false) {
        // Already in basket — flash the badge
        var badge = document.getElementById('agora-basket-badge');
        if (badge) {
          var orig = badge.style.background;
          badge.style.background = '#5cb85c';
          setTimeout(function(){ badge.style.background = orig; }, 800);
        }
      }
    },
    remove: async function(id) {
      await AgoraDB.basket.removeItem(id);
      render();
    },
    updateQty: async function(id, qty) {
      await AgoraDB.basket.updateQty(id, qty);
      render();
    },
    clearAll: async function() {
      if (confirm('Clear all items from your basket?')) {
        await AgoraDB.basket.clear();
        render();
      }
    },
    checkout: async function() {
      var s = await AgoraDB.auth.getSession();
      if (!s || !s.loggedIn) { window.location.href = 'index.html'; return; }
      var count = await AgoraDB.basket.getCount();
      if (count === 0) { alert('Your basket is empty.'); return; }
      AgoraBasket.close();
      window.location.href = 'payment.html';
    },
    refresh: function() { render(); }
  };

  // ── Init ────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    buildBasket();
    render();
  });

})();
