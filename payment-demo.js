/**
 * AGORA FM — Payment Demo (payment-demo.js)
 * Async version using Flask backend.
 */
(function () {
  var fmt = function(n){ return '£' + (parseFloat(n)||0).toFixed(2); };
  var handshakeDone = false;
  var handshakeTs   = null;

  async function prefillCustomer() {
    var s = await AgoraDB.auth.getSession();
    if (!s || !s.loggedIn) return;
    var name    = s.name  || '';
    var email   = s.email || '';
    var acctId  = 'AGF-' + (s.userId||'').slice(-5).toUpperCase();
    document.querySelectorAll('input[value="Sarah Mitchell"]').forEach(function(el){ el.value = name; });
    document.querySelectorAll('input[value="sarah.mitchell@company.co.uk"]').forEach(function(el){ el.value = email; });
    document.querySelectorAll('input[value="AGF-20841"]').forEach(function(el){ el.value = acctId; });
    var custSig = document.getElementById('cust-sig-val');
    if (custSig) custSig.value = name;
  }

  async function buildBasketSummary() {
    var b      = await AgoraDB.basket.get();
    var items  = b.items || [];
    var tbody  = document.getElementById('basket-summary-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (items.length === 0) return;
    items.forEach(function(item) {
      var line = parseFloat(item.price) * (item.qty||1);
      var vat  = line * 0.20;
      var tr = document.createElement('tr');
      tr.innerHTML = '<td>' + item.name + '<br><small style="color:rgba(85,137,168,0.8);font-size:0.72rem;">' + (item.supplierName||'') + '</small></td>' +
        '<td>' + (item.qty||1) + '</td><td>' + fmt(item.price) + '</td>' +
        '<td>' + fmt(line) + '</td><td>' + fmt(vat) + '</td>' +
        '<td style="color:rgba(241,143,1,0.7);">' + fmt(line*0.05) + '</td>' +
        '<td class="total-cell">' + fmt(line+vat) + '</td>';
      tbody.appendChild(tr);
    });
    var tfoot = document.getElementById('basket-summary-tfoot');
    if (tfoot) {
      tfoot.innerHTML = '<tr style="border-top:2px solid rgba(62,107,137,0.3);">' +
        '<td colspan="3" style="font-weight:600;color:#E3E5E8;">TOTALS</td>' +
        '<td style="font-weight:600;color:#E3E5E8;">' + fmt(b.subtotal) + '</td>' +
        '<td style="color:#E3E5E8;">' + fmt(b.vat) + '</td>' +
        '<td style="color:rgba(241,143,1,0.7);">' + fmt(b.commission) + '</td>' +
        '<td class="total-cell" style="font-size:1.05rem;">' + fmt(b.total) + '</td></tr>' +
        '<tr><td colspan="7" style="font-size:0.72rem;color:rgba(241,143,1,0.6);padding-top:6px;">5% Agora FM commission (' + fmt(b.commission) + ') is charged to the service provider, not the customer.</td></tr>';
    }
  }

  function lockPayment() {
    document.querySelectorAll('#payment-lock-overlay').forEach(function(o){ o.style.display='flex'; });
    ['btn-process-card','btn-generate-po','btn-download-po'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) { el.disabled=true; el.style.opacity='0.4'; el.style.cursor='not-allowed'; }
    });
  }
  function unlockPayment() {
    document.querySelectorAll('#payment-lock-overlay').forEach(function(o){ o.style.display='none'; });
    ['btn-process-card','btn-generate-po','btn-download-po'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) { el.disabled=false; el.style.opacity='1'; el.style.cursor='pointer'; }
    });
  }

  window.doHandshake = function() {
    handshakeDone = true;
    handshakeTs   = new Date().toISOString();
    window._handshakeDone = true;
    window._handshakeTs   = handshakeTs;
    var btn = document.getElementById('handshake-btn');
    if (btn) {
      btn.disabled = true;
      btn.style.background = btn.style.borderColor = '#5cb85c';
      btn.style.color = '#fff';
      btn.textContent = '✓ Handshake Accepted — ' + new Date().toLocaleTimeString('en-GB');
    }
    var hs = document.getElementById('handshake-section');
    if (hs) {
      var msg = document.createElement('div');
      msg.style.cssText = 'margin-top:12px;padding:10px 14px;background:rgba(92,184,92,0.1);border:1px solid rgba(92,184,92,0.3);border-radius:2px;font-size:0.75rem;color:#5cb85c;line-height:1.7;';
      msg.innerHTML = '<strong>Handshake recorded at ' + new Date().toLocaleTimeString('en-GB') + '</strong><br>' +
        '✓ Agora FM Terms &amp; Conditions agreed &nbsp;·&nbsp; ✓ Supplier terms accepted &nbsp;·&nbsp; ✓ 5% commission accepted';
      hs.appendChild(msg);
    }
    unlockPayment();
    var pm = document.getElementById('payment-methods-section');
    if (pm) pm.scrollIntoView({ behavior:'smooth', block:'start' });
  };

  window.processCard = async function() {
    if (!window._handshakeDone) { alert('Please complete the Agora FM Handshake first.'); return; }
    var name = document.querySelector('#panel-card input[placeholder*="Cardholder"]');
    var num  = document.querySelector('#panel-card input[placeholder*="••••"]');
    if (name && !name.value.trim()) { alert('Please enter the cardholder name.'); name.focus(); return; }
    if (num && num.value.replace(/\s/g,'').length < 16) { alert('Please enter a valid 16-digit card number.'); num.focus(); return; }
    var result = await AgoraDB.orders.create({ method: 'card', handshakeAt: window._handshakeTs || new Date().toISOString() });
    if (result.ok) {
      showBanner('Payment Successful — ' + result.order.id, 'Payment processed. Receipt sent to ' + result.order.customer_email + '. Transaction saved.');
      var btn = document.getElementById('btn-process-card') || document.querySelector('.action-btn-primary');
      if (btn) { btn.disabled=true; btn.textContent='✓ Payment Complete'; }
      if (window.AgoraNavUpdate) AgoraNavUpdate();
    } else {
      showBanner('Payment Failed', result.error || 'Please try again.');
    }
  };

  window.generatePO = async function() {
    if (!window._handshakeDone) { alert('Please complete the Agora FM Handshake first.'); return; }
    var supSig = document.getElementById('sup-sig');
    if (supSig && !supSig.value.trim()) { alert('Please enter the supplier signature.'); supSig.focus(); return; }
    var result = await AgoraDB.orders.create({ method: 'purchase_order', handshakeAt: window._handshakeTs || new Date().toISOString() });
    if (result.ok) {
      showBanner('Purchase Order Generated — ' + result.order.id, 'PO confirmed. Download PDF below or view in your dashboard.');
      var dlBtn = document.getElementById('btn-download-po');
      if (dlBtn) { dlBtn.disabled=false; dlBtn.style.opacity='1'; dlBtn.onclick = function(){ AgoraDB.orders.getPdf(result.order.id); }; }
      if (window.AgoraNavUpdate) AgoraNavUpdate();
    } else {
      showBanner('PO Failed', result.error || 'Please try again.');
    }
  };

  window.downloadPO = function() {
    showBanner('PDF', 'Complete the payment or PO generation first to download your PDF.');
  };

  function showBanner(title, sub) {
    var b = document.getElementById('success-banner');
    var t = document.getElementById('success-title');
    var s = document.getElementById('success-sub');
    if (!b) return;
    if (t) t.textContent = title;
    if (s) s.textContent = sub;
    b.classList.add('show');
    b.scrollIntoView({ behavior:'smooth', block:'nearest' });
  }

  document.addEventListener('DOMContentLoaded', async function() {
    await prefillCustomer();
    await buildBasketSummary();
    lockPayment();
  });
})();
