/**
 * AGORA FM — Nav Auth + Basket Badge (nav-auth.js)
 * Async-aware version for Flask backend.
 */
(function () {

  async function updateNav() {
    var s = await AgoraDB.auth.getSession();
    AgoraDB.auth._session = s;
    var loginBtn = document.querySelector('.btn-nav-login');
    var regBtn   = document.querySelector('.btn-nav-reg');
    if (s && s.loggedIn) {
      if (loginBtn) {
        loginBtn.textContent = 'Sign Out';
        loginBtn.href = '#';
        loginBtn.onclick = function(e) { e.preventDefault(); AgoraDB.auth.logout(); };
      }
      if (regBtn) {
        regBtn.textContent = s.type === 'supplier' ? 'My Dashboard' : 'My Dashboard';
        regBtn.href = s.type === 'supplier' ? 'supplier_dashboard.html' : 'dashboard.html';
        regBtn.onclick = null;
        // If this page has the logged-out "Register As Customer/Supplier" dropdown
        // (currently only index.html), remove it — logged-in users just get one dashboard link.
        var regWrap = regBtn.closest && regBtn.closest('.nav-reg-wrap');
        if (regWrap) {
          var dd = regWrap.querySelector('.nav-dropdown');
          if (dd) dd.remove();
        }
      }
    }
  }

  async function updateBasketBadge() {
    // Badge is now managed by basket.js — just trigger a refresh if available
    if (window.AgoraBasket && typeof AgoraBasket.refresh === 'function') {
      AgoraBasket.refresh();
    }
  }

  function injectAdminLink() {
    var footer = document.querySelector('.footer-bottom');
    if (!footer || document.getElementById('admin-db-link')) return;
    var link = document.createElement('a');
    link.id = 'admin-db-link';
    link.href = '#';
    link.style.cssText = 'font-size:0.65rem;color:rgba(241,143,1,0.3);text-decoration:none;letter-spacing:1px;margin-left:16px;';
    link.textContent = '⚙ View DB';
    link.onclick = function(e) { e.preventDefault(); showAdminPanel(); };
    footer.appendChild(link);
  }

  async function showAdminPanel() {
    var existing = document.getElementById('admin-panel-overlay');
    if (existing) { existing.remove(); return; }
    var data = await AgoraDB.admin.dump();
    var overlay = document.createElement('div');
    overlay.id = 'admin-panel-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(10,26,47,0.97);z-index:9999;overflow:auto;padding:32px;font-family:monospace;color:#E3E5E8;';
    var fmt = function(n){ return '£' + (n||0).toFixed(2); };
    var html = '<div style="max-width:1000px;margin:0 auto;">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;border-bottom:1px solid rgba(241,143,1,0.3);padding-bottom:16px;">';
    html += '<span style="font-family:\'Bebas Neue\',sans-serif;font-size:1.8rem;letter-spacing:3px;color:#F18F01;">AGORA FM — DATABASE VIEWER</span>';
    html += '<div style="display:flex;gap:12px;">';
    html += '<button onclick="AgoraDB.admin.reset().then(function(){location.reload()})" style="padding:8px 16px;background:rgba(231,76,60,0.2);border:1px solid rgba(231,76,60,0.4);border-radius:2px;color:#e74c3c;font-family:monospace;cursor:pointer;font-size:0.75rem;">⚠ Reset DB</button>';
    html += '<button onclick="document.getElementById(\'admin-panel-overlay\').remove()" style="padding:8px 16px;background:rgba(241,143,1,0.1);border:1px solid rgba(241,143,1,0.3);border-radius:2px;color:#F18F01;font-family:monospace;cursor:pointer;font-size:0.75rem;">✕ Close</button>';
    html += '</div></div>';

    if (data.stats) {
      html += '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px;">';
      [['Customers', data.stats.customers], ['Suppliers', data.stats.suppliers],
       ['Orders', data.stats.orders], ['Revenue', fmt(data.stats.revenue)],
       ['Commission (5%)', fmt(data.stats.commission)]].forEach(function(s){
        html += '<div style="background:rgba(17,34,64,0.8);border:1px solid rgba(62,107,137,0.3);padding:14px;border-radius:2px;text-align:center;">';
        html += '<div style="font-family:\'Bebas Neue\',sans-serif;font-size:1.6rem;color:#F18F01;">' + s[1] + '</div>';
        html += '<div style="font-size:0.65rem;color:rgba(227,229,232,0.4);letter-spacing:2px;text-transform:uppercase;margin-top:4px;">' + s[0] + '</div></div>';
      });
      html += '</div>';
    }

    function section(title, obj) {
      return '<h3 style="color:#F18F01;font-size:0.8rem;letter-spacing:2px;text-transform:uppercase;margin:0 0 8px;">' + title + '</h3>' +
             '<pre style="background:rgba(17,34,64,0.8);border:1px solid rgba(62,107,137,0.3);padding:12px;border-radius:2px;font-size:0.72rem;overflow:auto;margin-bottom:20px;">' +
             JSON.stringify(obj, null, 2) + '</pre>';
    }

    function documentsSection(docs) {
      docs = docs || [];
      var out = '<h3 style="color:#F18F01;font-size:0.8rem;letter-spacing:2px;text-transform:uppercase;margin:0 0 8px;">Supplier Documents (' + docs.length + ')</h3>';
      if (docs.length === 0) {
        out += '<div style="background:rgba(17,34,64,0.8);border:1px solid rgba(62,107,137,0.3);padding:14px;border-radius:2px;font-size:0.78rem;color:rgba(227,229,232,0.4);margin-bottom:20px;">No documents uploaded yet.</div>';
        return out;
      }
      out += '<div style="background:rgba(17,34,64,0.8);border:1px solid rgba(62,107,137,0.3);border-radius:2px;margin-bottom:20px;overflow:hidden;">';
      docs.forEach(function(d, i) {
        var typeLabel = d.doc_type === 'pl_insurance' ? '📄 PL Insurance' : '🏆 Accreditation';
        var sizeKb = d.file_size ? (d.file_size/1024).toFixed(0) + 'KB' : '';
        out += '<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;font-size:0.75rem;' +
          (i < docs.length-1 ? 'border-bottom:1px solid rgba(62,107,137,0.15);' : '') + '">' +
          '<span style="color:#F18F01;white-space:nowrap;">' + typeLabel + '</span>' +
          '<span style="color:rgba(227,229,232,0.4);white-space:nowrap;">' + d.supplier_id + '</span>' +
          '<span style="flex:1;color:#E3E5E8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (d.label || d.filename) + '</span>' +
          '<span style="color:rgba(227,229,232,0.3);white-space:nowrap;">' + sizeKb + '</span>' +
          '<a href="/api/suppliers/documents/' + d.id + '" target="_blank" style="color:#F18F01;text-decoration:none;border:1px solid rgba(241,143,1,0.35);padding:3px 10px;border-radius:2px;white-space:nowrap;">View →</a>' +
          '</div>';
      });
      out += '</div>';
      return out;
    }

    html += section('Session', data.session);
    html += section('Basket', data.basket);
    html += documentsSection(data.documents);
    html += section('Customers (' + (data.customers||[]).length + ')', data.customers);
    html += section('Suppliers (' + (data.suppliers||[]).length + ')', data.suppliers);
    html += section('Orders (' + (data.orders||[]).length + ')', data.orders);
    html += '</div>';
    overlay.innerHTML = html;
    document.body.appendChild(overlay);
  }

  async function init() {
    await updateNav();
    await updateBasketBadge();
    injectAdminLink();
  }

  window.AgoraNavUpdate = async function() { await updateBasketBadge(); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
